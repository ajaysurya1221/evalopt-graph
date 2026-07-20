"""Confidence scoring + adjudication.

``score_confidence`` turns a claim's status + trust provenance into a 0..1 number.
``adjudicate`` weighs contradictions by trust tier (T0 deterministic > T1 > T2 > T3 > T4 model),
resolves a contradiction only when one side is *decisively* stronger, preserves the rest, and
**blocks a final PASS while any central claim is unverified or under-evidenced**.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import epistemic
from .claim_ledger import ClaimLedger
from .contradictions import Contradiction
from .epistemic import Claim, Source

_STATUS_BASE = {
    epistemic.STATUS_CONFIRMED: 0.85,
    epistemic.STATUS_UNVERIFIED: 0.35,
    epistemic.STATUS_STALE: 0.30,
    epistemic.STATUS_CONTRADICTED: 0.20,
    epistemic.STATUS_SUPERSEDED: 0.10,
    epistemic.STATUS_REJECTED: 0.05,
}
_TIER_BONUS = {0: 0.12, 1: 0.08, 2: 0.05, 3: 0.0, 4: -0.05}


def score_confidence(claim: Claim, sources_by_id: dict[str, Source]) -> float:
    base = _STATUS_BASE.get(claim.status, 0.3)
    order = epistemic.trust_order(epistemic.best_supporting_trust(claim, sources_by_id))
    n_support = sum(1 for r in claim.evidence_refs if r in sources_by_id)
    score = base + _TIER_BONUS.get(order, -0.05) + min(0.05, 0.01 * n_support)
    return round(max(0.0, min(1.0, score)), 3)


def score_ledger(ledger: ClaimLedger) -> None:
    for c in ledger.claims():
        c.confidence = score_confidence(c, ledger.sources)


@dataclass
class AdjudicationResult:
    confirmed_facts: list[str] = field(default_factory=list)
    likely_conclusions: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    unresolved_contradictions: list[dict[str, Any]] = field(default_factory=list)
    resolved_contradictions: list[dict[str, Any]] = field(default_factory=list)
    central_unverified: list[str] = field(default_factory=list)
    critical_unverified: list[str] = field(default_factory=list)
    missing_central: list[str] = field(default_factory=list)
    blocks_pass: bool = False
    hard_block: bool = False  # a critical/missing central claim -> PASS may NOT be downgraded to warnings
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _claim_rank(claim: Claim, sources_by_id: dict[str, Source]) -> tuple[int, int, float]:
    """Sort key: stronger trust first, then confirmed-before-unverified, then higher confidence."""
    order = epistemic.trust_order(epistemic.best_supporting_trust(claim, sources_by_id))
    status_rank = 0 if claim.status == epistemic.STATUS_CONFIRMED else 1
    return (order, status_rank, -score_confidence(claim, sources_by_id))


def adjudicate(
    ledger: ClaimLedger,
    contradictions: list[Contradiction],
    *,
    required_tier: str = epistemic.T2_OFFICIAL,
    conclusions: list[str] | tuple[str, ...] = (),
    now: str | None = None,
) -> AdjudicationResult:
    """Weigh evidence, resolve decisively-won contradictions, and decide whether PASS is blocked."""
    res = AdjudicationResult()
    by_id = {c.id: c for c in ledger.claims()}
    sources = ledger.sources

    for x in contradictions:
        members = [by_id[cid] for cid in x.claim_ids if cid in by_id]
        if len(members) < 2:
            continue
        ranked = sorted(members, key=lambda c: _claim_rank(c, sources))
        best, second = ranked[0], ranked[1]
        best_order = epistemic.trust_order(epistemic.best_supporting_trust(best, sources))
        second_order = epistemic.trust_order(epistemic.best_supporting_trust(second, sources))
        # resolve ONLY when the winner is strictly stronger AND actually usable; else preserve it
        if best_order < second_order and best.status == epistemic.STATUS_CONFIRMED:
            x.status = "resolved"
            x.resolution = best.id
            x.resolved_by = "adjudicator"
            for loser in ranked[1:]:
                # deterministic/stronger evidence overrides weaker (incl. model) opinion
                ledger.set_status(loser.id, epistemic.STATUS_SUPERSEDED, verified_by="adjudicator")
            res.resolved_contradictions.append(x.to_dict())
            ledger.add_decision(
                {
                    "kind": "contradiction_resolved",
                    "subject": x.subject,
                    "winner": best.id,
                    "losers": [c.id for c in ranked[1:]],
                }
            )
        else:
            res.unresolved_contradictions.append(x.to_dict())

    # central claim coverage: any central (declared OR policy-derived; see promote_centrality) claim
    # that is not usable OR under-evidenced blocks PASS. Critical claims additionally HARD-block.
    for c in ledger.central_claims():
        if c.type == "assumption":
            continue  # an explicit assumption is surfaced, not a load-bearing fact
        usable = epistemic.is_usable(c, now)
        strong_enough = epistemic.meets_trust_requirement(c, sources, required_tier)
        if not usable or not strong_enough:
            res.central_unverified.append(c.id)
            if epistemic.is_critical(c):
                res.critical_unverified.append(c.id)

    # missing-central-claim: a CRITICAL conclusion asserted in the final answer with no ledgered USABLE
    # claim backing it is an unledgered central conclusion -> block until it is ledgered or an assumption.
    live = ledger.claims()
    for concl in conclusions or ():
        if not epistemic.is_critical_text(concl):
            continue
        ckw = epistemic.keywords(concl)
        if not ckw:
            continue
        covered = any(
            epistemic.is_usable(c, now) and len(ckw & epistemic.keywords(f"{c.subject} {c.text}")) >= 2
            for c in live
        )
        if not covered:
            res.missing_central.append(concl)

    # buckets for the final report
    for c in ledger.claims():
        if c.type == "assumption":
            res.assumptions.append(c.text)
        elif epistemic.is_usable(c, now):
            res.confirmed_facts.append(c.text)
        elif c.status in (epistemic.STATUS_UNVERIFIED,):
            res.likely_conclusions.append(c.text)

    # Block on both severity vocabularies: find_contradictions emits "high"; the semantic-checker path
    # (contradictions.central_claim_contradictions) remaps onto the 4-level scale and emits "blocking".
    _blocking_sev = ("high", "blocking")
    high_unresolved = [x for x in res.unresolved_contradictions if x.get("severity") in _blocking_sev]
    if res.central_unverified:
        res.blocks_pass = True
        res.reasons.append(
            f"{len(res.central_unverified)} central claim(s) unverified or below {required_tier}"
        )
    if res.missing_central:
        res.blocks_pass = True
        res.reasons.append(
            f"{len(res.missing_central)} critical conclusion(s) not backed by a ledgered confirmed claim"
        )
    if res.critical_unverified or res.missing_central:
        res.hard_block = True  # cannot be downgraded to PASS_WITH_WARNINGS
    if high_unresolved:
        res.blocks_pass = True
        res.reasons.append(f"{len(high_unresolved)} high-severity contradiction(s) unresolved")
    return res
