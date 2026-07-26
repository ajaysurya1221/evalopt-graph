"""Stable, host-independent governance and evidence-integrity API."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime
from math import isfinite
from typing import Any

from .attestation import (
    AdapterPolicy,
    EvidenceAttestation,
    EvidenceRequest,
    RetrievedArtifact,
    SupportAssessment,
    _hash_record,
    _issue_failure,
    _issue_material,
    claim_digest,
)
from .epistemic import (
    CENTRAL_CLAIM_TYPES,
    T2_OFFICIAL,
    TRUST_TIERS,
    _critical_text_conflict,
    is_at_least,
    is_critical_text,
    keywords,
)

EvidenceMaterial = RetrievedArtifact
_DECISIONS = {"ACCEPTED", "BLOCKED", "UNVERIFIED", "UNSUPPORTED", "FAILED"}


def _time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class GovernancePolicy:
    """Acceptance policy; host adapters and orchestration remain outside this value."""

    required_gates: tuple[str, ...] = ()
    minimum_trust: str = T2_OFFICIAL
    quality_threshold: float = 0.90
    require_evaluator: bool = False
    max_evidence_age_seconds: int = 60 * 60 * 24 * 30
    required_claim_ids: tuple[str, ...] = ()
    disqualified_claim_ids: tuple[str, ...] = ()
    allowed_verifiers: tuple[tuple[str, str], ...] = (("evalopt.lexical_support", "2"),)
    allowed_authority_policies: tuple[str, ...] = ()
    authorized_record_sha256: tuple[str, ...] = ()
    schema_version: str = "evalopt.governance-policy.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "required_gates", tuple(dict.fromkeys(self.required_gates)))
        object.__setattr__(self, "allowed_verifiers", tuple(tuple(item) for item in self.allowed_verifiers))
        object.__setattr__(
            self, "allowed_authority_policies", tuple(dict.fromkeys(self.allowed_authority_policies))
        )
        object.__setattr__(
            self, "authorized_record_sha256", tuple(dict.fromkeys(self.authorized_record_sha256))
        )
        object.__setattr__(self, "required_claim_ids", tuple(dict.fromkeys(self.required_claim_ids)))
        object.__setattr__(
            self,
            "disqualified_claim_ids",
            tuple(dict.fromkeys(self.disqualified_claim_ids)),
        )
        if self.minimum_trust not in TRUST_TIERS:
            raise ValueError(f"unknown minimum trust tier: {self.minimum_trust}")
        if self.schema_version != "evalopt.governance-policy.v1":
            raise ValueError(f"unsupported governance policy schema: {self.schema_version}")
        if any(not isinstance(gate, str) or not gate for gate in self.required_gates):
            raise ValueError("required gate names must be nonempty strings")
        if not 0 <= self.quality_threshold <= 1:
            raise ValueError("quality_threshold must be between zero and one")
        if (
            not isinstance(self.max_evidence_age_seconds, int)
            or isinstance(self.max_evidence_age_seconds, bool)
            or self.max_evidence_age_seconds <= 0
        ):
            raise ValueError("max_evidence_age_seconds must be a positive integer")
        if any(len(item) != 2 or not all(item) for item in self.allowed_verifiers):
            raise ValueError("allowed verifier entries require nonempty id and version")
        if any(not isinstance(item, str) or not item for item in self.required_claim_ids):
            raise ValueError("required claim ids must be nonempty strings")
        if any(not isinstance(item, str) or not item for item in self.disqualified_claim_ids):
            raise ValueError("disqualified claim ids must be nonempty strings")
        digests = (*self.allowed_authority_policies, *self.authorized_record_sha256)
        if any(len(item) != 64 or set(item) - set("0123456789abcdef") for item in digests):
            raise ValueError("authority and evidence allowlists require lowercase SHA-256 digests")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return _hash_record(self.to_dict())


@dataclass(frozen=True)
class ClaimRecord:
    id: str
    text: str
    claim_type: str = "model_inference"
    subject: str = ""
    stance: str = ""
    assessment_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        values = (self.id, self.text, self.claim_type, self.subject, self.stance)
        if any(not isinstance(value, str) for value in values):
            raise ValueError("claim text fields must be strings")
        assessment_ids = tuple(self.assessment_ids)
        if any(not isinstance(value, str) or not value for value in assessment_ids):
            raise ValueError("assessment ids must be nonempty strings")
        object.__setattr__(self, "assessment_ids", tuple(dict.fromkeys(assessment_ids)))
        if not self.id or not self.text.strip():
            raise ValueError("claim id and text must not be empty")

    @property
    def digest(self) -> str:
        return claim_digest(
            self.text,
            claim_type=self.claim_type,
            claim_subject=self.subject,
            claim_stance=self.stance,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AcceptanceInput:
    observed_at: str
    gate_results: tuple[tuple[str, str], ...] = ()
    criteria: tuple[str, ...] = ()
    claims: tuple[ClaimRecord, ...] = ()
    contradictions: tuple[tuple[str, str, str], ...] = ()
    attestations: tuple[EvidenceAttestation, ...] = ()
    assessments: tuple[SupportAssessment, ...] = ()
    tests_weakened: bool = False
    evaluator_score: float | None = None
    schema_version: str = "evalopt.acceptance-input.v1"

    def __post_init__(self) -> None:
        if self.schema_version != "evalopt.acceptance-input.v1":
            raise ValueError(f"unsupported acceptance input schema: {self.schema_version}")
        if not isinstance(self.observed_at, str):
            raise ValueError("observed_at must be a string")

        def rows(name: str, values: Iterable[Iterable[str]], width: int) -> tuple[tuple[str, ...], ...]:
            if isinstance(values, str | bytes):
                raise ValueError(f"{name} entries require {width} string fields")
            normalized: list[tuple[str, ...]] = []
            try:
                iterator = iter(values)
            except TypeError as exc:
                raise ValueError(f"{name} entries require {width} string fields") from exc
            for row in iterator:
                if isinstance(row, str | bytes):
                    raise ValueError(f"{name} entries require {width} string fields")
                try:
                    normalized.append(tuple(row))
                except TypeError as exc:
                    raise ValueError(f"{name} entries require {width} string fields") from exc
            if any(len(row) != width or not all(isinstance(item, str) for item in row) for row in normalized):
                raise ValueError(f"{name} entries require {width} string fields")
            return tuple(normalized)

        object.__setattr__(self, "gate_results", rows("gate_results", self.gate_results, 2))
        object.__setattr__(self, "contradictions", rows("contradictions", self.contradictions, 3))
        object.__setattr__(self, "criteria", tuple(self.criteria))
        object.__setattr__(self, "claims", tuple(self.claims))
        object.__setattr__(self, "attestations", tuple(self.attestations))
        object.__setattr__(self, "assessments", tuple(self.assessments))
        if any(not isinstance(item, str) for item in self.criteria):
            raise ValueError("criteria entries must be strings")
        typed = (
            ("claims", self.claims, ClaimRecord),
            ("attestations", self.attestations, EvidenceAttestation),
            ("assessments", self.assessments, SupportAssessment),
        )
        if any(not isinstance(item, cls) for _name, values, cls in typed for item in values):
            raise ValueError("claims and evidence entries must use their declared value types")
        severities = {"normal", "high", "blocking", "important", "minor", "explainable"}
        statuses = {"unresolved", "resolved"}
        normalized_contradictions = tuple(
            (id_, severity.casefold(), status.casefold()) for id_, severity, status in self.contradictions
        )
        if any(
            not id_ or severity not in severities or status not in statuses
            for id_, severity, status in normalized_contradictions
        ):
            raise ValueError("contradictions require a known severity and resolution status")
        object.__setattr__(self, "contradictions", normalized_contradictions)
        if not isinstance(self.tests_weakened, bool):
            raise ValueError("tests_weakened must be a boolean")
        score = self.evaluator_score
        if score is not None and (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
            or not isfinite(float(score))
            or not 0 <= score <= 1
        ):
            raise ValueError("evaluator_score must be a finite number between zero and one")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "observed_at": self.observed_at,
            "gate_results": [list(item) for item in self.gate_results],
            "criteria": list(self.criteria),
            "claims": [item.to_dict() for item in self.claims],
            "contradictions": [list(item) for item in self.contradictions],
            "attestations": [item.to_dict() for item in self.attestations],
            "assessments": [item.to_dict() for item in self.assessments],
            "tests_weakened": self.tests_weakened,
            "evaluator_score": self.evaluator_score,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AcceptanceInput:
        return cls(
            observed_at=str(value.get("observed_at", "")),
            gate_results=value.get("gate_results", ()),
            criteria=tuple(value.get("criteria", ())),
            claims=tuple(ClaimRecord(**item) for item in value.get("claims", ())),
            contradictions=value.get("contradictions", ()),
            attestations=tuple(EvidenceAttestation.from_dict(item) for item in value.get("attestations", ())),
            assessments=tuple(SupportAssessment.from_dict(item) for item in value.get("assessments", ())),
            tests_weakened=value.get("tests_weakened", False),
            evaluator_score=value.get("evaluator_score"),
            schema_version=str(value.get("schema_version", "evalopt.acceptance-input.v1")),
        )

    @property
    def digest(self) -> str:
        return _hash_record(self.to_dict())


@dataclass(frozen=True)
class AcceptanceDecision:
    status: str
    reasons: tuple[str, ...]
    policy_sha256: str
    input_sha256: str
    evidence_sha256: tuple[str, ...]
    record_sha256: str
    schema_version: str = "evalopt.acceptance-decision.v1"

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasons", tuple(self.reasons))
        object.__setattr__(self, "evidence_sha256", tuple(self.evidence_sha256))

    @classmethod
    def create(
        cls,
        status: str,
        reasons: Iterable[str],
        policy: GovernancePolicy,
        input_: AcceptanceInput,
        evidence: Iterable[str] = (),
    ) -> AcceptanceDecision:
        payload = {
            "schema_version": "evalopt.acceptance-decision.v1",
            "status": status,
            "reasons": tuple(dict.fromkeys(reasons)),
            "policy_sha256": policy.digest,
            "input_sha256": input_.digest,
            "evidence_sha256": tuple(dict.fromkeys(evidence)),
        }
        return cls(**payload, record_sha256=_hash_record(payload))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> AcceptanceDecision:
        data = dict(value)
        data["reasons"] = tuple(data.get("reasons", ()))
        data["evidence_sha256"] = tuple(data.get("evidence_sha256", ()))
        return cls(**data)

    def validate(self) -> bool:
        payload = self.to_dict()
        digest = payload.pop("record_sha256")
        return bool(
            self.schema_version == "evalopt.acceptance-decision.v1"
            and self.status in _DECISIONS
            and digest == _hash_record(payload)
        )

    def replay(self, policy: GovernancePolicy, input_: AcceptanceInput) -> bool:
        return self == evaluate_acceptance(policy, input_)


@dataclass(frozen=True, init=False)
class EvidenceAuthority:
    """Immutable authority policy; issuance consumes material already retrieved by a host."""

    def __init__(self, policies: Iterable[Mapping[str, object]]) -> None:
        normalized: dict[str, AdapterPolicy] = {}
        for value in policies:
            policy = AdapterPolicy(**value)
            if policy.adapter_id in normalized:
                raise ValueError(f"duplicate evidence adapter id: {policy.adapter_id}")
            normalized[policy.adapter_id] = policy
        object.__setattr__(self, "_policies", tuple(normalized.values()))

    @property
    def policy_hashes(self) -> tuple[str, ...]:
        return tuple(policy.digest for policy in self._policies)

    def _policy_for(self, adapter_id: str) -> AdapterPolicy | None:
        return next((policy for policy in self._policies if policy.adapter_id == adapter_id), None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "evalopt.evidence-authority.v1",
            "policies": [p.to_dict() for p in self._policies],
        }

    def issue(
        self,
        request: EvidenceRequest,
        material: EvidenceMaterial,
        *,
        observed_at: str,
        claim: ClaimRecord,
    ) -> tuple[EvidenceAttestation, SupportAssessment]:
        policy = self._policy_for(request.adapter_id)
        if policy is None:
            return _issue_failure(
                request,
                claim_text=claim.text,
                claim_type=claim.claim_type,
                claim_subject=claim.subject,
                claim_stance=claim.stance,
                status="UNSUPPORTED",
                reason=f"evidence adapter is not registered: {request.adapter_id}",
            )
        return _issue_material(
            policy,
            request,
            material,
            observed_at=observed_at,
            claim_text=claim.text,
            claim_type=claim.claim_type,
            claim_subject=claim.subject,
            claim_stance=claim.stance,
        )


def _claim_is_supported(
    claim: ClaimRecord,
    policy: GovernancePolicy,
    attestations: dict[str, EvidenceAttestation],
    assessments: dict[str, SupportAssessment],
    observed_at: datetime,
) -> tuple[bool, bool, bool, tuple[str, ...]]:
    used: list[str] = []
    stale = False
    supported = False
    contradicted = False
    for assessment_id in claim.assessment_ids:
        assessment = assessments.get(assessment_id)
        evidence = attestations.get(assessment.attestation_id) if assessment else None
        if not assessment or not evidence:
            continue
        eligible = (
            assessment.validate_record_hash()
            and evidence.validate_record_hash()
            and assessment.relation in {"SUPPORTS", "CONTRADICTS"}
            and assessment.claim_sha256 == claim.digest
            and assessment.attestation_record_sha256 == evidence.record_sha256
            and (assessment.verifier_id, assessment.verifier_version) in policy.allowed_verifiers
            and evidence.status == "VERIFIED"
            and evidence.policy_sha256 in policy.allowed_authority_policies
            and evidence.record_sha256 in policy.authorized_record_sha256
            and assessment.record_sha256 in policy.authorized_record_sha256
            and is_at_least(evidence.trust_tier, policy.minimum_trust)
        )
        if eligible:
            retrieved_at = _time(evidence.retrieved_at)
            if retrieved_at is None or retrieved_at > observed_at:
                continue
            if assessment.relation == "CONTRADICTS":
                contradicted = True
                used.extend((evidence.record_sha256, assessment.record_sha256))
                continue
            if (
                evidence.freshness_required
                and (observed_at - retrieved_at).total_seconds() > policy.max_evidence_age_seconds
            ):
                stale = True
                continue
            used.extend((evidence.record_sha256, assessment.record_sha256))
            supported = True
    return supported and not contradicted, stale, contradicted, tuple(used)


def _load_bearing(claim: ClaimRecord, policy: GovernancePolicy, criteria: tuple[str, ...]) -> bool:
    text = f"{claim.subject} {claim.text}"
    claim_words = keywords(text)
    return bool(
        claim.id in policy.required_claim_ids
        or claim.claim_type in CENTRAL_CLAIM_TYPES
        or is_critical_text(text)
        or any(
            (criterion_words := keywords(criterion))
            and (len(claim_words & criterion_words) >= 2 or criterion_words <= claim_words)
            for criterion in criteria
        )
    )


def _same_statement(left: str, right: str) -> bool:
    return " ".join(left.casefold().split()) == " ".join(right.casefold().split())


def evaluate_acceptance(policy: GovernancePolicy, input_: AcceptanceInput) -> AcceptanceDecision:
    """Return one deterministic terminal decision without mutating either input."""
    malformed: list[str] = []
    blocked: list[str] = []
    failed: list[str] = []
    unsupported: list[str] = []
    unverified: list[str] = []
    used: list[str] = []
    observed_at = _time(input_.observed_at)
    if observed_at is None:
        malformed.append("invalid_observation_time")
    if any(not item.validate_record_hash() for item in input_.attestations):
        malformed.append("invalid_attestation_record")
    if any(not item.validate_record_hash() for item in input_.assessments):
        malformed.append("invalid_support_record")
    if len({item.attestation_id for item in input_.attestations}) != len(input_.attestations):
        malformed.append("duplicate_attestation")
    if len({item.assessment_id for item in input_.assessments}) != len(input_.assessments):
        malformed.append("duplicate_support_assessment")
    if len({item.id for item in input_.claims}) != len(input_.claims):
        malformed.append("duplicate_claim")
    if observed_at is not None and any(
        (retrieved := _time(item.retrieved_at)) is not None and retrieved > observed_at
        for item in input_.attestations
        if item.status == "VERIFIED"
    ):
        malformed.append("evidence_from_future")
    score = input_.evaluator_score

    gates = dict(input_.gate_results)
    if len(gates) != len(input_.gate_results):
        malformed.append("duplicate_gate_observation")
    for gate in policy.required_gates:
        result = gates.get(gate)
        if result in (None, "NOT_CONFIGURED"):
            unsupported.append(f"required_gate_unavailable:{gate}")
        elif result != "PASS":
            failed.append(f"required_gate_failed:{gate}")
    if input_.tests_weakened is True:
        blocked.append("tests_weakened")
    if policy.require_evaluator and score is None:
        unsupported.append("evaluator_unavailable")
    elif score is not None and score < policy.quality_threshold:
        failed.append("quality_threshold_not_met")
    if any(
        status != "resolved" and severity in {"high", "blocking"}
        for _, severity, status in input_.contradictions
    ):
        blocked.append("unresolved_blocking_contradiction")

    critical_claims = [
        claim
        for claim in input_.claims
        if claim.id not in policy.disqualified_claim_ids
        and (claim.claim_type == "security_claim" or is_critical_text(f"{claim.subject} {claim.text}"))
    ]
    for index, left in enumerate(critical_claims):
        for right in critical_claims[index + 1 :]:
            if _critical_text_conflict(left.text, right.text):
                blocked.append(f"potential_critical_claim_conflict:{left.id}:{right.id}")

    evidence_by_id = {item.attestation_id: item for item in input_.attestations}
    assessment_by_id = {item.assessment_id: item for item in input_.assessments}
    claim_ids = {claim.id for claim in input_.claims}
    unverified.extend(
        f"required_claim_missing:{claim_id}"
        for claim_id in policy.required_claim_ids
        if claim_id not in claim_ids
    )
    supported_claims: set[str] = set()
    for claim in input_.claims:
        if not _load_bearing(claim, policy, input_.criteria):
            continue
        if claim.id in policy.disqualified_claim_ids:
            unverified.append(f"central_claim_disqualified:{claim.id}")
            continue
        if observed_at is None:
            continue
        supported, stale, contradicted, records = _claim_is_supported(
            claim, policy, evidence_by_id, assessment_by_id, observed_at
        )
        if not supported:
            reason = (
                "central_claim_contradicted"
                if contradicted
                else "central_claim_stale"
                if stale
                else "central_claim_unverified"
            )
            unverified.append(f"{reason}:{claim.id}")
            used.extend(records)
        else:
            supported_claims.add(claim.id)
            used.extend(records)
    for index, criterion in enumerate(input_.criteria):
        if not is_critical_text(criterion):
            continue
        covered = any(
            claim.id in supported_claims
            and claim.id not in policy.disqualified_claim_ids
            and _load_bearing(claim, policy, input_.criteria)
            and _same_statement(criterion, claim.text)
            for claim in input_.claims
        )
        if not covered:
            unverified.append(f"critical_criterion_unverified:{index}")

    if malformed:
        return AcceptanceDecision.create("FAILED", malformed, policy, input_)
    if blocked:
        return AcceptanceDecision.create("BLOCKED", blocked, policy, input_, used)
    if failed:
        return AcceptanceDecision.create("FAILED", failed, policy, input_, used)
    if unsupported:
        return AcceptanceDecision.create("UNSUPPORTED", unsupported, policy, input_, used)
    if unverified:
        return AcceptanceDecision.create("UNVERIFIED", unverified, policy, input_, used)
    return AcceptanceDecision.create("ACCEPTED", ("policy_satisfied",), policy, input_, used)


__all__ = [
    "GovernancePolicy",
    "ClaimRecord",
    "EvidenceRequest",
    "EvidenceMaterial",
    "EvidenceAttestation",
    "SupportAssessment",
    "EvidenceAuthority",
    "AcceptanceInput",
    "AcceptanceDecision",
    "evaluate_acceptance",
]
