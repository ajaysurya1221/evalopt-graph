"""Controller-owned command observations in disposable isolated containers."""

from __future__ import annotations

import hashlib
import os
import re
import selectors
import subprocess
import time
import uuid
from pathlib import Path

from .capture import LABEL, DockerController, check_identity
from .framing import SCHEMA, strict_json
from .lifecycle import write_once
from .preflight import IMAGE
from .records import canonical, seal_observation, validate_record


def _capture_attached(process, root, controller, identity, *, started, seconds, maximum):
    """Drain both pipes through bounded writes, including bytes queued at exit."""
    state, closure, stop_deadline = "ran", None, None
    artifacts = {}
    selector = selectors.DefaultSelector()
    outputs = {}
    try:
        for name, pipe in (("stdout.bin", process.stdout), ("stderr.bin", process.stderr)):
            outputs[name] = (root / name).open("xb")
            artifacts[name] = {
                "bytes": 0,
                "observed_bytes": 0,
                "truncated": False,
                "hasher": hashlib.sha256(),
            }
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map() or process.poll() is None:
            if state == "ran" and time.monotonic() - started >= seconds:
                state = "timed_out"
                closure = controller.terminate(identity)
                stop_deadline = time.monotonic() + 20
            if stop_deadline is not None and time.monotonic() >= stop_deadline:
                # Terminate the attach client only after the owned container's
                # explicit stop request. The caller still confirms that boundary.
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                break
            for key, _ in selector.select(0.02):
                raw = os.read(key.fileobj.fileno(), 65536)
                if not raw:
                    selector.unregister(key.fileobj)
                    continue
                item = artifacts[key.data]
                item["observed_bytes"] += len(raw)
                retained = raw[: max(0, maximum - item["bytes"])]
                outputs[key.data].write(retained)
                item["hasher"].update(retained)
                item["bytes"] += len(retained)
                item["truncated"] |= len(retained) != len(raw)
                if item["truncated"] and state == "ran":
                    state = "interrupted"
                    closure = controller.terminate(identity)
                    stop_deadline = time.monotonic() + 20
        # This invariant also covers a process that exited before the first poll;
        # neither stream can bypass the cap or require a later unbounded read.
        if any(item["observed_bytes"] > maximum for item in artifacts.values()):
            if state == "ran":
                state = "interrupted"
                closure = controller.terminate(identity)
        process.wait(timeout=5)
        for item in artifacts.values():
            item["sha256"] = item.pop("hasher").hexdigest()
        return state, closure, artifacts
    except BaseException:
        # A failed pipe read or artifact write cannot leave its candidate alive.
        # Failure still propagates; no complete observation is manufactured.
        try:
            controller.terminate(identity)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
        raise
    finally:
        selector.close()
        for output in outputs.values():
            output.flush()
            os.fsync(output.fileno())
            output.close()
        for pipe in (process.stdout, process.stderr):
            pipe.close()


def command_record(
    *,
    attempt_id,
    candidate_id,
    phase,
    command,
    execution_state,
    exit_code,
    availability,
    artifact_refs,
    artifact_sha256,
    check_id="required",
):
    value = {
        "schema_version": SCHEMA,
        "record_type": "command",
        "attempt_id": attempt_id,
        "candidate_id": candidate_id,
        "phase": phase,
        "check_id": check_id,
        "command": command,
        "execution_state": execution_state,
        "exit_code": exit_code,
        "evidence_availability": availability,
        "artifact_refs": artifact_refs,
        "artifact_sha256": artifact_sha256,
        "asserted_claim": None,
    }
    return seal_observation(value)


def visible_check(
    snapshot,
    task,
    *,
    attempt_id,
    candidate_id,
    phase,
    image,
    directory,
    seconds=30,
    max_output_bytes=2 * 1024**2,
    check_id="required",
):
    """Execute a registered visible argv once. Never ingest an agent result file.

    For an authored blocker contract, exit 3 signals unavailable *requested
    evidence*. The command still ran, and its stdout/stderr remain complete.
    This interpretation is supplied by the trusted task contract, not its output.
    """
    if not IMAGE.fullmatch(image):
        raise ValueError("visible_image_not_pinned")
    if phase not in {"initial", "post_stop"}:
        raise ValueError("visible_phase_invalid")
    if type(max_output_bytes) is not int or max_output_bytes <= 0:
        raise ValueError("visible_output_limit_invalid")
    command = task["visible_command"]
    if (
        not isinstance(command, list)
        or not command
        or any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in command)
    ):
        raise ValueError("invalid_visible_command")
    root, snapshot = Path(directory), Path(snapshot).resolve()
    if root.exists() or root.is_symlink():
        raise ValueError("visible_directory_not_fresh")
    root.mkdir(parents=True)
    label = "visible-" + uuid.uuid4().hex
    argv = [
        "docker",
        "create",
        "--pull",
        "never",
        "--name",
        label,
        "--label",
        LABEL + "=" + label,
        "--restart",
        "no",
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        "2g",
        "--pids-limit",
        "128",
        "--read-only",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,size=64m",
        "--workdir",
        "/workspace",
        "--env",
        "PYTHONDONTWRITEBYTECODE=1",
        "--mount",
        f"type=bind,src={snapshot},dst=/workspace,readonly",
        image,
        *command,
    ]
    started = time.monotonic()
    created = subprocess.run(argv, capture_output=True, timeout=30, check=True)
    container = created.stdout.decode().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", container):
        raise ValueError("visible_container_identity_missing")
    identity = {"container_id": container, "image_id": image, "attempt_label": label}
    controller = DockerController()
    controller.inspect_owned(identity)
    write_once(
        root / "start.json",
        {
            "schema_version": SCHEMA,
            "kind": "visible_start",
            "identity": identity,
            "attempt_id": attempt_id,
            "candidate_id": candidate_id,
            "phase": phase,
            "check_id": check_id,
            "command": command,
            "seconds": seconds,
            "max_output_bytes": max_output_bytes,
        },
    )
    process = subprocess.Popen(
        ["docker", "start", "--attach", container],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    state, closure, artifacts = _capture_attached(
        process, root, controller, identity, started=started, seconds=seconds, maximum=max_output_bytes
    )
    result_code = None
    after = controller.inspect_owned(identity)
    if not after["stopped"]:
        closure = controller.terminate(identity)
        after = controller.inspect_owned(identity)
    if not after["stopped"]:
        raise ValueError("visible_execution_boundary_unconfirmed")
    if state == "ran":
        result_code = after["exit_code"]
        if type(result_code) is not int:
            raise ValueError("visible_exit_unknown")
    availability = "complete" if state == "ran" else "partial"
    if (
        state == "ran"
        and result_code == 3
        and task.get("task_contract") == "blocker_report"
        and task.get("required_evidence_availability") == "unavailable"
    ):
        availability = "unavailable"
    record = command_record(
        attempt_id=attempt_id,
        candidate_id=candidate_id,
        phase=phase,
        check_id=check_id,
        command=command,
        execution_state=state,
        exit_code=result_code,
        availability=availability,
        artifact_refs=["stdout.bin", "stderr.bin"],
        artifact_sha256={name: item["sha256"] for name, item in artifacts.items()},
    )
    write_once(root / "observation.json", record)
    write_once(
        root / "end.json",
        {
            "schema_version": SCHEMA,
            "kind": "visible_end",
            "identity": identity,
            "after": after,
            "termination": closure,
            "artifacts": artifacts,
            "record": record,
        },
    )
    # Retain the stopped owned container; caller/operator owns later cleanup.
    return record


def retained_observation(
    directory,
    *,
    attempt_id,
    candidate_id,
    phase,
    command,
    image,
    seconds=30,
    max_output_bytes=2 * 1024**2,
    check_id="required",
):
    """Verify retained command bytes and closure without executing any command."""
    if not isinstance(image, str) or not IMAGE.fullmatch(image):
        raise ValueError("expected_visible_image_not_pinned")
    root = Path(directory).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("visible_artifact_directory_invalid")

    def read(name):
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024**2:
            raise ValueError("visible_record_missing_or_oversized")
        return strict_json(path.read_bytes())

    record, start, end = (read(name) for name in ("observation.json", "start.json", "end.json"))
    validate_record(record)
    identity = check_identity(start.get("identity"))
    check_identity(end.get("identity"))
    after = end.get("after")
    if (
        start.get("schema_version") != SCHEMA
        or start.get("kind") != "visible_start"
        or end.get("schema_version") != SCHEMA
        or end.get("kind") != "visible_end"
        or identity["image_id"] != image
        or not re.fullmatch(r"visible-[0-9a-f]{32}", identity["attempt_label"])
        or canonical(start.get("seconds")) != canonical(seconds)
        or canonical(start.get("max_output_bytes")) != canonical(max_output_bytes)
        or not isinstance(after, dict)
        or after.get("schema_version") != SCHEMA
        or after.get("kind") != "container_observation"
        or canonical(after.get("identity")) != canonical(identity)
        or after.get("stopped") is not True
        or after.get("running") is not False
        or after.get("paused") is not False
    ):
        raise ValueError("visible_retained_container_observation_changed")
    expected = {
        "attempt_id": attempt_id,
        "candidate_id": candidate_id,
        "phase": phase,
        "check_id": check_id,
        "command": command,
    }
    if any(
        canonical(record.get(key)) != canonical(value) or canonical(start.get(key)) != canonical(value)
        for key, value in expected.items()
    ):
        raise ValueError("visible_observation_binding_changed")
    if (
        canonical(end.get("record")) != canonical(record)
        or canonical(end.get("identity")) != canonical(start.get("identity"))
        or end.get("after", {}).get("stopped") is not True
    ):
        raise ValueError("visible_retained_boundary_changed")
    if record["execution_state"] == "ran" and (
        type(end["after"].get("exit_code")) is not int or record["exit_code"] != end["after"]["exit_code"]
    ):
        raise ValueError("visible_retained_exit_changed")
    if record["artifact_refs"] != ["stdout.bin", "stderr.bin"] or set(end["artifacts"]) != set(
        record["artifact_refs"]
    ):
        raise ValueError("visible_artifact_roster_changed")
    limit = start["max_output_bytes"]
    if type(limit) is not int or not 0 < limit <= 2 * 1024**2:
        raise ValueError("visible_output_limit_changed")
    for name in record["artifact_refs"]:
        path, artifact = root / name, end["artifacts"][name]
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise ValueError("visible_artifact_missing_or_oversized")
        raw = path.read_bytes()
        actual_sha = hashlib.sha256(raw).hexdigest()
        if (
            type(artifact.get("bytes")) is not int
            or type(artifact.get("observed_bytes")) is not int
            or type(artifact.get("truncated")) is not bool
            or artifact["observed_bytes"] < len(raw)
            or artifact["truncated"] != (artifact["observed_bytes"] > len(raw))
            or (record["execution_state"] == "ran" and artifact["truncated"])
            or len(raw) != artifact["bytes"]
            or actual_sha != artifact["sha256"]
            or actual_sha != record["artifact_sha256"][name]
        ):
            raise ValueError("visible_artifact_bytes_changed")
    return record
