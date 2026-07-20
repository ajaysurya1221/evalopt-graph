"""Unit contract for adapter-issued, content-bound evidence attestations.

These tests are deliberately offline.  Proposal producers control only an adapter id, locator,
and selector; adapter policy and retrieved bytes are the trusted inputs from which provenance is
derived.  The attestation layer establishes provenance and content integrity, while the separate
support assessment records whether the selected evidence supports the proposed claim.
"""

from __future__ import annotations

import os
from dataclasses import FrozenInstanceError
from hashlib import sha256

import pytest

from evalopt_graph import attestation as attestation_module
from evalopt_graph import epistemic, kernel
from evalopt_graph.attestation import (
    AdapterPolicy,
    DeterministicToolAdapter,
    EvidenceAttestation,
    EvidenceAuthority,
    EvidenceRequest,
    EvidenceResult,
    LocalFileAdapter,
    RecordedEvidenceAdapter,
    RetrievedArtifact,
    SupportAssessment,
)

NOW = "2026-07-11T12:00:00+00:00"
FUTURE = "2999-01-01T00:00:00+00:00"


def _policy(
    *,
    adapter_id: str = "recorded-official-docs",
    source_kind: str = "official_docs",
    trust_tier: str = epistemic.T2_OFFICIAL,
) -> AdapterPolicy:
    return AdapterPolicy(
        adapter_id=adapter_id,
        adapter_version="1",
        source_kind=source_kind,
        trust_tier=trust_tier,
        retrieval_mechanism="recorded_tool_result",
        parser_identity="text/plain@1",
        freshness_required=True,
    )


def _artifact(
    text: str,
    *,
    locator: str = "docs://evalopt/governance",
    retrieved_at: str = NOW,
    media_type: str = "text/plain",
) -> RetrievedArtifact:
    return RetrievedArtifact(
        content=text.encode(),
        final_locator=locator,
        retrieved_at=retrieved_at,
        media_type=media_type,
    )


def _recorded_authority(
    text: str,
    *,
    locator: str = "docs://evalopt/governance",
    retrieved_at: str = NOW,
) -> EvidenceAuthority:
    adapter = RecordedEvidenceAdapter(
        _policy(),
        {locator: _artifact(text, locator=locator, retrieved_at=retrieved_at)},
    )
    return EvidenceAuthority([adapter], now=lambda: NOW)


def _request(**changes: object) -> EvidenceRequest:
    packet: dict[str, object] = {
        "adapter_id": "recorded-official-docs",
        "locator": "docs://evalopt/governance",
        "quoted_span": "Evalopt uses a bounded retry budget.",
    }
    packet.update(changes)
    return EvidenceRequest.from_dict(packet)


@pytest.mark.parametrize(
    "field",
    ["adapter_id", "adapter_version", "retrieval_mechanism", "parser_identity"],
)
def test_adapter_policy_rejects_empty_identity_fields(field: str):
    values = {
        "adapter_id": "recorded-official-docs",
        "adapter_version": "1",
        "source_kind": "official_docs",
        "trust_tier": epistemic.T2_OFFICIAL,
        "retrieval_mechanism": "recorded_tool_result",
        "parser_identity": "text/plain@1",
        "freshness_required": True,
    }
    values[field] = ""

    with pytest.raises(ValueError, match="must not be empty"):
        AdapterPolicy(**values)


@pytest.mark.parametrize("field", ["final_locator", "media_type"])
def test_retrieved_artifact_rejects_empty_identity_fields(field: str):
    values = {
        "content": b"evidence",
        "final_locator": "docs://one",
        "retrieved_at": NOW,
        "media_type": "text/plain",
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        RetrievedArtifact(**values)


def test_producer_metadata_is_ignored_and_provenance_is_derived_from_adapter_policy():
    authority = _recorded_authority("Evalopt uses a bounded retry budget.\n")
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "recorded-official-docs",
            "locator": "docs://evalopt/governance",
            "quoted_span": "Evalopt uses a bounded retry budget.",
            # None of these producer-authored values is part of EvidenceRequest's authority.
            "source_kind": "test_output",
            "trust_tier": epistemic.T0_DETERMINISTIC,
            "retrieved_at": FUTURE,
            "status": "VERIFIED",
            "confirmed": True,
            "attestation_id": "attacker-issued",
            "parser_identity": "attacker@999",
        }
    )

    result = authority.attest(request, claim_text="Evalopt uses a bounded retry budget.")

    assert not hasattr(request, "source_kind")
    assert not hasattr(request, "trust_tier")
    assert not hasattr(request, "retrieved_at")
    assert result.attestation.status == "VERIFIED"
    assert result.attestation.source_kind == "official_docs"
    assert result.attestation.trust_tier == epistemic.T2_OFFICIAL
    assert result.attestation.retrieved_at == NOW
    assert result.attestation.parser_identity == "text/plain@1"
    assert result.attestation.attestation_id != "attacker-issued"
    assert result.support_assessment.relation == "SUPPORTS"


def test_exact_unique_quoted_span_is_content_bound():
    content = b"Heading\nEvalopt uses a bounded retry budget.\nFooter\n"
    authority = _recorded_authority(content.decode())

    result = authority.attest(_request(), claim_text="Evalopt uses a bounded retry budget.")

    assert result.attestation.status == "VERIFIED"
    assert result.attestation.selector_kind == "quoted_span"
    assert result.attestation.selected_text == "Evalopt uses a bounded retry budget."
    assert result.attestation.raw_content_sha256 == sha256(content).hexdigest()
    assert result.attestation.selected_sha256 == sha256(b"Evalopt uses a bounded retry budget.").hexdigest()
    assert result.support_assessment.relation == "SUPPORTS"


@pytest.mark.parametrize(
    ("content", "quoted_span", "reason_fragment"),
    [
        ("The document discusses retries.", "No such sentence.", "missing"),
        ("same span\nmiddle\nsame span\n", "same span", "ambiguous"),
    ],
)
def test_missing_or_ambiguous_quoted_span_is_unsupported(
    content: str,
    quoted_span: str,
    reason_fragment: str,
):
    authority = _recorded_authority(content)

    result = authority.attest(
        _request(quoted_span=quoted_span),
        claim_text="A claim that must not be confirmed",
    )

    assert result.attestation.status == "UNSUPPORTED"
    assert reason_fragment in result.attestation.failure_reason.lower()
    assert result.support_assessment.relation == "NOT_ASSESSED"


def test_json_pointer_selects_a_structured_field():
    locator = "mcp://catalog/widget"
    content = '{"feature":{"name":"safe mode","enabled":true}}'
    policy = _policy(adapter_id="recorded-mcp", source_kind="mcp_result")
    adapter = RecordedEvidenceAdapter(
        policy,
        {
            locator: _artifact(
                content,
                locator=locator,
                media_type="application/json",
            )
        },
    )
    authority = EvidenceAuthority([adapter], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "recorded-mcp",
            "locator": locator,
            "json_pointer": "/feature/name",
        }
    )

    result = authority.attest(request, claim_text="safe mode")

    assert result.attestation.status == "VERIFIED"
    assert result.attestation.selector_kind == "json_pointer"
    assert result.attestation.selector_value == "/feature/name"
    assert result.attestation.selected_text == "safe mode"
    assert result.support_assessment.relation == "SUPPORTS"


def test_missing_json_pointer_is_unsupported():
    locator = "mcp://catalog/widget"
    policy = _policy(adapter_id="recorded-mcp", source_kind="mcp_result")
    adapter = RecordedEvidenceAdapter(
        policy,
        {
            locator: _artifact(
                '{"feature":{"enabled":true}}',
                locator=locator,
                media_type="application/json",
            )
        },
    )
    authority = EvidenceAuthority([adapter], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "recorded-mcp",
            "locator": locator,
            "json_pointer": "/feature/missing",
        }
    )

    result = authority.attest(request, claim_text="The feature exists.")

    assert result.attestation.status == "UNSUPPORTED"
    assert "pointer" in result.attestation.failure_reason.lower()
    assert result.support_assessment.relation == "NOT_ASSESSED"


def test_local_file_adapter_reads_only_beneath_its_root(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("The local invariant holds.\n")
    authority = EvidenceAuthority([LocalFileAdapter(tmp_path)], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "local_file",
            "locator": "evidence.txt",
            "quoted_span": "The local invariant holds.",
        }
    )

    result = authority.attest(request, claim_text="The local invariant holds.")

    assert result.attestation.status == "VERIFIED"
    assert result.attestation.source_kind == "local_file"
    assert result.attestation.trust_tier == epistemic.T1_PRIMARY
    assert result.support_assessment.relation == "SUPPORTS"


@pytest.mark.parametrize("locator_kind", ["traversal", "absolute", "symlink"])
def test_local_file_adapter_blocks_paths_outside_root(tmp_path, locator_kind: str):
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("Outside content must not become trusted.\n")
    if locator_kind == "traversal":
        locator = "../outside.txt"
    elif locator_kind == "absolute":
        locator = str(outside)
    else:
        link = root / "link.txt"
        link.symlink_to(outside)
        locator = "link.txt"
    authority = EvidenceAuthority([LocalFileAdapter(root)], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "local_file",
            "locator": locator,
            "quoted_span": "Outside content must not become trusted.",
        }
    )

    result = authority.attest(request, claim_text="Outside content must not become trusted.")

    assert result.attestation.status == "BLOCKED"
    assert result.support_assessment.relation == "NOT_ASSESSED"
    assert result.attestation.raw_content_sha256 == ""


def test_revalidation_detects_local_content_mutation(tmp_path):
    evidence = tmp_path / "evidence.txt"
    evidence.write_text("The release is approved.\n")
    authority = EvidenceAuthority([LocalFileAdapter(tmp_path)], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "local_file",
            "locator": "evidence.txt",
            "quoted_span": "The release is approved.",
        }
    )
    result = authority.attest(request, claim_text="The release is approved.")
    evidence.write_text("The release is not approved.\n")

    validation = authority.revalidate(result.attestation)

    assert validation.valid is False
    assert validation.status == "FAILED"
    assert "content" in validation.reason.lower() or "hash" in validation.reason.lower()


@pytest.mark.parametrize(
    ("request_change", "reason_fragment"),
    [
        ({"expected_sha256": "0" * 64}, "hash"),
        ({"expected_final_locator": "docs://different/document"}, "locator"),
    ],
)
def test_expected_hash_or_final_locator_mismatch_fails_closed(
    request_change: dict[str, str],
    reason_fragment: str,
):
    authority = _recorded_authority("Evalopt uses a bounded retry budget.\n")

    result = authority.attest(
        _request(**request_change),
        claim_text="Evalopt uses a bounded retry budget.",
    )

    assert result.attestation.status == "FAILED"
    assert reason_fragment in result.attestation.failure_reason.lower()
    assert result.support_assessment.relation == "NOT_ASSESSED"


def test_future_timestamp_from_trusted_adapter_is_rejected():
    authority = _recorded_authority(
        "Evalopt uses a bounded retry budget.\n",
        retrieved_at=FUTURE,
    )

    result = authority.attest(_request(), claim_text="Evalopt uses a bounded retry budget.")

    assert result.attestation.status == "FAILED"
    assert "future" in result.attestation.failure_reason.lower()
    assert result.support_assessment.relation == "NOT_ASSESSED"


def test_empty_json_selection_returns_valid_unsupported_record():
    locator = "docs://empty-json"
    policy = _policy()
    authority = EvidenceAuthority(
        [
            RecordedEvidenceAdapter(
                policy,
                {
                    locator: RetrievedArtifact(
                        content=b'{"fact":""}',
                        final_locator=locator,
                        retrieved_at=NOW,
                        media_type="application/json",
                    )
                },
            )
        ],
        now=lambda: NOW,
    )

    result = authority.attest(
        EvidenceRequest(
            adapter_id=policy.adapter_id,
            locator=locator,
            json_pointer="/fact",
        ),
        claim_text="A nonempty claim.",
    )

    assert result.attestation.status == "UNSUPPORTED"
    assert result.attestation.validate_record_hash() is True
    assert result.support_assessment.relation == "NOT_ASSESSED"


@pytest.mark.parametrize(
    "changed_field",
    [
        "adapter_id",
        "adapter_version",
        "source_kind",
        "trust_tier",
        "retrieval_mechanism",
        "parser_identity",
        "freshness_required",
    ],
)
def test_revalidation_rejects_acceptance_policy_drift(changed_field: str):
    class MutablePolicyAdapter:
        def __init__(self):
            self.policy = _policy()

        def retrieve(self, locator: str) -> RetrievedArtifact:
            return _artifact("Evalopt uses a bounded retry budget.", locator=locator)

    adapter = MutablePolicyAdapter()
    authority = EvidenceAuthority([adapter], now=lambda: NOW)
    result = authority.attest(_request(), claim_text="Evalopt uses a bounded retry budget.")
    values = {
        "adapter_id": adapter.policy.adapter_id,
        "adapter_version": adapter.policy.adapter_version,
        "source_kind": adapter.policy.source_kind,
        "trust_tier": adapter.policy.trust_tier,
        "retrieval_mechanism": adapter.policy.retrieval_mechanism,
        "parser_identity": adapter.policy.parser_identity,
        "freshness_required": adapter.policy.freshness_required,
    }
    replacements = {
        "adapter_id": "recorded-docs-changed",
        "adapter_version": "2",
        "source_kind": "command_output",
        "trust_tier": epistemic.T0_DETERMINISTIC,
        "retrieval_mechanism": "changed_retrieval",
        "parser_identity": "text/plain@2",
        "freshness_required": not adapter.policy.freshness_required,
    }
    values[changed_field] = replacements[changed_field]
    adapter.policy = AdapterPolicy(**values)

    validation = authority.revalidate(result.attestation)

    assert validation.valid is False
    assert validation.status == "FAILED"
    assert "policy" in validation.reason


@pytest.mark.parametrize(
    ("changed_field", "changed_value"),
    [
        ("adapter_id", "other-adapter"),
        ("adapter_version", "2"),
        ("source_kind", "command_output"),
        ("trust_tier", epistemic.T0_DETERMINISTIC),
        ("retrieval_mechanism", "other-retrieval"),
        ("parser_identity", "text/plain@2"),
        ("freshness_required", False),
    ],
)
def test_recomputed_record_cannot_change_policy_derived_fields(changed_field, changed_value):
    text = "Evalopt uses a bounded retry budget."
    policy = _policy()
    authority = _recorded_authority(text)
    result = authority.attest(_request(), claim_text=text)
    payload = result.attestation.to_dict()
    payload.pop("record_sha256")
    payload.pop("attestation_id")
    payload[changed_field] = changed_value
    attestation_id = f"att-{attestation_module._hash_record(payload)[:24]}"
    record = {"attestation_id": attestation_id, **payload}
    forged = EvidenceAttestation(
        **record,
        record_sha256=attestation_module._hash_record(record),
    )

    valid, status, reason = attestation_module._revalidate_material(
        policy,
        forged,
        _artifact(text),
    )

    assert forged.validate_record_hash() is True
    assert valid is False
    assert status == "FAILED"
    assert "policy" in reason


def test_invalid_host_material_returns_a_failed_record():
    policy = _policy()
    authority = kernel.EvidenceAuthority([policy.to_dict()])
    claim = kernel.ClaimRecord("c1", "Evalopt uses a bounded retry budget.")

    evidence, support = authority.issue(
        _request(),
        object(),
        observed_at=NOW,
        claim=claim,
    )

    assert evidence.status == "FAILED"
    assert support.relation == "NOT_ASSESSED"


def test_authority_snapshot_ignores_later_registrations():
    authority = EvidenceAuthority([], now=lambda: NOW)
    snapshot = authority.snapshot()
    authority.register(RecordedEvidenceAdapter(_policy(), {}))

    assert authority.has_adapter(_policy().adapter_id) is True
    assert snapshot.has_adapter(_policy().adapter_id) is False


def test_negated_evidence_is_contradictory_not_supporting():
    authority = _recorded_authority("The API does not support offline mode.\n")
    request = _request(quoted_span="The API does not support offline mode.")

    result = authority.attest(request, claim_text="The API supports offline mode.")

    assert result.attestation.status == "VERIFIED"
    assert result.support_assessment.relation == "CONTRADICTS"
    assert result.support_assessment.relation != "SUPPORTS"


@pytest.mark.parametrize(
    ("claim", "evidence"),
    [
        ("Production authentication prevents remote code execution.", "remote"),
        (
            "All production passwords are encrypted.",
            "All production passwords are encrypted only in the mocked test fixture; deployment behavior is untested.",
        ),
        ("The feature is always enabled.", "The feature may be enabled in development."),
    ],
)
def test_partial_or_qualified_text_is_not_acceptance_capable(claim: str, evidence: str):
    authority = _recorded_authority(evidence)
    request = _request(quoted_span=evidence)

    result = authority.attest(request, claim_text=claim)

    assert result.attestation.status == "VERIFIED"
    assert result.support_assessment.relation == "INSUFFICIENT"


@pytest.mark.parametrize(
    ("claim_type", "claim_subject", "claim_text", "expected_relation"),
    [
        ("research_claim", "release approval", "Approved.", "INSUFFICIENT"),
        ("security_claim", "", "Approved.", "INSUFFICIENT"),
        (
            "security_claim",
            "production release",
            "The release is approved.",
            "INSUFFICIENT",
        ),
        (
            "security_claim",
            "production release",
            "The production release is approved.",
            "SUPPORTS",
        ),
    ],
)
def test_exact_text_support_is_bound_to_structured_claim_context(
    claim_type: str,
    claim_subject: str,
    claim_text: str,
    expected_relation: str,
):
    authority = _recorded_authority(claim_text)
    request = _request(quoted_span=claim_text)

    result = authority.attest(
        request,
        claim_text=claim_text,
        claim_type=claim_type,
        claim_subject=claim_subject,
    )

    assert result.attestation.status == "VERIFIED"
    assert result.support_assessment.relation == expected_relation


def test_abstract_stance_identifier_is_bound_but_not_lexically_required():
    claim_text = "LibA benchmark report: LibA is faster than LibB on the speed suite."
    authority = _recorded_authority(claim_text)

    result = authority.attest(
        _request(quoted_span=claim_text),
        claim_text=claim_text,
        claim_type="research_claim",
        claim_subject="speed",
        claim_stance="A_faster",
    )

    assert result.support_assessment.claim_stance == "A_faster"
    assert result.support_assessment.relation == "SUPPORTS"


def test_local_file_directory_swap_cannot_escape_open_root(tmp_path, monkeypatch):
    root = tmp_path / "root"
    inside = root / "inside"
    outside = tmp_path / "outside"
    inside.mkdir(parents=True)
    outside.mkdir()
    (inside / "proof.txt").write_text("inside proof\n")
    (outside / "proof.txt").write_text("outside secret\n")
    saved = root / "inside-saved"
    original_open = os.open
    swapped = False
    authority = EvidenceAuthority([LocalFileAdapter(root)], now=lambda: NOW)

    def swapping_open(path, flags, mode=0o777, *, dir_fd=None):
        nonlocal swapped
        if not swapped and str(path).endswith("proof.txt"):
            inside.rename(saved)
            inside.symlink_to(outside, target_is_directory=True)
            swapped = True
        return original_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", swapping_open)
    result = authority.attest(
        EvidenceRequest(
            adapter_id="local_file",
            locator="inside/proof.txt",
            quoted_span="outside secret",
        ),
        claim_text="outside secret",
    )

    assert swapped is True
    assert result.attestation.status != "VERIFIED"
    assert result.support_assessment.relation == "NOT_ASSESSED"


def test_unknown_adapter_is_unsupported_and_cannot_assess_support():
    authority = EvidenceAuthority([], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "producer-invented-adapter",
            "locator": "docs://invented",
            "quoted_span": "invented proof",
        }
    )

    result = authority.attest(request, claim_text="invented proof")

    assert result.attestation.status == "UNSUPPORTED"
    assert "adapter" in result.attestation.failure_reason.lower()
    assert result.support_assessment.relation == "NOT_ASSESSED"


def test_deterministic_tool_adapter_issues_t0_attestation_from_recorded_observation():
    locator = "tool://pytest/run-1"
    adapter = DeterministicToolAdapter(
        {
            locator: _artifact(
                "307 tests passed.",
                locator=locator,
            )
        }
    )
    authority = EvidenceAuthority([adapter], now=lambda: NOW)
    request = EvidenceRequest.from_dict(
        {
            "adapter_id": "deterministic_tool",
            "locator": locator,
            "quoted_span": "307 tests passed.",
        }
    )

    result = authority.attest(request, claim_text="307 tests passed.")

    assert result.attestation.status == "VERIFIED"
    assert result.attestation.trust_tier == epistemic.T0_DETERMINISTIC
    assert result.support_assessment.relation == "SUPPORTS"


def test_attestation_records_are_frozen():
    policy = _policy()
    artifact = _artifact("Evalopt uses a bounded retry budget.\n")
    request = _request()
    result = EvidenceAuthority(
        [RecordedEvidenceAdapter(policy, {artifact.final_locator: artifact})],
        now=lambda: NOW,
    ).attest(request, claim_text="Evalopt uses a bounded retry budget.")

    assert isinstance(result, EvidenceResult)
    assert isinstance(result.attestation, EvidenceAttestation)
    assert isinstance(result.support_assessment, SupportAssessment)
    for record, attribute, replacement in (
        (policy, "source_kind", "forged"),
        (artifact, "retrieved_at", FUTURE),
        (request, "locator", "docs://forged"),
        (result.attestation, "status", "VERIFIED"),
        (result.support_assessment, "relation", "SUPPORTS"),
        (result, "attestation", result.attestation),
    ):
        with pytest.raises(FrozenInstanceError):
            setattr(record, attribute, replacement)


def test_canonical_record_hashes_are_stable_across_input_mapping_order():
    authority = _recorded_authority("Evalopt uses a bounded retry budget.\n")
    forward = {
        "adapter_id": "recorded-official-docs",
        "locator": "docs://evalopt/governance",
        "quoted_span": "Evalopt uses a bounded retry budget.",
    }
    reverse = dict(reversed(list(forward.items())))

    first = authority.attest(
        EvidenceRequest.from_dict(forward),
        claim_text="Evalopt uses a bounded retry budget.",
    )
    second = authority.attest(
        EvidenceRequest.from_dict(reverse),
        claim_text="Evalopt uses a bounded retry budget.",
    )

    assert len(first.attestation.record_sha256) == 64
    assert len(first.support_assessment.record_sha256) == 64
    assert first.attestation.record_sha256 == second.attestation.record_sha256
    assert first.support_assessment.record_sha256 == second.support_assessment.record_sha256
    assert first.attestation.attestation_id == second.attestation.attestation_id
    assert first.support_assessment.assessment_id == second.support_assessment.assessment_id
