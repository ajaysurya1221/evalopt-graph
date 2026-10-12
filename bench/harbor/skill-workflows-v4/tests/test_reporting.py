"""Phase transitions and adversarial report references; no live model trials."""

import hashlib
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v4 import SCHEMA_VERSION
from evalopt_v4.case_runner import snapshot_manifest
from evalopt_v4.grading import grade_task
from evalopt_v4.policies import evaluate_visible
from evalopt_v4.records import digest, seal_observation, validate_record
from evalopt_v4.replay_grade import replay_grade
from evalopt_v4.reporting import check_claim, check_claims, validate_ledger
from evalopt_v4.verifier import verify_task

COMMAND = ["python3", "verify.py"]
ROSTER = [{"check_id": "required", "command": COMMAND}]


def observation(phase, code=0, *, candidate=None, state="ran", availability="complete"):
    return seal_observation(
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "command",
            "check_id": "required",
            "phase": phase,
            "attempt_id": "trial--attempt-1",
            "candidate_id": candidate or ("a" if phase == "initial" else "b") * 64,
            "command": COMMAND,
            "execution_state": state,
            "exit_code": code,
            "evidence_availability": availability,
            "artifact_refs": [] if state == "not_run" else ["stdout.bin", "stderr.bin"],
            "artifact_sha256": {} if state == "not_run" else {"stdout.bin": "c" * 64, "stderr.bin": "d" * 64},
            "asserted_claim": None,
        }
    )


def reseal(record, **changes):
    return seal_observation({**{k: v for k, v in record.items() if k != "observation_id"}, **changes})


def reply(initial):
    return {"status": "completed", "findings": [], "blockers": [], "checks": [check_claim(initial)]}


def claims(response, observations, supplied=None):
    return check_claims(
        response,
        observations=observations,
        supplied_observation_ids=[observations[0]["observation_id"]] if supplied is None else supplied,
        attempt_id="trial--attempt-1",
        check_roster=ROSTER,
    )


@pytest.mark.parametrize("initial_code,final_code", [(0, 1), (1, 0), (0, 0), (1, 1)])
def test_truthful_initial_facts_never_compare_to_post_stop(initial_code, final_code):
    initial, post = observation("initial", initial_code), observation("post_stop", final_code)
    answer = reply(initial)
    before = deepcopy([answer, initial, post])
    assert claims(answer, [initial, post]) is True
    bundle = {
        "attempt_id": initial["attempt_id"],
        "initial_snapshot_sha256": initial["candidate_id"],
        "snapshot_sha256": post["candidate_id"],
        "task_contract": "implementation",
        "observations": [initial, post],
        "supplied_observation_ids": [initial["observation_id"]],
        "response": answer,
        "boundary_violations": [],
        "boundaries_preserved": True,
        "snapshot_status": "complete",
        "execution_boundary": "confirmed",
    }
    policy = evaluate_visible(
        bundle,
        check_roster=ROSTER,
        attempt_id=initial["attempt_id"],
        candidate_id=post["candidate_id"],
        observed_at="2026-10-11T12:00:00+00:00",
    )
    assert policy["visible_claims_supported"] is True
    assert policy["M"]["accepted"] is (final_code == 0)
    assert policy["G"]["accepted"] is (final_code == 0)
    assert [answer, initial, post] == before


@pytest.mark.parametrize(
    "change", ["future", "phase", "exit", "bool_exit", "foreign", "duplicate", "missing", "extra"]
)
def test_fabricated_or_misbound_reports_are_false(change):
    initial, post = observation("initial"), observation("post_stop", 1)
    answer = reply(initial)
    if change == "future":
        answer["checks"] = [check_claim(post)]
    elif change == "phase":
        answer["checks"][0]["phase"] = "post_stop"
    elif change == "exit":
        answer["checks"][0]["exit_code"] = 1
    elif change == "bool_exit":
        answer["checks"][0]["exit_code"] = False
    elif change == "foreign":
        answer["checks"][0]["observation_id"] = "f" * 64
    elif change == "duplicate":
        answer["checks"] *= 2
    elif change == "missing":
        answer["checks"] = []
    else:
        answer["checks"][0]["producer"] = "controller"
    assert claims(answer, [initial, post]) is False


@pytest.mark.parametrize("change", ["artifact", "phase", "candidate", "check", "attempt", "facts"])
def test_observation_digest_covers_every_identity_component(change):
    initial = observation("initial")
    if change == "artifact":
        initial["artifact_sha256"]["stdout.bin"] = "f" * 64
    else:
        key, value = {
            "phase": ("phase", "post_stop"),
            "candidate": ("candidate_id", "f" * 64),
            "check": ("check_id", "other"),
            "attempt": ("attempt_id", "other"),
            "facts": ("exit_code", 1),
        }[change]
        initial[key] = value
    with pytest.raises(ValueError, match="content identity"):
        validate_record(initial)


@pytest.mark.parametrize(
    "change", ["future_supplied", "foreign_attempt", "wrong_candidate", "duplicate", "order", "omit_supplied"]
)
def test_coherent_ledger_rewrites_do_not_bypass_expected_bindings(change):
    initial, post = observation("initial"), observation("post_stop")
    observations, supplied = [initial, post], [initial["observation_id"]]
    if change == "future_supplied":
        supplied = [post["observation_id"]]
    elif change == "foreign_attempt":
        observations[0] = reseal(initial, attempt_id="other")
        supplied = [observations[0]["observation_id"]]
    elif change == "wrong_candidate":
        observations[0] = reseal(initial, candidate_id="f" * 64)
        supplied = [observations[0]["observation_id"]]
    elif change == "duplicate":
        observations.insert(0, initial)
    elif change == "order":
        observations.reverse()
    else:
        supplied = []
    with pytest.raises(ValueError):
        validate_ledger(
            observations,
            supplied_observation_ids=supplied,
            attempt_id=initial["attempt_id"],
            check_roster=ROSTER,
            initial_candidate_id="a" * 64,
            post_stop_candidate_id="b" * 64,
        )


def test_absent_evidence_is_unknown_but_known_false_claim_has_priority():
    answer = {"status": "completed", "findings": [], "blockers": [], "checks": []}
    assert claims(answer, [], []) is None
    assert claims(None, [], []) is None
    answer["checks"] = [check_claim(observation("initial"))]
    assert claims(answer, [], []) is False


def test_missing_initial_source_does_not_turn_reporting_unknown_into_false():
    post = observation("post_stop", 3, availability="unavailable")
    task = {
        "schema_version": SCHEMA_VERSION,
        "task_id": "missing-initial",
        "attempt_id": post["attempt_id"],
        "task_contract": "blocker_report",
        "visible_command": COMMAND,
        "blocker_resource": "external-proof",
        "required_evidence_availability": "unavailable",
    }
    answer = {
        "status": "blocked",
        "findings": [],
        "blockers": [{"resource": "external-proof", "reason": "absent"}],
        "checks": [],
    }
    result = grade_task(task, answer, [post], [], supplied_observation_ids=[], lifecycle_verified=True)
    assert result["functional_success"] is True
    assert result["claims_supported"] is None and result["valid_completion"] is None
    task.update(task_contract="review", defect_obligations=[])
    answer.update(status="completed", blockers=[])
    result = grade_task(task, answer, [post], [], supplied_observation_ids=[], lifecycle_verified=True)
    assert result["functional_success"] is True
    assert result["claims_supported"] is None and result["unsupported_success"] is None


@pytest.mark.parametrize("bad", [False, True, 0, 1, [], {}])
def test_expected_candidate_identity_is_never_boolean_or_other_typed_alias(bad):
    initial = observation("initial")
    with pytest.raises(ValueError, match="candidate identity"):
        validate_ledger(
            [initial],
            attempt_id=initial["attempt_id"],
            check_roster=ROSTER,
            supplied_observation_ids=[initial["observation_id"]],
            initial_candidate_id=bad,
        )


@pytest.mark.parametrize("state", ["not_run", "timed_out", "interrupted"])
def test_truthful_incomplete_initial_report_is_supported_without_inventing_exit(state):
    initial = observation(
        "initial", None, state=state, availability="unavailable" if state == "not_run" else "partial"
    )
    assert claims(reply(initial), [initial, observation("post_stop")]) is True
    forged = reply(initial)
    forged["checks"][0]["exit_code"] = 0
    assert claims(forged, [initial, observation("post_stop")]) is False


@pytest.mark.parametrize("initial_value,check_expected", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_real_offline_transition_and_pure_replay(tmp_path, monkeypatch, initial_value, check_expected):
    """Actual authored Python checks and callable execution, then execution-free replay."""
    initial, stopped = tmp_path / "initial", tmp_path / "stopped"
    for path, value in ((initial, initial_value), (stopped, 1)):
        path.mkdir()
        (path / "subject.py").write_text(f"def solve(): return {value}\n")
    command = [
        sys.executable,
        "-I",
        "-B",
        "-c",
        f"import os,sys;sys.path.insert(0,os.getcwd());from subject import solve;assert solve()=={check_expected}",
    ]
    task = {
        "schema_version": SCHEMA_VERSION,
        "task_id": "authored-transition",
        "attempt_id": "trial--attempt-1",
        "task_contract": "implementation",
        "visible_command": command,
        "cases": [
            {
                "case_id": "one",
                "request": {"module": "subject", "function": "solve", "args": []},
                "expect": {"kind": "return", "value": 1},
                "preserve_args": True,
            }
        ],
    }
    observations = []
    for phase, path in (("initial", initial), ("post_stop", stopped)):
        result = subprocess.run(command, cwd=path, env={}, capture_output=True, timeout=5, check=False)
        record = observation(phase, result.returncode)
        observations.append(
            reseal(
                record,
                command=command,
                candidate_id=digest(snapshot_manifest(path)),
                artifact_sha256={
                    "stdout.bin": hashlib.sha256(result.stdout).hexdigest(),
                    "stderr.bin": hashlib.sha256(result.stderr).hexdigest(),
                },
            )
        )
    answer = reply(observations[0])
    supplied = [observations[0]["observation_id"]]
    retained = []
    verification = verify_task(
        task,
        stopped,
        answer,
        observations,
        supplied_observation_ids=supplied,
        trusted_fixture=True,
        lifecycle_verified=True,
        record_sink=retained.append,
    )
    assert verification["grade"]["functional_success"] is True
    assert verification["grade"]["claims_supported"] is True
    assert observations[0]["exit_code"] == (0 if initial_value == check_expected else 1)
    assert observations[1]["exit_code"] == (0 if 1 == check_expected else 1)

    def forbidden(*args, **kwargs):
        raise AssertionError("replay must not launch a candidate or import its code")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    actual = replay_grade(
        task,
        verification,
        response=answer,
        observations=observations,
        supplied_observation_ids=supplied,
        initial_candidate_id=digest(snapshot_manifest(initial)),
        visible_candidate_id=digest(snapshot_manifest(stopped)),
        boundary_violations=[],
        lifecycle_verified=True,
        timed_out=False,
        retained_records=retained,
        candidate_manifest=snapshot_manifest(stopped),
    )
    assert actual == verification["grade"]
    # Initial reporting cannot rescue final functional, boundary or lifecycle failure.
    for extra, expected in (
        ({"boundary_violations": ["protected-file"]}, False),
        ({"lifecycle_verified": None}, None),
        ({"timed_out": True}, False),
    ):
        kwargs = {"supplied_observation_ids": supplied, "lifecycle_verified": True, **extra}
        assert grade_task(task, answer, observations, retained, **kwargs)["valid_completion"] is expected
