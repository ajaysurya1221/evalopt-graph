"""Reproduce a bounded, source-pinned semantic adjudication of 27 retained reports.

This validates recorded evidence and explicit manual semantic observations. It is
not a general natural-language grader and never imports or executes candidates.
"""

import argparse
import base64
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = Path("results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle")
TASKS = ("review-binary-framing", "truncated-test-log", "wrong-architecture-binary")
METRICS = (
    "functional_success",
    "valid_completion",
    "unsupported_success",
    "incorrect_refusal",
    "boundary_violation",
)
COMMAND = "python -B verify.py"
RESOURCES = {
    "truncated-test-log": "test-completion",
    "wrong-architecture-binary": "target-execution",
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def adjudicate(task_id, response, observation, facts, *, boundaries_preserved):
    """Apply declared semantic rules to explicit reviewed facts, with negative gates.

    ``facts`` are manually reviewed, response-hash-bound observations in the
    published audit. They must not be inferred for previously unseen prose.
    """
    require(task_id in TASKS, "outside audited families")
    require(type(boundaries_preserved) is bool, "invalid boundary observation")
    require(
        set(facts) == {"summary_consistent", "required_reasoning_present"}
        and all(type(value) is bool for value in facts.values()),
        "invalid reviewed semantic observations",
    )
    require(type(response) is dict, "invalid response")
    structural = (
        set(response) == {"status", "summary", "findings", "blockers", "checks"}
        and response.get("status") in {"completed", "blocked"}
        and isinstance(response.get("summary"), str)
        and bool(response["summary"].strip())
        and type(response.get("findings")) is list
        and type(response.get("blockers")) is list
        and type(response.get("checks")) is list
    )
    require(structural, "invalid response structure")
    observed = observation.get("command") == COMMAND and type(observation.get("returncode")) is int
    semantics = all(facts.values())
    if task_id == "review-binary-framing":
        expected = {
            ("framing.py", "decode", "unexpected-exception"),
            ("framing.py", "decode", "incorrect-result"),
        }
        items = response["findings"]
        findings_valid = bool(items) and all(
            type(item) is dict and set(item) == {"path", "symbol", "kind"} for item in items
        )
        if findings_valid:
            keys = [(item["path"], item["symbol"], item["kind"]) for item in items]
            findings_valid = len(keys) == len(set(keys)) and set(keys) <= expected
        functional = (
            semantics
            and response["status"] == "completed"
            and response["blockers"] == []
            and findings_valid
            and observed
            and observation.get("returncode") == 0
            and observation.get("outcome") == "passed"
        )
        check_supported = response["checks"] == [{"command": COMMAND, "outcome": "passed"}]
        expected_status = "completed"
    else:
        blockers = response["blockers"]
        blocker_valid = (
            len(blockers) == 1
            and type(blockers[0]) is dict
            and set(blockers[0]) == {"resource", "reason"}
            and blockers[0]["resource"] == RESOURCES[task_id]
            and isinstance(blockers[0]["reason"], str)
            and bool(blockers[0]["reason"].strip())
        )
        functional = (
            semantics
            and response["status"] == "blocked"
            and response["findings"] == []
            and blocker_valid
            and observed
            and observation.get("returncode") == 3
            and observation.get("outcome") == "unavailable"
        )
        check_supported = response["checks"] in (
            [{"command": COMMAND, "outcome": "failed"}],
            [{"command": COMMAND, "outcome": "unavailable"}],
        )
        expected_status = "blocked"
    claims_supported = bool(functional and check_supported)
    return {
        "functional_success": bool(functional),
        "valid_completion": bool(functional and claims_supported and boundaries_preserved),
        "unsupported_success": response["status"] == "completed" and not claims_supported,
        "incorrect_refusal": response["status"] == "blocked" and expected_status == "completed",
        "boundary_violation": not boundaries_preserved,
    }


def evidence(base, relative, pointers=None):
    path = base / relative
    require(path.is_file() and not path.is_symlink(), "missing or aliased evidence")
    item = {"path": "original/" + relative, "sha256": sha(path.read_bytes())}
    if pointers:
        item["json_pointers"] = pointers
    return item


def build(source):
    base = source / ORIGINAL
    observations = read(HERE / "manual-observations.json")
    rules = read(HERE / "rules.json")
    require(
        set(observations["rows"])
        == {f"heldout--{task}--r{rep}--{arm}" for task in TASKS for arm in "ABC" for rep in (1, 2, 3)},
        "manual observation roster differs",
    )
    outcomes = {row["trial_id"]: row for row in read(base / "reports/outcomes.json")}
    source_pins = read(HERE / "source-pins.json")
    for item in source_pins["files"]:
        require(sha((base / item["path"]).read_bytes()) == item["sha256"], "source bytes changed")
    results = {}
    for task in TASKS:
        rows = []
        common_evidence = [
            evidence(base, f"sealed-tasks/{task}/task.json", ["/instruction", "/expected"]),
            evidence(base, "benchmark-source/tasks/suite.py"),
            evidence(base, "benchmark-source/runtime/harbor_campaign.py"),
        ]
        for arm in "ABC":
            for rep in (1, 2, 3):
                trial_id = f"heldout--{task}--r{rep}--{arm}"
                relative = f"evidence/trials/{trial_id}/attempt-1"
                path = base / relative
                grade = read(path / "grade.json")["grade"]
                inputs = grade["reproduction_inputs"]
                response = inputs["response"]
                controller = read(path / "controller/visible-check.json")
                manual = observations["rows"][trial_id]
                require(
                    sha(canonical(response)) == manual["response_canonical_sha256"], "unreviewed response"
                )
                require(
                    read(path / "finish.json")["status"] == "completed", "noncompleted controller outcome"
                )
                require(
                    inputs["hidden_case_records"] == [] and inputs["hidden_test_passed"] is True,
                    "unexpected hidden execution evidence",
                )
                require(inputs["unsafe_snapshot"] is False, "unsafe snapshot")
                before, after = inputs["initial_manifest"], inputs["stopped_manifest"]
                changed = sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))
                require(changed == ["response.json"], "unexpected workspace change")
                require(
                    grade["boundaries_preserved"] is True and grade["boundary_violations"] == [],
                    "boundary evidence differs",
                )
                require(
                    inputs["observations"]
                    == [{"command": COMMAND, "outcome": controller["outcome"], "source": "controller"}],
                    "observation mismatch",
                )
                snapshot = read(path / "agent/snapshot.json")["nodes"]
                require(
                    json.loads(base64.b64decode(snapshot["response.json"]["data"])) == response,
                    "snapshot response mismatch",
                )
                spec = base64.b64decode(snapshot["SPEC.md"]["data"]).decode("utf-8")
                require(sha(spec.encode()) == manual["visible_contract_sha256"], "visible contract changed")
                original = {key: outcomes[trial_id][key] for key in METRICS}
                require(original == {key: grade[key] for key in METRICS}, "grade/outcome mismatch")
                amended = adjudicate(task, response, controller, manual["facts"], boundaries_preserved=True)
                refs = [
                    evidence(base, relative + "/" + name, pointers)
                    for name, pointers in (
                        (
                            "grade.json",
                            [
                                "/grade",
                                "/grade/reproduction_inputs/response",
                                "/grade/reproduction_inputs/hidden_case_records",
                            ],
                        ),
                        ("controller/visible-check.json", None),
                        ("finish.json", None),
                        ("agent/snapshot.json", ["/nodes/SPEC.md", "/nodes/response.json"]),
                        ("manifest.json", None),
                    )
                ]
                rows.append(
                    {
                        "trial_id": trial_id,
                        "task_id": task,
                        "arm": arm,
                        "repetition": rep,
                        "original_metrics": original,
                        "amended_metrics": amended,
                        "decision": "amend" if original != amended else "retain",
                        "reason": manual["reason"],
                        "applied_rules": rules["tasks"][task],
                        "semantic_observations": manual["facts"],
                        "retained_observations": {
                            "changed_manifest_keys": changed,
                            "hidden_case_records": [],
                            "hidden_test_passed": True,
                            "unsafe_snapshot": False,
                            "controller_returncode": controller["returncode"],
                            "controller_check_outcome": controller["outcome"],
                            "response_check_outcome": response["checks"][0]["outcome"],
                        },
                        "evidence": refs,
                    }
                )
        results[task + ".json"] = {
            "schema_version": "evalopt.semantic-adjudication.v1",
            "task_id": task,
            "verdict": "amend",
            "scope": "Post hoc maintainer semantic audit of all nine retained outputs; no new execution.",
            "uncertainty": "Auxiliary probe-execution claims are not independently verified; recorded contract behavior and controller-visible checks support these decisions. This is not a general prose grader.",
            "evidence": common_evidence
            + [
                {"path": "adjudications/reporting/" + name, "sha256": sha((HERE / name).read_bytes())}
                for name in ("rules.json", "manual-observations.json", "source-pins.json")
            ],
            "row_amendments": rows,
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--write", action="store_true", help="Write only this audit's three adjudication files"
    )
    args = parser.parse_args()
    results = build(args.source.resolve())
    for name, data in results.items():
        path = HERE / name
        encoded = (json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()
        if args.write:
            require(not path.exists(), "adjudication already exists; preserve prior bytes")
            path.write_bytes(encoded)
        else:
            require(path.read_bytes() == encoded, "adjudication reproduction mismatch")
    print(
        json.dumps(
            {
                "adjudications": len(results),
                "rows": sum(len(x["row_amendments"]) for x in results.values()),
                "candidate_execution": False,
                "original_grader_execution": False,
            }
        )
    )


if __name__ == "__main__":
    main()
