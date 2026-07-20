"""Ledger and trust-policy regressions for attested evidence."""

from __future__ import annotations

import json

import pytest

from evalopt_graph import attestation, epistemic
from evalopt_graph.attestation import (
    AdapterPolicy,
    EvidenceAuthority,
    EvidenceRequest,
    RecordedEvidenceAdapter,
    RetrievedArtifact,
)
from evalopt_graph.claim_ledger import ClaimLedger
from evalopt_graph.source_verification import verify_claim, verify_ledger

NOW = "2026-07-11T12:00:00+00:00"


def _attested_result(*, subject: str = ""):
    policy = AdapterPolicy(
        adapter_id="recorded-primary",
        adapter_version="1",
        source_kind="official_docs",
        trust_tier=epistemic.T2_OFFICIAL,
        retrieval_mechanism="recorded_tool_result",
        parser_identity="text/plain@1",
        freshness_required=False,
    )
    adapter = RecordedEvidenceAdapter(
        policy,
        {
            "docs://one": RetrievedArtifact(
                content=b"The retry budget is bounded.",
                final_locator="docs://one",
                retrieved_at=NOW,
                media_type="text/plain",
            )
        },
    )
    authority = EvidenceAuthority([adapter], now=lambda: NOW)
    return authority.attest(
        EvidenceRequest(
            adapter_id="recorded-primary",
            locator="docs://one",
            quoted_span="The retry budget is bounded.",
        ),
        claim_text="The retry budget is bounded.",
        claim_type="research_claim",
        claim_subject=subject,
    )


def test_attestation_and_support_assessment_roundtrip_through_snapshot_and_jsonl(tmp_path):
    result = _attested_result()
    assert result.attestation.status == "VERIFIED"
    assert result.support_assessment.relation == "SUPPORTS"

    knowledge = str(tmp_path / "knowledge")
    ledger = ClaimLedger(knowledge_dir=knowledge, now=lambda: NOW)
    ledger.add_attestation(result.attestation)
    ledger.add_support_assessment(result.support_assessment)
    source = ledger.add_source(
        kind=result.attestation.source_kind,
        locator=result.attestation.final_locator,
        summary=result.attestation.selected_text,
        quoted_span_or_hash=result.attestation.selected_sha256,
        trust_tier=result.attestation.trust_tier,
        retrieved_at=result.attestation.retrieved_at,
        attestation_id=result.attestation.attestation_id,
        attestation_status=result.attestation.status,
        support_assessment_id=result.support_assessment.assessment_id,
        support_relation=result.support_assessment.relation,
    )
    claim = ledger.add_claim(
        "The retry budget is bounded.",
        type="research_claim",
        source_type="official_docs",
        evidence_refs=[source.id],
        created_by="researcher",
    )

    snap = ledger.snapshot()
    restored = ClaimLedger.from_snapshot(snap)
    loaded = ClaimLedger.load(knowledge)
    for candidate in (restored, loaded):
        assert candidate.get_attestation(result.attestation.attestation_id) == result.attestation
        assert candidate.get_support_assessment(result.support_assessment.assessment_id) == (
            result.support_assessment
        )
        assert candidate.get_claim(claim.id) is not None


def test_tampered_attestation_history_fails_closed(tmp_path):
    result = _attested_result()
    knowledge = str(tmp_path / "knowledge")
    ledger = ClaimLedger(knowledge_dir=knowledge)
    ledger.add_attestation(result.attestation)

    path = tmp_path / "knowledge" / "attestations.jsonl"
    record = json.loads(path.read_text().splitlines()[0])
    record["selected_text"] = "tampered after attestation"
    path.write_text(json.dumps(record) + "\n")

    with pytest.raises(ValueError, match="attestation.*hash|hash.*attestation"):
        ClaimLedger.load(knowledge)


def test_tampered_support_assessment_history_fails_closed(tmp_path):
    result = _attested_result()
    knowledge = str(tmp_path / "knowledge")
    ledger = ClaimLedger(knowledge_dir=knowledge)
    ledger.add_attestation(result.attestation)
    ledger.add_support_assessment(result.support_assessment)

    path = tmp_path / "knowledge" / "support_assessments.jsonl"
    record = json.loads(path.read_text().splitlines()[0])
    record["relation"] = "SUPPORTS" if record["relation"] != "SUPPORTS" else "CONTRADICTS"
    path.write_text(json.dumps(record) + "\n")

    with pytest.raises(ValueError, match="support assessment.*hash|hash.*support assessment"):
        ClaimLedger.load(knowledge)


def test_recomputed_record_hash_cannot_bypass_attestation_enums():
    result = _attested_result()
    payload = result.attestation.to_dict()
    payload.pop("record_sha256")
    payload.pop("attestation_id")
    payload["status"] = "PRODUCER_VERIFIED"
    attestation_id = f"att-{attestation._hash_record(payload)[:24]}"
    record = {"attestation_id": attestation_id, **payload}
    forged = attestation.EvidenceAttestation(
        **record,
        record_sha256=attestation._hash_record(record),
    )

    with pytest.raises(ValueError, match="attestation record hash mismatch"):
        ClaimLedger().add_attestation(forged)


@pytest.mark.parametrize(
    "changes",
    [
        {"selected_sha256": "0" * 64},
        {"canonicalization": "unknown@999"},
        {"retrieved_at": "not-a-timestamp"},
        {"selector_kind": "regex"},
        {"source_kind": ""},
        {"source_kind": "producer_defined"},
        {"failure_reason": "inconsistent verified record"},
    ],
    ids=[
        "selected-hash",
        "canonicalization",
        "timestamp",
        "selector-kind",
        "empty-source-kind",
        "unknown-source-kind",
        "status-reason",
    ],
)
def test_recomputed_hash_cannot_bypass_attestation_semantic_invariants(changes):
    result = _attested_result()
    payload = result.attestation.to_dict()
    payload.pop("record_sha256")
    payload.pop("attestation_id")
    payload.update(changes)
    attestation_id = f"att-{attestation._hash_record(payload)[:24]}"
    record = {"attestation_id": attestation_id, **payload}
    forged = attestation.EvidenceAttestation(
        **record,
        record_sha256=attestation._hash_record(record),
    )

    assert forged.validate_record_hash() is False
    with pytest.raises(ValueError, match="attestation record hash mismatch"):
        ClaimLedger().add_attestation(forged)


def test_support_assessment_must_bind_the_exact_attestation_record_hash():
    result = _attested_result()
    payload = result.support_assessment.to_dict()
    payload.pop("record_sha256")
    payload.pop("assessment_id")
    payload["attestation_record_sha256"] = "0" * 64
    assessment_id = f"sup-{attestation._hash_record(payload)[:24]}"
    record = {"assessment_id": assessment_id, **payload}
    forged = attestation.SupportAssessment(
        **record,
        record_sha256=attestation._hash_record(record),
    )
    ledger = ClaimLedger()
    ledger.add_attestation(result.attestation)

    with pytest.raises(ValueError, match="mismatched attestation hash"):
        ledger.add_support_assessment(forged)


def test_support_assessment_cannot_be_reused_for_different_claim_text():
    result = _attested_result()
    ledger = ClaimLedger()
    ledger.add_attestation(result.attestation)
    ledger.add_support_assessment(result.support_assessment)
    source = ledger.add_source(
        kind=result.attestation.source_kind,
        locator=result.attestation.final_locator,
        summary=result.attestation.selected_text,
        trust_tier=result.attestation.trust_tier,
        retrieved_at=result.attestation.retrieved_at,
        attestation_id=result.attestation.attestation_id,
        attestation_status=result.attestation.status,
        support_assessment_id=result.support_assessment.assessment_id,
        support_relation=result.support_assessment.relation,
    )
    different = ledger.add_claim(
        "The retry budget is unlimited.",
        type="research_claim",
        evidence_refs=[source.id],
        created_by="researcher",
    )

    status, note = verify_claim(
        different,
        ledger.sources,
        support_assessments_by_id=ledger.support_assessments,
        now=NOW,
    )
    assert status == epistemic.STATUS_UNVERIFIED
    assert "irrelevant" in note


def test_support_assessment_is_bound_to_claim_subject_and_type():
    result = _attested_result(subject="debug logging")
    ledger = ClaimLedger()
    ledger.add_attestation(result.attestation)
    ledger.add_support_assessment(result.support_assessment)
    source = ledger.add_source(
        kind=result.attestation.source_kind,
        locator=result.attestation.final_locator,
        summary=result.attestation.selected_text,
        trust_tier=result.attestation.trust_tier,
        retrieved_at=result.attestation.retrieved_at,
        attestation_id=result.attestation.attestation_id,
        attestation_status=result.attestation.status,
        support_assessment_id=result.support_assessment.assessment_id,
        support_relation=result.support_assessment.relation,
    )
    different_context = ledger.add_claim(
        "The retry budget is bounded.",
        type="security_claim",
        subject="production encryption",
        evidence_refs=[source.id],
        created_by="researcher",
    )

    status, _ = verify_claim(
        different_context,
        ledger.sources,
        support_assessments_by_id=ledger.support_assessments,
        now=NOW,
    )
    assert status == epistemic.STATUS_UNVERIFIED


def test_deserialized_unbound_nonuser_evidence_is_downgraded():
    ledger = ClaimLedger()
    source = ledger.add_source(
        kind="test_output",
        locator="pytest",
        summary="production authentication is safe",
        trust_tier=epistemic.T0_DETERMINISTIC,
    )
    claim = ledger.add_claim(
        "production authentication is safe",
        type="security_claim",
        evidence_refs=[source.id],
        status=epistemic.STATUS_CONFIRMED,
        subject="production-auth",
    )

    restored = ClaimLedger.from_snapshot(ledger.snapshot())
    restored_source = restored.get_source(source.id)
    restored_claim = restored.get_claim(claim.id)
    assert restored_source is not None
    assert restored_source.trust_tier == epistemic.T4_MODEL
    assert restored_source.attestation_status == "UNVERIFIED"
    assert restored_claim is not None
    assert restored_claim.status == epistemic.STATUS_UNVERIFIED


def test_claim_acceptance_is_not_mutated_when_required_persistence_fails(tmp_path):
    knowledge = str(tmp_path / "knowledge")
    ledger = ClaimLedger(knowledge_dir=knowledge)
    claim = ledger.add_claim("claim", created_by="researcher")
    path = tmp_path / "knowledge" / "claims.jsonl"
    path.unlink()
    path.mkdir()

    with pytest.raises(RuntimeError, match="required evidence persistence failed"):
        ledger.set_status(claim.id, epistemic.STATUS_CONFIRMED, verified_by="source_verifier")
    assert claim.status == epistemic.STATUS_UNVERIFIED


def test_new_ledger_in_existing_directory_does_not_reuse_claim_or_source_ids(tmp_path):
    knowledge = str(tmp_path / "knowledge")
    first = ClaimLedger(knowledge_dir=knowledge)
    first_source = first.add_source(kind="local_file", locator="README.md")
    first_claim = first.add_claim("first")

    second = ClaimLedger(knowledge_dir=knowledge)
    second_source = second.add_source(kind="local_file", locator="docs/a.md")
    second_claim = second.add_claim("second")

    assert first_claim.id == "c1"
    assert second_claim.id == "c2"
    assert first_source.id == "s1"
    assert second_source.id == "s2"
    loaded = ClaimLedger.load(knowledge)
    assert {c.text for c in loaded.claims()} == {"first", "second"}


def test_verifier_persists_verified_by_in_the_same_revision(tmp_path):
    knowledge = str(tmp_path / "knowledge")
    ledger = ClaimLedger(knowledge_dir=knowledge, now=lambda: NOW)
    result = _attested_result()
    ledger.add_attestation(result.attestation)
    ledger.add_support_assessment(result.support_assessment)
    source = ledger.add_source(
        kind=result.attestation.source_kind,
        locator=result.attestation.final_locator,
        summary=result.attestation.selected_text,
        trust_tier=result.attestation.trust_tier,
        retrieved_at=result.attestation.retrieved_at,
        attestation_id=result.attestation.attestation_id,
        attestation_status=result.attestation.status,
        support_assessment_id=result.support_assessment.assessment_id,
        support_relation=result.support_assessment.relation,
    )
    claim = ledger.add_claim(
        "The retry budget is bounded.",
        type="research_claim",
        evidence_refs=[source.id],
        created_by="researcher",
    )

    verify_ledger(ledger, now=NOW)
    loaded = ClaimLedger.load(knowledge)
    persisted = loaded.get_claim(claim.id)
    assert persisted is not None
    assert persisted.status == epistemic.STATUS_CONFIRMED
    assert persisted.verified_by == ["source_verifier"]


@pytest.mark.parametrize(
    ("tier", "required"),
    [
        ("not-a-tier", epistemic.T2_OFFICIAL),
        (epistemic.T0_DETERMINISTIC, "not-a-tier"),
        ("not-a-tier", "also-not-a-tier"),
    ],
)
def test_unknown_trust_tiers_fail_closed(tier, required):
    assert epistemic.is_at_least(tier, required) is False


def test_unknown_trust_tier_is_not_counted_as_nonmodel_support():
    source = epistemic.Source(id="s1", trust_tier="unknown")
    claim = epistemic.Claim(id="c1", text="claim", evidence_refs=[source.id])
    assert epistemic.has_nonmodel_support(claim, {source.id: source}) is False
    assert epistemic.best_supporting_trust(claim, {source.id: source}) == epistemic.T4_MODEL


@pytest.mark.parametrize("filename", ["contradictions.jsonl", "decisions.jsonl"])
def test_malformed_governance_history_fails_closed_on_load(tmp_path, filename):
    knowledge = tmp_path / "knowledge"
    knowledge.mkdir()
    (knowledge / filename).write_text("{not-json}\n")

    with pytest.raises(ValueError, match=filename):
        ClaimLedger.load(str(knowledge))
