import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import observe

IMAGE = "sha256:" + "a" * 64


def fixture(monkeypatch, code=0, polls=None, stdout_bytes=b"controller stdout\n", stderr_bytes=b""):
    calls = []

    class Controller:
        def inspect_owned(self, identity):
            return {"stopped": True, "exit_code": code}

        def terminate(self, identity):
            calls.append("stop")
            return {"execution_boundary": "confirmed"}

    class Process:
        def __init__(self, args, stdout, stderr, stdin):
            calls.append(args)
            for name, raw in (("stdout", stdout_bytes), ("stderr", stderr_bytes)):
                read, write = os.pipe()
                os.write(write, raw)
                os.close(write)
                setattr(self, name, os.fdopen(read, "rb"))

        def poll(self):
            return 0 if not polls else polls.pop(0)

        def wait(self, timeout):
            return 0

        def terminate(self):
            calls.append("attach-terminated")

    monkeypatch.setattr(observe, "DockerController", Controller)
    monkeypatch.setattr(
        observe.subprocess,
        "run",
        lambda args, **kwargs: calls.append(args) or SimpleNamespace(stdout=("c" * 64).encode()),
    )
    monkeypatch.setattr(observe.subprocess, "Popen", Process)
    return calls


def test_exit_three_does_not_mean_command_not_run(tmp_path, monkeypatch):
    calls = fixture(monkeypatch, 3)
    record = observe.visible_check(
        tmp_path,
        {
            "visible_command": ["python3", "verify.py"],
            "task_contract": "blocker_report",
            "required_evidence_availability": "unavailable",
        },
        attempt_id="a",
        candidate_id="c",
        image=IMAGE,
        directory=tmp_path / "visible",
    )
    assert record["execution_state"] == "ran" and record["exit_code"] == 3
    assert record["evidence_availability"] == "unavailable"
    assert "--network" in calls[0] and "none" in calls[0] and "--pull" in calls[0] and "never" in calls[0]
    assert ",readonly" in next(arg for arg in calls[0] if arg.startswith("type=bind"))
    assert not any("rm" in row for row in calls if isinstance(row, list))


def test_same_exit_for_implementation_retains_complete_output(tmp_path, monkeypatch):
    fixture(monkeypatch, 3)
    record = observe.visible_check(
        tmp_path,
        {"visible_command": ["python3", "verify.py"], "task_contract": "implementation"},
        attempt_id="a",
        candidate_id="c",
        image=IMAGE,
        directory=tmp_path / "visible",
    )
    assert record["evidence_availability"] == "complete" and record["exit_code"] == 3
    assert json.loads((tmp_path / "visible/end.json").read_text())["artifacts"]["stdout.bin"]["bytes"] > 0


def test_timeout_stops_exact_container_before_record(tmp_path, monkeypatch):
    calls = fixture(monkeypatch, polls=[None])
    record = observe.visible_check(
        tmp_path,
        {"visible_command": ["python3", "verify.py"]},
        attempt_id="a",
        candidate_id="c",
        image=IMAGE,
        directory=tmp_path / "visible",
        seconds=-1,
    )
    assert "stop" in calls and record["execution_state"] == "timed_out" and record["exit_code"] is None


def test_complete_observation_requires_real_artifact_reference():
    with pytest.raises(ValueError):
        observe.command_record(
            attempt_id="a",
            candidate_id="c",
            command=["test"],
            execution_state="ran",
            exit_code=0,
            availability="complete",
            artifact_refs=[],
        )


@pytest.mark.parametrize("channel", ["stdout", "stderr", "both"])
def test_fast_exited_process_cannot_bypass_stream_cap(tmp_path, monkeypatch, channel):
    calls = fixture(
        monkeypatch,
        stdout_bytes=b"s" * (16 if channel in {"stdout", "both"} else 0),
        stderr_bytes=b"e" * (16 if channel in {"stderr", "both"} else 0),
    )
    result = observe.visible_check(
        tmp_path,
        {"visible_command": ["x"]},
        attempt_id="a",
        candidate_id="c",
        image=IMAGE,
        directory=tmp_path / "visible",
        max_output_bytes=8,
    )
    assert result["execution_state"] == "interrupted"
    assert result["evidence_availability"] == "partial" and result["exit_code"] is None
    assert "stop" in calls
    end = json.loads((tmp_path / "visible/end.json").read_text())
    assert end["after"]["stopped"]
    for name, artifact in end["artifacts"].items():
        assert (tmp_path / "visible" / name).stat().st_size == artifact["bytes"] <= 8
        if artifact["observed_bytes"]:
            assert artifact["truncated"] and artifact["observed_bytes"] == 16


def test_exact_cap_with_complete_eof_is_not_truncated(tmp_path, monkeypatch):
    fixture(monkeypatch, stdout_bytes=b"12345678", stderr_bytes=b"abcdefgh")
    result = observe.visible_check(
        tmp_path,
        {"visible_command": ["x"]},
        attempt_id="a",
        candidate_id="c",
        image=IMAGE,
        directory=tmp_path / "visible",
        max_output_bytes=8,
    )
    assert result["execution_state"] == "ran" and result["evidence_availability"] == "complete"
    end = json.loads((tmp_path / "visible/end.json").read_text())
    assert not any(item["truncated"] for item in end["artifacts"].values())


def test_stream_read_failure_requests_exact_stop_and_never_fabricates_record(tmp_path, monkeypatch):
    calls = fixture(monkeypatch)

    def failed(*_):
        raise OSError("synthetic pipe error")

    monkeypatch.setattr(observe.os, "read", failed)
    with pytest.raises(OSError, match="synthetic"):
        observe.visible_check(
            tmp_path,
            {"visible_command": ["x"]},
            attempt_id="a",
            candidate_id="c",
            image=IMAGE,
            directory=tmp_path / "visible",
        )
    assert "stop" in calls
    assert not (tmp_path / "visible/observation.json").exists()


def test_output_overflow_cannot_override_unconfirmed_container_stop(tmp_path, monkeypatch):
    fixture(monkeypatch, stdout_bytes=b"x" * 16)
    identities = []

    class Unconfirmed:
        def inspect_owned(self, identity):
            return {"stopped": False, "exit_code": None}

        def terminate(self, identity):
            identities.append(identity)
            return {"execution_boundary": "unconfirmed"}

    monkeypatch.setattr(observe, "DockerController", Unconfirmed)
    with pytest.raises(ValueError, match="boundary_unconfirmed"):
        observe.visible_check(
            tmp_path,
            {"visible_command": ["x"]},
            attempt_id="a",
            candidate_id="c",
            image=IMAGE,
            directory=tmp_path / "visible",
            max_output_bytes=8,
        )
    assert identities and all(identity["container_id"] == "c" * 64 for identity in identities)
    assert not (tmp_path / "visible/observation.json").exists()


@pytest.mark.skipif(
    not os.environ.get("EVALOPT_V2_DOCKER_CONTROL_IMAGE"), reason="explicit local Docker image required"
)
def test_real_visible_container_is_stopped_without_candidate_mutation(tmp_path):
    image = os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "verify.py").write_text(
        "import os\nassert not os.path.exists('/trusted')\nprint('visible-control')\n"
    )
    record = observe.visible_check(
        workspace,
        {"visible_command": ["python3", "verify.py"], "task_contract": "implementation"},
        attempt_id="offline-control",
        candidate_id="fixture",
        image=image,
        directory=tmp_path / "visible",
    )
    end = json.loads((tmp_path / "visible/end.json").read_text())
    assert record["exit_code"] == 0 and end["after"]["stopped"]
    assert sorted(p.name for p in workspace.iterdir()) == ["verify.py"]
    # Test-only cleanup after exact owned stopped identity was retained.
    subprocess.run(
        ["docker", "rm", end["identity"]["container_id"]], capture_output=True, timeout=15, check=True
    )


@pytest.mark.skipif(
    not os.environ.get("EVALOPT_V2_DOCKER_CONTROL_IMAGE"), reason="explicit local Docker image required"
)
@pytest.mark.parametrize("channel", ["stdout", "stderr", "both"])
def test_real_fast_oversized_output_retains_bounded_bytes_and_stop(tmp_path, channel):
    image = os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    code = "import os;" + ";".join(
        f"os.write({fd}, b'x' * 65536)"
        for fd, name in ((1, "stdout"), (2, "stderr"))
        if channel in {name, "both"}
    )
    (workspace / "verify.py").write_text(code)
    result = observe.visible_check(
        workspace,
        {"visible_command": ["python3", "verify.py"]},
        attempt_id="offline-bounded-capture",
        candidate_id="fixture",
        image=image,
        directory=tmp_path / "visible",
        max_output_bytes=8,
    )
    end = json.loads((tmp_path / "visible/end.json").read_text())
    try:
        assert result["execution_state"] == "interrupted"
        assert result["evidence_availability"] == "partial" and result["exit_code"] is None
        assert end["after"]["stopped"]
        assert all(item["bytes"] <= 8 for item in end["artifacts"].values())
        assert any(item["truncated"] for item in end["artifacts"].values())
    finally:
        subprocess.run(
            ["docker", "rm", end["identity"]["container_id"]], capture_output=True, timeout=15, check=True
        )
