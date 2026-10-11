#!/usr/bin/env python3
"""Reproduce a stopped-round receipt from public projections, without execution."""

import hashlib
import json
import sys
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    for name, expected in read(here / "checksums.json").items():
        if Path(name).name != name or sha(here / name) != expected:
            raise ValueError("public artifact checksum mismatch")
    receipt = read(here / "receipt.json")
    for name, expected in receipt["source_hashes"].items():
        path = repo / name
        if path.resolve() != path.absolute() or sha(path) != expected:
            raise ValueError("replay source differs from original frozen analysis")
    sys.path.insert(0, str(repo / "bench/harbor/skill-workflows-v2"))
    from evalopt_v2.analysis import reconcile
    from evalopt_v2.descriptive import kernel_metrics, outcomes, resources
    from evalopt_v2.records import digest
    from evalopt_v2.registration import development_gate, validate_registration

    registration = read(here.parent / "development-registration-2026-10-11/registration.json")
    validate_registration(registration, expected_sha256=receipt["registration_sha256"])
    inputs = read(here / "inputs.json")
    report = read(here / "report.json")
    if sha(here / "report.json") != receipt["report_sha256"]:
        raise ValueError("original report bytes changed")
    if digest(report) != receipt["report_canonical_sha256"]:
        raise ValueError("original report content changed")
    expected_ids = [row["trial_id"] for row in registration["schedule"]]
    ledger = inputs["ledger"]
    if [row["trial_id"] for row in ledger] != expected_ids:
        raise ValueError("schedule partition differs")
    counts = {
        state: sum(row["state"] == state for row in ledger)
        for state in ("finalized", "unfinalized", "unstarted")
    }
    if sum(counts.values()) != len(expected_ids):
        raise ValueError("unknown schedule state")
    if any(counts[key] != receipt[key] for key in counts):
        raise ValueError("schedule counts differ")
    if any(row["registration_sha256"] != receipt["registration_sha256"] for row in ledger):
        raise ValueError("cross-round attempt identity")
    known_ids = [row["trial_id"] for row in ledger if row["state"] == "finalized"]
    if [row["trial_id"] for row in inputs["rows"]] != known_ids:
        raise ValueError("known outcomes differ from finalized rows")
    actual_attempts = [(row["trial_id"], row["attempt"]) for row in inputs["attempts"]]
    if actual_attempts != [
        (row["trial_id"], row["attempt"]) for row in ledger if row["state"] != "unstarted"
    ]:
        raise ValueError("attempt accounting differs")
    resolved = reconcile(registration["tasks"], inputs["rows"], "development")
    timing = inputs["controller_timings"]
    rebuilt = {
        "stage": "development",
        "scheduled_rows": resolved,
        "secondary_outcomes": outcomes(resolved),
        "gate": development_gate(registration["tasks"], inputs["rows"], controls_passed=True, revision=0),
        "conclusion": "development_only",
        "resources": resources(registration["schedule"], inputs["attempts"]),
        "kernel": kernel_metrics(inputs["stopped_policy_projections"]),
        "registration_sha256": receipt["registration_sha256"],
        "retained_attempts": len(inputs["attempts"]),
        "finalized_rows": len(inputs["rows"]),
        "unfinalized_trials": [row["trial_id"] for row in ledger if row["state"] == "unfinalized"],
        "controller_time": {
            "observed_seconds": sum(row["controller_wall_seconds"] for row in timing),
            "known_attempts": len(timing),
            "retained_attempts": len(inputs["attempts"]),
            "scope": "setup_agent_capture_visible_and_hidden_verification",
        },
    }
    if rebuilt != report or report["gate"] != receipt["original_gate"]:
        raise ValueError("original frozen report did not reproduce")
    unknown = sum(row["reported_valid_completion"] is None for row in resolved)
    if unknown != receipt["unknown_outcomes"]:
        raise ValueError("missing outcome count differs")
    print(
        json.dumps(
            {
                "status": "PASS",
                "scheduled": len(expected_ids),
                **counts,
                "unknown_outcomes": unknown,
                "gate_ready": report["gate"]["ready"],
                "scope": "public projection arithmetic; no candidate execution or replication",
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
