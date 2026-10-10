"""Mirror the executed grader's response text decoding in offline replay."""

from __future__ import annotations

import json

import pytest

import test_skill_workflow_heldout_publication as base


@pytest.fixture
def sealed(tmp_path):
    return base.sealed.__wrapped__(tmp_path)


@pytest.fixture
def reviewed_pilot(tmp_path):
    return base.reviewed_pilot.__wrapped__(tmp_path)


@pytest.fixture
def frozen(sealed, reviewed_pilot, tmp_path, monkeypatch):
    return base.frozen.__wrapped__(sealed, reviewed_pilot, tmp_path, monkeypatch)


@pytest.fixture
def recorded(frozen, tmp_path, monkeypatch):
    return base.recorded.__wrapped__(frozen, tmp_path, monkeypatch)


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16", "utf-32"])
def test_negative_encoded_response_grade_replays_without_more_permissive_json_decoding(
    recorded, tmp_path, monkeypatch, encoding
):
    response = {
        "status": "completed",
        "summary": "Synthetic encoded response",
        "findings": [],
        "blockers": [],
        "checks": [{"command": "python -B verify.py", "outcome": "passed"}],
    }
    raw = json.dumps(response).encode(encoding)
    strict = base.verifier.strict_json
    assert strict(raw) == response  # Precisely the unwanted bytes-only behavior.
    with pytest.raises(ValueError):
        strict(raw.decode("utf-8"))
    # The fixture grades exactly the text read by runtime/verify.py; the replay
    # function itself remains unpatched and must accept this retained failure.
    with monkeypatch.context() as context:
        context.setattr(
            base.verifier,
            "strict_json",
            lambda value: strict(value.decode("utf-8") if isinstance(value, bytes) else value),
        )
        record = recorded(raw_response=raw)
    grade = record.store.root / "trials" / record.trial["trial_id"] / "attempt-1/grade.json"
    original = grade.read_bytes()
    result = base.export(record, tmp_path / "public")
    assert result["grade_records_replayed"] == 1
    assert grade.read_bytes() == original
    rows = base.publication.read_json(tmp_path / "public/reports/outcomes.json")
    retained = next(row for row in rows if row["trial_id"] == record.trial["trial_id"])
    assert retained["valid_completion"] is False
    assert base.publication.verify_public_bundle(tmp_path / "public") == result


@pytest.mark.parametrize("response_state", ["unsafe", "missing", "directory"])
def test_unreadable_or_withheld_response_replays_the_executed_negative_grade(
    sealed, tmp_path, monkeypatch, response_state
):
    task_root, _ = sealed
    identity = base.publication.read_json(task_root / "candidate-manifest.json")["tasks"][0]["id"]
    task = base.suite.load_task(identity, task_root=task_root, split="heldout")
    workspace = tmp_path / "stopped"
    base.suite.materialize_agent(task, workspace, task_root=task_root)
    initial = base.suite.file_manifest(workspace)
    if response_state == "unsafe":
        base.write_json(
            workspace / "response.json",
            {
                "status": "completed",
                "summary": "This response must be withheld with the unsafe snapshot",
                "findings": [],
                "blockers": [],
                "checks": [{"command": task["visible_check"], "outcome": "passed"}],
            },
        )
        (workspace / "unsafe-link").symlink_to("outside-snapshot")
    elif response_state == "directory":
        (workspace / "response.json").mkdir()
    stopped = base.suite.file_manifest(workspace)
    observation = {"command": task["visible_check"], "source": "controller", "outcome": "passed"}
    config = {
        "initial_manifest": initial,
        "observations": [observation],
        "unsafe_snapshot": response_state == "unsafe",
    }
    monkeypatch.setattr(
        base.verifier,
        "evaluate_cases",
        lambda candidate, invoke: base.suite.evaluate_cases(candidate, invoke, task_root=task_root),
    )
    requests = []

    def invoke(request):
        requests.append(request)
        return {"result": "HIDDEN_EXPECTED_SENTINEL", "args": request["args"]}

    # The runtime withholds an unsafe snapshot entirely; missing/directory
    # response paths instead produce read_text() OSError. Both yield None.
    grade = base.verifier.collect_grade(task, config, stopped, None, invoke)
    grade["boundary_violation"] = not grade["boundaries_preserved"]
    assert grade["valid_completion"] is False
    assert bool(requests) is (response_state != "unsafe")
    attempt = tmp_path / "retained"
    base.write_json(attempt / "agent/node-manifest.json", stopped)
    base.write_json(attempt / "agent/snapshot.json", json.loads(base.encode_snapshot(workspace)))
    base.write_json(attempt / "grade.json", {"grade": grade})
    base.write_json(attempt / "finish.json", {"status": "completed"})
    base.write_json(attempt / "visible.json", {"gates": [{"name": "visible_check", "status": "PASS"}]})
    original = (attempt / "grade.json").read_bytes()
    assert base.publication.replay_grade(attempt, {"task_id": identity}, task_root)
    assert (attempt / "grade.json").read_bytes() == original


@pytest.mark.parametrize(
    "projection",
    [
        "request",
        "response",
        "valid_completion",
        "functional_success",
        "boundaries_preserved",
        "claims_supported",
        "response_valid",
    ],
)
def test_replay_rejects_boolean_integer_aliases_in_retained_evidence(
    sealed, tmp_path, monkeypatch, projection
):
    task_root, _ = sealed
    identity = base.publication.read_json(task_root / "candidate-manifest.json")["tasks"][0]["id"]
    task = base.suite.load_task(identity, task_root=task_root, split="heldout")
    # Direct replay fixture with one finite numeric input; never executed as
    # candidate code or represented as a frozen registration/public artifact.
    cases_path = task_root / identity / "hidden_cases.json"
    cases = base.publication.read_json(cases_path)
    cases[0]["args"] = [1]
    base.write_json(cases_path, cases)
    workspace = tmp_path / "typed-stopped"
    base.suite.materialize_agent(task, workspace, task_root=task_root)
    initial = base.suite.file_manifest(workspace)
    response = (
        False
        if projection == "response"
        else {
            "status": "completed",
            "summary": "Synthetic typed evidence",
            "findings": [],
            "blockers": [],
            "checks": [{"command": task["visible_check"], "outcome": "passed"}],
        }
    )
    base.write_json(workspace / "response.json", response)
    stopped = base.suite.file_manifest(workspace)
    observation = {"command": task["visible_check"], "source": "controller", "outcome": "passed"}
    monkeypatch.setattr(
        base.verifier,
        "evaluate_cases",
        lambda candidate, invoke: base.suite.evaluate_cases(candidate, invoke, task_root=task_root),
    )
    grade = base.verifier.collect_grade(
        task,
        {"initial_manifest": initial, "observations": [observation], "unsafe_snapshot": False},
        stopped,
        response,
        lambda request: {"result": "HIDDEN_EXPECTED_SENTINEL", "args": request["args"]},
    )
    grade["boundary_violation"] = not grade["boundaries_preserved"]
    attempt = tmp_path / "typed-retained"
    base.write_json(attempt / "agent/node-manifest.json", stopped)
    base.write_json(attempt / "agent/snapshot.json", json.loads(base.encode_snapshot(workspace)))
    base.write_json(attempt / "grade.json", {"grade": grade})
    base.write_json(attempt / "finish.json", {"status": "completed"})
    base.write_json(attempt / "visible.json", {"gates": [{"name": "visible_check", "status": "PASS"}]})
    assert base.publication.replay_grade(attempt, {"task_id": identity}, task_root)
    if projection == "request":
        grade["reproduction_inputs"]["hidden_case_records"][0]["request"]["args"][0] = True
    elif projection == "response":
        assert grade["reproduction_inputs"]["response"] is False
        grade["reproduction_inputs"]["response"] = 0
    else:
        assert grade[projection] is True
        grade[projection] = 1
    base.write_json(attempt / "grade.json", {"grade": grade})
    with pytest.raises((ValueError, base.publication.GradeReplayError)):
        base.publication.replay_grade(attempt, {"task_id": identity}, task_root)
