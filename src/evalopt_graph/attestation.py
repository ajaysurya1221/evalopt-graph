"""Pure evidence authority: proposal fields in, content-bound records out."""

from __future__ import annotations

import json
import re
import unicodedata
from base64 import b64decode, b64encode
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from .epistemic import (
    SOURCE_KIND_TRUST,
    T4_MODEL,
    TRUST_TIERS,
    is_critical_text,
)

VERIFIED, BLOCKED, UNVERIFIED, UNSUPPORTED, FAILED = (
    "VERIFIED",
    "BLOCKED",
    "UNVERIFIED",
    "UNSUPPORTED",
    "FAILED",
)
SUPPORTS, CONTRADICTS, INSUFFICIENT, NOT_ASSESSED = (
    "SUPPORTS",
    "CONTRADICTS",
    "INSUFFICIENT",
    "NOT_ASSESSED",
)

_SCHEMA = "evalopt.evidence-attestation.v1"
_CANON = "utf8-nfc-lf@1"
_STATUSES = {VERIFIED, BLOCKED, UNVERIFIED, UNSUPPORTED, FAILED}
_RELATIONS = {SUPPORTS, CONTRADICTS, INSUFFICIENT, NOT_ASSESSED}
_SELECTORS = {"", "quoted_span", "json_pointer"}
_SOURCE_KINDS = {*SOURCE_KIND_TRUST, "unverified"}


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def _hash_record(value: Mapping[str, object]) -> str:
    return sha256(_canonical_json(value)).hexdigest()


def _sha(value: str | bytes) -> str:
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def _is_sha(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else None


def _known(cls: type[object], value: Mapping[str, Any]) -> dict[str, Any]:
    names = {item.name for item in fields(cls)}
    return {key: item for key, item in value.items() if key in names}


def claim_digest(text: str, *, claim_type: str = "", claim_subject: str = "", claim_stance: str = "") -> str:
    return _hash_record(
        {
            "version": "evalopt.claim-identity.v1",
            "text": text.strip(),
            "type": claim_type,
            "subject": claim_subject,
            "stance": claim_stance,
        }
    )


@dataclass(frozen=True)
class AdapterPolicy:
    adapter_id: str
    adapter_version: str
    source_kind: str
    trust_tier: str
    retrieval_mechanism: str
    parser_identity: str
    freshness_required: bool
    max_bytes: int = 2_000_000
    max_selected_bytes: int = 200_000

    def __post_init__(self) -> None:
        identity = (
            self.adapter_id,
            self.adapter_version,
            self.retrieval_mechanism,
            self.parser_identity,
        )
        if not all(identity):
            raise ValueError("adapter policy identity fields must not be empty")
        if self.source_kind not in SOURCE_KIND_TRUST:
            raise ValueError(f"unknown source kind: {self.source_kind}")
        if self.trust_tier not in TRUST_TIERS:
            raise ValueError(f"unknown trust tier: {self.trust_tier}")
        if self.max_bytes <= 0 or not 0 < self.max_selected_bytes <= self.max_bytes:
            raise ValueError("byte limits must be positive and selected content must fit within material")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def digest(self) -> str:
        return _hash_record({"schema_version": _SCHEMA, **self.to_dict()})


@dataclass(frozen=True)
class RetrievedArtifact:
    content: bytes
    final_locator: str
    retrieved_at: str
    media_type: str = "application/octet-stream"

    def __post_init__(self) -> None:
        if not isinstance(self.content, bytes):
            object.__setattr__(self, "content", bytes(self.content))
        if not self.final_locator:
            raise ValueError("retrieved artifact final_locator must not be empty")
        if not self.media_type:
            raise ValueError("retrieved artifact media_type must not be empty")

    def to_dict(self) -> dict[str, str]:
        return {
            "content_base64": b64encode(self.content).decode("ascii"),
            "final_locator": self.final_locator,
            "retrieved_at": self.retrieved_at,
            "media_type": self.media_type,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> RetrievedArtifact:
        return cls(
            b64decode(str(value.get("content_base64", "")), validate=True),
            str(value.get("final_locator", "")),
            str(value.get("retrieved_at", "")),
            str(value.get("media_type", "application/octet-stream")),
        )


@dataclass(frozen=True)
class EvidenceRequest:
    adapter_id: str
    locator: str
    quoted_span: str | None = None
    json_pointer: str | None = None
    expected_sha256: str | None = None
    expected_final_locator: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> EvidenceRequest:
        def optional(key: str) -> str | None:
            item = value.get(key)
            return None if item is None else str(item)

        return cls(
            str(value.get("adapter_id", "")),
            str(value.get("locator", "")),
            optional("quoted_span"),
            optional("json_pointer"),
            optional("expected_sha256"),
            optional("expected_final_locator"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceAttestation:
    schema_version: str
    attestation_id: str
    adapter_id: str
    adapter_version: str
    retrieval_mechanism: str
    parser_identity: str
    policy_sha256: str
    requested_locator: str
    final_locator: str
    source_kind: str
    trust_tier: str
    retrieved_at: str
    freshness_required: bool
    media_type: str
    canonicalization: str
    raw_content_sha256: str
    normalized_content_sha256: str
    selector_kind: str
    selector_value: str
    selected_text: str
    selected_sha256: str
    status: str
    failure_reason: str
    record_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> EvidenceAttestation:
        return cls(**_known(cls, value))

    def validate_record_hash(self) -> bool:
        record = self.to_dict()
        digest = record.pop("record_sha256")
        if not _is_sha(digest) or _hash_record(record) != digest:
            return False
        attestation_id = record.pop("attestation_id")
        selected_hash = _sha(self.selected_text) if self.selected_text else ""
        base_valid = bool(
            attestation_id == f"att-{_hash_record(record)[:24]}"
            and self.schema_version == _SCHEMA
            and self.canonicalization == _CANON
            and self.status in _STATUSES
            and self.source_kind in _SOURCE_KINDS
            and self.trust_tier in TRUST_TIERS
            and self.selector_kind in _SELECTORS
            and self.adapter_id
            and _is_sha(self.policy_sha256)
            and self.selected_sha256 == selected_hash
            and all(
                not item or _is_sha(item)
                for item in (
                    self.raw_content_sha256,
                    self.normalized_content_sha256,
                    self.selected_sha256,
                )
            )
            and (not self.retrieved_at or _timestamp(self.retrieved_at))
        )
        if not base_valid:
            return False
        if self.status != VERIFIED:
            return bool(self.failure_reason and not self.selected_text and not self.selected_sha256)
        required = (
            self.adapter_version,
            self.retrieval_mechanism,
            self.parser_identity,
            self.policy_sha256,
            self.final_locator,
            self.retrieved_at,
            self.raw_content_sha256,
            self.normalized_content_sha256,
            self.selector_kind,
            self.selected_sha256,
        )
        return bool(
            all(required)
            and not self.failure_reason
            and self.source_kind != "unverified"
            and _timestamp(self.retrieved_at)
            and (self.selector_kind != "quoted_span" or self.selector_value)
        )


@dataclass(frozen=True)
class SupportAssessment:
    schema_version: str
    assessment_id: str
    claim_sha256: str
    claim_type: str
    claim_subject: str
    claim_stance: str
    attestation_id: str
    attestation_record_sha256: str
    relation: str
    verifier_id: str
    verifier_version: str
    reason: str
    record_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> SupportAssessment:
        return cls(**_known(cls, value))

    def validate_record_hash(self) -> bool:
        record = self.to_dict()
        digest = record.pop("record_sha256")
        if not _is_sha(digest) or _hash_record(record) != digest:
            return False
        assessment_id = record.pop("assessment_id")
        return bool(
            assessment_id == f"sup-{_hash_record(record)[:24]}"
            and self.schema_version == _SCHEMA
            and self.relation in _RELATIONS
            and _is_sha(self.claim_sha256)
            and _is_sha(self.attestation_record_sha256)
            and self.attestation_id.startswith("att-")
            and self.verifier_id
            and self.verifier_version
        )


class _SelectionError(Exception):
    pass


def _normalize(content: bytes) -> tuple[str, bytes]:
    text = content.decode()
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return text, text.encode()


def _pointer(document: object, pointer: str) -> object:
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise KeyError(pointer)
    current = document
    for encoded in pointer[1:].split("/"):
        token = encoded.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and token in current:
            current = current[token]
        elif isinstance(current, list) and token.isdigit() and int(token) < len(current):
            current = current[int(token)]
        else:
            raise KeyError(token)
    return current


def _select(text: str, raw: bytes, kind: str, value: str) -> str:
    if kind == "quoted_span":
        if not value or text.count(value) != 1:
            reason = "empty" if not value else "missing" if value not in text else "ambiguous"
            raise _SelectionError(f"quoted span is {reason} in retrieved content")
        return value
    if kind == "json_pointer":
        try:
            selected = _pointer(json.loads(raw.decode()), value)
        except KeyError as exc:
            raise _SelectionError(f"JSON pointer is missing or invalid: {value}") from exc
        return selected if isinstance(selected, str) else _canonical_json(selected).decode()
    raise _SelectionError(f"unsupported selector kind: {kind}")


_WORDS = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_NEGATIONS = {"no", "not", "never", "without", "cannot", "can't", "isn't", "doesn't"}
_STOP = {"a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "of", "to", "that"}


def _tokens(text: str) -> set[str]:
    return {word for word in _WORDS.findall(text.casefold()) if word not in _STOP | _NEGATIONS}


def _support(claim: str, evidence: str, claim_type: str, subject: str) -> tuple[str, str]:
    left = unicodedata.normalize("NFC", " ".join(claim.casefold().split()))
    right = unicodedata.normalize("NFC", " ".join(evidence.casefold().split()))
    if not left:
        return NOT_ASSESSED, "no claim text was supplied"
    overlap = len(_tokens(left) & _tokens(right)) / max(1, min(len(_tokens(left)), len(_tokens(right))))
    left_neg = bool(set(_WORDS.findall(left)) & _NEGATIONS)
    right_neg = bool(set(_WORDS.findall(right)) & _NEGATIONS)
    if left_neg != right_neg and overlap >= 0.75:
        return CONTRADICTS, "selected evidence has opposite polarity to the claim"
    if left != right:
        return INSUFFICIENT, "deterministic verifier requires an exact normalized claim/evidence match"
    claim_tokens, subject_tokens = _tokens(claim), _tokens(subject)
    critical = {token for token in subject_tokens if is_critical_text(token)}
    if critical - claim_tokens or (subject_tokens and not claim_tokens & subject_tokens):
        return INSUFFICIENT, "claim subject is not grounded in the selected evidence text"
    if claim_type == "security_claim" and not subject_tokens and not is_critical_text(claim):
        return INSUFFICIENT, "critical claim lacks self-contained subject context"
    return SUPPORTS, "selected evidence exactly matches the normalized claim text"


def _build(
    request: EvidenceRequest,
    policy: AdapterPolicy | None,
    material: RetrievedArtifact | None,
    *,
    retrieved_at: str = "",
    raw_hash: str = "",
    normalized_hash: str = "",
    selector_kind: str = "",
    selector_value: str = "",
    selected: str = "",
    status: str,
    reason: str,
) -> EvidenceAttestation:
    payload: dict[str, Any] = {
        "schema_version": _SCHEMA,
        "adapter_id": policy.adapter_id if policy else request.adapter_id or "unresolved_request",
        "adapter_version": policy.adapter_version if policy else "",
        "retrieval_mechanism": policy.retrieval_mechanism if policy else "",
        "parser_identity": policy.parser_identity if policy else "",
        "policy_sha256": policy.digest if policy else _hash_record({"unresolved": True}),
        "requested_locator": request.locator,
        "final_locator": material.final_locator if material else "",
        "source_kind": policy.source_kind if policy else "unverified",
        "trust_tier": policy.trust_tier if policy else T4_MODEL,
        "retrieved_at": retrieved_at,
        "freshness_required": policy.freshness_required if policy else False,
        "media_type": material.media_type if material else "",
        "canonicalization": _CANON,
        "raw_content_sha256": raw_hash,
        "normalized_content_sha256": normalized_hash,
        "selector_kind": selector_kind,
        "selector_value": selector_value,
        "selected_text": selected,
        "selected_sha256": _sha(selected) if selected else "",
        "status": status,
        "failure_reason": reason,
    }
    attestation_id = f"att-{_hash_record(payload)[:24]}"
    record = {"attestation_id": attestation_id, **payload}
    return EvidenceAttestation(**record, record_sha256=_hash_record(record))


def _failed(
    request: EvidenceRequest,
    policy: AdapterPolicy | None,
    status: str,
    reason: str,
) -> EvidenceAttestation:
    kind = (
        "quoted_span"
        if request.quoted_span is not None
        else "json_pointer"
        if request.json_pointer is not None
        else ""
    )
    value = request.quoted_span if request.quoted_span is not None else request.json_pointer or ""
    return _build(
        request,
        policy,
        None,
        selector_kind=kind,
        selector_value=value,
        status=status,
        reason=reason,
    )


def _assessment(
    evidence: EvidenceAttestation,
    relation: str,
    reason: str,
    claim: str,
    claim_type: str,
    subject: str,
    stance: str,
) -> SupportAssessment:
    payload = {
        "schema_version": _SCHEMA,
        "claim_sha256": claim_digest(
            claim,
            claim_type=claim_type,
            claim_subject=subject,
            claim_stance=stance,
        ),
        "claim_type": claim_type,
        "claim_subject": subject,
        "claim_stance": stance,
        "attestation_id": evidence.attestation_id,
        "attestation_record_sha256": evidence.record_sha256,
        "relation": relation,
        "verifier_id": "evalopt.lexical_support",
        "verifier_version": "2",
        "reason": reason,
    }
    assessment_id = f"sup-{_hash_record(payload)[:24]}"
    record = {"assessment_id": assessment_id, **payload}
    return SupportAssessment(**record, record_sha256=_hash_record(record))


def _issue_material(
    policy: AdapterPolicy,
    request: EvidenceRequest,
    material: RetrievedArtifact,
    *,
    observed_at: str,
    claim_text: str,
    claim_type: str = "",
    claim_subject: str = "",
    claim_stance: str = "",
) -> tuple[EvidenceAttestation, SupportAssessment]:
    """Issue deterministic records from material already retrieved by a host."""
    if not isinstance(material, RetrievedArtifact):
        evidence = _failed(request, policy, FAILED, "host supplied invalid evidence material")
    else:
        retrieved_at = material.retrieved_at or observed_at
        retrieved, observed = _timestamp(retrieved_at), _timestamp(observed_at)
        if len(material.content) > policy.max_bytes:
            evidence = _failed(request, policy, BLOCKED, "retrieved content exceeds the byte limit")
        elif observed is None or retrieved is None or retrieved > observed:
            evidence = _failed(request, policy, FAILED, "retrieval timestamp is invalid or in the future")
        elif request.expected_sha256 and request.expected_sha256.casefold() != _sha(material.content):
            evidence = _failed(
                request,
                policy,
                FAILED,
                "retrieved content hash does not match expected hash",
            )
        elif request.expected_final_locator and request.expected_final_locator != material.final_locator:
            evidence = _failed(
                request,
                policy,
                FAILED,
                "retrieved final locator does not match expected locator",
            )
        elif (request.quoted_span is None) == (request.json_pointer is None):
            evidence = _failed(
                request,
                policy,
                UNSUPPORTED,
                "exactly one quoted span or JSON pointer selector is required",
            )
        else:
            try:
                text, normalized = _normalize(material.content)
                kind = "quoted_span" if request.quoted_span is not None else "json_pointer"
                value = request.quoted_span if request.quoted_span is not None else request.json_pointer or ""
                selected = _select(text, material.content, kind, value)
            except _SelectionError as exc:
                evidence = _failed(request, policy, UNSUPPORTED, str(exc))
            except Exception as exc:
                evidence = _failed(request, policy, FAILED, f"selector parser failed: {exc}")
            else:
                if not selected:
                    evidence = _failed(
                        request,
                        policy,
                        UNSUPPORTED,
                        "selector resolved to an empty value",
                    )
                elif len(selected.encode()) > policy.max_selected_bytes:
                    evidence = _failed(
                        request,
                        policy,
                        BLOCKED,
                        "selected evidence exceeds the byte limit",
                    )
                else:
                    evidence = _build(
                        request,
                        policy,
                        material,
                        retrieved_at=retrieved_at,
                        raw_hash=_sha(material.content),
                        normalized_hash=_sha(normalized),
                        selector_kind=kind,
                        selector_value=value,
                        selected=selected,
                        status=VERIFIED,
                        reason="",
                    )
    relation, reason = (
        _support(claim_text, evidence.selected_text, claim_type, claim_subject)
        if evidence.status == VERIFIED
        else (NOT_ASSESSED, f"attestation status is {evidence.status}")
    )
    return evidence, _assessment(
        evidence,
        relation,
        reason,
        claim_text,
        claim_type,
        claim_subject,
        claim_stance,
    )


def _issue_failure(
    request: EvidenceRequest,
    *,
    claim_text: str,
    status: str,
    reason: str,
    claim_type: str = "",
    claim_subject: str = "",
    claim_stance: str = "",
) -> tuple[EvidenceAttestation, SupportAssessment]:
    evidence = _failed(request, None, status, reason)
    assessment = _assessment(
        evidence,
        NOT_ASSESSED,
        f"attestation status is {status}",
        claim_text,
        claim_type,
        claim_subject,
        claim_stance,
    )
    return evidence, assessment


def _revalidate_material(
    policy: AdapterPolicy,
    evidence: EvidenceAttestation,
    material: RetrievedArtifact,
) -> tuple[bool, str, str]:
    if evidence.status != VERIFIED or not evidence.validate_record_hash():
        return False, FAILED, "attestation is not a valid verified record"
    if evidence.policy_sha256 != policy.digest:
        return False, FAILED, "adapter policy no longer matches attestation"
    derived = (
        evidence.adapter_id,
        evidence.adapter_version,
        evidence.source_kind,
        evidence.trust_tier,
        evidence.retrieval_mechanism,
        evidence.parser_identity,
        evidence.freshness_required,
    )
    expected = (
        policy.adapter_id,
        policy.adapter_version,
        policy.source_kind,
        policy.trust_tier,
        policy.retrieval_mechanism,
        policy.parser_identity,
        policy.freshness_required,
    )
    if derived != expected:
        return False, FAILED, "adapter policy fields do not match attestation"
    try:
        text, normalized = _normalize(material.content)
        selected = _select(
            text,
            material.content,
            evidence.selector_kind,
            evidence.selector_value,
        )
    except Exception as exc:
        return False, FAILED, f"content cannot be reselected: {exc}"
    same = (
        len(material.content) <= policy.max_bytes
        and material.final_locator == evidence.final_locator
        and material.media_type == evidence.media_type
        and (not material.retrieved_at or material.retrieved_at == evidence.retrieved_at)
        and _sha(material.content) == evidence.raw_content_sha256
        and _sha(normalized) == evidence.normalized_content_sha256
        and selected == evidence.selected_text
        and _sha(selected) == evidence.selected_sha256
    )
    if same:
        return True, VERIFIED, "attestation content and policy revalidated"
    return False, FAILED, "retrieved content or locator changed"


_COMPATIBILITY_ADAPTERS = {
    "AttestationValidation",
    "DeterministicToolAdapter",
    "EvidenceAdapter",
    "EvidenceAuthority",
    "EvidenceResult",
    "LocalFileAdapter",
    "RecordedEvidenceAdapter",
}


def __getattr__(name: str):
    if name not in _COMPATIBILITY_ADAPTERS:
        raise AttributeError(name)
    from . import evidence_adapters

    value = getattr(evidence_adapters, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_COMPATIBILITY_ADAPTERS})


__all__ = [
    "AdapterPolicy",
    "EvidenceAttestation",
    "EvidenceRequest",
    "RetrievedArtifact",
    "SupportAssessment",
    "claim_digest",
]
