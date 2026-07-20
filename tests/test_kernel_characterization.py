"""Frozen behavior contract for the pre-reduction evidence boundary."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import pytest

from evalopt_graph import epistemic
from evalopt_graph.attestation import (
    AdapterPolicy,
    DeterministicToolAdapter,
    EvidenceAttestation,
    EvidenceAuthority,
    EvidenceRequest,
    LocalFileAdapter,
    RecordedEvidenceAdapter,
    RetrievedArtifact,
    SupportAssessment,
)

NOW = "2026-07-11T12:00:00+00:00"
CLAIM = "The bounded evidence contract is active."
LOCATOR = "recorded://contract"


def _policy(**changes: object) -> AdapterPolicy:
    values = {
        "adapter_id": "recorded-contract",
        "adapter_version": "1",
        "source_kind": "official_docs",
        "trust_tier": epistemic.T2_OFFICIAL,
        "retrieval_mechanism": "recorded_contract",
        "parser_identity": "text/plain@1",
        "freshness_required": True,
    }
    values.update(changes)
    return AdapterPolicy(**values)


def _artifact(text: str = CLAIM, **changes: object) -> RetrievedArtifact:
    values = {
        "content": text.encode(),
        "final_locator": LOCATOR,
        "retrieved_at": NOW,
        "media_type": "text/plain",
    }
    values.update(changes)
    return RetrievedArtifact(**values)


def _authority(artifact: RetrievedArtifact | None = None) -> EvidenceAuthority:
    policy = _policy()
    material = artifact or _artifact()
    return EvidenceAuthority(
        [RecordedEvidenceAdapter(policy, {LOCATOR: material})],
        now=lambda: NOW,
    )


@pytest.mark.parametrize(
    ("changes", "status"),
    [
        ({"expected_sha256": "0" * 64}, "FAILED"),
        ({"expected_final_locator": "recorded://other"}, "FAILED"),
        ({"quoted_span": "missing"}, "UNSUPPORTED"),
        ({"quoted_span": None, "json_pointer": None}, "UNSUPPORTED"),
    ],
)
def test_failure_matrix_remains_distinct(changes: dict[str, object], status: str):
    request = {
        "adapter_id": "recorded-contract",
        "locator": LOCATOR,
        "quoted_span": CLAIM,
    }
    request.update(changes)

    result = _authority().attest(EvidenceRequest.from_dict(request), claim_text=CLAIM)

    assert result.attestation.status == status
    assert result.support_assessment.relation == "NOT_ASSESSED"
    assert result.attestation.validate_record_hash()
    assert result.support_assessment.validate_record_hash()


def test_model_dictionary_cannot_assign_authority_fields():
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "recorded-contract",
            "locator": LOCATOR,
            "quoted_span": CLAIM,
            "source_kind": "test_output",
            "trust_tier": epistemic.T0_DETERMINISTIC,
            "retrieved_at": "2999-01-01T00:00:00+00:00",
            "verification_state": "VERIFIED",
            "confirmation": True,
            "content_sha256": "f" * 64,
        }
    )

    result = _authority().attest(request, claim_text=CLAIM)

    assert set(request.to_dict()) == {
        "adapter_id",
        "locator",
        "quoted_span",
        "json_pointer",
        "expected_sha256",
        "expected_final_locator",
    }
    assert result.attestation.source_kind == "official_docs"
    assert result.attestation.trust_tier == epistemic.T2_OFFICIAL
    assert result.attestation.retrieved_at == NOW
    assert result.attestation.status == "VERIFIED"


def test_policy_and_registration_are_frozen_before_retrieval():
    class MutableAdapter:
        def __init__(self) -> None:
            self.policy = _policy()

        def retrieve(self, locator: str) -> RetrievedArtifact:
            return _artifact(final_locator=locator)

    adapter = MutableAdapter()
    authority = EvidenceAuthority([adapter], now=lambda: NOW)
    snapshot = authority.snapshot()
    adapter.policy = _policy(source_kind="mcp_result", trust_tier=epistemic.T0_DETERMINISTIC)
    authority.register(
        RecordedEvidenceAdapter(
            _policy(adapter_id="late-registration"),
            {LOCATOR: _artifact()},
        )
    )

    result = snapshot.attest(
        EvidenceRequest("recorded-contract", LOCATOR, quoted_span=CLAIM),
        claim_text=CLAIM,
    )

    assert result.attestation.source_kind == "official_docs"
    assert result.attestation.trust_tier == epistemic.T2_OFFICIAL
    assert snapshot.has_adapter("late-registration") is False


def test_serialization_and_hash_replay_are_deterministic():
    result = _authority().attest(
        EvidenceRequest("recorded-contract", LOCATOR, quoted_span=CLAIM),
        claim_text=CLAIM,
        claim_type="research_claim",
        claim_subject="contract",
    )

    attestation = EvidenceAttestation.from_dict(result.attestation.to_dict())
    assessment = SupportAssessment.from_dict(result.support_assessment.to_dict())

    assert attestation == result.attestation
    assert assessment == result.support_assessment
    assert attestation.validate_record_hash()
    assert assessment.validate_record_hash()
    assert replace(attestation, status="FAILED").validate_record_hash() is False


def test_valid_local_and_deterministic_material_remain_accepted(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text(CLAIM + "\n")
    local = EvidenceAuthority([LocalFileAdapter(tmp_path)], now=lambda: NOW).attest(
        EvidenceRequest("local_file", "evidence.txt", quoted_span=CLAIM),
        claim_text=CLAIM,
    )
    tool_locator = "tool://contract"
    material = _artifact(final_locator=tool_locator)
    deterministic = EvidenceAuthority(
        [DeterministicToolAdapter({tool_locator: material})], now=lambda: NOW
    ).attest(
        EvidenceRequest("deterministic_tool", tool_locator, quoted_span=CLAIM),
        claim_text=CLAIM,
    )

    assert local.attestation.status == deterministic.attestation.status == "VERIFIED"
    assert local.support_assessment.relation == deterministic.support_assessment.relation == "SUPPORTS"
    assert local.attestation.raw_content_sha256 == sha256((CLAIM + "\n").encode()).hexdigest()
    assert deterministic.attestation.trust_tier == epistemic.T0_DETERMINISTIC
