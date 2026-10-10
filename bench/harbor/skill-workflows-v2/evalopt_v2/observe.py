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

from .capture import LABEL, DockerController
from .framing import SCHEMA
from .lifecycle import write_once
from .preflight import IMAGE
from .records import validate_record


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
    *, attempt_id, candidate_id, command, execution_state, exit_code, availability, artifact_refs
):
    value = {
        "schema_version": SCHEMA,
        "record_type": "command",
        "attempt_id": attempt_id,
        "candidate_id": candidate_id,
        "command": command,
        "execution_state": execution_state,
        "exit_code": exit_code,
        "evidence_availability": availability,
        "artifact_refs": artifact_refs,
        "asserted_claim": None,
    }
    validate_record(value)
    return value


def visible_check(
    snapshot, task, *, attempt_id, candidate_id, image, directory, seconds=30, max_output_bytes=2 * 1024**2
):
    """Execute a registered visible argv once. Never ingest an agent result file.

    For an authored blocker contract, exit 3 signals unavailable *requested
    evidence*. The command still ran, and its stdout/stderr remain complete.
    This interpretation is supplied by the trusted task contract, not its output.
    """
    if not IMAGE.fullmatch(image):
        raise ValueError("visible_image_not_pinned")
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
        command=command,
        execution_state=state,
        exit_code=result_code,
        availability=availability,
        artifact_refs=["stdout.bin", "stderr.bin"],
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
