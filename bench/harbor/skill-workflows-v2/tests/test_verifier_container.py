"""Controller fault controls; actual Docker behavior is covered separately."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import verifier_container as containers
from evalopt_v2.case_runner import SCHEMA, snapshot_manifest
from evalopt_v2.records import canonical, digest
from evalopt_v2.verifier import CaseBoundaryError, collect_cases


class DockerFixture:
    def __init__(self, fault=None):
        self.fault = fault
        self.commands = []
        self.containers = {}

    def run(self, argv, **kwargs):
        assert kwargs["check"] is False
        self.commands.append(argv[1:])
        args = argv[1:]
        if args[:2] == ["image", "inspect"]:
            return subprocess.CompletedProcess(argv, 0, b"sha256:" + b"1" * 64 + b"\n", b"")
        if args[0] == "create":
            if self.fault == "create-timeout":
                raise subprocess.TimeoutExpired(argv, 30)
            cid = f"{len(self.containers) + 1:064x}"
            label = args[args.index("--label") + 1].split("=", 1)[1]
            mounts = {}
            for i, arg in enumerate(args):
                if arg == "--mount":
                    parts = dict(part.split("=", 1) for part in args[i + 1].split(",") if "=" in part)
                    mounts[parts["dst"]] = Path(parts["src"])
            self.containers[cid] = {"label": label, "mounts": mounts, "started": False}
            return subprocess.CompletedProcess(argv, 0, cid.encode() + b"\n", b"")
        cid = args[-1]
        item = self.containers[cid]
        if args[0] == "start":
            item["started"] = True
            control = json.loads((item["mounts"]["/case-control"] / "request.json").read_text())
            req = control["request"]
            result = {
                "schema_version": SCHEMA,
                "record_type": "case_invocation",
                "request": req,
                "candidate_id": digest(snapshot_manifest(item["mounts"]["/snapshot"])),
                "state": "returned",
                "value": req["args"][0],
                "args_after": req["args"],
            }
            if self.fault == "wrong-request":
                result["request"]["args"] = ["forged"]
            (item["mounts"]["/case-output"] / "invocation.json").write_bytes(canonical(result))
        elif args[0] == "inspect":
            if self.fault == "inspect-error" and item["started"]:
                return subprocess.CompletedProcess(argv, 1, b"", b"daemon error")
            state = {
                "Status": "exited" if item["started"] else "created",
                "Running": False,
                "Restarting": False,
                "Dead": False,
                "ExitCode": 0,
                "FinishedAt": "fixture",
            }
            if self.fault == "still-running" and item["started"]:
                state.update(Status="running", Running=True)
            result = {
                "Id": cid if self.fault != "wrong-container" else "0" * 64,
                "Image": "sha256:" + "1" * 64,
                "Config": {"Labels": {"evalopt.v2.case": item["label"]}},
                "HostConfig": {
                    "AutoRemove": False,
                    "RestartPolicy": {"Name": "no"},
                    "NetworkMode": "none",
                    "NanoCpus": 1_000_000_000,
                    "Memory": 2 * 1024**3,
                    "PidsLimit": 128,
                    "Privileged": False,
                    "CapAdd": None,
                    "SecurityOpt": None,
                },
                "State": state,
            }
            return subprocess.CompletedProcess(argv, 0, canonical(result), b"")
        elif args[0] == "rm" and self.fault == "cleanup-crash":
            raise subprocess.TimeoutExpired(argv, 30)
        return subprocess.CompletedProcess(argv, 0, b"", b"")


def setup(tmp_path, monkeypatch, fault=None):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "subject.py").write_text("def probe(x): return x\n")
    artifacts = tmp_path / "cases"
    artifacts.mkdir()
    fake = DockerFixture(fault)
    monkeypatch.setattr(containers.subprocess, "run", fake.run)
    return snapshot, artifacts, fake, containers.docker_invoker("local-fixture", artifact_root=artifacts)


def test_every_case_has_distinct_container_and_no_hidden_oracle_mount(tmp_path, monkeypatch):
    snapshot, artifacts, fake, invoke = setup(tmp_path, monkeypatch)
    records = [invoke(snapshot, {"module": "subject", "function": "probe", "args": [i]}) for i in range(2)]
    assert len(fake.containers) == 2
    assert len(list(artifacts.glob("case-*/retained.json"))) == 2
    assert len({record["container_boundary"]["container_id"] for record in records}) == 2
    for item in fake.containers.values():
        assert set(item["mounts"]) == {"/snapshot", "/controller/evalopt_v2", "/case-control", "/case-output"}
        control = json.loads((item["mounts"]["/case-control"] / "request.json").read_text())
        assert set(control) == {"request", "timeout_seconds"}
    for command in fake.commands:
        if command[0] == "create":
            assert "--privileged" not in command and "--cap-add" not in command
            assert command[command.index("--network") + 1] == "none"
            assert command[command.index("--pull") + 1] == "never"


@pytest.mark.parametrize(
    "fault", ["create-timeout", "inspect-error", "still-running", "wrong-container", "wrong-request"]
)
def test_uncertain_side_effect_or_capture_stops_entire_remaining_roster(tmp_path, monkeypatch, fault):
    snapshot, artifacts, fake, invoke = setup(tmp_path, monkeypatch, fault)
    cases = [
        {
            "case_id": str(i),
            "request": {"module": "subject", "function": "probe", "args": [i]},
            "expect": {"kind": "return", "value": i},
            "preserve_args": True,
        }
        for i in range(3)
    ]
    records = collect_cases(cases, lambda request, **limits: invoke(snapshot, request, **limits))
    assert len(records) == 3
    assert [row["invocation"]["reason"] for row in records] == [
        "case_boundary_unconfirmed",
        "prior_case_boundary_unconfirmed",
        "prior_case_boundary_unconfirmed",
    ]
    assert sum(command[0] == "create" for command in fake.commands) == 1
    assert len(list(artifacts.glob("case-*"))) == 1
    if fault == "wrong-container":
        assert not any(command[0] in {"start", "kill", "rm"} for command in fake.commands)


def test_cleanup_crash_keeps_durable_stopped_result_and_stops_admission(tmp_path, monkeypatch):
    snapshot, artifacts, fake, invoke = setup(tmp_path, monkeypatch, "cleanup-crash")
    req = {"module": "subject", "function": "probe", "args": [1]}
    with pytest.raises(CaseBoundaryError):
        invoke(snapshot, req)
    assert json.loads((artifacts / "case-0001/boundary.json").read_text())["status"] == "confirmed"
    assert json.loads((artifacts / "case-0001/retained.json").read_text())["value"] == 1
    with pytest.raises(CaseBoundaryError):
        invoke(snapshot, req)
    assert len(fake.containers) == 1


class ManualClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class SlowDockerFixture(DockerFixture):
    def __init__(self, clock, delays, *, timeout_start=False):
        super().__init__()
        self.clock, self.delays = clock, dict(delays)
        self.timeout_start = timeout_start
        self.calls_at = []

    def run(self, argv, **kwargs):
        stage = argv[1]
        self.calls_at.append((stage, self.clock(), kwargs["timeout"]))
        result = super().run(argv, **kwargs)
        self.clock.now += self.delays.pop(stage, 0)
        if stage == "start" and self.timeout_start:
            raise subprocess.TimeoutExpired(argv, kwargs["timeout"])
        return result


def slow_setup(tmp_path, monkeypatch, delays, *, timeout_start=False):
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    (snapshot / "subject.py").write_text("def probe(x): return x\n")
    artifacts = tmp_path / "cases"
    artifacts.mkdir()
    clock = ManualClock()
    fake = SlowDockerFixture(clock, delays, timeout_start=timeout_start)
    monkeypatch.setattr(containers.subprocess, "run", fake.run)
    invoke = containers.docker_invoker("local-fixture", artifact_root=artifacts, clock=clock)
    cases = [
        {
            "case_id": str(i),
            "request": {"module": "subject", "function": "probe", "args": [i]},
            "expect": {"kind": "return", "value": i},
            "preserve_args": True,
        }
        for i in range(3)
    ]
    records = collect_cases(
        cases,
        lambda request, **limits: invoke(snapshot, request, **limits),
        total_seconds=1,
        case_seconds=5,
        clock=clock,
    )
    return artifacts, fake, records


@pytest.mark.parametrize("delays", [{"create": 2}, {"create": 0.3, "inspect": 0.8}])
def test_setup_cannot_start_a_case_after_absolute_verifier_deadline(tmp_path, monkeypatch, delays):
    artifacts, fake, records = slow_setup(tmp_path, monkeypatch, delays)
    assert not any(command[0] == "start" for command in fake.commands)
    assert [row["invocation"]["reason"] for row in records] == [
        "case_setup_deadline",
        "verifier_budget_exhausted",
        "verifier_budget_exhausted",
    ]
    boundary = json.loads((artifacts / "case-0001/boundary.json").read_text())
    assert boundary["status"] == "confirmed"
    assert boundary["execution_started"] is False
    assert boundary["execution_deadline_monotonic"] == 1
    create_call = next(call for call in fake.calls_at if call[0] == "create")
    assert create_call[2] <= 1


@pytest.mark.parametrize("timeout_start", [False, True])
def test_execution_is_bounded_by_remaining_absolute_budget(tmp_path, monkeypatch, timeout_start):
    artifacts, fake, records = slow_setup(
        tmp_path, monkeypatch, {"create": 0.3, "inspect": 0.2, "start": 0.7}, timeout_start=timeout_start
    )
    assert [row["invocation"]["state"] for row in records] == ["timeout", "not_run", "not_run"]
    assert records[0]["invocation"]["reason"] == "outer_case_deadline"
    starts = [call for call in fake.calls_at if call[0] == "start"]
    assert starts == [("start", 0.5, 0.5)]
    assert any(command[0] == "kill" for command in fake.commands)
    # The late inner record remains forensic evidence; it does not become a pass.
    assert json.loads((artifacts / "case-0001/output/invocation.json").read_text())["state"] == "returned"
    assert json.loads((artifacts / "case-0001/retained.json").read_text())["state"] == "timeout"
    boundary = json.loads((artifacts / "case-0001/boundary.json").read_text())
    assert boundary["closure_started_monotonic"] == 1.2
    assert boundary["closure_deadline_monotonic"] == 31.2
