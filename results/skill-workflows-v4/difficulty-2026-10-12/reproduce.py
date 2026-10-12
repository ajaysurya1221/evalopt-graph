#!/usr/bin/env python3
"""DRAFT: pure public projection replay; never opens a private campaign.

Review before publication. A separate endpoint audit checks correspondence under
the retained controller custody/review assumptions; this file proves only consistency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import stat
import sys
import tempfile
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def strict_equal(left, right):
    return canonical(left) == canonical(right)


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite JSON constant")

    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=constant)


def shape(value, required, optional=()):
    require(
        type(value) is dict and set(required) <= set(value) <= set(required) | set(optional),
        "unknown or missing projection fields",
    )


def sha_value(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "invalid digest")


def tri(value):
    require(type(value) is bool or value is None, "outcome must be boolean or null")


def number(value):
    require(type(value) is int and value in (1, 2), "invalid attempt number")


def validate_inputs(registration, inputs):
    from evalopt_v4.accounting import validate_usage

    shape(
        inputs,
        {
            "registration_sha256",
            "rows",
            "attempts",
            "controller_timings",
            "ledger",
            "stopped_policy_projections",
        },
    )
    sha_value(inputs["registration_sha256"])
    for field in ("rows", "attempts", "controller_timings", "ledger", "stopped_policy_projections"):
        require(type(inputs[field]) is list, "projection roster must be a list")
    schedule = {row["trial_id"]: row for row in registration["schedule"]}

    def trial(value):
        require(type(value) is str and value in schedule, "unregistered trial identity")

    flags = {
        "valid_completion",
        "functional_success",
        "unsupported_success",
        "incorrect_refusal",
        "boundary_violation",
        "raw_valid_completion",
        "raw_functional_success",
        "boundary_preserved",
        "claims_supported",
        "response_contract_valid",
        "check_claims_supported",
        "semantic_response_assessable",
        "semantic_failure_evidence_valid",
        "lifecycle_verified",
    }
    for row in inputs["rows"]:
        require(type(row) is dict, "outcome must be an object")
        trial(row.get("trial_id"))
        scheduled = schedule[row["trial_id"]]
        shape(
            row,
            set(scheduled)
            | flags
            | {"contract_dispute", "runtime_identity_verified", "timed_out", "verifier_status"},
            {"missing_reason"},
        )
        require(strict_equal({k: row[k] for k in scheduled}, scheduled), "typed schedule identity differs")
        for field in flags:
            tri(row[field])
        require(
            type(row["contract_dispute"]) is bool
            and type(row["runtime_identity_verified"]) is bool
            and type(row["timed_out"]) is bool,
            "invalid evidence flags",
        )
        require(
            type(row["verifier_status"]) is str
            and row["verifier_status"] in {"completed", "not_run", "failed_to_run"},
            "invalid verifier state",
        )
        require(
            row["boundary_violation"]
            is (None if row["boundary_preserved"] is None else not row["boundary_preserved"]),
            "boundary flags disagree",
        )
        require(
            row["valid_completion"]
            is (row["raw_valid_completion"] if row["runtime_identity_verified"] or row["timed_out"] else None)
            and row["functional_success"]
            is (row["raw_functional_success"] if row["runtime_identity_verified"] else None),
            "runtime eligibility projection differs",
        )
        require(not row["timed_out"] or row["raw_valid_completion"] is False, "timeout must fail completion")
        if not row["runtime_identity_verified"]:
            require(
                row["unsupported_success"] is None and row["incorrect_refusal"] is None
                and all(row[name] is None for name in ('response_contract_valid', 'check_claims_supported', 'semantic_response_assessable', 'semantic_failure_evidence_valid')),
                "ineligible execution cannot establish secondary outcomes",
            )
        if row["valid_completion"] is True:
            require(
                all(
                    row[key] is True
                    for key in (
                        "functional_success",
                        "boundary_preserved",
                        "claims_supported",
                        "response_contract_valid",
                        "check_claims_supported",
                        "semantic_response_assessable",
                        "lifecycle_verified",
                    )
                )
                and row["verifier_status"] == "completed"
                and not row["timed_out"],
                "successful completion contradicts typed evidence",
            )
        require(
            ("missing_reason" in row) is (row["valid_completion"] is None),
            "missing reason differs from raw completion",
        )
        if "missing_reason" in row:
            require(
                row["missing_reason"]
                in {
                    "required_evidence_unavailable",
                    "docker_inspection_before_container_creation",
                    "unresolved_required_evidence",
                },
                "nonpublic missing reason",
            )
    hashes = {
        "start_sha256",
        "final_sha256",
        "grade_sha256",
        "usage_sha256",
        "failure_sha256",
        "retry_sha256",
    }
    for row in inputs["ledger"]:
        shape(row, {"trial_id", "registration_sha256", "state", "attempts"})
        trial(row["trial_id"])
        sha_value(row["registration_sha256"])
        require(
            type(row["state"]) is str and row["state"] in {"finalized", "unfinalized", "unstarted"},
            "invalid trial state",
        )
        require(type(row["attempts"]) is list, "attempt roster must be a list")
        for attempt in row["attempts"]:
            shape(attempt, {"attempt", "state"}, hashes)
            number(attempt["attempt"])
            require(
                type(attempt["state"]) is str and attempt["state"] in {"finalized", "unfinalized"},
                "invalid attempt state",
            )
            for name in set(attempt) & hashes:
                sha_value(attempt[name])
            require("start_sha256" in attempt, "retained attempt start seal missing")
            if attempt["state"] == "finalized":
                require(
                    {"final_sha256", "grade_sha256", "usage_sha256"} <= set(attempt),
                    "finalized attempt seals missing",
                )
    for attempt in inputs["attempts"]:
        shape(attempt, {"trial_id", "attempt", "usage"})
        trial(attempt["trial_id"])
        number(attempt["attempt"])
        validate_usage(attempt["usage"])
        allowed_agent_reasons = {
            "partial_native_record",
            "owned_turn_start_missing",
            "owned_turn_end_missing",
            "owned_turn_aborted",
            "owned_turns_missing",
            "owned_turn_usage_missing",
            "owned_response_usage_missing",
        }
        for agent in attempt["usage"]["agents"]:
            require(
                all(type(reason) is str and reason in allowed_agent_reasons for reason in agent["reasons"]),
                "nonpublic native accounting reason",
            )
    for item in inputs["controller_timings"]:
        shape(item, {"trial_id", "attempt", "controller_wall_seconds"})
        trial(item["trial_id"])
        number(item["attempt"])
        value = item["controller_wall_seconds"]
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "invalid duration")
    for item in inputs["stopped_policy_projections"]:
        shape(item, {"trial_id", "valid_completion", "policies"})
        trial(item["trial_id"])
        tri(item["valid_completion"])
        shape(item["policies"], {"U", "M", "G"})
        for name, decision in item["policies"].items():
            shape(decision, {"accepted", "decision"} if name == "G" else {"accepted"})
            require(type(decision["accepted"]) is bool, "acceptance must be boolean")
            if name == "G":
                shape(decision["decision"], {"status"})
                status = decision["decision"]["status"]
                require(
                    type(status) is str
                    and status in {"ACCEPTED", "BLOCKED", "UNVERIFIED", "UNSUPPORTED", "FAILED"},
                    "invalid kernel status",
                )
                require(decision["accepted"] is (status == "ACCEPTED"), "kernel acceptance/status mismatch")


def validate_receipt(receipt):
    required = {
        "schema_version",
        "mechanism_claim_allowed",
        "larger_benchmark_authorized",
        "upgrade_claim_allowed",
        "source_hashes",
        "registration_artifact",
        "registration_sha256",
        "report_sha256",
        "report_canonical_sha256",
        "controls_passed",
    }
    optional = {"preservation_manifest_sha256", "endpoint_audit_sha256", "native_replay_review_sha256"}
    shape(receipt, required, optional)
    require(receipt["schema_version"] == "evalopt.v4-difficulty-publication.v1", "unknown receipt schema")
    require(
        receipt["upgrade_claim_allowed"] is False
        and receipt["mechanism_claim_allowed"] is False
        and receipt["larger_benchmark_authorized"] is False
        and receipt["controls_passed"] is True,
        "invalid difficulty scope or controls",
    )
    for key in ({"registration_sha256", "report_sha256", "report_canonical_sha256"} | optional) & set(
        receipt
    ):
        sha_value(receipt[key])
    require(type(receipt["source_hashes"]) is dict, "invalid source inventory")
    for key, value in receipt["source_hashes"].items():
        require(type(key) is str, "invalid source path")
        sha_value(value)
    require(
        type(receipt["registration_artifact"]) is str
        and receipt["registration_artifact"].startswith("results/skill-workflows-v4/")
        and receipt["registration_artifact"].endswith("/registration.json"),
        "invalid registration artifact",
    )


def require_runtime():
    require(
        platform.python_implementation() == "CPython" and sys.version_info[:3] == (3, 13, 12),
        "CPython 3.13.12 required",
    )
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode is True, "run with -I -B")


def flat_inventory(bundle):
    require(bundle.is_dir() and not bundle.is_symlink(), "bundle must be a real directory")
    entries = list(bundle.iterdir())
    require(
        all(stat.S_ISREG(p.lstat().st_mode) for p in entries),
        "public bundle must contain regular files only; directories and links are forbidden",
    )
    return {p.name for p in entries}


def rebuild(registration, inputs, *, expected_pin, controls_passed):
    # Callers must pin these exact pure source files before importing this module
    # into a public replay process. No candidate code or private logs are loaded.
    from evalopt_v4.analysis import reconcile, report
    from evalopt_v4.descriptive import kernel_metrics, resources
    from evalopt_v4.registration import validate_registration

    validate_registration(registration, expected_sha256=expected_pin)
    require(
        registration["stage"] == "difficulty" and len(registration["schedule"]) == 16,
        "bounded sixteen-row difficulty screen only",
    )
    require(all(row["arm"] == "B" for row in registration["schedule"]), "upstream-only screen")
    require(controls_passed is True, "frozen replay requires controls passed")
    validate_inputs(registration, inputs)
    require(inputs["registration_sha256"] == expected_pin, "wrong round")
    schedule = registration["schedule"]
    ledger = inputs["ledger"]
    require(
        [x["trial_id"] for x in ledger] == [x["trial_id"] for x in schedule], "ledger differs from schedule"
    )
    expected_attempts = []
    finalized_ids = []
    unfinished_ids = []
    phase = "finalized"
    sealed_attempts = set()
    for row in ledger:
        require(row["registration_sha256"] == expected_pin, "cross-round ledger")
        state = row["state"]
        require(state in {"finalized", "unfinalized", "unstarted"}, "unknown ledger state")
        attempts = row["attempts"]
        if state == "unstarted":
            require(not attempts, "unstarted row has attempts")
            phase = "unstarted"
            continue
        require(phase == "finalized", "execution beyond the first unfinished/unstarted row")
        require(1 <= len(attempts) <= 2, "attempt count outside frozen retry limit")
        require([a["attempt"] for a in attempts] == list(range(1, len(attempts) + 1)), "attempt gap")
        require(all(a["state"] == "finalized" for a in attempts[:-1]), "retry before prior finalization")
        require(all("retry_sha256" in a for a in attempts[:-1]), "retry authorization seal missing")
        require(attempts[-1]["state"] == state, "row/latest-attempt mismatch")
        for attempt in attempts:
            key = (row["trial_id"], attempt["attempt"])
            expected_attempts.append(key)
            if attempt["state"] == "finalized":
                sealed_attempts.add(key)
        if state == "finalized":
            finalized_ids.append(row["trial_id"])
        else:
            unfinished_ids.append(row["trial_id"])
            phase = "unfinalized"
    rows = inputs["rows"]
    require([r["trial_id"] for r in rows] == finalized_ids, "outcomes differ from finalized rows")
    attempts = inputs["attempts"]
    require(
        [(a["trial_id"], a["attempt"]) for a in attempts] == expected_attempts,
        "missing or duplicated retained attempt",
    )
    for attempt in attempts:
        if (attempt["trial_id"], attempt["attempt"]) not in sealed_attempts:
            from evalopt_v4.accounting import derive_usage

            require(
                strict_equal(attempt["usage"], derive_usage({})), "unsealed usage must remain unavailable"
            )
    stopped = inputs["stopped_policy_projections"]
    require([r["trial_id"] for r in stopped] == finalized_ids, "policy roster differs from final rows")
    raw = {r["trial_id"]: r["valid_completion"] for r in rows}
    require(
        all(r["valid_completion"] is raw[r["trial_id"]] for r in stopped),
        "policy labels differ from raw outcome",
    )
    resolved = reconcile(registration["tasks"], rows, "difficulty")
    adjusted = {r["trial_id"]: r["reported_valid_completion"] for r in resolved}
    # Match frozen campaign.kernel_ground_truth: disputes apply across all arms
    # and to hidden labels in secondary acceptance-policy comparisons.
    policy_rows = [
        {**r, "raw_valid_completion": r["valid_completion"], "valid_completion": adjusted[r["trial_id"]]}
        for r in stopped
    ]
    timing = inputs["controller_timings"]
    seen_timing = set()
    total_seconds = 0
    for item in timing:
        key = (item["trial_id"], item["attempt"])
        require(key in sealed_attempts and key not in seen_timing, "unsealed or duplicate controller timing")
        seen_timing.add(key)
        value = item["controller_wall_seconds"]
        require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "invalid duration")
        total_seconds += value
    require(
        [(item["trial_id"], item["attempt"]) for item in timing]
        == [key for key in expected_attempts if key in seen_timing],
        "timing differs from frozen accumulation order",
    )
    result = report(registration["tasks"], rows, registration_record=registration)
    result.update(
        resources=resources(schedule, attempts),
        kernel=kernel_metrics(policy_rows),
        registration_sha256=expected_pin,
        retained_attempts=len(attempts),
        finalized_rows=len(rows),
        unfinalized_trials=unfinished_ids,
        controller_time={
            "observed_seconds": total_seconds if timing else None,
            "known_attempts": len(timing),
            "retained_attempts": len(attempts),
            "scope": "setup_agent_capture_visible_and_hidden_verification",
        },
    )
    return result


def within(root, relative):
    require(
        isinstance(relative, str)
        and relative
        and not Path(relative).is_absolute()
        and ".." not in Path(relative).parts,
        "invalid public relative path",
    )
    path = root / relative
    require(path.resolve() == path.absolute() and path.is_file(), "missing or indirect public file")
    return path


def main():
    require_runtime()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    bundle, repo = args.bundle.absolute(), args.repo.absolute()
    require(bundle.resolve() == bundle and repo.resolve() == repo, "indirect bundle/repository root")
    inventory = flat_inventory(bundle)
    checksums = read(bundle / "checksums.json")
    require(
        type(checksums) is dict and set(checksums) == inventory - {"checksums.json"},
        "public roster differs from checksum inventory",
    )
    for name, expected in checksums.items():
        sha_value(expected)
        require(
            Path(name).name == name and sha(within(bundle, name)) == expected, "public byte checksum differs"
        )
    receipt = read(bundle / "receipt.json")
    validate_receipt(receipt)
    required = {
        f"bench/harbor/skill-workflows-v4/evalopt_v4/{name}"
        for name in (
            "__init__.py",
            "accounting.py",
            "analysis.py",
            "descriptive.py",
            "records.py",
            "registration.py",
            "framing.py",
        )
    }
    require(set(receipt["source_hashes"]) == required, "incomplete or extra replay source roster")
    for name, expected in receipt["source_hashes"].items():
        require(sha(within(repo, name)) == expected, "frozen pure analysis source changed")
    package = repo / "bench/harbor/skill-workflows-v4/evalopt_v4"
    require(
        not any(p.name == "__pycache__" or p.suffix in {".pyc", ".pyo"} for p in package.rglob("*")),
        "unregistered executable bytecode",
    )
    # Import only the declared seven-file dependency closure. Never add the
    # repository/harness itself to sys.path: an unpinned adjacent module could
    # otherwise shadow a stdlib dependency before arithmetic starts.
    with tempfile.TemporaryDirectory(prefix="evalopt-public-pure-") as temporary:
        import_root = Path(temporary)
        copied_package = import_root / "evalopt_v4"
        copied_package.mkdir()
        for name, expected in receipt["source_hashes"].items():
            original = within(repo, name)
            raw = original.read_bytes()
            require(hashlib.sha256(raw).hexdigest() == expected, "source changed while copying")
            copied = copied_package / Path(name).name
            copied.write_bytes(raw)
            require(sha(copied) == expected and sha(original) == expected, "pure copy identity differs")
        sys.path.insert(0, str(import_root))
        try:
            from evalopt_v4.records import digest

            registration = read(within(repo, receipt["registration_artifact"]))
            report = read(bundle / "report.json")
            require(
                sha(bundle / "report.json") == receipt["report_sha256"]
                and digest(report) == receipt["report_canonical_sha256"],
                "retained native report changed",
            )
            result = rebuild(
                registration,
                read(bundle / "inputs.json"),
                expected_pin=receipt["registration_sha256"],
                controls_passed=receipt["controls_passed"],
            )
            require(strict_equal(result, report), "public projection does not reproduce native frozen report")
        finally:
            sys.path.remove(str(import_root))
    print(
        json.dumps(
            {
                "status": "PASS",
                "finalized_rows": result["finalized_rows"],
                "retained_attempts": result["retained_attempts"],
                "unknown_outcomes": sum(
                    r["reported_valid_completion"] is None for r in result["scheduled_rows"]
                ),
                "gate": result["gate"],
                "scope": "public projection consistency only; no candidate execution or live replication",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
