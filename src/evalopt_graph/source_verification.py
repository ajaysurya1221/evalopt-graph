"""Legacy claim projection verifier; stable acceptance is evaluated by the kernel."""

from __future__ import annotations

import re
from typing import Any

from . import epistemic
from .attestation import claim_digest
from .claim_ledger import ClaimLedger
from .epistemic import Claim, Source

DEFAULT_MAX_AGE_SECONDS = 60 * 60 * 24 * 30
_WORDS = re.compile(r"[a-z0-9_./@-]{3,}")
_STOP = {"the", "and", "for", "with", "that", "this", "are", "was", "use", "uses", "using", "from", "into"}


def _keywords(text: str) -> set[str]:
    return {word for word in _WORDS.findall((text or "").lower()) if word not in _STOP}


def evidence_supports(claim: Claim, source: Source) -> bool:
    claim_words = _keywords(f"{claim.subject} {claim.text}")
    source_words = _keywords(f"{source.summary} {source.quoted_span_or_hash} {source.locator}")
    return (
        bool(source_words)
        if not claim_words
        else len(claim_words & source_words) >= max(1, len(claim_words) // 6)
    )


def is_fresh(
    source: Source,
    now: str | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> bool:
    if not source.freshness_required:
        return True
    retrieved = epistemic._parse_iso(source.retrieved_at)
    current = epistemic._parse_iso(now)
    if retrieved is None or current is None:
        return False
    return 0 <= (current - retrieved).total_seconds() <= max_age_seconds


def _binding(source: Source) -> bool:
    return any(
        (
            source.attestation_id,
            source.attestation_status,
            source.support_assessment_id,
            source.support_relation,
        )
    )


def _assessment_matches(
    claim: Claim,
    source: Source,
    assessments: dict[str, Any] | None,
) -> bool:
    if not _binding(source):
        return True
    assessment = assessments.get(source.support_assessment_id) if assessments else None
    expected = claim_digest(
        claim.text,
        claim_type=claim.type,
        claim_subject=claim.subject,
        claim_stance=claim.stance,
    )
    return bool(
        source.attestation_id
        and source.attestation_status == "VERIFIED"
        and assessment
        and assessment.assessment_id == source.support_assessment_id
        and assessment.attestation_id == source.attestation_id
        and assessment.relation == source.support_relation
        and assessment.claim_sha256 == expected
        and assessment.claim_type == claim.type
        and assessment.claim_subject == claim.subject
        and assessment.claim_stance == claim.stance
        and (assessment.verifier_id, assessment.verifier_version) == ("evalopt.lexical_support", "2")
    )


def verify_claim(
    claim: Claim,
    sources_by_id: dict[str, Source],
    *,
    support_assessments_by_id: dict[str, Any] | None = None,
    now: str | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> tuple[str, str]:
    if claim.status in {
        epistemic.STATUS_CONTRADICTED,
        epistemic.STATUS_SUPERSEDED,
        epistemic.STATUS_REJECTED,
    }:
        return claim.status, "left as-is (terminal status)"
    if epistemic.is_expired(claim, now):
        return epistemic.STATUS_STALE, "claim past its expiry"
    if epistemic.is_user_provided(claim):
        return epistemic.STATUS_CONFIRMED, "user-provided"

    relevant, contradicting = [], []
    irrelevant = 0
    for source in (sources_by_id[ref] for ref in claim.evidence_refs if ref in sources_by_id):
        if _binding(source):
            if not _assessment_matches(claim, source, support_assessments_by_id):
                irrelevant += 1
            elif source.support_relation == "SUPPORTS":
                relevant.append(source)
            elif source.support_relation == "CONTRADICTS":
                contradicting.append(source)
            else:
                irrelevant += 1
        elif evidence_supports(claim, source):
            relevant.append(source)
        else:
            irrelevant += 1

    if relevant and contradicting:
        return epistemic.STATUS_UNVERIFIED, "conflicting verified support assessments require adjudication"
    if not relevant:
        if contradicting:
            return epistemic.STATUS_CONTRADICTED, "verified evidence contradicts the claim"
        note = "no relevant supporting evidence (a self-declared source type is not proof)"
        return epistemic.STATUS_UNVERIFIED, note + (
            f" ({irrelevant} irrelevant source(s) rejected)" if irrelevant else ""
        )
    if any(source.freshness_required and not is_fresh(source, now, max_age_seconds) for source in relevant):
        return epistemic.STATUS_STALE, "supporting source is stale (freshness required)"
    if any(source.trust_tier == epistemic.T0_DETERMINISTIC for source in relevant):
        return epistemic.STATUS_CONFIRMED, "backed by deterministic evidence"
    nonmodel = [
        source
        for source in relevant
        if epistemic.is_known_trust_tier(source.trust_tier) and source.trust_tier != epistemic.T4_MODEL
    ]
    if not nonmodel:
        return epistemic.STATUS_UNVERIFIED, "only model-generated or unknown-tier support (not proof)"
    note = "supported by " + ", ".join(sorted({source.trust_tier for source in nonmodel}))
    return epistemic.STATUS_CONFIRMED, note + (
        f"; {irrelevant} irrelevant source(s) rejected" if irrelevant else ""
    )


def verify_ledger(
    ledger: ClaimLedger,
    *,
    now: str | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    verifier: str = "source_verifier",
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for claim in ledger.claims():
        status, note = verify_claim(
            claim,
            ledger.sources,
            support_assessments_by_id=ledger.support_assessments,
            now=now,
            max_age_seconds=max_age_seconds,
        )
        if status != claim.status or verifier not in claim.verified_by or note != claim.notes:
            claim = ledger.set_status(claim.id, status, verified_by=verifier, notes=note) or claim
        counts[claim.status] = counts.get(claim.status, 0) + 1
    return counts
