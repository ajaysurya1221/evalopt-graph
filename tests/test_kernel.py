from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from evalopt_graph import kernel
from evalopt_graph.attestation import AdapterPolicy
from evalopt_graph.epistemic import T2_OFFICIAL

NOW = "2026-07-11T12:00:00+00:00"
TEXT = "The production release is approved."


def _authority():
    policy = AdapterPolicy(
        adapter_id="recorded-docs",
        adapter_version="1",
        source_kind="official_docs",
        trust_tier=T2_OFFICIAL,
        retrieval_mechanism="host_recorded",
        parser_identity="text/plain@1",
        freshness_required=True,
    )
    return kernel.EvidenceAuthority([policy.to_dict()]), policy


def _evidence(*, text=TEXT, retrieved_at=NOW, issued_at=NOW):
    authority, policy = _authority()
    claim = kernel.ClaimRecord(
        id="c1",
        text=text,
        claim_type="security_claim",
        subject="production release",
    )
    attestation, assessment = authority.issue(
        kernel.EvidenceRequest("recorded-docs", "docs://release", quoted_span=text),
        kernel.EvidenceMaterial(text.encode(), "docs://release", retrieved_at, "text/plain"),
        observed_at=issued_at,
        claim=claim,
    )
    return (
        authority,
        policy,
        replace(claim, assessment_ids=(assessment.assessment_id,)),
        attestation,
        assessment,
    )


def _input(**changes):
    authority, policy, claim, attestation, assessment = _evidence()
    values = {
        "observed_at": NOW,
        "gate_results": (("tests", "PASS"),),
        "criteria": ("The production release is approved.",),
        "claims": (claim,),
        "attestations": (attestation,),
        "assessments": (assessment,),
    }
    values.update(changes)
    acceptance = kernel.AcceptanceInput(**values)
    governance = kernel.GovernancePolicy(
        required_gates=("tests",),
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=(attestation.record_sha256, assessment.record_sha256),
    )
    return governance, acceptance


def test_stable_api_is_one_screen():
    assert kernel.__all__ == [
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


def test_host_supplied_material_issues_a_policy_bound_record_without_retrieval():
    authority, policy, _claim, attestation, assessment = _evidence()

    assert authority.policy_hashes == (policy.digest,)
    assert attestation.policy_sha256 == policy.digest
    assert attestation.status == "VERIFIED"
    assert assessment.relation == "SUPPORTS"

    with pytest.raises(FrozenInstanceError):
        authority._policies = ()


def test_acceptance_is_deterministic_serializable_and_replayable():
    policy, input_ = _input()

    first = kernel.evaluate_acceptance(policy, input_)
    second = kernel.evaluate_acceptance(policy, input_)

    assert first == second
    assert first.status == "ACCEPTED"
    assert first.validate()
    assert first.replay(policy, input_)
    assert first.to_dict()["policy_sha256"] == policy.digest
    assert kernel.AcceptanceInput.from_dict(input_.to_dict()) == input_
    assert kernel.AcceptanceDecision.from_dict(first.to_dict()) == first


@pytest.mark.parametrize(
    ("changes", "policy_changes", "status", "reason"),
    [
        ({"tests_weakened": True}, {}, "BLOCKED", "tests_weakened"),
        ({"gate_results": (("tests", "FAIL"),)}, {}, "FAILED", "required_gate_failed:tests"),
        ({"gate_results": ()}, {}, "UNSUPPORTED", "required_gate_unavailable:tests"),
        (
            {"claims": (replace(_evidence()[2], assessment_ids=()),)},
            {},
            "UNVERIFIED",
            "central_claim_unverified:c1",
        ),
        (
            {"contradictions": (("x1", "blocking", "unresolved"),)},
            {},
            "BLOCKED",
            "unresolved_blocking_contradiction",
        ),
        ({"observed_at": "not-a-time"}, {}, "FAILED", "invalid_observation_time"),
    ],
)
def test_terminal_states_remain_distinct(changes, policy_changes, status, reason):
    policy, input_ = _input(**changes)
    if policy_changes:
        policy = replace(policy, **policy_changes)

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == status
    assert reason in decision.reasons


def test_unallowlisted_authority_or_verifier_cannot_authorize_claim():
    policy, input_ = _input()

    no_authority = replace(policy, allowed_authority_policies=())
    no_verifier = replace(policy, allowed_verifiers=(("other", "1"),))

    assert kernel.evaluate_acceptance(no_authority, input_).status == "UNVERIFIED"
    assert kernel.evaluate_acceptance(no_verifier, input_).status == "UNVERIFIED"


def test_claim_importance_is_derived_instead_of_producer_controlled():
    policy, input_ = _input(claims=(replace(_evidence()[2], assessment_ids=()),))

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == "UNVERIFIED"
    assert "central_claim_unverified:c1" in decision.reasons


def test_controller_policy_can_require_a_noncritical_claim():
    claim = kernel.ClaimRecord("policy-required", "The parser uses a bounded queue.")
    input_ = kernel.AcceptanceInput(observed_at=NOW, claims=(claim,))
    policy = kernel.GovernancePolicy(required_claim_ids=(claim.id,))

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == "UNVERIFIED"
    assert "central_claim_unverified:policy-required" in decision.reasons

    missing = kernel.evaluate_acceptance(
        kernel.GovernancePolicy(required_claim_ids=(claim.id,)),
        kernel.AcceptanceInput(observed_at=NOW),
    )
    assert missing.status == "UNVERIFIED"
    assert "required_claim_missing:policy-required" in missing.reasons
    disqualified = kernel.evaluate_acceptance(
        kernel.GovernancePolicy(
            required_claim_ids=(claim.id,),
            disqualified_claim_ids=(claim.id,),
        ),
        input_,
    )
    assert disqualified.status == "UNVERIFIED"
    assert "central_claim_disqualified:policy-required" in disqualified.reasons


def test_well_formed_but_unauthorized_records_cannot_authorize_claim():
    policy, input_ = _input()
    unauthorized = replace(policy, authorized_record_sha256=())

    assert input_.attestations[0].validate_record_hash()
    assert input_.assessments[0].validate_record_hash()
    assert kernel.evaluate_acceptance(unauthorized, input_).status == "UNVERIFIED"


def test_evidence_material_round_trips_without_mutable_aliasing():
    material = kernel.EvidenceMaterial(b"recorded bytes", "local://record", NOW, "text/plain")

    assert kernel.EvidenceMaterial.from_dict(material.to_dict()) == material


def test_tampered_record_fails_before_acceptance():
    policy, input_ = _input()
    forged = replace(input_.attestations[0], source_kind="mcp_result")

    decision = kernel.evaluate_acceptance(policy, replace(input_, attestations=(forged,)))

    assert decision.status == "FAILED"
    assert "invalid_attestation_record" in decision.reasons


def test_duplicate_identity_records_fail_closed():
    policy, input_ = _input()

    decision = kernel.evaluate_acceptance(
        policy,
        replace(
            input_,
            attestations=(input_.attestations[0], input_.attestations[0]),
            assessments=(input_.assessments[0], input_.assessments[0]),
        ),
    )

    assert decision.status == "FAILED"
    assert {"duplicate_attestation", "duplicate_support_assessment"} <= set(decision.reasons)


def test_nested_input_rows_are_copied_before_evaluation():
    policy, input_ = _input()
    gate = ["tests", "PASS"]
    contradiction = ["x1", "minor", "resolved"]
    frozen = replace(input_, gate_results=(gate,), contradictions=(contradiction,))
    before = kernel.evaluate_acceptance(policy, frozen)

    gate[1] = "FAIL"
    contradiction[1:] = ["blocking", "unresolved"]

    assert frozen.gate_results == (("tests", "PASS"),)
    assert frozen.contradictions == (("x1", "minor", "resolved"),)
    assert kernel.evaluate_acceptance(policy, frozen) == before
    assert before.status == "ACCEPTED"


def test_gate_result_rows_reject_bare_strings_instead_of_splitting_characters():
    with pytest.raises(ValueError, match="gate_results entries"):
        kernel.AcceptanceInput(observed_at=NOW, gate_results=("ok",))

    with pytest.raises(ValueError, match="gate_results entries"):
        kernel.AcceptanceInput.from_dict(
            {
                "schema_version": "evalopt.acceptance-input.v1",
                "observed_at": NOW,
                "gate_results": ["ok"],
                "criteria": [],
                "claims": [],
                "contradictions": [],
                "attestations": [],
                "assessments": [],
                "tests_weakened": False,
                "evaluator_score": None,
            }
        )


def test_contradiction_enums_are_normalized_and_unknown_values_rejected():
    policy, input_ = _input(contradictions=(("x1", "HIGH", "RESOLVED"),))

    assert input_.contradictions == (("x1", "high", "resolved"),)
    assert kernel.evaluate_acceptance(policy, input_).status == "ACCEPTED"
    with pytest.raises(ValueError, match="known severity"):
        replace(input_, contradictions=(("x1", "critical", "unresolved"),))


def test_stale_required_evidence_is_distinctly_unverified():
    old = "2025-01-01T00:00:00+00:00"
    authority, _adapter, claim, evidence, support = _evidence(retrieved_at=old)
    input_ = kernel.AcceptanceInput(
        observed_at=NOW,
        criteria=(TEXT,),
        claims=(claim,),
        attestations=(evidence,),
        assessments=(support,),
    )
    policy = kernel.GovernancePolicy(
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=(evidence.record_sha256, support.record_sha256),
    )

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == "UNVERIFIED"
    assert "central_claim_stale:c1" in decision.reasons


def test_future_evidence_fails_temporal_validation():
    future = "2027-01-01T00:00:00+00:00"
    authority, _adapter, claim, evidence, support = _evidence(retrieved_at=future, issued_at=future)
    input_ = kernel.AcceptanceInput(
        observed_at=NOW,
        criteria=(TEXT,),
        claims=(claim,),
        attestations=(evidence,),
        assessments=(support,),
    )
    policy = kernel.GovernancePolicy(
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=(evidence.record_sha256, support.record_sha256),
    )

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == "FAILED"
    assert "evidence_from_future" in decision.reasons


def test_critical_criterion_requires_the_supported_claim_to_match():
    opposite = "The production release is not approved."
    authority, _adapter, claim, evidence, support = _evidence(text=opposite)
    input_ = kernel.AcceptanceInput(
        observed_at=NOW,
        criteria=(TEXT,),
        claims=(claim,),
        attestations=(evidence,),
        assessments=(support,),
    )
    policy = kernel.GovernancePolicy(
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=(evidence.record_sha256, support.record_sha256),
    )

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == "UNVERIFIED"
    assert "critical_criterion_unverified:0" in decision.reasons


def test_disqualified_claim_cannot_satisfy_a_critical_criterion():
    policy, input_ = _input()
    policy = replace(
        policy,
        disqualified_claim_ids=(input_.claims[0].id,),
    )

    decision = kernel.evaluate_acceptance(policy, input_)

    assert decision.status == "UNVERIFIED"
    assert "central_claim_disqualified:c1" in decision.reasons
    assert "critical_criterion_unverified:0" in decision.reasons


def test_authorized_contradicting_support_prevents_acceptance():
    authority, _adapter, claim, evidence, support = _evidence()
    opposite = "The production release is not approved."
    conflicting_evidence, conflicting_support = authority.issue(
        kernel.EvidenceRequest("recorded-docs", "docs://opposite", quoted_span=opposite),
        kernel.EvidenceMaterial(opposite.encode(), "docs://opposite", NOW, "text/plain"),
        observed_at=NOW,
        claim=claim,
    )
    claim = replace(
        claim,
        assessment_ids=(support.assessment_id, conflicting_support.assessment_id),
    )
    input_ = kernel.AcceptanceInput(
        observed_at=NOW,
        criteria=(TEXT,),
        claims=(claim,),
        attestations=(evidence, conflicting_evidence),
        assessments=(support, conflicting_support),
    )
    policy = kernel.GovernancePolicy(
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=tuple(
            item.record_sha256 for item in (evidence, support, conflicting_evidence, conflicting_support)
        ),
    )

    decision = kernel.evaluate_acceptance(policy, input_)

    assert conflicting_support.relation == "CONTRADICTS"
    assert decision.status == "UNVERIFIED"
    assert "central_claim_contradicted:c1" in decision.reasons


def _two_critical_claim_decision(first_text, second_text):
    authority, _adapter = _authority()
    first = kernel.ClaimRecord("first", first_text)
    second = kernel.ClaimRecord("second", second_text)
    records = []
    claims = []
    for claim in (first, second):
        evidence, support = authority.issue(
            kernel.EvidenceRequest(
                "recorded-docs",
                f"docs://{claim.id}",
                quoted_span=claim.text,
            ),
            kernel.EvidenceMaterial(
                claim.text.encode(),
                f"docs://{claim.id}",
                NOW,
                "text/plain",
            ),
            observed_at=NOW,
            claim=claim,
        )
        records.extend((evidence, support))
        claims.append(replace(claim, assessment_ids=(support.assessment_id,)))
    policy = kernel.GovernancePolicy(
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=tuple(item.record_sha256 for item in records),
    )
    input_ = kernel.AcceptanceInput(
        observed_at=NOW,
        criteria=(first.text,),
        claims=tuple(claims),
        attestations=tuple(records[::2]),
        assessments=tuple(records[1::2]),
    )

    return kernel.evaluate_acceptance(policy, input_)


def test_opposite_critical_claims_fail_closed_without_host_labels():
    decision = _two_critical_claim_decision(
        "Production is enabled.",
        "Production is disabled.",
    )

    assert decision.status == "BLOCKED"
    assert "potential_critical_claim_conflict:first:second" in decision.reasons


def test_compatible_critical_neighbors_are_not_treated_as_opposites():
    decision = _two_critical_claim_decision(
        "Authentication requires MFA for administrators.",
        "Authentication requires MFA for remote users.",
    )

    assert decision.status == "ACCEPTED"


@pytest.mark.parametrize(
    "changes",
    [
        {"evaluator_score": float("nan")},
        {"tests_weakened": "false"},
        {"gate_results": (("tests",),)},
        {"contradictions": (("x1", "blocking"),)},
        {"claims": ({"id": "not-a-value-type"},)},
    ],
)
def test_structurally_invalid_input_is_rejected_at_construction(changes):
    _policy, input_ = _input()

    with pytest.raises(ValueError):
        replace(input_, **changes)
