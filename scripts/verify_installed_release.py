#!/usr/bin/env python3
"""Verify the public API and deterministic replay from an installed wheel."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
import sys

STABLE_API = [
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


def verify(expected_version: str) -> None:
    import evalopt_graph as evalopt

    assert evalopt.__version__ == expected_version, (
        f"package __version__ is {evalopt.__version__!r}, expected {expected_version!r}"
    )
    assert importlib.metadata.version("evalopt-graph") == expected_version
    assert evalopt.__all__ == STABLE_API, (
        f"stable API changed: expected {STABLE_API!r}, found {evalopt.__all__!r}"
    )

    metadata = importlib.metadata.metadata("evalopt-graph")
    runtime_requirements = [
        requirement
        for requirement in metadata.get_all("Requires-Dist", [])
        if "extra ==" not in requirement and "extra == " not in requirement
    ]
    assert not runtime_requirements, f"unexpected runtime dependencies: {runtime_requirements!r}"

    policy = evalopt.GovernancePolicy(required_gates=("tests",))
    input_ = evalopt.AcceptanceInput(
        observed_at="2026-07-20T00:00:00+00:00",
        gate_results=(("tests", "PASS"),),
    )
    decision = evalopt.evaluate_acceptance(policy, input_)
    assert decision.status == "ACCEPTED"
    assert decision.validate()
    assert decision.replay(policy, input_)

    encoded = json.dumps(decision.to_dict(), sort_keys=True)
    restored = evalopt.AcceptanceDecision.from_dict(json.loads(encoded))
    assert restored == decision
    assert restored.validate()
    assert restored.replay(policy, input_)

    cli_version = subprocess.run(
        [sys.executable, "-m", "evalopt_graph.cli", "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    assert cli_version == f"evalopt {expected_version}", cli_version


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    verify(args.version)
    print(f"installed evalopt-graph {args.version} API and replay verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
