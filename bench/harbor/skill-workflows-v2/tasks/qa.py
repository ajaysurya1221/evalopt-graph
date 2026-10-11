"""Offline conformance for repository-authored task fixtures, never live outputs.

The local fresh-process runner is not a sandbox. This module accepts only the
fixed authored task roster beside it or an explicitly selected authored root.
It is not a production candidate verification path.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BENCH))
from evalopt_v2.case_runner import run_case, snapshot_manifest, strict_json  # noqa: E402
from evalopt_v2.grading import evaluate_case, validate_case  # noqa: E402
from evalopt_v2.records import canonical, digest, validate_record  # noqa: E402
from evalopt_v2.registration import validate_tasks  # noqa: E402
from evalopt_v2.verifier import OracleDomainError, verify_task  # noqa: E402

ROOT = Path(__file__).resolve().parent


def load(name, *, task_root=ROOT):
    task_root = Path(task_root)
    catalog = strict_json((task_root / "catalog.json").read_bytes())
    selected = [item for item in catalog if item["id"] == name]
    if len(selected) != 1:
        raise ValueError("task must be a unique authored catalog member")
    metadata = selected[0]
    if (
        metadata["split"] not in {"development", "heldout"}
        or not name
        or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in name)
    ):
        raise ValueError("invalid authored task path")
    directory = task_root / metadata["split"] / name
    task = strict_json((directory / "task.json").read_bytes())
    if any(task.get(key) != value for key, value in metadata.items()):
        raise ValueError("task metadata differs from catalog")
    if task["task_id"] != name or task["visible_command"] != ["python3", "-B", "verify.py"]:
        raise ValueError("task identity or visible command differs")
    ids = [validate_case(case)["case_id"] for case in task["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case identity")
    controls = strict_json((directory / "controls.json").read_bytes())
    return directory, task, controls


def oracle_for(directory):
    rows = strict_json((directory / "oracle_cases.json").read_bytes())
    lookup = {}
    for index, item in enumerate(rows):
        if set(item) != {"request", "expect"}:
            raise ValueError("invalid finite oracle entry")
        validate_case({"case_id": str(index), **item, "preserve_args": True})
        key = canonical(item["request"])
        if key in lookup:
            raise ValueError("duplicate finite oracle request")
        lookup[key] = item["expect"]

    def oracle(request):
        key = canonical(request)
        if key not in lookup:
            raise OracleDomainError("request outside the visible finite domain")
        return copy.deepcopy(lookup[key])

    return oracle


def boundaries(directory, snapshot, task):
    before = snapshot_manifest(directory / "agent")
    after = snapshot_manifest(snapshot)
    allowed = set(task["allowed_changes"])
    failures = []
    for path in sorted(set(before) | set(after)):
        if path not in allowed and before.get(path) != after.get(path):
            failures.append(path)
        elif path in allowed and (
            before.get(path, {}).get("kind") != "file"
            or after.get(path, {}).get("kind") != "file"
            or before[path]["mode"] != after[path]["mode"]
        ):
            failures.append(path)
    return failures


def visible_observation(directory, snapshot, task, controls):
    """Actually execute the authored visible check in a disposable fixture copy."""
    before = snapshot_manifest(snapshot)
    with tempfile.TemporaryDirectory(prefix="evalopt-v2-task-smoke-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(snapshot, workspace)
        result = subprocess.run(
            task["visible_command"],
            cwd=workspace,
            env={
                "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            capture_output=True,
            timeout=10,
            check=False,
        )
        if snapshot_manifest(workspace) != before:
            raise ValueError("visible check modified its workspace")
    expected = controls["observed_check"]
    if result.returncode != expected["exit_code"]:
        raise ValueError(f"visible check exit differs: {directory.name}: {result.returncode}")
    record = {
        "schema_version": task["schema_version"],
        "record_type": "command",
        "attempt_id": task["attempt_id"],
        "candidate_id": digest(before),
        **expected,
        "artifact_refs": ["authored-visible-stdout", "authored-visible-stderr"],
        "asserted_claim": None,
    }
    validate_record(record)
    return record


def run_task(name, *, task_root=ROOT):
    directory, task, controls = load(name, task_root=task_root)
    before = snapshot_manifest(directory)
    snapshot = directory / controls["positive_snapshot"]
    observed = visible_observation(directory, snapshot, task, controls)
    response = controls["positive_response"]
    is_review = task["task_contract"] == "review"
    oracle = oracle_for(directory) if is_review else None
    checks = []

    def grade(root=snapshot, answer=response, violation=()):
        return verify_task(
            task,
            root,
            answer,
            [observed],
            baseline=directory / "baseline" if is_review else None,
            oracle=oracle,
            boundary_violations=violation,
            trusted_fixture=True,
            lifecycle_verified=True,
        )["grade"]

    if is_review:
        # A clean review is not proven by an empty response: exercise every
        # declared oracle input on both real source trees independently.
        candidate_verdicts = []
        for case in task["cases"]:
            if oracle(case["request"]) != case["expect"]:
                raise ValueError("finite oracle and task cases differ")
            baseline = run_case(directory / "baseline", case["request"], trusted_fixture=True)
            if evaluate_case(case, baseline)["verdict"] != "pass":
                raise ValueError("review baseline violates visible contract")
            candidate = run_case(snapshot, case["request"], trusted_fixture=True)
            candidate_verdicts.append(evaluate_case(case, candidate)["verdict"])
        if not task["defect_obligations"] and set(candidate_verdicts) != {"pass"}:
            raise ValueError("clean review candidate violates contract")
        if task["defect_obligations"] and "fail" not in candidate_verdicts:
            raise ValueError("review regression has no actual incorrect control")
        checks.extend(["finite-baseline-contract", "finite-candidate-contract"])
        mapped = [item for item in task["defect_obligations"] if "supported_locations" in item]
        if mapped:
            failures = {
                case["case_id"]
                for case, verdict in zip(task["cases"], candidate_verdicts, strict=True)
                if verdict == "fail"
            }
            for obligation in mapped:
                ids = obligation.get("witness_case_ids", [])
                if not ids or len(ids) != len(set(ids)) or not set(ids).issubset(failures):
                    raise ValueError("mapped witness does not demonstrate an actual regression")
            checks.append("mapped-witness-domain")
    elif task["task_contract"] == "implementation":
        for case in task["cases"]:
            invocation = run_case(snapshot, case["request"], trusted_fixture=True)
            if evaluate_case(case, invocation)["verdict"] != "pass":
                raise ValueError(f"oracle mismatch: {name}/{case['case_id']}")
        checks.append("every-oracle-case")

    if boundaries(directory, snapshot, task):
        raise ValueError("positive oracle changes frozen files")
    if grade()["valid_completion"] is not True:
        raise ValueError("positive control rejected")
    checks.extend(["positive-completion", "positive-boundaries", "actual-visible-check"])
    for negative in controls["negative_snapshots"]:
        outcome = grade(directory / negative)
        if outcome["functional_success"] is not False:
            raise ValueError(f"incorrect solution not rejected: {name}/{negative}")
        checks.append("negative-snapshot:" + negative)

    wrong = copy.deepcopy(response)
    wrong["checks"][0]["exit_code"] = 123
    if grade(answer=wrong)["valid_completion"] is not False:
        raise ValueError("false command claim accepted")
    checks.append("false-command-claim")
    wrong = copy.deepcopy(response)
    if is_review:
        wrong["findings"] = (
            []
            if task["defect_obligations"]
            else [
                {
                    "path": task["cases"][0]["request"]["module"] + ".py",
                    "symbol": "solve",
                    "kind": "incorrect-result",
                    "witness": task["cases"][0]["request"],
                }
            ]
        )
    else:
        wrong["status"] = "completed" if task["task_contract"] == "blocker_report" else "blocked"
    if grade(answer=wrong)["valid_completion"] is not False:
        raise ValueError("missed defect, false finding, false completion or refusal accepted")
    checks.append("negative-response")
    if task["task_contract"] == "blocker_report":
        wrong = copy.deepcopy(response)
        wrong["blockers"][0]["resource"] = "different-unavailable-resource"
        if grade(answer=wrong)["valid_completion"] is not False:
            raise ValueError("wrong blocker resource accepted")
        checks.append("wrong-blocker-resource")
    if is_review and response["findings"]:
        wrong = copy.deepcopy(response)
        wrong["findings"].append(
            {
                "path": task["cases"][0]["request"]["module"] + ".py",
                "symbol": "solve",
                "kind": "incorrect-result",
                "witness": task["cases"][0]["request"],
            }
        )
        if grade(answer=wrong)["valid_completion"] is not False:
            raise ValueError("extra unsupported review finding accepted")
        repeated = copy.deepcopy(response)
        repeated["findings"].append(copy.deepcopy(response["findings"][0]))
        if grade(answer=repeated)["valid_completion"] is not True:
            raise ValueError("duplicate supported consequence is not neutral")
        checks.extend(["extra-unsupported-finding", "duplicate-supported-neutral"])
    for index, helper_response in enumerate(controls.get("positive_helper_responses", [])):
        if not is_review or grade(answer=helper_response)["valid_completion"] is not True:
            raise ValueError("supported helper finding rejected")
        repeated = copy.deepcopy(response)
        repeated["findings"].extend(copy.deepcopy(helper_response["findings"]))
        if grade(answer=repeated)["valid_completion"] is not True:
            raise ValueError("entry and helper duplicate obligation coverage is not neutral")
        checks.extend([f"supported-helper:{index}", f"entry-helper-duplicate-neutral:{index}"])
    for index, location_response in enumerate(controls.get("unsupported_location_responses", [])):
        outcome = grade(answer=location_response)
        if not is_review or (
            outcome["functional_success"] is not False or outcome["valid_completion"] is not False
        ):
            raise ValueError("unrelated finding location accepted")
        checks.append(f"unrelated-location:{index}")
    with tempfile.TemporaryDirectory(prefix="evalopt-v2-boundary-") as temporary:
        altered = Path(temporary) / "workspace"
        shutil.copytree(snapshot, altered)
        (altered / "forbidden.txt").write_text("unexpected edit")
        violations = boundaries(directory, altered, task)
        if (
            "forbidden.txt" not in violations
            or grade(altered, violation=violations)["valid_completion"] is not False
        ):
            raise ValueError("new forbidden file not rejected")
    checks.append("boundary-violation")
    if snapshot_manifest(directory) != before:
        raise ValueError("authored QA mutated task sources")
    return {
        "task_id": name,
        "checks": checks,
        "passed": len(checks),
        "case_count": len(task["cases"]),
        "task_source_sha256": digest(before),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task")
    parser.add_argument(
        "--task-root",
        type=Path,
        default=ROOT,
        help="explicit trusted authored task root; never live candidate outputs",
    )
    parser.add_argument("--stage", choices=("development", "heldout"), default="development")
    args = parser.parse_args()
    catalog = strict_json((args.task_root / "catalog.json").read_bytes())
    selected = [row for row in catalog if row["split"] == args.stage]
    validate_tasks(selected, args.stage)
    if args.task and args.task not in {row["id"] for row in selected}:
        raise ValueError("selected task is outside selected stage")
    names = [args.task] if args.task else [row["id"] for row in selected]
    results = [run_task(name, task_root=args.task_root) for name in names]
    print(
        json.dumps(
            {
                "schema_version": "evalopt.v2-authored-controls.v1",
                "tasks": results,
                "passed": sum(row["passed"] for row in results),
                "models_invoked": 0,
                "isolation": "trusted-authored-fresh-process-controls",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
