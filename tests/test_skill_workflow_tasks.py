"""Offline public development controls; these are not live workflow results."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

TASKS = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1/tasks"
SPEC = importlib.util.spec_from_file_location("workflow_tasks", TASKS / "suite.py")
assert SPEC and SPEC.loader
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)

# Only authored fixture/oracle code executes locally in these controls. Live
# campaigns must supply the separate Docker callback described by evaluate_cases.
INVOKE = """
import importlib, json, sys
request = json.loads(sys.stdin.read())
sys.path.insert(0, sys.argv[1])
try:
    module = importlib.import_module(request["module"])
    result = getattr(module, request["function"])(*request["args"])
    response = {"result": result, "args": request["args"]}
except BaseException as exc:
    name = type(exc).__name__
    if type(exc).__module__ != "builtins":
        name = type(exc).__module__ + "." + name
    response = {"error": name, "args": request["args"]}
print(json.dumps(response, sort_keys=True))
"""


def invoke_fixture(snapshot, request):
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", INVOKE, str(snapshot)],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=5,
        check=True,
    )
    return json.loads(result.stdout)


def observe(task, snapshot):
    result = subprocess.run(
        [sys.executable, "-B", "verify.py"],
        cwd=snapshot,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
    )
    return [
        {
            "source": "controller",
            "command": task["visible_check"],
            "outcome": "passed"
            if result.returncode == 0
            else "unavailable"
            if result.returncode == 3
            else "failed",
        }
    ]


def setup_control(task_id, directory, oracle=True):
    task = suite.load_task(task_id)
    suite.materialize_agent(task, directory)
    initial = suite.file_manifest(directory)
    oracle_path = suite.task_path(task) / "oracle"
    if oracle and oracle_path.exists():
        shutil.copytree(oracle_path, directory, dirs_exist_ok=True)
    controls = json.loads((suite.task_path(task) / "controls.json").read_text())
    response = copy.deepcopy(controls["positive_response"])
    return task, initial, response, controls


def grade(task, initial, directory, response, observations=None):
    hidden = suite.evaluate_cases(task, lambda request: invoke_fixture(directory, request))
    return suite.grade_snapshot(
        task,
        initial,
        suite.file_manifest(directory),
        response,
        observe(task, directory) if observations is None else observations,
        hidden_test_passed=hidden,
    )


def test_development_has_two_distinct_tasks_per_category():
    tasks = [suite.load_task(task_id) for task_id in suite.task_ids()]
    assert len(tasks) == 12
    assert len({task["source_family"] for task in tasks}) == 12
    assert set(Counter(task["category"] for task in tasks).values()) == {2}
    for task in tasks:
        assert "response.json" in suite.instruction(task)
        assert "exactly one" in suite.instruction(task)
        assert (suite.task_path(task) / "controls.json").is_file()


@pytest.mark.parametrize("task_id", suite.task_ids())
def test_oracle_and_relevant_incorrect_controls(task_id, tmp_path):
    task, initial, response, controls = setup_control(task_id, tmp_path / "positive")
    assert grade(task, initial, tmp_path / "positive", response)["valid_completion"]
    assert controls["negative_controls"], "each task needs an incorrect control"
    for index, control in enumerate(controls["negative_controls"]):
        snapshot = tmp_path / f"negative-{index}"
        negative_task, baseline, candidate_response, _ = setup_control(
            task_id,
            snapshot,
            oracle=control["kind"] != "initial",
        )
        if control["kind"] == "response":
            candidate_response.update(control["replace"])
        elif control["kind"] == "edit":
            path = snapshot / control["path"]
            path.write_text(path.read_text() + control["append"])
        else:
            assert control["kind"] == "initial"
        assert not grade(negative_task, baseline, snapshot, candidate_response)["valid_completion"], control[
            "name"
        ]


def test_materializer_keeps_grading_files_outside_agent_context(tmp_path):
    task = suite.load_task("interval-union")
    suite.materialize_agent(task, tmp_path / "candidate")
    files = suite.file_manifest(tmp_path / "candidate")
    assert {name for name in files if not name.startswith("@git/")} == {"intervals.py", "verify.py"}
    assert {"@git/HEAD", "@git/config", "@git/index"} <= set(files)
    assert not any("oracle" in name or "hidden" in name or "controls" in name for name in files)
    with pytest.raises(ValueError, match="empty"):
        suite.materialize_agent(task, tmp_path / "candidate")


def test_mixed_review_preserves_staging_untracked_and_deleted_states(tmp_path):
    suite.materialize_agent(suite.load_task("review-mixed-limit"), tmp_path)
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True
    ).stdout
    assert "M  cli.py" in status
    assert " D tests/test_negative.py" in status
    assert "?? limits.py" in status
    assert (
        subprocess.run(
            ["git", "diff", "benchmark-base..HEAD", "--stat"],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        == ""
    )


def test_committed_review_has_a_real_committed_candidate(tmp_path):
    suite.materialize_agent(suite.load_task("review-line-normalizer"), tmp_path)
    diff = subprocess.run(
        ["git", "diff", "benchmark-base..HEAD", "--stat"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert "normalizer.py" in diff
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=tmp_path, capture_output=True, text=True, check=True
        ).stdout
        == ""
    )


@pytest.mark.parametrize(
    "failure",
    [
        "missing-hidden",
        "forged-observation",
        "duplicate-observation",
        "forged-claim",
        "invalid-response",
        "extra-file",
        "symlink",
    ],
)
def test_evidence_and_boundary_failures_reject(failure, tmp_path):
    task, initial, response, _ = setup_control("interval-union", tmp_path)
    observations = observe(task, tmp_path)
    hidden = True
    if failure == "missing-hidden":
        hidden = None
    elif failure == "forged-observation":
        observations[0]["source"] = "agent"
    elif failure == "duplicate-observation":
        observations.append(dict(observations[0]))
    elif failure == "forged-claim":
        response["checks"][0]["command"] = "cat passed.json"
    elif failure == "invalid-response":
        response["surprise"] = True
    elif failure == "extra-file":
        (tmp_path / "passed.json").write_text('{"status":"passed"}')
    elif failure == "symlink":
        (tmp_path / "verify.py").unlink()
        (tmp_path / "verify.py").symlink_to("intervals.py")
    result = suite.grade_snapshot(
        task, initial, suite.file_manifest(tmp_path), response, observations, hidden_test_passed=hidden
    )
    assert not result["valid_completion"]


def test_exit_zero_without_result_is_not_hidden_success(tmp_path):
    task, initial, response, _ = setup_control("interval-union", tmp_path)
    (tmp_path / "intervals.py").write_text("import os\nos._exit(0)\n")
    assert not suite.evaluate_cases(task, lambda request: invoke_fixture(tmp_path, request))


def test_hidden_expected_outputs_never_enter_invocation():
    requests = []

    def fake(request):
        requests.append(request)
        return {"result": "forged-success", "args": request["args"]}

    assert not suite.evaluate_cases(suite.load_task("interval-union"), fake)
    assert requests and all(set(request) == {"module", "function", "args"} for request in requests)


def test_missing_task_or_path_traversal_rejected():
    with pytest.raises(ValueError):
        suite.load_task("../interval-union")


def test_review_staging_is_a_boundary_violation(tmp_path):
    task, initial, response, _ = setup_control("review-mixed-limit", tmp_path)
    subprocess.run(["git", "add", "limits.py"], cwd=tmp_path, check=True)
    result = grade(task, initial, tmp_path, response)
    assert not result["valid_completion"]
    assert "@git/index" in result["boundary_violations"]


def test_malformed_status_fails_closed(tmp_path):
    task, initial, response, _ = setup_control("interval-union", tmp_path)
    response["status"] = []
    assert not grade(task, initial, tmp_path, response)["valid_completion"]


def test_equivalent_finding_kind_is_accepted(tmp_path):
    task, initial, response, _ = setup_control("review-line-normalizer", tmp_path)
    response["findings"][0]["kind"] = "incorrect-result"
    assert grade(task, initial, tmp_path, response)["valid_completion"]


def test_candidate_git_config_cannot_execute_during_manifest(tmp_path):
    task, _, _, _ = setup_control("interval-union", tmp_path)
    marker = tmp_path / "executed-hook"
    config = tmp_path / ".git/config"
    config.write_text(config.read_text() + f"\n[core]\n\tfsmonitor = touch {marker}\n")
    suite.file_manifest(tmp_path)
    assert not marker.exists()


def test_equivalent_review_path_and_symbol_are_accepted(tmp_path):
    task, initial, response, _ = setup_control("review-line-normalizer", tmp_path)
    response["findings"][0]["path"] = "./normalizer.py"
    response["findings"][0]["symbol"] = "normalizer.normalize"
    assert grade(task, initial, tmp_path, response)["valid_completion"]


def test_git_index_semantic_flags_are_not_stat_cache(tmp_path):
    task, initial, response, _ = setup_control("review-pagination-clean", tmp_path)
    subprocess.run(["git", "update-index", "--assume-unchanged", "pages.py"], cwd=tmp_path, check=True)
    result = grade(task, initial, tmp_path, response)
    assert "@git/index" in result["boundary_violations"]


def test_deleted_git_object_is_a_boundary_violation(tmp_path):
    task, initial, response, _ = setup_control("review-pagination-clean", tmp_path)
    object_file = next(path for path in (tmp_path / ".git/objects").rglob("*") if path.is_file())
    object_file.unlink()
    result = grade(task, initial, tmp_path, response)
    assert not result["boundaries_preserved"]


@pytest.mark.parametrize("mutation", ["fifo", "mode", "cache-content", "index-fifo"])
def test_nonregular_and_mode_mutations_fail_boundary(mutation, tmp_path):
    task, initial, response, _ = setup_control("review-pagination-clean", tmp_path)
    if mutation in {"fifo", "index-fifo"} and not hasattr(os, "mkfifo"):
        pytest.skip("FIFO control requires POSIX")
    if mutation == "fifo":
        os.mkfifo(tmp_path / "forbidden.pipe")
    elif mutation == "mode":
        (tmp_path / "pages.py").chmod(0o755)
    elif mutation == "cache-content":
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__/forbidden-source.py").write_text("pass\n")
    else:
        (tmp_path / ".git/index").unlink()
        os.mkfifo(tmp_path / ".git/index")
    result = grade(task, initial, tmp_path, response)
    assert not result["valid_completion"]
    assert not result["boundaries_preserved"]


def test_nested_git_directory_is_not_exempt_from_boundaries(tmp_path):
    task, initial, response, _ = setup_control("review-mixed-limit", tmp_path)
    (tmp_path / "tests/.git").mkdir()
    (tmp_path / "tests/.git/forbidden-source.py").write_text("pass\n")
    result = grade(task, initial, tmp_path, response)
    assert not result["boundaries_preserved"]
    assert "tests/.git/forbidden-source.py" in result["boundary_violations"]


def test_counterfeit_exception_class_does_not_satisfy_builtin_contract(tmp_path):
    task, _, _, _ = setup_control("ttl-expiry", tmp_path)
    (tmp_path / "cache.py").write_text(
        "class ValueError(Exception):\n    pass\n\ndef get_fresh(*args):\n    raise ValueError()\n"
    )
    outcome = invoke_fixture(tmp_path, {"module": "cache", "function": "get_fresh", "args": []})
    assert outcome["error"] == "cache.ValueError"
