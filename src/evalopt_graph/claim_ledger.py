"""Compatibility claim ledger; stable acceptance lives in :mod:`evalopt_graph.kernel`."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

from . import epistemic
from .attestation import EvidenceAttestation, SupportAssessment, claim_digest
from .epistemic import Claim, Source

_FILES = (
    "claims.jsonl",
    "sources.jsonl",
    "attestations.jsonl",
    "support_assessments.jsonl",
    "assumptions.jsonl",
    "contradictions.jsonl",
    "decisions.jsonl",
)


class ClaimLedger:
    """Folded legacy view over append-only JSONL records."""

    def __init__(self, knowledge_dir: str | None = None, now: Callable[[], str] | None = None) -> None:
        self._claims: dict[str, Claim] = {}
        self._sources: dict[str, Source] = {}
        self._attestations: dict[str, EvidenceAttestation] = {}
        self._support_assessments: dict[str, SupportAssessment] = {}
        self._contradictions: list[dict[str, Any]] = []
        self._decisions: list[dict[str, Any]] = []
        self.knowledge_dir, self._now = knowledge_dir, now or epistemic.now_iso
        self._cseq = self._sseq = 0
        if knowledge_dir:
            Path(knowledge_dir).mkdir(parents=True, exist_ok=True)
            for name in _FILES:
                try:
                    (Path(knowledge_dir) / name).touch(exist_ok=True)
                except OSError:
                    pass
            self._cseq = _max_records(_read(knowledge_dir, "claims.jsonl"), "c")
            self._sseq = _max_records(_read(knowledge_dir, "sources.jsonl"), "s")

    def _id(self, kind: str) -> str:
        if kind == "c":
            self._cseq += 1
            return f"c{self._cseq}"
        self._sseq += 1
        return f"s{self._sseq}"

    def _append(self, filename: str, record: dict[str, Any], *, required: bool = False) -> None:
        if not self.knowledge_dir:
            return
        try:
            with open(Path(self.knowledge_dir) / filename, "a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(record, sort_keys=required, separators=(",", ":") if required else None) + "\n"
                )
                if required:
                    handle.flush()
                    os.fsync(handle.fileno())
        except Exception as exc:
            if required:
                raise RuntimeError(f"required evidence persistence failed for {filename}: {exc}") from exc

    def add_attestation(self, value: EvidenceAttestation) -> EvidenceAttestation:
        _valid_attestation(value)
        prior = self._attestations.get(value.attestation_id)
        if prior is not None:
            if prior != value:
                raise ValueError(f"conflicting immutable attestation id: {value.attestation_id}")
            return prior
        self._append("attestations.jsonl", value.to_dict(), required=True)
        self._attestations[value.attestation_id] = value
        return value

    def add_support_assessment(self, value: SupportAssessment) -> SupportAssessment:
        _valid_assessment(value)
        _valid_link(value, self._attestations)
        prior = self._support_assessments.get(value.assessment_id)
        if prior is not None:
            if prior != value:
                raise ValueError(f"conflicting immutable support assessment id: {value.assessment_id}")
            return prior
        self._append("support_assessments.jsonl", value.to_dict(), required=True)
        self._support_assessments[value.assessment_id] = value
        return value

    def get_attestation(self, record_id: str) -> EvidenceAttestation | None:
        return self._attestations.get(record_id)

    def get_support_assessment(self, record_id: str) -> SupportAssessment | None:
        return self._support_assessments.get(record_id)

    def add_source(
        self,
        *,
        kind: str = "local_file",
        locator: str = "",
        summary: str = "",
        quoted_span_or_hash: str = "",
        trust_tier: str | None = None,
        freshness_required: bool = False,
        retrieved_at: str | None = None,
        attestation_id: str = "",
        attestation_status: str = "",
        support_assessment_id: str = "",
        support_relation: str = "",
    ) -> Source:
        source = Source(
            id=self._id("s"),
            kind=kind,
            locator=locator,
            retrieved_at=self._now() if retrieved_at is None else retrieved_at,
            freshness_required=freshness_required,
            trust_tier=trust_tier or epistemic.default_trust_for_kind(kind),
            summary=summary,
            quoted_span_or_hash=quoted_span_or_hash,
            attestation_id=attestation_id,
            attestation_status=attestation_status,
            support_assessment_id=support_assessment_id,
            support_relation=support_relation,
        )
        self._validate_source_bindings(source)
        self._append(
            "sources.jsonl", source.to_dict(), required=bool(attestation_id or support_assessment_id)
        )
        self._sources[source.id] = source
        return source

    def update_source(self, source_id: str, **changes: Any) -> Source | None:
        source = self._sources.get(source_id)
        if source is None:
            return None
        allowed = set(Source.__dataclass_fields__) - {"id"}
        candidate = replace(source, **{key: value for key, value in changes.items() if key in allowed})
        if source.attestation_id and (
            candidate.attestation_id != source.attestation_id
            or candidate.support_assessment_id != source.support_assessment_id
        ):
            raise ValueError("immutable evidence bindings cannot be removed or replaced")
        self._validate_source_bindings(candidate)
        self._append(
            "sources.jsonl",
            candidate.to_dict(),
            required=bool(candidate.attestation_id or candidate.support_assessment_id),
        )
        self._sources[source_id] = candidate
        return candidate

    def _validate_source_bindings(self, source: Source) -> None:
        if source.support_assessment_id and not source.attestation_id:
            raise ValueError("support assessment link requires an attestation id")
        if not source.attestation_id:
            return
        evidence = self._attestations.get(source.attestation_id)
        if evidence is None:
            raise ValueError(f"source references unknown attestation {source.attestation_id}")
        expected = {
            "kind": evidence.source_kind,
            "locator": evidence.final_locator,
            "retrieved_at": evidence.retrieved_at,
            "trust_tier": evidence.trust_tier,
        }
        if any(getattr(source, key) != value for key, value in expected.items()):
            raise ValueError(f"source projection does not match attestation {source.attestation_id}")
        allowed = {evidence.status} | (
            {"UNVERIFIED", "UNSUPPORTED", "FAILED", "BLOCKED"} if evidence.status == "VERIFIED" else set()
        )
        if source.attestation_status not in allowed:
            raise ValueError("source attestation_status does not safely derive from its attestation")
        if not source.support_assessment_id:
            if source.support_relation:
                raise ValueError("support relation requires a support assessment id")
            return
        assessment = self._support_assessments.get(source.support_assessment_id)
        if assessment is None or assessment.attestation_id != source.attestation_id:
            raise ValueError("source references an unknown or mismatched support assessment")
        relation = assessment.relation if source.attestation_status == evidence.status else "NOT_ASSESSED"
        if source.support_relation != relation:
            raise ValueError("source support relation does not match its immutable assessment")

    def add_claim(
        self,
        text: str,
        *,
        type: str = "model_inference",
        source_type: str = "claude_inference",
        evidence_refs: list[str] | None = None,
        status: str = epistemic.STATUS_UNVERIFIED,
        confidence: float = 0.0,
        created_by: str = "",
        subject: str = "",
        stance: str = "",
        central: bool = False,
        expires_at: str | None = None,
        notes: str = "",
    ) -> Claim:
        if status == epistemic.STATUS_UNVERIFIED and source_type == "user":
            status = epistemic.STATUS_CONFIRMED
        claim = Claim(
            id=self._id("c"),
            text=text,
            type=type,
            source_type=source_type,
            evidence_refs=list(evidence_refs or []),
            confidence=confidence,
            status=status,
            created_by=created_by,
            created_at=self._now(),
            subject=subject,
            stance=stance,
            central=central,
            expires_at=expires_at,
            notes=notes,
        )
        self._append("claims.jsonl", claim.to_dict(), required=True)
        self._claims[claim.id] = claim
        if type == "assumption":
            self._append("assumptions.jsonl", claim.to_dict())
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        return self._claims.get(claim_id)

    def get_source(self, source_id: str) -> Source | None:
        return self._sources.get(source_id)

    def update_claim(self, claim_id: str, **changes: Any) -> Claim | None:
        claim = self._claims.get(claim_id)
        if claim is None:
            return None
        allowed = set(Claim.__dataclass_fields__) - {"id"}
        candidate = replace(claim, **{key: value for key, value in changes.items() if key in allowed})
        self._append("claims.jsonl", candidate.to_dict(), required=True)
        self._claims[claim_id] = candidate
        return candidate

    def set_status(
        self,
        claim_id: str,
        status: str,
        *,
        verified_by: str | None = None,
        notes: str | None = None,
    ) -> Claim | None:
        claim = self._claims.get(claim_id)
        if claim is None:
            return None
        next_notes = claim.notes if notes is None else notes
        if status == epistemic.STATUS_CONFIRMED and epistemic.self_certifies(claim, verified_by or ""):
            note = "self-certification rejected (creator == verifier; needs an independent verifier)"
            candidate = replace(claim, notes=f"{next_notes} | {note}" if next_notes else note)
        else:
            verified = list(claim.verified_by)
            if verified_by and verified_by not in verified:
                verified.append(verified_by)
            candidate = replace(claim, status=status, notes=next_notes, verified_by=verified)
        self._append("claims.jsonl", candidate.to_dict(), required=True)
        self._claims[claim_id] = candidate
        return candidate

    def supersede(self, claim_id: str, by: str = "") -> None:
        self.set_status(claim_id, epistemic.STATUS_SUPERSEDED, verified_by=by)

    def add_contradiction(self, record: dict[str, Any]) -> None:
        self._append("contradictions.jsonl", record, required=True)
        self._contradictions.append(record)

    def add_decision(self, record: dict[str, Any]) -> None:
        self._append("decisions.jsonl", record, required=True)
        self._decisions.append(record)

    @property
    def sources(self) -> dict[str, Source]:
        return self._sources

    @property
    def attestations(self) -> dict[str, EvidenceAttestation]:
        return self._attestations

    @property
    def support_assessments(self) -> dict[str, SupportAssessment]:
        return self._support_assessments

    def claims(self) -> list[Claim]:
        return list(self._claims.values())

    def usable_claims(self, now: str | None = None) -> list[Claim]:
        return [claim for claim in self._claims.values() if epistemic.is_usable(claim, now)]

    def claims_by_type(self, claim_type: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.type == claim_type]

    def claims_by_status(self, status: str) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.status == status]

    def assumptions(self) -> list[Claim]:
        return self.claims_by_type("assumption")

    def central_claims(self) -> list[Claim]:
        return [claim for claim in self._claims.values() if claim.central]

    def promote_centrality(self, acceptance_criteria=(), *, extra_texts=()) -> list[str]:
        promoted: list[str] = []
        for claim in list(self._claims.values()):
            reasons = epistemic.derive_centrality(claim, acceptance_criteria, extra_texts=extra_texts)
            if reasons:
                changes: dict[str, Any] = {"centrality_policy_reasons": reasons}
                if not claim.central:
                    changes["central"] = True
                    promoted.append(claim.id)
                self.update_claim(claim.id, **changes)
        return promoted

    def premises_for(self, agent: str, now: str | None = None) -> list[Claim]:
        claims = self.usable_claims(now)
        for claim in claims:
            if agent and agent not in claim.used_by:
                claim.used_by.append(agent)
        return claims

    def snapshot(self) -> dict[str, Any]:
        return {
            "claims": [item.to_dict() for item in self._claims.values()],
            "sources": [item.to_dict() for item in self._sources.values()],
            "attestations": [item.to_dict() for item in self._attestations.values()],
            "support_assessments": [item.to_dict() for item in self._support_assessments.values()],
            "contradictions": list(self._contradictions),
            "decisions": list(self._decisions),
            "seq": {"claim": self._cseq, "source": self._sseq},
        }

    @classmethod
    def from_snapshot(
        cls,
        snap: dict[str, Any] | None,
        *,
        knowledge_dir: str | None = None,
        now: Callable[[], str] | None = None,
    ) -> ClaimLedger:
        ledger = cls(knowledge_dir=knowledge_dir, now=now)
        disk = ledger._cseq, ledger._sseq
        ledger._restore(snap or {})
        seq = (snap or {}).get("seq", {})
        ledger._cseq = max(disk[0], int(seq.get("claim", 0)), _max(ledger._claims, "c"))
        ledger._sseq = max(disk[1], int(seq.get("source", 0)), _max(ledger._sources, "s"))
        return ledger

    @classmethod
    def load(cls, knowledge_dir: str) -> ClaimLedger:
        ledger = cls()
        ledger._restore(
            {
                "attestations": _read(knowledge_dir, "attestations.jsonl"),
                "support_assessments": _read(knowledge_dir, "support_assessments.jsonl"),
                "sources": _read(knowledge_dir, "sources.jsonl"),
                "claims": _read(knowledge_dir, "claims.jsonl"),
                "contradictions": _read(knowledge_dir, "contradictions.jsonl"),
                "decisions": _read(knowledge_dir, "decisions.jsonl"),
            }
        )
        ledger._cseq, ledger._sseq = _max(ledger._claims, "c"), _max(ledger._sources, "s")
        ledger.knowledge_dir = knowledge_dir
        return ledger

    def _restore(self, data: dict[str, Any]) -> None:
        for record in data.get("attestations", []):
            value = EvidenceAttestation.from_dict(record)
            _valid_attestation(value)
            _insert(self._attestations, value.attestation_id, value, "attestation")
        for record in data.get("support_assessments", []):
            value = SupportAssessment.from_dict(record)
            _valid_assessment(value)
            _valid_link(value, self._attestations)
            _insert(self._support_assessments, value.assessment_id, value, "support assessment")
        for record in data.get("sources", []):
            source = _source_from_record(record)
            self._validate_source_bindings(source)
            self._sources[source.id] = source
        for record in data.get("claims", []):
            claim = _claim_from_record(record, self._sources, self._support_assessments)
            self._claims[claim.id] = claim
        self._contradictions = list(data.get("contradictions", []))
        self._decisions = list(data.get("decisions", []))


def _source_from_record(record: dict[str, Any]) -> Source:
    source = Source.from_dict(record)
    binding = (
        source.attestation_id,
        source.attestation_status,
        source.support_assessment_id,
        source.support_relation,
    )
    if source.kind in {"controller_test_output", "controller_command_output"}:
        return source
    if not any(binding) and source.trust_tier != epistemic.T4_MODEL:
        return replace(
            source,
            kind="legacy_unattested_snapshot",
            trust_tier=epistemic.T4_MODEL,
            freshness_required=False,
            attestation_status="UNVERIFIED",
            support_relation="NOT_ASSESSED",
        )
    return source


def _claim_from_record(
    record: dict[str, Any],
    sources: dict[str, Source],
    assessments: dict[str, SupportAssessment],
) -> Claim:
    claim = Claim.from_dict(record)
    if claim.status != epistemic.STATUS_CONFIRMED or claim.source_type == "user":
        return claim
    if claim.created_by == "verification" and any(
        (source := sources.get(source_id))
        and source.trust_tier == epistemic.T0_DETERMINISTIC
        and source.kind in {"controller_test_output", "controller_command_output"}
        for source_id in claim.evidence_refs
    ):
        return claim
    expected = claim_digest(
        claim.text,
        claim_type=claim.type,
        claim_subject=claim.subject,
        claim_stance=claim.stance,
    )
    for source_id in claim.evidence_refs:
        source = sources.get(source_id)
        assessment = assessments.get(source.support_assessment_id) if source else None
        if (
            source
            and assessment
            and source.attestation_status == "VERIFIED"
            and source.support_relation == "SUPPORTS"
            and assessment.claim_sha256 == expected
        ):
            return claim
    note = "serialized non-user confirmation downgraded pending attested re-verification"
    return replace(
        claim,
        status=epistemic.STATUS_UNVERIFIED,
        notes=f"{claim.notes} | {note}" if claim.notes else note,
    )


def _max(items: Mapping[str, Any], prefix: str) -> int:
    values = []
    for key in items:
        try:
            values.append(int(key[len(prefix) :])) if key.startswith(prefix) else None
        except ValueError:
            pass
    return max(values, default=0)


def _max_records(records: Iterable[dict[str, Any]], prefix: str) -> int:
    return _max({str(record.get("id", "")): None for record in records}, prefix)


def _valid_attestation(value: EvidenceAttestation) -> None:
    if not value.validate_record_hash():
        raise ValueError(f"attestation record hash mismatch: {value.attestation_id}")


def _valid_assessment(value: SupportAssessment) -> None:
    if not value.validate_record_hash():
        raise ValueError(f"support assessment record hash mismatch: {value.assessment_id}")


def _valid_link(value: SupportAssessment, evidence: dict[str, EvidenceAttestation]) -> None:
    attestation = evidence.get(value.attestation_id)
    if attestation is None:
        raise ValueError(f"support assessment {value.assessment_id} references unknown attestation")
    if value.attestation_record_sha256 != attestation.record_sha256:
        raise ValueError(f"support assessment {value.assessment_id} references a mismatched attestation hash")


def _insert(store: dict[str, Any], key: str, value: Any, label: str) -> None:
    if key in store and store[key] != value:
        raise ValueError(f"conflicting immutable {label} id: {key}")
    store[key] = value


def _read(directory: str, filename: str) -> list[dict[str, Any]]:
    path = Path(directory) / filename
    if not path.is_file():
        return []
    records = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except Exception as exc:
                    raise ValueError(f"invalid {filename} JSON at line {line_number}: {exc}") from exc
                if not isinstance(record, dict):
                    raise ValueError(f"invalid {filename} record at line {line_number}: expected object")
                records.append(record)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError(f"cannot read required evidence history {filename}: {exc}") from exc
    return records
