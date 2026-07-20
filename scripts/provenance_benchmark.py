#!/usr/bin/env python3
"""Small deterministic conformance probe for the frozen evidence boundary.

This is not an evaluation harness. It generates one fixed regression corpus, executes it in-process,
and writes one summary. Harbor owns tasks, isolation, trials, artifacts, and aggregation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

NOW = "2026-07-11T12:00:00+00:00"
SEED = 20260711
ROOT = Path(__file__).resolve().parents[1]

LEGACY_VARIANTS = (
    "official_docs_kind",
    "mcp_result_kind",
    "local_file_kind",
    "test_output_kind",
    "command_output_kind",
    "git_diff_kind",
    "declared_t0",
    "unknown_tier",
    "future_timestamp",
    "confirmed_status",
    "verifier_creator",
    "opposite_summary",
)
ADAPTER_VARIANTS = (
    "unknown_adapter",
    "missing_selector",
    "missing_quote",
    "ambiguous_quote",
    "hash_mismatch",
    "final_locator_mismatch",
    "future_adapter_timestamp",
    "opposite_evidence",
    "qualified_evidence",
    "missing_json_pointer",
    "local_traversal",
    "altered_after_retrieval",
)
VALID_VARIANTS = (
    "recorded_exact",
    "recorded_expected_hash",
    "recorded_expected_locator",
    "recorded_json_pointer",
    "local_exact",
    "deterministic_exact",
    "unicode_exact",
    "multiline_exact",
)


@dataclass(frozen=True)
class Case:
    id: str
    kind: str
    variant: str
    claim: str
    subject: str


def generate_cases(seed: int = SEED) -> tuple[Case, ...]:
    """Return the versioned 12 + 12 + 8 generated regression corpus."""
    rng = random.Random(seed)
    cases: list[Case] = []
    for kind, variants in (
        ("legacy", LEGACY_VARIANTS),
        ("adapter", ADAPTER_VARIANTS),
        ("valid", VALID_VARIANTS),
    ):
        for index, variant in enumerate(variants, 1):
            marker = rng.randrange(10**8, 10**9)
            if variant == "unicode_exact":
                claim = f"Café fact {marker} is supported."
            elif variant == "multiline_exact":
                claim = f"Recorded fact {marker} is supported.\nSecond line is exact."
            elif kind == "legacy":
                claim = f"Provenance claim {marker} is independently verified."
            else:
                claim = f"Recorded fact {marker} is supported."
            cases.append(Case(f"{kind}-{index:02d}", kind, variant, claim, f"record-{marker}"))
    rng.shuffle(cases)
    return tuple(cases)


def _legacy_packet(case: Case) -> dict[str, Any]:
    kinds = {
        "mcp_result_kind": "mcp_result",
        "local_file_kind": "local_file",
        "test_output_kind": "test_output",
        "command_output_kind": "command_output",
        "git_diff_kind": "git_diff",
    }
    summary = (
        case.claim.replace(" is independently verified", " is not independently verified")
        if case.variant == "opposite_summary"
        else case.claim
    )
    source = {
        "kind": kinds.get(case.variant, "official_docs"),
        "locator": f"missing://{case.id}",
        "summary": summary,
        "quoted_span_or_hash": summary,
        "retrieved_at": "2999-01-01T00:00:00+00:00",
        "trust_tier": "T0_deterministic" if case.variant == "declared_t0" else "T2_official_docs",
        "freshness_required": False,
        "verification_status": "VERIFIED",
        "confirmed": True,
        "parser_identity": "producer@999",
        "adapter_id": "producer-invented",
        "content_sha256": "f" * 64,
    }
    if case.variant == "unknown_tier":
        source["trust_tier"] = "producer-tier"
    return {
        "claim": {
            "text": case.claim,
            "type": "research_claim",
            "subject": case.subject,
            "source_type": "official_docs",
            "status": "confirmed",
            "created_by": "source_verifier",
            "verified_by": ["source_verifier"],
            "trust_tier": "T0_deterministic",
        },
        "sources": [source],
    }


def _legacy_rejected(case: Case, repo: Path) -> bool:
    from evalopt_graph import MockProvider, RunContext, new_state, run_research_loop

    packet = _legacy_packet(case)

    def investigate(state, context, phase):
        del state, context
        return [packet] if phase == "investigation" else []

    final = run_research_loop(
        new_state(
            f"Assess {case.subject}",
            str(repo),
            mode="research",
            research_questions=[case.subject],
            max_research_rounds=1,
        ),
        RunContext(provider=MockProvider(), investigation_hook=investigate, now=lambda: NOW),
    )
    claim = next(item for item in final["knowledge"]["claims"] if item.get("subject") == case.subject)
    sources = {item["id"]: item for item in final["knowledge"].get("sources", []) if item.get("id")}
    linked = [sources[ref] for ref in claim.get("evidence_refs", ()) if ref in sources]
    return claim.get("status") != "confirmed" and not any(
        item.get("attestation_status") == "VERIFIED" and item.get("support_relation") == "SUPPORTS"
        for item in linked
    )


def _policy(adapter_id: str = "recorded-conformance"):
    from evalopt_graph.attestation import AdapterPolicy
    from evalopt_graph.epistemic import T2_OFFICIAL

    return AdapterPolicy(
        adapter_id,
        "1",
        "official_docs",
        T2_OFFICIAL,
        "recorded_conformance",
        "text/plain@1",
        True,
    )


def _adapter_passed(case: Case, repo: Path) -> bool:
    from evalopt_graph.attestation import EvidenceRequest, RetrievedArtifact
    from evalopt_graph.evidence_adapters import (
        EvidenceAuthority,
        LocalFileAdapter,
        RecordedEvidenceAdapter,
    )

    locator = f"recorded://{case.id}"
    policy = _policy()
    content = case.claim
    request = EvidenceRequest(policy.adapter_id, locator, quoted_span=case.claim)
    retrieved_at = NOW
    media_type = "text/plain"

    if case.variant == "unknown_adapter":
        result = EvidenceAuthority([], now=lambda: NOW).attest(request, claim_text=case.claim)
        return result.attestation.status == "UNSUPPORTED"
    if case.variant == "missing_selector":
        request = EvidenceRequest(policy.adapter_id, locator)
    elif case.variant == "missing_quote":
        content = "The requested claim is absent."
    elif case.variant == "ambiguous_quote":
        content = f"{case.claim}\n{case.claim}"
    elif case.variant == "hash_mismatch":
        request = EvidenceRequest(policy.adapter_id, locator, case.claim, expected_sha256="0" * 64)
    elif case.variant == "final_locator_mismatch":
        request = EvidenceRequest(
            policy.adapter_id,
            locator,
            case.claim,
            expected_final_locator="recorded://different",
        )
    elif case.variant == "future_adapter_timestamp":
        retrieved_at = "2999-01-01T00:00:00+00:00"
    elif case.variant == "opposite_evidence":
        content = case.claim.replace(" is ", " is not ")
        request = EvidenceRequest(policy.adapter_id, locator, quoted_span=content)
    elif case.variant == "qualified_evidence":
        content = case.claim + " This is only true in the fixture."
        request = EvidenceRequest(policy.adapter_id, locator, quoted_span=content)
    elif case.variant == "missing_json_pointer":
        content, media_type = "{}", "application/json"
        request = EvidenceRequest(policy.adapter_id, locator, json_pointer="/fact")
    elif case.variant == "local_traversal":
        outside = repo.parent / "outside.txt"
        outside.write_text(case.claim, encoding="utf-8")
        authority = EvidenceAuthority([LocalFileAdapter(repo)], now=lambda: NOW)
        result = authority.attest(
            EvidenceRequest("local_file", "../outside.txt", quoted_span=case.claim),
            claim_text=case.claim,
        )
        return result.attestation.status == "BLOCKED"
    elif case.variant == "altered_after_retrieval":

        class ChangingAdapter:
            def __init__(self) -> None:
                self.policy = policy
                self.calls = 0

            def retrieve(self, requested_locator: str) -> RetrievedArtifact:
                self.calls += 1
                value = case.claim if self.calls == 1 else "Content changed after attestation."
                return RetrievedArtifact(value.encode(), requested_locator, NOW, "text/plain")

        authority = EvidenceAuthority([ChangingAdapter()], now=lambda: NOW)
        result = authority.attest(request, claim_text=case.claim)
        checked = authority.revalidate(result.attestation)
        return result.attestation.status == "VERIFIED" and not checked.valid and checked.status == "FAILED"

    artifact = RetrievedArtifact(content.encode(), locator, retrieved_at, media_type)
    authority = EvidenceAuthority(
        [RecordedEvidenceAdapter(policy, {locator: artifact})],
        now=lambda: NOW,
    )
    result = authority.attest(request, claim_text=case.claim)
    expected = {
        "missing_selector": ("UNSUPPORTED", "NOT_ASSESSED"),
        "missing_quote": ("UNSUPPORTED", "NOT_ASSESSED"),
        "ambiguous_quote": ("UNSUPPORTED", "NOT_ASSESSED"),
        "hash_mismatch": ("FAILED", "NOT_ASSESSED"),
        "final_locator_mismatch": ("FAILED", "NOT_ASSESSED"),
        "future_adapter_timestamp": ("FAILED", "NOT_ASSESSED"),
        "opposite_evidence": ("VERIFIED", "CONTRADICTS"),
        "qualified_evidence": ("VERIFIED", "INSUFFICIENT"),
        "missing_json_pointer": ("UNSUPPORTED", "NOT_ASSESSED"),
    }[case.variant]
    return (result.attestation.status, result.support_assessment.relation) == expected


def _valid_passed(case: Case, repo: Path) -> bool:
    from evalopt_graph.attestation import EvidenceRequest, RetrievedArtifact
    from evalopt_graph.evidence_adapters import (
        DeterministicToolAdapter,
        EvidenceAuthority,
        LocalFileAdapter,
        RecordedEvidenceAdapter,
    )

    locator = f"recorded://{case.id}"
    content = case.claim
    request = EvidenceRequest("recorded-conformance", locator, quoted_span=case.claim)
    if case.variant == "recorded_json_pointer":
        content = json.dumps({"fact": case.claim})
        request = EvidenceRequest("recorded-conformance", locator, json_pointer="/fact")
    if case.variant == "local_exact":
        (repo / "evidence.txt").write_text(case.claim + "\n", encoding="utf-8")
        authority = EvidenceAuthority([LocalFileAdapter(repo)], now=lambda: NOW)
        request = EvidenceRequest("local_file", "evidence.txt", quoted_span=case.claim)
    else:
        artifact = RetrievedArtifact(
            content.encode(),
            locator,
            NOW,
            "application/json" if case.variant == "recorded_json_pointer" else "text/plain",
        )
        if case.variant == "deterministic_exact":
            authority = EvidenceAuthority([DeterministicToolAdapter({locator: artifact})], now=lambda: NOW)
            request = EvidenceRequest("deterministic_tool", locator, quoted_span=case.claim)
        else:
            policy = _policy()
            if case.variant == "recorded_expected_hash":
                request = EvidenceRequest(
                    policy.adapter_id,
                    locator,
                    quoted_span=case.claim,
                    expected_sha256=hashlib.sha256(artifact.content).hexdigest(),
                )
            elif case.variant == "recorded_expected_locator":
                request = EvidenceRequest(
                    policy.adapter_id,
                    locator,
                    quoted_span=case.claim,
                    expected_final_locator=locator,
                )
            authority = EvidenceAuthority(
                [RecordedEvidenceAdapter(policy, {locator: artifact})], now=lambda: NOW
            )
    result = authority.attest(request, claim_text=case.claim)
    checked = authority.revalidate(result.attestation)
    return (
        result.attestation.status == "VERIFIED"
        and result.support_assessment.relation == "SUPPORTS"
        and checked.valid
    )


def run_conformance(seed: int = SEED) -> dict[str, Any]:
    cases = generate_cases(seed)
    outcomes: dict[str, list[tuple[str, bool]]] = {"legacy": [], "adapter": [], "valid": []}
    with tempfile.TemporaryDirectory(prefix="evalopt-conformance-") as directory:
        repo = Path(directory)
        for case in cases:
            passed = {
                "legacy": _legacy_rejected,
                "adapter": _adapter_passed,
                "valid": _valid_passed,
            }[case.kind](case, repo)
            outcomes[case.kind].append((case.id, passed))
    summary: dict[str, Any] = {
        "schema_version": "evalopt.generated-conformance.v1",
        "seed": seed,
        "legacy": {"attempts": 12, "rejected": sum(ok for _, ok in outcomes["legacy"])},
        "adapter": {"attempts": 12, "passed": sum(ok for _, ok in outcomes["adapter"])},
        "valid": {"attempts": 8, "passed": sum(ok for _, ok in outcomes["valid"])},
    }
    summary["failures"] = [case_id for rows in outcomes.values() for case_id, ok in rows if not ok]
    summary["passed"] = not summary["failures"]
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="summary JSON path outside the repository")
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)
    output = Path(args.out).resolve()
    if output.is_relative_to(ROOT):
        raise SystemExit("conformance output must be outside the repository")
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = run_conformance(args.seed)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
