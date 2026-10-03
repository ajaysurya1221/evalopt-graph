"""Epistemic core: typed Claim / Source models, trust tiers, and the reliance rules that stop
hallucination from propagating.

The central invariant (the anti-hallucination rule): **no agent may pass a naked
conclusion downstream**. Every important claim is an evidence packet with a ``status`` and
``trust`` provenance, and only claims that are *usable* (confirmed / user-provided / deterministic)
may be relied on as premises by a downstream node.

This module is pure stdlib and has no dependency on the rest of the package, so the ledger,
verifier, contradiction finder, confidence scorer and research mode can all be unit-tested in
isolation with no network, no LangGraph and no API key.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

# --- claim types ---------------------------------------------------------------------------
CLAIM_TYPES = (
    "user_requirement",
    "code_fact",
    "api_fact",
    "dependency_fact",
    "architecture_decision",
    "security_claim",
    "performance_claim",
    "research_claim",
    "assumption",
    "model_inference",
)

# --- source types (provenance of the evidence behind a claim) ------------------------------
SOURCE_TYPES = (
    "user",
    "official_docs",
    "source_code",
    "command_output",
    "test_result",
    "package_metadata",
    "web_primary_source",
    "web_secondary_source",
    "codex_review",
    "claude_inference",
)

# --- claim status --------------------------------------------------------------------------
STATUS_CONFIRMED = "confirmed"
STATUS_UNVERIFIED = "unverified"
STATUS_CONTRADICTED = "contradicted"
STATUS_STALE = "stale"
STATUS_SUPERSEDED = "superseded"
STATUS_REJECTED = "rejected"
CLAIM_STATUSES = (
    STATUS_CONFIRMED,
    STATUS_UNVERIFIED,
    STATUS_CONTRADICTED,
    STATUS_STALE,
    STATUS_SUPERSEDED,
    STATUS_REJECTED,
)

# Only these may be relied on as premises by a downstream node. ``confirmed`` is the umbrella for
# user-provided and deterministic results (the verifier promotes those to confirmed). Everything
# else (unverified / contradicted / stale / superseded / rejected — i.e. model-inference-only) must
# NOT be used as a premise, and may only appear in final output explicitly marked as an assumption.
USABLE_STATUSES = frozenset({STATUS_CONFIRMED})
UNUSABLE_STATUSES = frozenset(
    {STATUS_UNVERIFIED, STATUS_CONTRADICTED, STATUS_STALE, STATUS_SUPERSEDED, STATUS_REJECTED}
)

# --- trust tiers (lower order == stronger) -------------------------------------------------
T0_DETERMINISTIC = "T0_deterministic"
T1_PRIMARY = "T1_primary"
T2_OFFICIAL = "T2_official_docs"
T3_SECONDARY = "T3_secondary"
T4_MODEL = "T4_model_generated"
TRUST_TIERS = (T0_DETERMINISTIC, T1_PRIMARY, T2_OFFICIAL, T3_SECONDARY, T4_MODEL)
TRUST_ORDER = {T0_DETERMINISTIC: 0, T1_PRIMARY: 1, T2_OFFICIAL: 2, T3_SECONDARY: 3, T4_MODEL: 4}

# Default trust tier per *source_type* (a Source may override with its own ``trust_tier``).
SOURCE_TYPE_TRUST = {
    "user": T1_PRIMARY,
    "source_code": T0_DETERMINISTIC,
    "command_output": T0_DETERMINISTIC,
    "test_result": T0_DETERMINISTIC,
    "package_metadata": T2_OFFICIAL,
    "official_docs": T2_OFFICIAL,
    "web_primary_source": T2_OFFICIAL,
    "web_secondary_source": T3_SECONDARY,
    "codex_review": T4_MODEL,
    "claude_inference": T4_MODEL,
}
# Default trust tier per Source *kind* (source schema).
SOURCE_KIND_TRUST = {
    "local_file": T1_PRIMARY,
    "git_diff": T0_DETERMINISTIC,
    "command_output": T0_DETERMINISTIC,
    "test_output": T0_DETERMINISTIC,
    "official_docs": T2_OFFICIAL,
    "web_page": T3_SECONDARY,
    "mcp_result": T2_OFFICIAL,
    "codex_output": T4_MODEL,
}

DETERMINISTIC_SOURCE_TYPES = frozenset({"command_output", "test_result", "source_code"})
MODEL_SOURCE_TYPES = frozenset({"claude_inference", "codex_review"})

# --- centrality policy: a claim is CENTRAL (must be verified before PASS) when the answer hinges on
# it. Centrality is DERIVED by policy, never trusted purely from a model's self-declared flag. --------
# Claim types whose correctness the final answer structurally depends on.
CENTRAL_CLAIM_TYPES = frozenset({"api_fact", "dependency_fact", "architecture_decision", "security_claim"})
# Topics that are CRITICAL — an unverified central claim here BLOCKS PASS (never a soft downgrade).
_CRITICAL_RE = re.compile(
    r"\b(auth\w*|authn|authz|authoriz\w*|login|logout|password|passwd|token|session|secret|credential"
    r"|api[_-]?key|mfa|2fa|oauth\w*|sso|rbac|access[\s_-]*control|permission\w*|role[\s_-]*based"
    r"|crypto\w*|encrypt\w*|decrypt\w*|tls|ssl|cert\w*|payments?|pay|billing|invoice|charge|refund|checkout"
    r"|privacy|pii|gdpr|hipaa|pci|migrat\w*|schema\s+change|data[\s_-]*loss|delete|destroy|drop\s+table"
    r"|truncate|production|prod\b|deploy\w*|rollout|remote|rce|sql\s*inject\w*|xss|csrf|ssrf|exfil\w*)\b",
    re.I,
)
_KW_RE = re.compile(r"[a-z0-9_./@-]{3,}")
_KW_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "are",
        "was",
        "use",
        "uses",
        "using",
        "from",
        "into",
        "must",
        "should",
        "implement",
        "verify",
        "returns",
        "return",
        "support",
        "add",
    }
)
_POLARITY_WORDS = {
    "enable": ("enabled", 1),
    "enabled": ("enabled", 1),
    "disable": ("enabled", -1),
    "disabled": ("enabled", -1),
    "allow": ("allowed", 1),
    "allowed": ("allowed", 1),
    "permit": ("allowed", 1),
    "permitted": ("allowed", 1),
    "deny": ("allowed", -1),
    "denied": ("allowed", -1),
    "forbidden": ("allowed", -1),
    "prohibited": ("allowed", -1),
    "safe": ("safe", 1),
    "unsafe": ("safe", -1),
    "valid": ("valid", 1),
    "invalid": ("valid", -1),
    "supported": ("supported", 1),
    "unsupported": ("supported", -1),
    "available": ("available", 1),
    "unavailable": ("available", -1),
    "active": ("active", 1),
    "inactive": ("active", -1),
    "approved": ("approved", 1),
    "rejected": ("approved", -1),
    "authorized": ("authorized", 1),
    "unauthorized": ("authorized", -1),
    "verified": ("verified", 1),
    "unverified": ("verified", -1),
    "pass": ("passed", 1),
    "passed": ("passed", 1),
    "fail": ("passed", -1),
    "failed": ("passed", -1),
    "present": ("present", 1),
    "absent": ("present", -1),
}
_NEGATED_RE = re.compile(r"\b(not|never|without|cannot)\b|n't\b", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        s = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def trust_order(tier: str) -> int:
    return TRUST_ORDER.get(tier, TRUST_ORDER[T4_MODEL])


def is_known_trust_tier(tier: str) -> bool:
    """Whether ``tier`` is one of the policy-defined trust tiers.

    Unknown values are never promoted to a usable tier.  ``trust_order`` still sorts them with T4
    for backward-compatible scoring, while authorization-style comparisons fail closed below.
    """
    return tier in TRUST_ORDER


def is_at_least(tier: str, required: str) -> bool:
    """True if ``tier`` is as strong as or stronger than ``required`` (T0 strongest)."""
    if not is_known_trust_tier(tier) or not is_known_trust_tier(required):
        return False
    return trust_order(tier) <= trust_order(required)


def default_trust_for_source_type(source_type: str) -> str:
    return SOURCE_TYPE_TRUST.get(source_type, T4_MODEL)


def default_trust_for_kind(kind: str) -> str:
    return SOURCE_KIND_TRUST.get(kind, T4_MODEL)


# ============================== data models ==============================


@dataclass
class Source:
    """Where a piece of evidence actually came from (locatable + trust-tiered)."""

    id: str
    kind: str = "local_file"
    locator: str = ""  # path / url / command / log-id
    retrieved_at: str = ""
    freshness_required: bool = False
    trust_tier: str = T4_MODEL
    summary: str = ""
    quoted_span_or_hash: str = ""
    # Adapter-issued evidence is linked through immutable attestation/support records.  Empty values
    # preserve the trusted-controller ``add_source`` API for one compatibility cycle.  An untrusted
    # legacy packet is required to set explicit UNVERIFIED / NOT_ASSESSED markers, which fail closed.
    attestation_id: str = ""
    attestation_status: str = ""
    support_assessment_id: str = ""
    support_relation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Source:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Claim:
    """An evidence packet. A claim is only usable as a downstream premise when ``status`` is in
    :data:`USABLE_STATUSES` (and not expired)."""

    id: str
    text: str
    type: str = "model_inference"
    source_type: str = "claude_inference"
    evidence_refs: list[str] = field(default_factory=list)  # Source ids backing this claim
    confidence: float = 0.0
    status: str = STATUS_UNVERIFIED
    created_by: str = ""
    verified_by: list[str] = field(default_factory=list)
    used_by: list[str] = field(default_factory=list)
    created_at: str = ""
    expires_at: str | None = None
    notes: str = ""
    # additive metadata (not in the minimal schema) used for contradiction detection + adjudication
    subject: str = ""  # topic key: claims with the same subject are compared for contradictions
    stance: str = ""  # the position taken on the subject (differing stances => contradiction)
    central: bool = False  # a central claim must meet the trust requirement before a final PASS
    centrality_policy_reasons: list[str] = field(default_factory=list)  # why policy marks it central

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Claim:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ============================== reliance rules ==============================


def is_expired(claim: Claim, now: str | None = None) -> bool:
    exp = _parse_iso(claim.expires_at)
    if exp is None:
        return False
    cur = _parse_iso(now) or datetime.now(timezone.utc)
    return cur >= exp


def is_usable(claim: Claim, now: str | None = None) -> bool:
    """Whether a downstream node may rely on this claim as a premise."""
    return claim.status in USABLE_STATUSES and not is_expired(claim, now)


def is_deterministic(claim: Claim) -> bool:
    return claim.source_type in DETERMINISTIC_SOURCE_TYPES


def is_user_provided(claim: Claim) -> bool:
    return claim.source_type == "user"


def source_has_verified_support(source: Source) -> bool:
    """Whether a source is eligible to raise a claim's trust.

    Sources created directly by trusted controller code predate attestations and have all four binding
    fields empty.  Once any binding metadata is present, the complete adapter-issued chain is required.
    This lets old deterministic controller paths keep working without allowing explicitly downgraded
    model packets to become evidence.
    """
    binding = (
        source.attestation_id,
        source.attestation_status,
        source.support_assessment_id,
        source.support_relation,
    )
    if not any(binding):
        return True
    return bool(
        source.attestation_id
        and source.support_assessment_id
        and source.attestation_status == "VERIFIED"
        and source.support_relation == "SUPPORTS"
    )


def best_supporting_trust(claim: Claim, sources_by_id: dict[str, Source]) -> str:
    """The strongest trust tier among the claim's ACTUAL supporting sources.

    Trust may not be self-manufactured: when a claim references no real Source, its trust collapses to
    T1 for user-provided claims (the user is authoritative) and otherwise to T4 (model-generated). A
    model cannot raise its own trust tier by merely declaring ``source_type='official_docs'``.
    """
    tiers = []
    for ref in claim.evidence_refs:
        source = sources_by_id.get(ref)
        if source is None or not source_has_verified_support(source):
            continue
        # An unknown tier is not a new, non-model tier.  Normalize it to the weakest known tier so
        # scoring and contradiction ordering cannot treat attacker-chosen labels as authority.
        tiers.append(source.trust_tier if is_known_trust_tier(source.trust_tier) else T4_MODEL)
    if tiers:
        return min(tiers, key=trust_order)
    return T1_PRIMARY if is_user_provided(claim) else T4_MODEL


def meets_trust_requirement(
    claim: Claim, sources_by_id: dict[str, Source], required: str = T2_OFFICIAL
) -> bool:
    """A central claim must be backed by evidence at least as strong as ``required`` (default T2).

    Only user-provided claims are trusted without a Source; a self-declared *deterministic* source_type
    no longer counts — determinism must be backed by a real T0 Source (via ``best_supporting_trust``).
    """
    if is_user_provided(claim):
        return True
    return is_at_least(best_supporting_trust(claim, sources_by_id), required)


def has_nonmodel_support(claim: Claim, sources_by_id: dict[str, Source]) -> bool:
    """True if at least one supporting source is NOT model-generated (T4). Model consensus alone
    (claude/codex) can suggest a hypothesis but cannot confirm a claim."""
    for r in claim.evidence_refs:
        s = sources_by_id.get(r)
        if (
            s
            and source_has_verified_support(s)
            and is_known_trust_tier(s.trust_tier)
            and s.trust_tier != T4_MODEL
        ):
            return True
    return False


# --- provenance / self-certification / centrality policy ------------------------------------


def self_certifies(claim: Claim, verifier: str) -> bool:
    """A claim being confirmed by its own creator. Claim creation and verification must be distinct
    roles — an agent may not certify its own guess, and it must not be able to dodge this by
    *declaring* a stronger ``source_type`` (e.g. 'official_docs'). User-provided claims are exempt
    (the user is authoritative and is confirmed at creation, not via a verifier)."""
    return bool(verifier) and verifier == claim.created_by and claim.source_type != "user"


def keywords(text: str) -> set[str]:
    return {w for w in _KW_RE.findall((text or "").lower()) if w not in _KW_STOP}


def _critical_text_conflict(left: str, right: str) -> bool:
    """Recognize a bounded set of opposite polarities over the same proposition core."""
    if " ".join(left.casefold().split()) == " ".join(right.casefold().split()):
        return False

    def proposition(text: str) -> tuple[set[tuple[str, int]], set[str]]:
        words = {word.strip("./") for word in keywords(text)}
        negated = bool(_NEGATED_RE.search(text))
        markers = set()
        for word in words:
            if marker := _POLARITY_WORDS.get(word):
                base, sign = marker
                markers.add((base, -sign if negated else sign))
        core = words - set(_POLARITY_WORDS) - {"not", "never", "without", "cannot"}
        return markers, core

    left_markers, left_core = proposition(left)
    right_markers, right_core = proposition(right)
    return bool(
        left_core
        and left_core == right_core
        and any(
            left_base == right_base and left_sign == -right_sign
            for left_base, left_sign in left_markers
            for right_base, right_sign in right_markers
        )
    )


def is_critical_text(text: str) -> bool:
    """True if the text concerns a CRITICAL topic (security/auth/privacy/payments/data-loss/
    migration/production/remote) where an unverified conclusion must hard-block PASS."""
    return bool(_CRITICAL_RE.search(text or ""))


def central_criteria(acceptance_criteria: list[str] | tuple[str, ...]) -> list[str]:
    """The acceptance criteria that touch a CRITICAL topic (security/auth/privacy/payments/data-loss/
    migration/production). These are the load-bearing claims a green build must still not assert
    without independent evidence."""
    return [c for c in (acceptance_criteria or ()) if c and is_critical_text(c)]


def is_critical(claim: Claim) -> bool:
    return claim.type == "security_claim" or is_critical_text(f"{claim.subject} {claim.text}")


def derive_centrality(
    claim: Claim, acceptance_criteria: list[str] | tuple[str, ...] = (), *, extra_texts=()
) -> list[str]:
    """Policy-derived centrality reasons (empty list == not central by policy). Centrality is a
    property of the ROLE a claim plays, not a flag the creating agent can lower to dodge PASS-blocking.
    """
    reasons: list[str] = []
    if claim.type == "assumption":
        return reasons  # an explicit assumption is surfaced, not treated as a load-bearing fact
    if claim.type in CENTRAL_CLAIM_TYPES:
        reasons.append(f"high-risk claim type ({claim.type})")
    if is_critical(claim):
        reasons.append("touches a critical topic (security/auth/privacy/payments/data-loss/prod)")
    ckw = keywords(f"{claim.subject} {claim.text}")
    if ckw:
        for crit in acceptance_criteria or ():
            ck = keywords(crit)
            if ck and (len(ckw & ck) >= 2 or ck <= ckw):
                reasons.append("required by an acceptance criterion")
                break
        for t in extra_texts or ():
            if len(ckw & keywords(t)) >= 2:
                reasons.append("used by the implementation plan / patch rationale / synthesis")
                break
    return reasons
