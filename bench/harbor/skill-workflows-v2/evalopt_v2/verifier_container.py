"""Fresh, non-privileged Docker container per callable case; no hidden expectations.

The host grades returned records only after exact-container termination. The
inner result descriptor separates diagnostics from runner completion, but cannot
attest arbitrary introspective code inside the same Python interpreter.
"""

from __future__ import annotations

import hashlib
import math
import os
import subprocess
import time
import uuid
from pathlib import Path

from .case_runner import (
    MAX_OUTPUT,
    SCHEMA,
    snapshot_manifest,
    strict_json,
    validate_invocation,
    validate_request,
)
from .records import canonical, digest
from .verifier import CaseBoundaryError, chroot_invoker


def _write(path, value):
    with Path(path).open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(Path(path).parent, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def case_main():
    """Fixed one-case container entrypoint: no oracle, roster, or grade is mounted."""
    control = strict_json(Path("/case-control/request.json").read_bytes())
    if not isinstance(control, dict) or set(control) != {"request", "timeout_seconds"}:
        raise ValueError("invalid case control")
    result = chroot_invoker()(Path("/snapshot"), **control)
    _write("/case-output/invocation.json", result)


def docker_invoker(image, *, artifact_root, package_root=None, docker="docker", clock=time.monotonic):
    """Return a callable that retains one owned-container record per invocation.

    ``artifact_root`` is controller-owned and must be empty. The adapter resolves
    a locally present immutable image once, never pulls, never mounts Docker in
    the container, and never removes a container with uncertain termination.
    """
    package = Path(package_root or Path(__file__).resolve().parent).resolve()
    root = Path(artifact_root)
    if not root.is_dir() or root.is_symlink() or any(root.iterdir()):
        raise ValueError("case artifact root must be an empty controller directory")
    root = root.resolve()
    if not package.is_dir() or not (package / "verifier_container.py").is_file():
        raise ValueError("invalid trusted verifier package")

    def command(argv, timeout=30, *, cutoff=None):
        if cutoff is not None:
            timeout = min(timeout, cutoff - clock())
            if timeout <= 0:
                raise subprocess.TimeoutExpired([docker, *argv], 0)
        return subprocess.run([docker, *argv], capture_output=True, timeout=timeout, check=False)

    inspected = command(["image", "inspect", "--format", "{{.Id}}", image])
    image_id = inspected.stdout.decode("ascii").strip()
    if inspected.returncode or not image_id.startswith("sha256:") or len(image_id) != 71:
        raise ValueError("required local verifier image unavailable")
    count = 0
    poisoned = False

    def inspect(container, label, *, cutoff=None):
        result = command(["inspect", "--format", "{{json .}}", container], cutoff=cutoff)
        if result.returncode:
            raise CaseBoundaryError("case_container_inspect_failed")
        value = strict_json(result.stdout)
        if (
            value.get("Id") != container
            or value.get("Image") != image_id
            or value.get("Config", {}).get("Labels", {}).get("evalopt.v2.case") != label
            or value.get("HostConfig", {}).get("AutoRemove") is not False
            or value.get("HostConfig", {}).get("RestartPolicy", {}).get("Name") not in {"no", ""}
        ):
            raise CaseBoundaryError("case_container_identity_contradiction")
        host = value.get("HostConfig", {})
        if (
            host.get("NetworkMode") != "none"
            or host.get("NanoCpus") != 1_000_000_000
            or host.get("Memory") != 2 * 1024**3
            or host.get("PidsLimit") != 128
            or host.get("Privileged") is not False
            or host.get("CapAdd") not in (None, [])
            or host.get("SecurityOpt") not in (None, [])
        ):
            raise CaseBoundaryError("case_container_configuration_contradiction")
        state = value.get("State", {})
        return {
            "container_id": container,
            "image_id": image_id,
            "case_label": label,
            "status": state.get("Status"),
            "running": state.get("Running"),
            "restarting": state.get("Restarting"),
            "dead": state.get("Dead"),
            "exit_code": state.get("ExitCode"),
            "finished_at": state.get("FinishedAt"),
        }

    def execute(snapshot, request, *, timeout_seconds=5, deadline=None):
        nonlocal count, poisoned
        if poisoned:
            raise CaseBoundaryError("prior_case_boundary_unconfirmed")
        request = validate_request(request)
        if type(timeout_seconds) not in {int, float} or not 0 < timeout_seconds <= 120:
            raise ValueError("invalid case deadline")
        entered_at = clock()
        if deadline is not None and (type(deadline) not in {int, float} or not math.isfinite(deadline)):
            raise ValueError("invalid absolute verifier deadline")
        execution_deadline = min(entered_at + timeout_seconds, deadline if deadline is not None else math.inf)
        if Path(snapshot).is_symlink():
            raise ValueError("snapshot root must not be a symlink")
        source = Path(snapshot).resolve()
        before = snapshot_manifest(source)
        count += 1
        directory = root / f"case-{count:04d}"
        directory.mkdir()
        control, output = directory / "control", directory / "output"
        control.mkdir()
        output.mkdir()
        _write(control / "request.json", {"request": request, "timeout_seconds": timeout_seconds})
        label = uuid.uuid4().hex
        _write(
            directory / "ownership.json",
            {
                "schema_version": SCHEMA,
                "case_label": label,
                "image_id": image_id,
                "candidate_id": digest(before),
                "entered_at_monotonic": entered_at,
                "execution_deadline_monotonic": execution_deadline,
            },
        )
        create = [
            "create",
            "--pull",
            "never",
            "--name",
            "evalopt-v2-case-" + label,
            "--label",
            "evalopt.v2.case=" + label,
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "2g",
            "--pids-limit",
            "128",
            "--restart",
            "no",
            "--entrypoint",
            "python3",
        ]
        for path, target, readonly in (
            (source, "/snapshot", True),
            (control, "/case-control", True),
            (output, "/case-output", False),
            (package, "/controller/evalopt_v2", True),
        ):
            create.extend(
                ["--mount", f"type=bind,src={path},dst={target}" + (",readonly" if readonly else "")]
            )
        create.extend(
            [
                image_id,
                "-I",
                "-B",
                "-c",
                "import sys;sys.path.insert(0,'/controller');from evalopt_v2.verifier_container import case_main;case_main()",
            ]
        )
        default = {
            "schema_version": SCHEMA,
            "record_type": "case_invocation",
            "request": request,
            "candidate_id": digest(before),
            "isolation": "fresh_case_container_chroot_unprivileged",
        }
        if clock() >= execution_deadline:
            actual = {
                **default,
                "state": "not_run",
                "reason": "case_setup_deadline",
                "container_boundary": {"status": "not_started"},
            }
            _write(directory / "boundary.json", {"status": "not_started", "reason": "case_setup_deadline"})
            _write(directory / "retained.json", actual)
            return validate_invocation(actual, request)
        created = command(create, cutoff=execution_deadline)
        container = created.stdout.decode("ascii").strip()
        if created.returncode or len(container) != 64 or any(c not in "0123456789abcdef" for c in container):
            poisoned = True
            _write(
                directory / "boundary.json",
                {"status": "unconfirmed", "reason": "case_create_failed", "case_label": label},
            )
            raise CaseBoundaryError("case_create_failed")
        _write(directory / "created.json", {"container_id": container, "case_label": label})
        host_timeout, execution_started = False, False
        diagnostics = {"returncode": None, "reason": "case_setup_deadline"}
        try:
            if clock() < execution_deadline:
                try:
                    inspect(container, label, cutoff=execution_deadline)
                except subprocess.TimeoutExpired:
                    pass  # No start occurred; only bounded closure may follow.
                else:
                    if clock() < execution_deadline:
                        execution_started = True
                        try:
                            started = command(["start", "--attach", container], cutoff=execution_deadline)
                            diagnostics = {
                                "returncode": started.returncode,
                                "stdout_sha256": hashlib.sha256(started.stdout).hexdigest(),
                                "stderr_sha256": hashlib.sha256(started.stderr).hexdigest(),
                            }
                        except subprocess.TimeoutExpired:
                            host_timeout = True
                            diagnostics = {"returncode": None, "reason": "outer_case_deadline"}
                        if clock() >= execution_deadline:
                            host_timeout = True
            # This separate bounded window permits only safety closure/capture.
            # It never admits a late start or extends the callable's time limit.
            closure_started = clock()
            closure_deadline = closure_started + 30
            if host_timeout:
                command(["kill", "--signal", "KILL", container], timeout=5, cutoff=closure_deadline)
            state = inspect(container, label, cutoff=closure_deadline)
            if state["running"] is not False or state["restarting"] is not False:
                command(["kill", "--signal", "KILL", container], timeout=5, cutoff=closure_deadline)
                state = inspect(container, label, cutoff=closure_deadline)
            allowed_status = {"exited"} if execution_started else {"created", "exited"}
            if (
                state["status"] not in allowed_status
                or state["running"] is not False
                or state["restarting"] is not False
                or state["dead"] is not False
            ):
                raise CaseBoundaryError("case_container_not_confirmed_stopped")
            if clock() >= closure_deadline:
                raise CaseBoundaryError("case_safety_closure_deadline")
            _write(
                directory / "boundary.json",
                {
                    "status": "confirmed",
                    "observation": state,
                    "diagnostics": diagnostics,
                    "execution_started": execution_started,
                    "execution_deadline_monotonic": execution_deadline,
                    "closure_started_monotonic": closure_started,
                    "closure_deadline_monotonic": closure_deadline,
                },
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            poisoned = True
            if not (directory / "boundary.json").exists():
                _write(
                    directory / "boundary.json",
                    {
                        "status": "unconfirmed",
                        "reason": "case_container_boundary_unavailable",
                        "container_id": container,
                        "case_label": label,
                    },
                )
            raise CaseBoundaryError("case_container_boundary_unavailable") from error
        path = output / "invocation.json"
        try:
            if not execution_started:
                actual = {**default, "state": "not_run", "reason": "case_setup_deadline"}
            elif host_timeout:
                actual = {**default, "state": "timeout", "reason": "outer_case_deadline"}
            elif state["exit_code"] != 0 or not path.is_file() or path.is_symlink():
                actual = {**default, "state": "not_run", "reason": "case_runner_evidence_unavailable"}
            else:
                if path.stat().st_size > MAX_OUTPUT * 2:
                    raise ValueError("case result size exceeded")
                actual = strict_json(path.read_bytes())
                validate_invocation(actual, request)
                if actual.get("candidate_id") != digest(before):
                    raise ValueError("case snapshot identity mismatch")
                actual["isolation"] = default["isolation"]
            if snapshot_manifest(source) != before:
                raise ValueError("immutable snapshot changed")
            actual["container_boundary"] = {
                "status": "confirmed",
                "container_id": container,
                "image_id": image_id,
                "case_label": label,
            }
            _write(directory / "retained.json", actual)
        except (OSError, ValueError, TypeError, RecursionError) as error:
            poisoned = True
            raise CaseBoundaryError("case_result_provenance_or_capture_failed") from error
        # Removal happens after durable exact-container closure and retained data.
        removed = command(["rm", container], timeout=5, cutoff=closure_deadline)
        _write(directory / "cleanup.json", {"removed": removed.returncode == 0, "container_id": container})
        return validate_invocation(actual, request)

    def invoke(snapshot, request, *, timeout_seconds=5, deadline=None):
        nonlocal poisoned
        try:
            return execute(snapshot, request, timeout_seconds=timeout_seconds, deadline=deadline)
        except CaseBoundaryError:
            poisoned = True
            raise
        except (OSError, ValueError, TypeError, RecursionError, subprocess.SubprocessError) as error:
            # A failed Docker transport may have performed its mutation. Do not
            # infer that a create/start/kill failed merely from CLI failure.
            poisoned = True
            raise CaseBoundaryError("case_controller_or_durable_capture_failed") from error

    return invoke
