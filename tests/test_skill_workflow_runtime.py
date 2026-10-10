"""Offline controls for controller classification, capture and launch readiness."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench" / "harbor" / "skill-workflows-v1"
sys.path.insert(0, str(BENCH))
from runtime.observations import quiesce_processes, runtime_observations  # noqa: E402
from runtime.readiness import verify_readiness  # noqa: E402
from runtime.snapshot import encode_snapshot, regular_snapshot, terminal_status  # noqa: E402


def test_snapshot_binds_modes_empty_directories_and_link_targets(tmp_path):
    file = tmp_path / "source.py"
    file.write_text("pass\n")
    original = encode_snapshot(tmp_path)
    file.chmod(0o755)
    assert encode_snapshot(tmp_path) != original
    modes = encode_snapshot(tmp_path)
    (tmp_path / "unauthorized-empty").mkdir()
    assert encode_snapshot(tmp_path) != modes
    (tmp_path / "link").symlink_to("/outside/candidate")
    payload = json.loads(encode_snapshot(tmp_path))
    assert payload["nodes"]["link"] == {
        "type": "symlink",
        "mode": stat.S_IMODE((tmp_path / "link").lstat().st_mode),
        "target": "/outside/candidate",
    }
    assert not regular_snapshot(tmp_path)


def test_snapshot_does_not_read_fifo(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    assert json.loads(encode_snapshot(tmp_path))["nodes"]["pipe"]["type"] == "special"
    assert not regular_snapshot(tmp_path)


@pytest.mark.parametrize("captured,graded", [(False, False), (True, False), (True, True)])
def test_timeout_never_becomes_retryable_infrastructure(captured, graded):
    assert terminal_status(
        "AgentTimeoutError", agent_started=True, captured=captured, grade_exists=graded
    ) == ("timeout", None)


def test_failure_phase_is_not_inferred_from_missing_grade():
    assert terminal_status(
        "NonZeroAgentExitCodeError", agent_started=True, captured=False, grade_exists=False
    ) == ("agent_failure", None)
    assert terminal_status("ValueError", agent_started=True, captured=False, grade_exists=False) == (
        "agent_failure",
        None,
    )
    assert terminal_status(
        "EnvironmentStartError", agent_started=False, captured=False, grade_exists=False
    ) == ("infra_failure", "container_start")
    assert terminal_status(None, agent_started=True, captured=True, grade_exists=False) == (
        "infra_failure",
        "verifier_infrastructure",
    )


def test_ready_flag_without_capability_evidence_cannot_launch(tmp_path):
    (tmp_path / "summary.json").write_text(json.dumps({"status": "PASS", "checks": {}}))
    with pytest.raises(ValueError, match="preflight is incomplete"):
        verify_readiness(tmp_path, tmp_path, {}, tmp_path)


def test_provider_quota_exceptions_pause_instead_of_agent_retry():
    for error in ("ApiUsageLimitError", "ApiRateLimitError"):
        assert terminal_status(error, agent_started=True, captured=True, grade_exists=False) == (
            "infra_failure",
            "subscription_exhausted",
        )
    assert terminal_status(
        "ApiProviderResourceNotFoundError", agent_started=True, captured=False, grade_exists=False
    ) == ("agent_failure", None)


def test_runtime_identity_rejects_silent_model_substitution(tmp_path):
    rows = [
        {"type": "session_meta", "payload": {"cli_version": "0.154.0"}},
        {"type": "turn_context", "payload": {"model": "gpt-6-astra", "effort": "ultra"}},
    ]
    session = tmp_path / "session.jsonl"
    session.write_text("\n".join(json.dumps(row) for row in rows))
    assert runtime_observations(tmp_path, "eval-opt")["runtime_valid"]
    assert not runtime_observations(tmp_path, "eval-opt")["entrypoint_load_observed"]
    rows.append({"type": "turn_context", "payload": {"model": "other", "effort": "ultra"}})
    session.write_text("\n".join(json.dumps(row) for row in rows))
    assert not runtime_observations(tmp_path, None)["runtime_valid"]


def test_cleanup_sweeps_child_forked_during_termination():
    processes = {1: ("10", "S"), 201: ("11", "R")}
    killed = []

    def kill(pid):
        killed.append(pid)
        if pid == 201:
            processes[202] = ("12", "R")
        del processes[pid]

    quiesce_processes(lambda: dict(processes), kill, {"1": "10"}, set(), lambda: None)
    assert killed == [201, 202]
    assert processes == {1: ("10", "S")}


def test_cleanup_fails_closed_for_persistent_respawning():
    with pytest.raises(RuntimeError, match="quiescent"):
        quiesce_processes(lambda: {201: ("11", "R")}, lambda _: None, {}, set(), lambda: None)


@pytest.mark.parametrize("returncode,passed", [(0, True), (1, False)])
def test_offline_oracle_requires_successful_verifier_exit(tmp_path, monkeypatch, returncode, passed):
    from runtime import offline_controls

    destination = tmp_path / "controls"
    monkeypatch.setattr(offline_controls, "task_ids", lambda **_: ["duration-parser"])
    monkeypatch.setattr(offline_controls, "image_identity", lambda image: image)

    def materialize(task, target, **options):
        (target / "environment/workspace").mkdir(parents=True)
        (target / "tests").mkdir()
        return {}

    def verifier_result(*args, **kwargs):
        (destination / "duration-parser/verifier-output/grade.json").write_text(
            json.dumps({"valid_completion": True})
        )
        return SimpleNamespace(returncode=returncode, stderr="")

    monkeypatch.setattr(offline_controls, "materialize", materialize)
    monkeypatch.setattr(offline_controls, "visible_check", lambda *args: ({}, b""))
    monkeypatch.setattr(offline_controls, "subprocess", SimpleNamespace(run=verifier_result))
    result = offline_controls.controls(destination, "agent", "verifier")
    assert result["controls"][0]["oracle_passed"] is passed
    assert result["all_passed"] is passed


def test_offline_oracle_empty_task_set_is_not_ready(tmp_path, monkeypatch):
    from runtime import offline_controls

    monkeypatch.setattr(offline_controls, "task_ids", lambda **_: [])
    monkeypatch.setattr(offline_controls, "image_identity", lambda image: image)
    result = offline_controls.controls(tmp_path / "empty", "agent", "verifier")
    assert result["controls"] == []
    assert result["all_passed"] is False
