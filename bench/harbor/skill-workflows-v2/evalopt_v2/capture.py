"""External, exact-container termination and bounded stopped-filesystem capture.

No command executes inside a candidate. This module never starts, restarts,
unpauses, deletes, or grades a container. The caller must disable auto-removal
and restart before dispatch and retain this controller outside the worker.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from .framing import SCHEMA, strict_json

LABEL = "evalopt.v2.attempt"
HEX = re.compile(r"[0-9a-f]{64}")


class CaptureError(ValueError):
    """Static reason; Docker output may contain private data and is not interpolated."""


def now():
    return datetime.now(timezone.utc).isoformat()


def check_identity(identity):
    if not isinstance(identity, dict) or set(identity) != {"container_id", "image_id", "attempt_label"}:
        raise CaptureError("invalid_container_identity")
    if (
        not isinstance(identity["container_id"], str)
        or not isinstance(identity["image_id"], str)
        or not HEX.fullmatch(identity["container_id"])
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", identity["image_id"])
    ):
        raise CaptureError("incomplete_container_identity")
    if not isinstance(identity["attempt_label"], str) or not re.fullmatch(
        r"[a-zA-Z0-9_.-]{1,128}", identity["attempt_label"]
    ):
        raise CaptureError("invalid_attempt_label")
    return identity


def check_capture_options(source, max_bytes, timeout):
    if not isinstance(source, str):
        raise CaptureError("unsafe_capture_source")
    path = PurePosixPath(source)
    if (
        not source.startswith("/")
        or str(path) != source
        or ".." in path.parts
        or path == PurePosixPath("/")
        or path.parts[1] in {"proc", "sys", "dev"}
    ):
        raise CaptureError("unsafe_capture_source")
    if (
        type(max_bytes) is not int
        or max_bytes <= 0
        or isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not 0 < timeout < float("inf")
    ):
        raise CaptureError("invalid_capture_limit")


def run_command(argv, *, timeout):
    return subprocess.run(argv, capture_output=True, timeout=timeout, check=False)


def _stream(argv, destination, *, max_bytes, timeout, popen=subprocess.Popen):
    """Retain bounded stdout/stderr while draining concurrently; kill only our client."""
    started = time.monotonic()
    process = popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    selector = selectors.DefaultSelector()
    digest, size, stderr, reason = hashlib.sha256(), 0, bytearray(), None
    try:
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        with destination.open("xb") as stream:
            while selector.get_map():
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    reason = "capture_timeout"
                    break
                for key, _ in selector.select(min(remaining, 0.1)):
                    chunk = os.read(key.fileobj.fileno(), 64 * 1024)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "stderr":
                        stderr.extend(chunk[: max(0, 65536 - len(stderr))])
                        if len(stderr) == 65536:
                            reason = "capture_stderr_limit"
                            break
                    else:
                        kept = chunk[: max(0, max_bytes - size)]
                        stream.write(kept)
                        digest.update(kept)
                        size += len(kept)
                        if len(kept) != len(chunk):
                            reason = "capture_size_limit"
                            break
                if reason:
                    break
            stream.flush()
            os.fsync(stream.fileno())
        if reason is None:
            try:
                process.wait(timeout=max(0.001, timeout - (time.monotonic() - started)))
            except subprocess.TimeoutExpired:
                reason = "capture_timeout"
    except BaseException:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        raise
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=5)
        selector.close()
        process.stdout.close()
        process.stderr.close()
    if reason is None and process.returncode != 0:
        reason = "capture_command_failed"
    if reason is None and size == 0:
        reason = "capture_empty_output"
    return {
        "status": "complete" if reason is None else "partial" if size else "missing",
        "bytes": size,
        "sha256": digest.hexdigest(),
        "returncode": process.returncode,
        "reason": reason,
        "stderr_bytes": len(stderr),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
    }


class DockerController:
    def __init__(self, *, docker="docker", command=run_command, stream=_stream, command_timeout=15):
        self.docker, self.command, self.stream = docker, command, stream
        self.command_timeout = command_timeout

    def inspect_owned(self, identity):
        check_identity(identity)
        # Avoid fetching environment/auth configuration, labels of other containers,
        # command lines or mounts. All selected fields have a specific gate below.
        template = (
            '{{json .Id}} {{json .Image}} {{json (index .Config.Labels "'
            + LABEL
            + '")}} {{json .State}} {{json .HostConfig.RestartPolicy.Name}} {{json .HostConfig.AutoRemove}}'
        )
        result = self.command(
            [self.docker, "container", "inspect", "--format", template, identity["container_id"]],
            timeout=self.command_timeout,
        )
        if result.returncode != 0:
            raise CaptureError("container_inspection_unavailable")
        raw = result.stdout.decode("utf-8") if isinstance(result.stdout, bytes) else result.stdout
        if len(raw) > 65536:
            raise CaptureError("container_inspection_oversize")
        decoder, position, values = json.JSONDecoder(), 0, []
        try:
            while position < len(raw):
                while position < len(raw) and raw[position].isspace():
                    position += 1
                if position == len(raw):
                    break
                _, end = decoder.raw_decode(raw, position)
                values.append(strict_json(raw[position:end]))
                position = end
        except (ValueError, UnicodeError) as exc:
            raise CaptureError("malformed_container_inspection") from exc
        if len(values) != 6:
            raise CaptureError("malformed_container_inspection")
        cid, image, label, state, restart, auto_remove = values
        if (cid, image, label) != (identity["container_id"], identity["image_id"], identity["attempt_label"]):
            raise CaptureError("container_ownership_changed")
        if restart not in ("", "no") or auto_remove is not False:
            raise CaptureError("unsafe_container_lifecycle_configuration")
        if (
            not isinstance(state, dict)
            or any(
                type(state.get(key)) is not bool
                for key in ("Running", "Paused", "Restarting", "Dead", "OOMKilled")
            )
            or type(state.get("Pid")) is not int
            or state["Pid"] < 0
            or type(state.get("ExitCode")) is not int
            or not isinstance(state.get("FinishedAt"), str)
        ):
            raise CaptureError("malformed_container_state")
        if state["Dead"] or state["Restarting"]:
            raise CaptureError("ambiguous_container_state")
        stopped = state["Running"] is False and state["Paused"] is False and state["Pid"] == 0
        if (not state["Running"] and not stopped) or (state["Running"] and state["Pid"] == 0):
            raise CaptureError("contradictory_container_state")
        return {
            "schema_version": SCHEMA,
            "kind": "container_observation",
            "identity": dict(identity),
            "observed_at": now(),
            "running": state["Running"],
            "paused": state["Paused"],
            "stopped": stopped,
            "oom_killed": state["OOMKilled"],
            "exit_code": state.get("ExitCode"),
            "finished_at": state.get("FinishedAt"),
        }

    def terminate(self, identity):
        before = self.inspect_owned(identity)
        requested_at, started = now(), time.monotonic()
        command_state = "not_required"
        if not before["stopped"]:
            try:
                response = self.command(
                    [self.docker, "container", "kill", "--signal", "KILL", identity["container_id"]],
                    timeout=self.command_timeout,
                )
                command_state = "returned" if response.returncode == 0 else "failed"
            except (OSError, subprocess.TimeoutExpired):
                command_state = "unavailable"
        # A successful signal request is not the boundary. Conversely a command
        # error can race an actual exit: inspect that exact owned container again.
        after = self.inspect_owned(identity)
        return {
            "schema_version": SCHEMA,
            "kind": "termination",
            "identity": dict(identity),
            "requested_at": requested_at,
            "confirmed_at": after["observed_at"] if after["stopped"] else None,
            "wall_seconds": time.monotonic() - started,
            "command_state": command_state,
            "execution_boundary": "confirmed" if after["stopped"] else "unconfirmed",
            "before": before,
            "after": after,
            "native_end_inferred": False,
        }

    def capture(self, identity, source, destination, *, max_bytes=64 * 1024**2, timeout=60):
        check_capture_options(source, max_bytes, timeout)
        destination = Path(destination)
        if (
            destination.exists()
            or destination.is_symlink()
            or not destination.parent.is_dir()
            or destination.parent.is_symlink()
        ):
            raise CaptureError("capture_destination_not_fresh")
        before = self.inspect_owned(identity)
        if not before["stopped"]:
            raise CaptureError("capture_requires_stopped_container")
        record = self.stream(
            [self.docker, "container", "cp", f"{identity['container_id']}:{source}", "-"],
            destination,
            max_bytes=max_bytes,
            timeout=timeout,
        )
        after = self.inspect_owned(identity)
        if not after["stopped"]:
            raise CaptureError("container_changed_during_capture")
        return {
            "schema_version": SCHEMA,
            "kind": "capture",
            "source": source,
            "file": destination.name,
            **record,
            "before": before,
            "after": after,
            "native_end_inferred": False,
        }
