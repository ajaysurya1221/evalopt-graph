"""Contradiction detection.

A contradiction is two (or more) live claims about the **same subject** that take **different
stances**, or an explicit negation between claim texts. Contradictions are *preserved*, not smoothed
away: the adjudicator may resolve one when trust tiers differ decisively, otherwise it is reported
as an unresolved uncertainty in the final output (anti-hallucination rule #9).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import epistemic
from .epistemic import Claim

_LIVE_STATUSES = frozenset(
    {
        epistemic.STATUS_CONFIRMED,
        epistemic.STATUS_UNVERIFIED,
        epistemic.STATUS_STALE,
        epistemic.STATUS_CONTRADICTED,
    }
)
_NEGATION_TOKENS = (" not ", " no ", " never ", "n't ", " unsupported", " false", " cannot ", " incompatible")


@dataclass
class Contradiction:
    id: str
    subject: str
    claim_ids: list[str] = field(default_factory=list)
    summary: str = ""
    status: str = "unresolved"  # unresolved | resolved
    resolution: str = ""  # winning claim id when resolved
    resolved_by: str = ""
    severity: str = "normal"  # normal | high (security/central)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _negates(a: str, b: str) -> bool:
    a, b = (a or "").lower(), (b or "").lower()
    if not a or not b:
        return False
    # crude polarity flip: same core phrase, one side carries a negation token the other lacks
    a_neg = any(t in f" {a} " for t in _NEGATION_TOKENS)
    b_neg = any(t in f" {b} " for t in _NEGATION_TOKENS)
    if a_neg == b_neg:
        return False
    core_a = a.replace("not ", "").replace("no ", "")
    core_b = b.replace("not ", "").replace("no ", "")
    shared = set(core_a.split()) & set(core_b.split())
    return len(shared) >= 3


# severity scale for the semantic checker
SEV_BLOCKING = "blocking"
SEV_IMPORTANT = "important"
SEV_MINOR = "minor"
SEV_EXPLAINABLE = "explainable"


def central_claim_contradictions(
    claims: list[Claim], *, semantic_checker: Any = None, id_prefix: str = "xc"
) -> list[Contradiction]:
    """Two-layer contradiction detection for CENTRAL claims only (cheap: pairwise over central
    claims, not all low-value claims).

    Layer 1: the deterministic heuristic (subject/stance + negation). Layer 2: an optional
    ``semantic_checker(claim_a, claim_b) -> severity|None`` (an LLM subagent in Layer 1) consulted
    ONLY for central pairs the heuristic didn't already flag. Severity ∈ {blocking, important,
    minor, explainable}. Conflicts are never smoothed away.
    """
    central = [c for c in claims if c.central and c.status in _LIVE_STATUSES]
    out = find_contradictions(central, id_prefix=id_prefix)
    for x in out:  # promote heuristic severity onto the 4-level scale
        x.severity = SEV_BLOCKING if x.severity == "high" else SEV_IMPORTANT
    if semantic_checker is None:
        return out

    flagged = {frozenset(x.claim_ids) for x in out}
    seq = len(out)
    for i in range(len(central)):
        for j in range(i + 1, len(central)):
            a, b = central[i], central[j]
            if frozenset({a.id, b.id}) in flagged:
                continue
            try:
                sev = semantic_checker(a, b)
            except Exception:
                sev = None
            if sev in (SEV_BLOCKING, SEV_IMPORTANT, SEV_MINOR, SEV_EXPLAINABLE):
                seq += 1
                out.append(
                    Contradiction(
                        id=f"{id_prefix}{seq}",
                        subject=(a.subject or a.text[:60]),
                        claim_ids=[a.id, b.id],
                        summary=f"semantic contradiction ({sev}) between {a.id} and {b.id}",
                        severity=sev,
                    )
                )
    return out


def find_contradictions(claims: list[Claim], *, id_prefix: str = "x") -> list[Contradiction]:
    """Find contradictions among live claims. Deterministic and order-stable."""
    live = [c for c in claims if c.status in _LIVE_STATUSES]
    out: list[Contradiction] = []
    seq = 0

    # 1) same subject, differing non-empty stances
    by_subject: dict[str, list[Claim]] = {}
    for c in live:
        if c.subject:
            by_subject.setdefault(c.subject, []).append(c)
    for subject in sorted(by_subject):
        group = by_subject[subject]
        stances = {c.stance for c in group if c.stance}
        if len(stances) > 1:
            seq += 1
            severity = "high" if any(epistemic.is_critical(claim) for claim in group) else "normal"
            out.append(
                Contradiction(
                    id=f"{id_prefix}{seq}",
                    subject=subject,
                    claim_ids=[c.id for c in group],
                    summary=f"conflicting stances on '{subject}': {sorted(stances)}",
                    severity=severity,
                )
            )

    # 2) explicit text negation among claims not already grouped above. Producer-chosen subject
    # labels cannot suppress a contradiction visible in the claim text.
    flagged_pairs = {
        frozenset((left, right))
        for contradiction in out
        for index, left in enumerate(contradiction.claim_ids)
        for right in contradiction.claim_ids[index + 1 :]
    }
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            pair = frozenset((live[i].id, live[j].id))
            critical_pair = epistemic.is_critical(live[i]) and epistemic.is_critical(live[j])
            negates = _negates(live[i].text, live[j].text)
            conflicts = negates or (
                critical_pair and epistemic._critical_text_conflict(live[i].text, live[j].text)
            )
            if pair not in flagged_pairs and conflicts:
                seq += 1
                out.append(
                    Contradiction(
                        id=f"{id_prefix}{seq}",
                        subject=live[i].text[:60],
                        claim_ids=[live[i].id, live[j].id],
                        summary=(
                            f"{'text negation' if negates else 'potential critical conflict'}: "
                            f"'{live[i].text[:60]}' vs '{live[j].text[:60]}'"
                        ),
                        severity=("high" if critical_pair else "normal"),
                    )
                )
    return out
