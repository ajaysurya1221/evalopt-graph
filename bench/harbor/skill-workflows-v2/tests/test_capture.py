import fcntl
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.capture import LABEL, CaptureError, DockerController, _stream
from evalopt_v2.framing import SCHEMA
from evalopt_v2.lifecycle import (
    close_attempt,
    continuation_decision,
    prepare_supervisor,
    read_record,
    recover_closure,
    signal_agent_complete,
    supervise,
    write_once,
)

IDENTITY = {"container_id": "a" * 64, "image_id": "sha256:" + "b" * 64, "attempt_label": "v2-test"}


def inspect_result(*, running=False, label="v2-test", restart="no", auto_remove=False, **changes):
    state = {
        "Running": running,
        "Paused": False,
        "Restarting": False,
        "Dead": False,
        "OOMKilled": False,
        "Pid": 123 if running else 0,
        "ExitCode": 137,
        "FinishedAt": "2026-10-11T00:00:00Z",
    }
    state.update(changes)
    return SimpleNamespace(
        returncode=0,
        stdout=" ".join(
            json.dumps(value)
            for value in (IDENTITY["container_id"], IDENTITY["image_id"], label, state, restart, auto_remove)
        ).encode(),
    )


class FakeController:
    def inspect_owned(self, identity):
        return {"identity": identity, "running": True, "stopped": False}

    def terminate(self, identity):
        return {"execution_boundary": "confirmed", "identity": identity}

    def capture(self, identity, source, destination, **kwargs):
        destination.write_bytes(b"test archive bytes")
        return {
            "status": "complete",
            "file": destination.name,
            "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        }


def good_usage():
    bounds = {"input_tokens": 100, "output_tokens": 7, "model_calls": 1, "tool_calls": 0}
    return {
        "schema_version": SCHEMA,
        "kind": "usage",
        "provenance_status": "valid",
        "accounting_status": "partial",
        "delegation_status": "unverified",
        "exact_totals": None,
        "lower_bounds": bounds,
        "agents": [
            {
                "agent": "agent-0",
                "parent": None,
                "lower_bounds": dict(bounds),
                "complete": False,
                "reasons": ["partial_native_record"],
            }
        ],
        "reasons": ["partial_native_record"],
        "source_hashes": ["c" * 64],
        "efficiency_eligible": False,
    }


class CaptureTests(unittest.TestCase):
    def test_full_identity_required(self):
        identity = dict(IDENTITY, container_id="a" * 12)
        with self.assertRaisesRegex(CaptureError, "incomplete_container_identity"):
            DockerController(command=lambda *a, **k: self.fail("must not query")).terminate(identity)

    def test_foreign_label_never_killed(self):
        calls = []

        def command(argv, **kwargs):
            calls.append(argv)
            return inspect_result(running=True, label="foreign")

        with self.assertRaisesRegex(CaptureError, "ownership_changed"):
            DockerController(command=command).terminate(IDENTITY)
        self.assertEqual(len(calls), 1)

    def test_restart_and_autoremove_rejected(self):
        for kwargs in ({"restart": "always"}, {"auto_remove": True}):
            with (
                self.subTest(kwargs=kwargs),
                self.assertRaisesRegex(CaptureError, "unsafe_container_lifecycle"),
            ):
                DockerController(command=lambda *a, bound=kwargs, **k: inspect_result(**bound)).terminate(
                    IDENTITY
                )

    def test_inspection_error_not_absence(self):
        with self.assertRaisesRegex(CaptureError, "inspection_unavailable"):
            DockerController(command=lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"")).terminate(
                IDENTITY
            )

    def test_kill_only_full_owned_id_and_confirm_independently(self):
        calls = []

        def command(argv, **kwargs):
            calls.append(argv)
            return (
                inspect_result(running=len(calls) == 1)
                if "inspect" in argv
                else SimpleNamespace(returncode=0)
            )

        result = DockerController(command=command).terminate(IDENTITY)
        self.assertEqual(result["execution_boundary"], "confirmed")
        self.assertEqual(
            calls[1], ["docker", "container", "kill", "--signal", "KILL", IDENTITY["container_id"]]
        )
        self.assertFalse(result["native_end_inferred"])

    def test_kill_success_without_stopped_inspection_unconfirmed(self):
        def command(argv, **kwargs):
            return inspect_result(running=True) if "inspect" in argv else SimpleNamespace(returncode=0)

        self.assertEqual(
            DockerController(command=command).terminate(IDENTITY)["execution_boundary"], "unconfirmed"
        )

    def test_signal_error_with_actual_exit_is_not_fabricated_success(self):
        calls = []

        def command(argv, **kwargs):
            calls.append(argv)
            return (
                inspect_result(running=len(calls) == 1)
                if "inspect" in argv
                else SimpleNamespace(returncode=1)
            )

        result = DockerController(command=command).terminate(IDENTITY)
        self.assertEqual(result["execution_boundary"], "confirmed")
        self.assertEqual(result["command_state"], "failed")

    def test_state_booleans_not_coerced(self):
        for kwargs in (
            {"Running": 0},
            {"Pid": True},
            {"Pid": -1},
            {"Running": True, "Pid": 0},
            {"Dead": True},
            {"Paused": True},
            {"ExitCode": True},
            {"FinishedAt": None},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(CaptureError):
                DockerController(command=lambda *a, bound=kwargs, **k: inspect_result(**bound)).inspect_owned(
                    IDENTITY
                )

    def test_stopped_capture_rechecks_ownership(self):
        calls = []

        def command(*args, **kwargs):
            calls.append(1)
            return inspect_result(label="v2-test" if len(calls) == 1 else "foreign")

        def stream(argv, target, **kwargs):
            target.write_bytes(b"partial")
            return {"status": "complete"}

        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(CaptureError, "ownership_changed"),
        ):
            DockerController(command=command, stream=stream).capture(
                IDENTITY, "/workspace", Path(temporary) / "out.tar"
            )

    def test_stream_preserves_bounded_real_process_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "out"
            result = _stream(
                [sys.executable, "-I", "-B", "-c", "import sys;sys.stdout.buffer.write(b'x'*10000)"],
                path,
                max_bytes=128,
                timeout=5,
            )
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["reason"], "capture_size_limit")
            self.assertEqual(path.read_bytes(), b"x" * 128)
            self.assertEqual(result["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_stream_timeout_kills_our_real_client(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = _stream(
                [sys.executable, "-I", "-B", "-c", "import time;time.sleep(60)"],
                Path(temporary) / "out",
                max_bytes=128,
                timeout=0.1,
            )
            self.assertEqual(result["reason"], "capture_timeout")
            self.assertEqual(result["status"], "missing")

    def test_stream_stderr_cannot_deadlock_or_grow_unbounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = _stream(
                [sys.executable, "-I", "-B", "-c", "import sys;sys.stderr.buffer.write(b'x'*1000000)"],
                Path(temporary) / "out",
                max_bytes=128,
                timeout=5,
            )
            self.assertEqual(result["reason"], "capture_stderr_limit")
            self.assertEqual(result["stderr_bytes"], 65536)

    def test_unsafe_capture_paths_rejected_before_backend(self):
        with tempfile.TemporaryDirectory() as temporary:
            controller = DockerController(command=lambda *a, **k: self.fail("must not query"))
            for source in ("/", "../x", "/a/../b", "/proc/1", "/workspace/", "/sys/x"):
                with self.subTest(source=source), self.assertRaises(CaptureError):
                    controller.capture(IDENTITY, source, Path(temporary) / "out")


class ClosureTests(unittest.TestCase):
    def test_durable_finalization_recovers_identical_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "close"
            result = close_attempt(FakeController(), IDENTITY, path, ["/workspace"], reason="deadline")
            original = (path / "closure.json").read_bytes()
            (path / "closure.json").unlink()
            self.assertEqual(recover_closure(path), result)
            self.assertEqual((path / "closure.json").read_bytes(), original)

    def test_changed_archive_cannot_be_rehashed_during_recovery(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "close"
            close_attempt(FakeController(), IDENTITY, path, ["/workspace"], reason="deadline")
            (path / "output-000.tar").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "artifact_changed"):
                recover_closure(path)

    def test_crash_after_stop_cannot_create_a_historical_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "close"
            with patch(
                "evalopt_v2.lifecycle.write_once",
                side_effect=lambda p, v: (
                    (_ for _ in ()).throw(KeyboardInterrupt())
                    if p.name == "termination.json"
                    else write_once(p, v)
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    close_attempt(FakeController(), IDENTITY, path, ["/workspace"], reason="deadline")
            with self.assertRaisesRegex(ValueError, "interrupted_closure_requires_inspection"):
                close_attempt(FakeController(), IDENTITY, path, ["/workspace"], reason="deadline")

    def test_inspection_timeout_finalizes_explicit_failure(self):
        class Failed(FakeController):
            def terminate(self, identity):
                raise subprocess.TimeoutExpired("docker", 15)

        with tempfile.TemporaryDirectory() as temporary:
            result = close_attempt(
                Failed(), IDENTITY, Path(temporary) / "close", ["/workspace"], reason="deadline"
            )
            self.assertEqual(result["execution_boundary"], "unconfirmed")
            self.assertEqual(result["snapshot"], "missing")
            self.assertEqual(
                continuation_decision(
                    result, good_usage(), runtime_identity_verified=True, quota_allowed=True
                )["decision"],
                "stop",
            )

    def test_partial_capture_never_complete(self):
        class Failed(FakeController):
            def capture(self, identity, source, destination, **kwargs):
                destination.write_bytes(b"partial")
                raise OSError("simulated failure")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "close"
            result = close_attempt(Failed(), IDENTITY, path, ["/workspace"], reason="deadline")
            self.assertEqual(result["snapshot"], "partial")
            self.assertEqual((path / "output-000.tar").read_bytes(), b"partial")
            self.assertEqual(read_record(path / "capture-000.json")["status"], "partial")

    def test_missing_child_end_may_continue_with_proven_cutoff(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = close_attempt(
                FakeController(), IDENTITY, Path(temporary) / "close", ["/workspace"], reason="deadline"
            )
            decision = continuation_decision(
                result, good_usage(), runtime_identity_verified=True, quota_allowed=True
            )
            self.assertEqual(decision["decision"], "continue")
            self.assertEqual(decision["historical_delegation"], "unverified")
            self.assertFalse(decision["retry_authorized"])
            self.assertFalse(decision["task_success_inferred"])

    def test_contradictions_and_unknown_permission_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            closure = close_attempt(
                FakeController(), IDENTITY, Path(temporary) / "close", ["/workspace"], reason="deadline"
            )
            for changes in (
                {"provenance_status": "invalid"},
                {"delegation_status": "violated"},
                {"accounting_status": "unavailable"},
            ):
                usage = dict(good_usage(), **changes)
                with self.subTest(changes=changes):
                    self.assertEqual(
                        continuation_decision(
                            closure, usage, runtime_identity_verified=True, quota_allowed=True
                        )["decision"],
                        "stop",
                    )
            for runtime, quota in ((False, True), (True, None), (1, True), (True, 1)):
                self.assertEqual(
                    continuation_decision(
                        closure, good_usage(), runtime_identity_verified=runtime, quota_allowed=quota
                    )["decision"],
                    "stop",
                )

    def test_changed_start_identity_or_limits_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "close"
            close_attempt(FakeController(), IDENTITY, path, ["/workspace"], reason="deadline")
            with self.assertRaisesRegex(ValueError, "identity_changed"):
                close_attempt(
                    FakeController(), IDENTITY, path, ["/workspace"], reason="deadline", max_bytes=1
                )


class SupervisorTests(unittest.TestCase):
    def test_invalid_capture_spec_never_creates_ready_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "supervisor"
            for paths, size, timeout in (
                (["/proc/1"], 100, 10),
                ([{}], 100, 10),
                (["/workspace", "/workspace"], 100, 10),
                (["/workspace"], True, 10),
                (["/workspace"], 100, float("inf")),
            ):
                with self.subTest(paths=paths, size=size, timeout=timeout), self.assertRaises(ValueError):
                    prepare_supervisor(
                        target,
                        IDENTITY,
                        paths,
                        seconds=10,
                        worker_pid=os.getpid(),
                        max_bytes=size,
                        capture_timeout=timeout,
                    )
                self.assertFalse(target.exists())

    def test_malformed_sentinel_stops_without_claiming_agent_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=10, worker_pid=os.getpid()
            )
            directory = Path(prepared["spec"]).parent
            write_once(directory / "agent-complete.json", {"unbound": True})
            result = supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())
            self.assertEqual(result["reason"], "worker_interrupted")
            self.assertEqual(result["execution_boundary"], "confirmed")
            self.assertTrue((directory / "supervision-failure.json").is_file())

    def test_unhashable_accounting_states_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            closure = close_attempt(
                FakeController(), IDENTITY, Path(temporary) / "closure", ["/workspace"], reason="deadline"
            )
            for field in ("delegation_status", "accounting_status", "provenance_status"):
                usage = good_usage()
                usage[field] = {}
                result = continuation_decision(
                    closure, usage, runtime_identity_verified=True, quota_allowed=True
                )
                self.assertEqual(result["decision"], "stop")
                self.assertIn("usage_invalid", result["reasons"])

    def test_supervisor_records_deadline_and_recovers_without_container_calls(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=0.05, worker_pid=os.getpid()
            )
            self.assertIn("deadline_monotonic", read_record(prepared["spec"]))
            result = supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())
            self.assertEqual(result["reason"], "deadline")
            self.assertEqual(result, supervise(prepared["spec"], prepared["spec_sha256"]))

    def test_controller_completion_sentinel_and_wrong_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=10, worker_pid=os.getpid()
            )
            with self.assertRaisesRegex(ValueError, "spec_changed"):
                signal_agent_complete(prepared["spec"], "0" * 64)
            signal_agent_complete(prepared["spec"], prepared["spec_sha256"])
            self.assertEqual(
                supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())["reason"],
                "agent_end",
            )

    def test_worker_disappearance_triggers_distinct_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=10, worker_pid=os.getpid()
            )
            with patch("evalopt_v2.lifecycle.worker_identity", return_value=None):
                result = supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())
            self.assertEqual(result["reason"], "worker_interrupted")
            closure = read_record(Path(prepared["spec"]).parent / "closure/closure.json")
            self.assertEqual(
                continuation_decision(
                    closure, good_usage(), runtime_identity_verified=True, quota_allowed=True
                )["decision"],
                "stop",
            )

    def test_supervisor_source_and_clock_drift_rejected_before_container_queries(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=10, worker_pid=os.getpid()
            )
            for target in ("supervisor_sources", "clock_epoch"):
                with (
                    self.subTest(target=target),
                    patch("evalopt_v2.lifecycle." + target, return_value="changed"),
                    self.assertRaisesRegex(ValueError, "source_or_clock_changed"),
                ):
                    supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())

    def test_missing_lock_and_unsafe_directory_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=10, worker_pid=os.getpid()
            )
            directory = Path(prepared["spec"]).parent
            (directory / "supervisor.lock").unlink()
            with self.assertRaisesRegex(ValueError, "lock_missing"):
                supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())
            directory.chmod(0o777)
            with self.assertRaisesRegex(ValueError, "unsafe_supervisor_directory"):
                supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())

    def test_two_supervisors_cannot_own_one_closure(self):
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", IDENTITY, ["/workspace"], seconds=10, worker_pid=os.getpid()
            )
            with (Path(prepared["spec"]).parent / "supervisor.lock").open("rb") as held:
                fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with self.assertRaises(BlockingIOError):
                    supervise(prepared["spec"], prepared["spec_sha256"], controller=FakeController())

    def test_forged_usage_and_closure_cannot_authorize_continuation(self):
        with tempfile.TemporaryDirectory() as temporary:
            closure = close_attempt(
                FakeController(), IDENTITY, Path(temporary) / "closure", ["/workspace"], reason="deadline"
            )
            usage = good_usage()
            usage["lower_bounds"]["input_tokens"] = 0
            self.assertEqual(
                continuation_decision(closure, usage, runtime_identity_verified=True, quota_allowed=True)[
                    "decision"
                ],
                "stop",
            )
            del closure["artifacts"]["termination.json"]
            self.assertEqual(
                continuation_decision(
                    closure, good_usage(), runtime_identity_verified=True, quota_allowed=True
                )["decision"],
                "stop",
            )


@unittest.skipUnless(
    os.environ.get("EVALOPT_V2_DOCKER_CONTROL_IMAGE"),
    "opt-in disposable Docker fault controls; no model calls",
)
class ActualDockerControls(unittest.TestCase):
    def setUp(self):
        self.image = os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"]
        self.label = "v2-capture-" + uuid.uuid4().hex
        self.ids = []

    def tearDown(self):
        for cid in self.ids:
            result = subprocess.run(
                [
                    "docker",
                    "container",
                    "inspect",
                    "--format",
                    '{{index .Config.Labels "' + LABEL + '"}}',
                    cid,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            self.assertEqual(result.stdout.strip(), self.label)
            subprocess.run(
                ["docker", "container", "rm", "--force", cid], capture_output=True, timeout=15, check=True
            )

    def create(self):
        program = "import os,time;os.mkdir('/tmp/v2');open('/tmp/v2/early','w').write('early');pid=os.fork();\nif pid==0:\n os.setsid();time.sleep(1);open('/tmp/v2/late','w').write('late')\nelse:\n print('ready',flush=True);time.sleep(60)"
        cid = subprocess.run(
            [
                "docker",
                "container",
                "create",
                "--pull",
                "never",
                "--name",
                self.label,
                "--label",
                LABEL + "=" + self.label,
                "--network",
                "none",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "64",
                "--memory",
                "128m",
                "--cpus",
                "1",
                "--user",
                "65534:65534",
                self.image,
                "/usr/bin/python3",
                "-I",
                "-B",
                "-c",
                program,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
        self.ids.append(cid)
        subprocess.run(["docker", "container", "start", cid], capture_output=True, timeout=15, check=True)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            logs = subprocess.run(
                ["docker", "container", "logs", cid], capture_output=True, timeout=5, check=True
            ).stdout
            if b"ready" in logs:
                break
            time.sleep(0.02)
        else:
            self.fail("trusted fixture failed to become ready")
        image = subprocess.run(
            ["docker", "container", "inspect", "--format", "{{.Image}}", cid],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        ).stdout.strip()
        return {"container_id": cid, "image_id": image, "attempt_label": self.label}

    def test_actual_detached_late_writer_cannot_change_stopped_capture(self):
        identity = self.create()
        controller = DockerController()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "close"
            result = close_attempt(controller, identity, path, ["/tmp/v2"], reason="deadline")
            self.assertEqual(result["execution_boundary"], "confirmed")
            self.assertEqual(result["snapshot"], "complete")
            with tarfile.open(fileobj=io.BytesIO((path / "output-000.tar").read_bytes())) as tar:
                names = tar.getnames()
                self.assertTrue(any(n.endswith("/early") for n in names))
                self.assertFalse(any(n.endswith("/late") for n in names))
            time.sleep(1.1)
            controller.capture(identity, "/tmp/v2", Path(temporary) / "again.tar")
            self.assertEqual(
                (path / "output-000.tar").read_bytes(), (Path(temporary) / "again.tar").read_bytes()
            )

    def test_actual_wrong_label_denies_signal_and_missing_source_stays_missing(self):
        identity = self.create()
        controller = DockerController()
        with self.assertRaisesRegex(CaptureError, "ownership_changed"):
            controller.terminate(dict(identity, attempt_label="wrong"))
        self.assertTrue(controller.inspect_owned(identity)["running"])
        controller.terminate(identity)
        with tempfile.TemporaryDirectory() as temporary:
            result = controller.capture(identity, "/absent-v2-control", Path(temporary) / "missing.tar")
            self.assertNotEqual(result["status"], "complete")

    def test_actual_external_supervisor_survives_owned_worker_death(self):
        identity = self.create()
        worker = subprocess.Popen(
            [sys.executable, "-I", "-B", "-c", "import time;time.sleep(60)"],
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        supervisor = None
        try:
            with tempfile.TemporaryDirectory() as temporary:
                prepared = prepare_supervisor(
                    Path(temporary) / "supervisor", identity, ["/tmp/v2"], seconds=10, worker_pid=worker.pid
                )
                root = str(Path(__file__).resolve().parents[1])
                launcher = "import sys;sys.path.insert(0,sys.argv.pop(1));from evalopt_v2.lifecycle import supervisor_main;raise SystemExit(supervisor_main())"
                supervisor = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-B",
                        "-c",
                        launcher,
                        root,
                        "--spec",
                        prepared["spec"],
                        "--spec-sha256",
                        prepared["spec_sha256"],
                    ],
                    start_new_session=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                ready = Path(prepared["spec"]).parent / "ready.json"
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and not ready.exists() and supervisor.poll() is None:
                    time.sleep(0.02)
                self.assertTrue(ready.is_file())
                worker.kill()
                worker.wait(timeout=5)
                _, stderr = supervisor.communicate(timeout=20)
                self.assertEqual(supervisor.returncode, 0, stderr.decode())
                end = read_record(ready.parent / "end.json")
                self.assertEqual(end["reason"], "worker_interrupted")
                self.assertEqual(end["execution_boundary"], "confirmed")
                self.assertTrue(DockerController().inspect_owned(identity)["stopped"])
        finally:
            for process in (worker, supervisor):
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

    def test_actual_external_deadline_stops_without_worker_completion(self):
        identity = self.create()
        with tempfile.TemporaryDirectory() as temporary:
            prepared = prepare_supervisor(
                Path(temporary) / "supervisor", identity, ["/tmp/v2"], seconds=0.2, worker_pid=os.getpid()
            )
            root = str(Path(__file__).resolve().parents[1])
            launcher = "import sys;sys.path.insert(0,sys.argv.pop(1));from evalopt_v2.lifecycle import supervisor_main;raise SystemExit(supervisor_main())"
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-B",
                    "-c",
                    launcher,
                    root,
                    "--spec",
                    prepared["spec"],
                    "--spec-sha256",
                    prepared["spec_sha256"],
                ],
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                timeout=20,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            end = read_record(Path(prepared["spec"]).parent / "end.json")
            self.assertEqual(end["reason"], "deadline")
            self.assertEqual(end["execution_boundary"], "confirmed")
            self.assertTrue(DockerController().inspect_owned(identity)["stopped"])


if __name__ == "__main__":
    unittest.main()
