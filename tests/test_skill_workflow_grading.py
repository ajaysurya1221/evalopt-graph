"""Retained hidden replies permit grade replay without exposing expected values to candidates."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
from runtime.verify import collect_grade, strict_json  # noqa: E402
from tasks.suite import evaluate_cases, grade_snapshot, load_task, task_path  # noqa: E402


def inputs():
    task = load_task("duration-parser")
    response = json.loads((task_path(task) / "controls.json").read_text())["positive_response"]
    config = {
        "initial_manifest": {"duration.py": "old", "verify.py": "unchanged"},
        "observations": [{"command": task["visible_check"], "outcome": "passed", "source": "controller"}],
        "unsafe_snapshot": False,
    }
    stopped = {"duration.py": "new", "verify.py": "unchanged", "response.json": "response"}
    return task, config, stopped, response


def test_retained_case_replies_reproduce_grade_without_candidate_execution():
    task, config, stopped, response = inputs()
    cases = iter(json.loads((task_path(task) / "hidden_cases.json").read_text()))

    def oracle_reply(request):
        case = next(cases)
        assert set(request) == {"module", "function", "args"}
        assert request["args"] == case["args"]
        key = "error" if "raises" in case else "result"
        return {key: case.get("raises") if key == "error" else case["result"], "args": request["args"]}

    retained = collect_grade(task, config, stopped, response, oracle_reply)
    evidence = retained.pop("reproduction_inputs")
    assert retained["valid_completion"] is True
    records = iter(evidence["hidden_case_records"])

    def replay(request):
        record = next(records)
        assert request == record["request"]
        return record["actual"]

    hidden = evaluate_cases(task, replay)
    assert list(records) == []
    assert hidden is evidence["hidden_test_passed"] is True
    assert (
        grade_snapshot(
            task,
            evidence["initial_manifest"],
            evidence["stopped_manifest"],
            evidence["response"],
            evidence["observations"],
            hidden_test_passed=hidden,
        )
        == retained
    )


@pytest.mark.parametrize("actual", [None, [], {"result": 42, "args": ["0s"]}])
def test_failed_or_malformed_hidden_reply_is_retained(actual):
    task, config, stopped, response = inputs()
    grade = collect_grade(task, config, stopped, response, lambda _: actual)
    evidence = grade["reproduction_inputs"]
    assert grade["valid_completion"] is False
    assert evidence["hidden_test_passed"] is False
    assert evidence["hidden_case_records"] == [
        {"request": {"module": "duration", "function": "parse", "args": ["0s"]}, "actual": actual}
    ]


@pytest.mark.parametrize("error", [ValueError("malformed output"), subprocess.TimeoutExpired("child", 5)])
def test_invocation_failure_has_explicit_replay_record(error):
    task, config, stopped, response = inputs()

    def failed(_):
        raise error

    grade = collect_grade(task, config, stopped, response, failed)
    record = grade["reproduction_inputs"]["hidden_case_records"][0]
    assert record["error"] == "candidate_invocation_failed"
    assert "actual" not in record
    assert grade["valid_completion"] is False


def test_unsafe_snapshot_never_executes_hidden_candidate():
    task, config, stopped, response = inputs()
    config["unsafe_snapshot"] = True

    def forbidden(_):
        pytest.fail("unsafe candidate was executed")

    grade = collect_grade(task, config, stopped, response, forbidden)
    assert grade["reproduction_inputs"]["hidden_case_records"] == []
    assert grade["reproduction_inputs"]["hidden_test_passed"] is False


def test_invocation_mutation_cannot_rewrite_retained_request():
    task, config, stopped, response = inputs()

    def mutate(request):
        request["args"].append("injected")
        return {"result": 0, "args": request["args"]}

    grade = collect_grade(task, config, stopped, response, mutate)
    record = grade["reproduction_inputs"]["hidden_case_records"][0]
    assert record["request"]["args"] == ["0s"]
    assert record["actual"]["args"] == ["0s", "injected"]
    assert grade["valid_completion"] is False


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_hidden_reply_is_a_retained_failure_not_a_store_error(value):
    task, config, stopped, response = inputs()
    grade = collect_grade(
        task, config, stopped, response, lambda request: {"result": value, "args": request["args"]}
    )
    assert grade["valid_completion"] is False
    assert grade["reproduction_inputs"]["hidden_case_records"][0]["error"] == "candidate_invocation_failed"
    json.dumps(grade, allow_nan=False)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_nonfinite_candidate_json_is_rejected(value):
    with pytest.raises(ValueError, match="nonfinite"):
        strict_json('{"result": ' + value + "}")


def test_overflowing_json_float_cannot_enter_canonical_evidence():
    with pytest.raises(ValueError):
        strict_json('{"result": 1e999}')
