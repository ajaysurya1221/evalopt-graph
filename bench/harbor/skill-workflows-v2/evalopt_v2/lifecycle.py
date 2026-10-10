"""Durable closure independent of native ends, hidden grades and task acceptance."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from .accounting import validate_usage
from .capture import HEX, CaptureError, DockerController, check_capture_options, check_identity, now
from .framing import SCHEMA, strict_json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def write_once(path, value):
    """Publish complete bytes exclusively; interrupted temp files are not records."""
    path = Path(path)
    raw = canonical(value) + b"\n"
    if path.exists():
        if path.is_symlink() or path.read_bytes() != raw:
            raise ValueError("immutable_record_changed")
        return
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        os.unlink(temporary)


def read_record(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("record_missing_or_unsafe")
    return strict_json(path.read_bytes())


def manifest(directory):
    result = {}
    for path in sorted(Path(directory).iterdir()):
        if path.name.startswith(".pending-") or path.name in {"finalize.json", "closure.json"}:
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError("unsafe_closure_artifact")
        raw = path.read_bytes()
        result[path.name] = {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
    return result


def recover_closure(directory):
    """Replay a frozen intent only. No new container queries or rehashed repairs."""
    directory = Path(directory)
    intent = read_record(directory / "finalize.json")
    if (
        set(intent) != {"schema_version", "kind", "artifacts", "closure"}
        or intent["schema_version"] != SCHEMA
        or intent["kind"] != "closure_intent"
    ):
        raise ValueError("invalid_closure_intent")
    if manifest(directory) != intent["artifacts"]:
        raise ValueError("closure_artifact_changed")
    if canonical(intent["closure"].get("artifacts")) != canonical(intent["artifacts"]):
        raise ValueError("closure_intent_artifact_mismatch")
    validate_closure(intent["closure"])
    write_once(directory / "closure.json", intent["closure"])
    return intent["closure"]


def check_capture_roster(capture_paths, max_bytes, capture_timeout):
    if (
        not isinstance(capture_paths, list)
        or not capture_paths
        or len(capture_paths) > 8
        or not all(isinstance(item, str) for item in capture_paths)
        or len(set(capture_paths)) != len(capture_paths)
    ):
        raise ValueError("invalid_capture_roster")
    for source in capture_paths:
        check_capture_options(source, max_bytes, capture_timeout)


def close_attempt(
    controller, identity, directory, capture_paths, *, reason, max_bytes=64 * 1024**2, capture_timeout=60
):
    """Close one attempt from an external supervisor; never restart a candidate.

    Recovery before a durable finalization intent records an interrupted closure,
    not a new historical boundary. The operator must investigate before admission.
    """
    check_identity(identity)
    if reason not in {"agent_end", "deadline", "worker_interrupted"}:
        raise ValueError("unknown_closure_reason")
    check_capture_roster(capture_paths, max_bytes, capture_timeout)
    directory = Path(directory)
    if directory.exists():
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("unsafe_closure_directory")
        start = read_record(directory / "start.json")
        if (
            start["identity"] != identity
            or start["capture_paths"] != capture_paths
            or start["reason"] != reason
            or start["max_bytes"] != max_bytes
            or start["capture_timeout"] != capture_timeout
        ):
            raise ValueError("closure_identity_changed")
        if (directory / "finalize.json").exists():
            return recover_closure(directory)
        # A fresh current stop cannot fill a missing historical close transaction.
        raise ValueError("interrupted_closure_requires_inspection")
    directory.mkdir(parents=True)
    write_once(
        directory / "start.json",
        {
            "schema_version": SCHEMA,
            "kind": "closure_start",
            "identity": identity,
            "capture_paths": capture_paths,
            "reason": reason,
            "started_at": now(),
            "max_bytes": max_bytes,
            "capture_timeout": capture_timeout,
        },
    )
    termination, captures, failures = None, [], []
    try:
        termination = controller.terminate(identity)
        write_once(directory / "termination.json", termination)
        if termination["execution_boundary"] != "confirmed":
            failures.append("execution_boundary_unconfirmed")
        else:
            for index, source in enumerate(capture_paths):
                target = directory / f"output-{index:03d}.tar"
                try:
                    captured = controller.capture(
                        identity, source, target, max_bytes=max_bytes, timeout=capture_timeout
                    )
                except (OSError, ValueError, TimeoutError, subprocess.TimeoutExpired) as exc:
                    captured = {
                        "schema_version": SCHEMA,
                        "kind": "capture",
                        "source": source,
                        "file": target.name if target.is_file() else None,
                        "status": "partial" if target.is_file() else "missing",
                        "reason": type(exc).__name__,
                    }
                captures.append(captured)
                write_once(directory / f"capture-{index:03d}.json", captured)
                if captured["status"] != "complete":
                    failures.append("required_capture_incomplete")
    except (OSError, CaptureError, TimeoutError, subprocess.TimeoutExpired) as exc:
        failures.append("termination_observation_unavailable")
        write_once(
            directory / "termination-failure.json",
            {
                "schema_version": SCHEMA,
                "kind": "termination_failure",
                "error_type": type(exc).__name__,
                "observed_at": now(),
            },
        )
    closure = {
        "schema_version": SCHEMA,
        "kind": "closure",
        "identity": identity,
        "reason": reason,
        "execution_boundary": "confirmed"
        if termination and termination["execution_boundary"] == "confirmed"
        else "unconfirmed",
        "snapshot": "complete"
        if len(captures) == len(capture_paths) and all(item["status"] == "complete" for item in captures)
        else "missing"
        if not captures
        else "partial",
        "native_end_inferred": False,
        "failures": sorted(set(failures)),
        "finished_at": now(),
        "artifacts": manifest(directory),
    }
    write_once(
        directory / "finalize.json",
        {
            "schema_version": SCHEMA,
            "kind": "closure_intent",
            "artifacts": manifest(directory),
            "closure": closure,
        },
    )
    return recover_closure(directory)


def validate_closure(closure):
    fields = {
        "schema_version",
        "kind",
        "identity",
        "reason",
        "execution_boundary",
        "snapshot",
        "native_end_inferred",
        "failures",
        "finished_at",
        "artifacts",
    }
    if (
        not isinstance(closure, dict)
        or set(closure) != fields
        or closure["schema_version"] != SCHEMA
        or closure["kind"] != "closure"
    ):
        raise ValueError("invalid_closure_schema")
    check_identity(closure["identity"])
    if (
        closure["reason"] not in {"agent_end", "deadline", "worker_interrupted"}
        or closure["execution_boundary"] not in {"confirmed", "unconfirmed"}
        or closure["snapshot"] not in {"complete", "partial", "missing"}
        or closure["native_end_inferred"] is not False
    ):
        raise ValueError("invalid_closure_state")
    if (
        not isinstance(closure["failures"], list)
        or not all(isinstance(reason, str) for reason in closure["failures"])
        or not isinstance(closure["artifacts"], dict)
        or "start.json" not in closure["artifacts"]
    ):
        raise ValueError("invalid_closure_artifacts")
    for name, record in closure["artifacts"].items():
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or not isinstance(record, dict)
            or set(record) != {"sha256", "bytes"}
            or type(record["bytes"]) is not int
            or record["bytes"] < 0
            or not isinstance(record["sha256"], str)
            or not HEX.fullmatch(record["sha256"])
        ):
            raise ValueError("invalid_closure_artifact_identity")
    if closure["execution_boundary"] == "confirmed" and "termination.json" not in closure["artifacts"]:
        raise ValueError("closure_boundary_evidence_missing")
    if closure["snapshot"] == "complete" and (
        closure["execution_boundary"] != "confirmed"
        or closure["failures"]
        or "capture-000.json" not in closure["artifacts"]
        or "output-000.tar" not in closure["artifacts"]
    ):
        raise ValueError("closure_snapshot_evidence_missing")
    return closure


def continuation_decision(closure, usage, *, runtime_identity_verified, quota_allowed):
    """Prospective authored-only rule; neither continuation nor a timeout means success.

    Missing native child ends may leave historical delegation unverified after a
    proven container cutoff. That uncertainty is retained and never authorizes an
    attempt retry. Invalid provenance or an observed cap breach still stops.
    """
    reasons = []
    if runtime_identity_verified is not True:
        reasons.append("runtime_identity_unverified")
    if quota_allowed is not True:
        reasons.append("subscription_permission_unavailable")
    try:
        validate_closure(closure)
    except (ValueError, TypeError, KeyError):
        reasons.append("closure_invalid")
    if isinstance(closure, dict):
        if closure.get("execution_boundary") != "confirmed":
            reasons.append("execution_boundary_unconfirmed")
        if closure.get("snapshot") != "complete" or closure.get("failures") != []:
            reasons.append("required_capture_incomplete")
        if closure.get("native_end_inferred") is not False:
            reasons.append("native_end_inference_forbidden")
        if closure.get("reason") == "worker_interrupted":
            reasons.append("worker_interrupted_requires_inspection")
    usage_valid = True
    try:
        validate_usage(usage)
    except (ValueError, TypeError, KeyError):
        usage_valid = False
        reasons.append("usage_invalid")
    if usage_valid:
        if usage.get("provenance_status") != "valid":
            reasons.append("accounting_provenance_invalid_or_unavailable")
        if usage.get("delegation_status") not in {"verified", "unverified"}:
            reasons.append("delegation_limit_violated")
        if usage.get("accounting_status") not in {"complete", "partial"}:
            reasons.append("accounting_unavailable")
    return {
        "schema_version": SCHEMA,
        "kind": "continuation",
        "decision": "stop" if reasons else "continue",
        "reasons": sorted(set(reasons)),
        "retry_authorized": False,
        "task_success_inferred": False,
        "historical_delegation": usage["delegation_status"] if usage_valid else "unverified",
    }


def supervisor_sources():
    root = Path(__file__).resolve().parent
    return {
        name: hashlib.sha256((root / name).read_bytes()).hexdigest()
        for name in ("framing.py", "accounting.py", "capture.py", "lifecycle.py")
    }


def clock_epoch():
    """Bind cross-process monotonic deadlines to this boot, never wall-clock time."""
    boot = Path("/proc/sys/kernel/random/boot_id")
    if boot.is_file():
        raw = boot.read_bytes()
    else:
        raw = subprocess.run(
            ["/usr/sbin/sysctl", "-n", "kern.boottime"], capture_output=True, timeout=5, check=True
        ).stdout
    if not raw.strip():
        raise ValueError("clock_epoch_unavailable")
    return hashlib.sha256(raw.strip()).hexdigest()


def worker_identity(pid):
    """Observe only a specified worker PID/start value; never read command lines."""
    if type(pid) is not int or pid <= 1:
        raise ValueError("invalid_worker_pid")
    result = subprocess.run(
        ["/bin/ps", "-p", str(pid), "-o", "stat=", "-o", "lstart="],
        capture_output=True,
        timeout=5,
        check=False,
    )
    if result.returncode == 1 and not result.stdout.strip() and not result.stderr.strip():
        return None
    if result.returncode != 0:
        raise ValueError("worker_observation_unavailable")
    parts = result.stdout.decode("ascii").strip().split(maxsplit=1)
    if len(parts) != 2 or not parts[1].strip():
        raise ValueError("worker_observation_malformed")
    if parts[0].startswith("Z"):
        return None
    return {"pid": pid, "started_sha256": hashlib.sha256(parts[1].encode()).hexdigest()}


def prepare_supervisor(
    directory, identity, capture_paths, *, seconds, worker_pid, max_bytes=64 * 1024**2, capture_timeout=60
):
    """Publish deadline before starting agent work; caller waits for ready.json.

    This directory must be outside all candidate mounts. Mode 0700 is necessary
    but not a substitute for the dispatcher's no-controller-mount invariant.
    """
    check_identity(identity)
    check_capture_roster(capture_paths, max_bytes, capture_timeout)
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not 0 < seconds <= 1800:
        raise ValueError("invalid_supervisor_budget")
    worker = worker_identity(worker_pid)
    if worker is None:
        raise ValueError("worker_missing_before_dispatch")
    directory = Path(directory).absolute()
    if directory.exists() or directory.is_symlink():
        raise ValueError("supervisor_directory_not_fresh")
    directory = directory.resolve()
    directory.mkdir(mode=0o700, parents=True)
    if directory.resolve() != directory:
        raise ValueError("supervisor_path_contains_symlink")
    spec = {
        "schema_version": SCHEMA,
        "kind": "supervisor_spec",
        "identity": identity,
        "capture_paths": capture_paths,
        "max_bytes": max_bytes,
        "capture_timeout": capture_timeout,
        "worker": worker,
        "deadline_monotonic": time.monotonic() + seconds,
        "clock_epoch": clock_epoch(),
        "source_hashes": supervisor_sources(),
        "created_at": now(),
    }
    write_once(directory / "spec.json", spec)
    (directory / "supervisor.lock").touch(mode=0o600, exist_ok=False)
    return {
        "spec": str(directory / "spec.json"),
        "spec_sha256": hashlib.sha256((directory / "spec.json").read_bytes()).hexdigest(),
    }


def signal_agent_complete(spec_path, spec_sha256):
    """Only the external controller writes this sentinel, after its agent call exits."""
    spec_path = Path(spec_path)
    if hashlib.sha256(spec_path.read_bytes()).hexdigest() != spec_sha256:
        raise ValueError("supervisor_spec_changed")
    write_once(
        spec_path.parent / "agent-complete.json",
        {
            "schema_version": SCHEMA,
            "kind": "agent_completion_signal",
            "spec_sha256": spec_sha256,
            "observed_at": now(),
        },
    )


def supervise(spec_path, spec_sha256, *, controller=None, poll_seconds=0.05):
    """Run in an independent start_new_session process, never in the agent worker.

    An existing end can be replayed; an interrupted pre-finalization closure cannot
    be silently retried. The scheduler must stop if this supervisor disappears.
    """
    spec_path = Path(spec_path).absolute()
    directory = spec_path.parent
    if directory.resolve() != directory or directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError("unsafe_supervisor_directory")
    raw = spec_path.read_bytes()
    if spec_path.is_symlink() or hashlib.sha256(raw).hexdigest() != spec_sha256:
        raise ValueError("supervisor_spec_changed")
    spec = strict_json(raw)
    fields = {
        "schema_version",
        "kind",
        "identity",
        "capture_paths",
        "max_bytes",
        "capture_timeout",
        "worker",
        "deadline_monotonic",
        "clock_epoch",
        "source_hashes",
        "created_at",
    }
    if not isinstance(spec, dict) or set(spec) != fields:
        raise ValueError("invalid_supervisor_spec")
    if (
        spec.get("schema_version") != SCHEMA
        or spec.get("kind") != "supervisor_spec"
        or spec.get("source_hashes") != supervisor_sources()
        or spec.get("clock_epoch") != clock_epoch()
    ):
        raise ValueError("supervisor_source_or_clock_changed")
    check_identity(spec["identity"])
    check_capture_roster(spec["capture_paths"], spec["max_bytes"], spec["capture_timeout"])
    worker = spec["worker"]
    if (
        not isinstance(worker, dict)
        or set(worker) != {"pid", "started_sha256"}
        or type(worker["pid"]) is not int
        or worker["pid"] <= 1
        or not isinstance(worker["started_sha256"], str)
        or not HEX.fullmatch(worker["started_sha256"])
    ):
        raise ValueError("invalid_supervisor_worker")
    deadline = spec["deadline_monotonic"]
    if (
        isinstance(deadline, bool)
        or not isinstance(deadline, (int, float))
        or not 0 < deadline < float("inf")
    ):
        raise ValueError("invalid_absolute_deadline")
    lock_path = directory / "supervisor.lock"
    if lock_path.is_symlink() or not lock_path.is_file():
        raise ValueError("supervisor_lock_missing")
    with lock_path.open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (directory / "end.json").exists():
            end = read_record(directory / "end.json")
            closure = recover_closure(directory / "closure")
            if end["spec_sha256"] != spec_sha256 or end["closure_sha256"] != digest(closure):
                raise ValueError("supervisor_end_changed")
            return end
        controller = DockerController() if controller is None else controller
        # Never modify the original ready receipt on a recovery invocation.
        ready = directory / "ready.json"
        if not ready.exists():
            write_once(directory / "initial-container.json", controller.inspect_owned(spec["identity"]))
            write_once(
                ready,
                {
                    "schema_version": SCHEMA,
                    "kind": "supervisor_ready",
                    "spec_sha256": spec_sha256,
                    "pid": os.getpid(),
                    "observed_at": now(),
                },
            )
        elif read_record(ready).get("spec_sha256") != spec_sha256:
            raise ValueError("supervisor_ready_changed")
        if (directory / "closure" / "finalize.json").exists():
            closure = recover_closure(directory / "closure")
        else:
            if (directory / "closure").exists():
                raise ValueError("interrupted_closure_requires_inspection")
            while True:
                if time.monotonic() >= deadline:
                    reason = "deadline"
                    break
                try:
                    if hashlib.sha256(spec_path.read_bytes()).hexdigest() != spec_sha256:
                        raise ValueError("supervisor_spec_changed")
                    signal = directory / "agent-complete.json"
                    if signal.exists() or signal.is_symlink():
                        record = read_record(signal)
                        if (
                            not isinstance(record, dict)
                            or set(record) != {"schema_version", "kind", "spec_sha256", "observed_at"}
                            or record["schema_version"] != SCHEMA
                            or record["kind"] != "agent_completion_signal"
                            or record["spec_sha256"] != spec_sha256
                        ):
                            raise ValueError("invalid_agent_completion_signal")
                        reason = "agent_end"
                        break
                    observed = worker_identity(spec["worker"]["pid"])
                except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
                    # Stop with the previously validated in-memory identity, not
                    # with a modified record. This is never ordinary completion.
                    write_once(
                        directory / "supervision-failure.json",
                        {
                            "schema_version": SCHEMA,
                            "kind": "supervision_failure",
                            "error_type": type(exc).__name__,
                            "observed_at": now(),
                            "spec_sha256": spec_sha256,
                        },
                    )
                    observed = None
                if observed != spec["worker"]:
                    reason = "worker_interrupted"
                    break
                time.sleep(min(poll_seconds, max(0, deadline - time.monotonic())))
            closure = close_attempt(
                controller,
                spec["identity"],
                directory / "closure",
                spec["capture_paths"],
                reason=reason,
                max_bytes=spec["max_bytes"],
                capture_timeout=spec["capture_timeout"],
            )
        end = {
            "schema_version": SCHEMA,
            "kind": "supervisor_end",
            "spec_sha256": spec_sha256,
            "closure_sha256": digest(closure),
            "reason": closure["reason"],
            "execution_boundary": closure["execution_boundary"],
            "snapshot": closure["snapshot"],
            "native_end_inferred": False,
            "finished_at": now(),
        }
        write_once(directory / "end.json", end)
        return end


def supervisor_main(argv=None):
    parser = argparse.ArgumentParser(description="External v2 authored-task supervisor; no agent dispatch.")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    args = parser.parse_args(argv)
    result = supervise(args.spec, args.spec_sha256)
    print(
        json.dumps(
            {
                "schema_version": SCHEMA,
                "kind": "supervisor_exit",
                "execution_boundary": result["execution_boundary"],
                "snapshot": result["snapshot"],
            }
        )
    )
    return 0 if result["execution_boundary"] == "confirmed" and result["snapshot"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(supervisor_main())
