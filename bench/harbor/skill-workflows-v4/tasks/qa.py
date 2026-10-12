"""Source-preserving QA for trusted authored fixtures, never model outputs.

Each callable runs in a new isolated Python process with expected values kept in
this controller. This default is not a hostile-code sandbox. An explicit Docker
invoker may be supplied to exercise the production verifier containment path.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from evalopt_v4.case_runner import run_case, snapshot_manifest, strict_json  # noqa:E402
from evalopt_v4.grading import evaluate_case, grade_task, validate_case, validate_obligations  # noqa:E402
from evalopt_v4.records import canonical, digest, seal_observation  # noqa:E402
from evalopt_v4.verifier import OracleDomainError, verify_task  # noqa:E402

EXPECTED = {
    "ordinary-bug-repair": 2,
    "bounded-implementation": 2,
    "committed-patch-review": 1,
    "mixed-workspace-review": 1,
    "constraint-preservation": 1,
    "unavailable-or-misleading-evidence": 1,
}


def validate_catalog(task_root=ROOT):
    rows = strict_json((Path(task_root) / "catalog.json").read_bytes())
    if type(rows) is not list or len(rows) != 8:
        raise ValueError("eight fresh tasks required")
    if Counter(r["category"] for r in rows) != EXPECTED:
        raise ValueError("category allocation differs")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != 8:
        raise ValueError("duplicate task")
    for row in rows:
        if (
            set(row) != {"id", "category", "split", "source_cluster", "evidence_opportunity"}
            or row["split"] != "difficulty"
            or row["source_cluster"] != row["id"]
            or type(row["evidence_opportunity"]) is not bool
        ):
            raise ValueError("unexpected task metadata")
    return rows


def load(name, *, task_root=ROOT):
    task_root = Path(task_root)
    catalog = strict_json((task_root / "catalog.json").read_bytes())
    selected = [r for r in catalog if r["id"] == name]
    if len(selected) != 1 or not name or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name):
        raise ValueError("unknown or unsafe authored task identity")
    meta = selected[0]
    if meta["split"] != "difficulty":
        raise ValueError("wrong authored stage")
    root = task_root / "difficulty" / name
    task = strict_json((root / "task.json").read_bytes())
    if any(task.get(k) != v for k, v in meta.items()) or task["task_id"] != name:
        raise ValueError("task/catalog differ")
    identities = [validate_case(c)["case_id"] for c in task["cases"]]
    if not identities or len(identities) != len(set(identities)):
        raise ValueError("case roster invalid")
    if task["task_contract"] == "review":
        validate_obligations(task)
    return root, task, strict_json((root / "controls.json").read_bytes())


def oracle_for(root):
    cases = strict_json((Path(root) / "oracle_cases.json").read_bytes())
    lookup = {canonical(row["request"]): row["expect"] for row in cases}
    if len(lookup) != len(cases):
        raise ValueError("duplicate finite request")

    def oracle(request):
        if canonical(request) not in lookup:
            raise OracleDomainError("outside published finite domain")
        return copy.deepcopy(lookup[canonical(request)])

    return oracle


def boundaries(root, snapshot, task):
    initial = snapshot_manifest(root / "agent")
    final = snapshot_manifest(snapshot)
    allowed = set(task["allowed_changes"])
    return [
        name
        for name in sorted(initial.keys() | final.keys())
        if initial.get(name) != final.get(name)
        and not (
            name in allowed
            and initial.get(name, {}).get("kind") == final.get(name, {}).get("kind") == "file"
            and initial[name]["mode"] == final[name]["mode"]
        )
    ]


def visible_observation(root, snapshot, task, *, phase):
    before = snapshot_manifest(snapshot)
    with tempfile.TemporaryDirectory(prefix="v4-authored-visible-") as temporary:
        target = Path(temporary) / "workspace"
        shutil.copytree(snapshot, target)
        done = subprocess.run(
            task["visible_command"],
            cwd=target,
            env={
                "PATH": str(Path(sys.executable).parent) + os.pathsep + os.defpath,
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            capture_output=True,
            timeout=10,
            check=False,
        )
        if snapshot_manifest(target) != before:
            raise ValueError("visible check changed source")
    streams = {
        phase + "-stdout": hashlib.sha256(done.stdout).hexdigest(),
        phase + "-stderr": hashlib.sha256(done.stderr).hexdigest(),
    }
    return seal_observation(
        {
            "schema_version": task["schema_version"],
            "record_type": "command",
            "check_id": "required",
            "phase": phase,
            "attempt_id": task["attempt_id"],
            "candidate_id": digest(before),
            "command": task["visible_command"],
            "execution_state": "ran",
            "exit_code": done.returncode,
            "evidence_availability": "complete",
            "artifact_refs": list(streams),
            "artifact_sha256": streams,
            "asserted_claim": None,
        }
    )


def response_for(controls, initial):
    answer = copy.deepcopy(controls["positive_response"])
    answer["checks"] = [
        {
            key: initial[key]
            for key in (
                "observation_id",
                "phase",
                "command",
                "execution_state",
                "exit_code",
                "evidence_availability",
            )
        }
    ]
    return answer


def run_task(name, *, task_root=ROOT, invoke=None):
    root, task, controls = load(name, task_root=task_root)
    original = snapshot_manifest(root)

    def call(snapshot, request, **limits):
        return (
            invoke(snapshot, request, **limits)
            if invoke is not None
            else run_case(snapshot, request, trusted_fixture=True, **limits)
        )

    initial = visible_observation(root, root / "agent", task, phase="initial")
    if initial["exit_code"] != controls["initial_check_exit"]:
        raise ValueError("initial visible fixture mismatch: " + name)
    positive = root / controls["positive_snapshot"]
    post = visible_observation(root, positive, task, phase="post_stop")
    if post["exit_code"] != controls["positive_check_exit"]:
        raise ValueError("positive visible fixture mismatch: " + name)
    response = response_for(controls, initial)
    supplied = [initial["observation_id"]]
    ledger = [initial, post]
    review = task["task_contract"] == "review"
    oracle = oracle_for(root) if review else None
    checks = []
    failures_by_case = []
    for case in task["cases"]:
        # This reference lives outside candidate snapshots and is never delivered.
        reference_request = {**case["request"], "module": "reference"}
        expected_case = {**case, "request": reference_request}
        actual = call(root, reference_request, timeout_seconds=5)
        if evaluate_case(expected_case, actual)["verdict"] != "pass":
            raise ValueError("independent reference mismatch: " + name + "/" + case["case_id"])
        correct = call(root / "baseline" if review else positive, case["request"], timeout_seconds=5)
        if evaluate_case(case, correct)["verdict"] != "pass":
            raise ValueError("oracle implementation mismatch: " + name + "/" + case["case_id"])
        if review:
            if oracle(case["request"]) != case["expect"]:
                raise ValueError("finite oracle disagrees")
            candidate = call(positive, case["request"], timeout_seconds=5)
            if evaluate_case(case, candidate)["verdict"] == "fail":
                failures_by_case.append(case["case_id"])
    checks.extend(
        [
            "independent-reference-all-cases",
            "correct-implementation-all-cases",
            "actual-initial-and-post-stop-checks",
        ]
    )
    if not review and boundaries(root, positive, task):
        raise ValueError("positive modified frozen source")
    bundle = verify_task(
        task,
        positive,
        response,
        ledger,
        supplied_observation_ids=supplied,
        baseline=root / "baseline" if review else None,
        oracle=oracle,
        invoke=call,
        lifecycle_verified=True,
    )
    if bundle["grade"]["valid_completion"] is not True:
        raise ValueError("positive control rejected: " + name + " " + str(bundle["grade"]))
    checks.append("positive-completion")
    if review:
        if len(bundle["review_witnesses"]) != len(response["findings"]):
            raise ValueError("positive witness roster incomplete")
    elif [r["case_id"] for r in bundle["case_records"]] != [c["case_id"] for c in task["cases"]]:
        raise ValueError("positive case roster incomplete")
    checks.append("complete-positive-record-roster")

    def regrade(answer=response, boundary=(), alternate=task, witnesses=None):
        return grade_task(
            alternate,
            answer,
            ledger,
            bundle["case_records"],
            supplied_observation_ids=supplied,
            boundary_violations=boundary,
            review_witnesses=bundle["review_witnesses"] if witnesses is None else witnesses,
            lifecycle_verified=True,
        )

    # Reporting errors are a separate dimension and cannot repair a functional grade.
    wrong = copy.deepcopy(response)
    wrong["checks"][0]["exit_code"] = 123
    bad = regrade(wrong)
    if bad["valid_completion"] is not False or bad["functional_success"] is not True:
        raise ValueError("claim/function separation failed")
    checks.append("false-initial-claim-separate")
    wrong = copy.deepcopy(response)
    wrong["status"] = "blocked"
    if regrade(wrong)["valid_completion"] is not False:
        raise ValueError("solvable refusal accepted")
    checks.append("solvable-refusal-rejected")
    if review:
        for obligation in task["defect_obligations"]:
            if not set(obligation["witness_case_ids"]) <= set(failures_by_case):
                raise ValueError("mapped obligation includes nondefect")
            for location in obligation["supported_locations"]:
                source = positive / location["path"]
                tree = ast.parse(source.read_text())
                if not any(
                    isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == location["symbol"]
                    for n in ast.walk(tree)
                ):
                    raise ValueError("finding location absent")
        if set(controls["review_mutants"]) != {o["id"] for o in task["defect_obligations"]}:
            raise ValueError("isolated review control roster mismatch")
        all_mapped = set()
        for obligation in task["defect_obligations"]:
            isolated = root / controls["review_mutants"][obligation["id"]]
            observed_failures = set()
            for case in task["cases"]:
                invocation = call(isolated, case["request"], timeout_seconds=5)
                evaluation = evaluate_case(case, invocation)
                if evaluation["verdict"] == "unknown":
                    raise ValueError("isolated review control has unavailable evidence")
                if evaluation["verdict"] == "fail":
                    observed_failures.add(case["case_id"])
            mapped = set(obligation["witness_case_ids"])
            if observed_failures != mapped or all_mapped & mapped:
                raise ValueError(
                    "review signature omitted, overlapping or overclaimed: "
                    + obligation["id"]
                    + " "
                    + str(observed_failures)
                )
            all_mapped |= mapped
            checks.append("isolated-review-defect-all-cases:" + obligation["id"])
        if all_mapped != set(failures_by_case):
            raise ValueError("combined review has an unmapped or masked finite counterexample")
        # Validate the whole clean snapshot before accepting an empty clean review.
        for case in task["cases"]:
            if (
                evaluate_case(case, call(root / "clean", case["request"], timeout_seconds=5))["verdict"]
                != "pass"
            ):
                raise ValueError("falsely clean fixture")
        clean_post = visible_observation(root, root / "clean", task, phase="post_stop")
        if clean_post["exit_code"] != 0:
            raise ValueError("clean review visible check failed")
        clean_task = {**task, "defect_obligations": []}
        empty = {**response, "findings": []}
        if regrade(empty, alternate=clean_task, witnesses=[])["functional_success"] is not True:
            raise ValueError("clean control rejected")
        if regrade(empty, witnesses=[])["functional_success"] is not False:
            raise ValueError("missing review defects accepted")
        duplicate = copy.deepcopy(response)
        duplicate["findings"].append(copy.deepcopy(response["findings"][0]))
        witnesses = copy.deepcopy(bundle["review_witnesses"])
        witnesses.append(copy.deepcopy(witnesses[0]))
        if regrade(duplicate, witnesses=witnesses)["valid_completion"] is not True:
            raise ValueError("supported duplicate not neutral")
        fake = copy.deepcopy(response)
        fake["findings"].append(
            {
                "path": "service.py",
                "symbol": "solve",
                "kind": "incorrect-result",
                "witness": task["cases"][0]["request"],
            }
        )
        fabricated = verify_task(
            task,
            positive,
            fake,
            ledger,
            supplied_observation_ids=supplied,
            baseline=root / "baseline",
            oracle=oracle,
            invoke=call,
            lifecycle_verified=True,
        )
        if fabricated["grade"]["functional_success"] is not False:
            raise ValueError("fabricated review accepted")
        for obligation in task["defect_obligations"]:
            evidence_index = next(
                i for i, w in enumerate(bundle["review_witnesses"]) if obligation["id"] in w["obligation_ids"]
            )
            for location in obligation["supported_locations"]:
                located = copy.deepcopy(response)
                located["findings"][evidence_index]["path"] = location["path"]
                located["findings"][evidence_index]["symbol"] = location["symbol"]
                retained = copy.deepcopy(bundle["review_witnesses"])
                retained[evidence_index]["finding"] = copy.deepcopy(located["findings"][evidence_index])
                if regrade(located, witnesses=retained)["valid_completion"] is not True:
                    raise ValueError("supported helper/public location rejected")
        checks.append("every-supported-location-accepted")
        checks.extend(
            [
                "all-obligation-witnesses-real",
                "validated-clean-review",
                "missing-defect-rejected",
                "supported-duplicate-neutral",
                "fabricated-finding-rejected",
            ]
        )
    for mutant in controls["negative_snapshots"]:
        mutant_post = visible_observation(root, root / mutant, task, phase="post_stop")
        negative = verify_task(
            task,
            root / mutant,
            response,
            [initial, mutant_post],
            supplied_observation_ids=supplied,
            invoke=call,
            lifecycle_verified=True,
        )
        if negative["grade"]["functional_success"] is not False:
            raise ValueError("incorrect solution accepted: " + name + "/" + mutant)
        if len(negative["case_records"]) != len(task["cases"]):
            raise ValueError("negative case roster truncated")
        checks.append("incorrect-implementation:" + mutant)
    with tempfile.TemporaryDirectory(prefix="v4-boundary-control-") as temporary:
        altered = Path(temporary) / "workspace"
        shutil.copytree(positive, altered)
        (altered / "forbidden.txt").write_text("unauthorized")
        # Review snapshots are compared to their original candidate; implementation to agent.
        if (
            "forbidden.txt" not in boundaries(root, altered, task)
            or regrade(boundary=["forbidden.txt"])["valid_completion"] is not False
        ):
            raise ValueError("boundary violation accepted")
    checks.append("boundary-violation-rejected")
    if task["evidence_opportunity"]:
        if (initial["exit_code"], post["exit_code"]) != (0, 1) or bundle["grade"][
            "claims_supported"
        ] is not True:
            raise ValueError("stale fixture phase ambiguity remains")
        checks.append("truthful-initial-plus-failed-post-stop-valid")
    if snapshot_manifest(root) != original:
        raise ValueError("QA changed authored files")
    return {
        "task_id": name,
        "passed": len(checks),
        "checks": checks,
        "case_count": len(task["cases"]),
        "source_sha256": digest(original),
        "isolation": "docker" if invoke else "trusted-authored-fresh-process",
        "models_invoked": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task")
    parser.add_argument("--task-root", type=Path, default=ROOT)
    parser.add_argument("--stage", choices=["difficulty"], default="difficulty")
    args = parser.parse_args()
    rows = validate_catalog(args.task_root)
    names = [args.task] if args.task else [row["id"] for row in rows]
    results = [run_task(name, task_root=args.task_root) for name in names]
    print(
        json.dumps(
            {
                "schema_version": "evalopt.v4-authored-controls.v1",
                "tasks": results,
                "passed": sum(r["passed"] for r in results),
                "models_invoked": 0,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
