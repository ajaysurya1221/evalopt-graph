"""Read-only current absence/storage observations; no candidate signals or cleanup."""

import fcntl
import hashlib
import json
import math
import os
import shlex
import shutil
import subprocess
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from amendment import hashed, mkdir, read, safe, write_once

IMAGE_LOCK_SHA = "fcb2e2b709674342e3749dba80409b50573ddc6a1a4cb49e1edb6e219e509bc1"
PROBE_IMAGE = "sha256:84c7fae6b256dcc56a350790e2a9715eefc7dad662a9d8e8a472363aa71ef18d"
FLOOR = 100 * 1024**3
WARNING = 150 * 1024**3
MAX_AGE = 60


def now():
    return datetime.now(timezone.utc).isoformat()


def storage_reason(observation, current):
    if type(current) not in (int, float) or not math.isfinite(current):
        return "invalid_storage_telemetry"
    for name in ("host", "vm"):
        item = observation.get(name, {})
        value, measured = item.get("free_bytes"), item.get("monotonic")
        if (
            type(value) is not int
            or value < 0
            or type(measured) not in (int, float)
            or not math.isfinite(measured)
        ):
            return "invalid_storage_telemetry"
        if not 0 <= current - measured <= MAX_AGE:
            return "stale_storage_telemetry"
        if value <= FLOOR:
            return name + "_storage_floor"
    return None


class Storage:
    def __init__(self, ctx, root):
        self.ctx, self.root = ctx, root

    def storage(self):
        host = {"free_bytes": shutil.disk_usage(self.ctx.paths.campaign).free, "monotonic": time.monotonic()}
        if any(os.environ.get(k) for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY")):
            raise ValueError("ambiguous non-default Docker backend")
        context = subprocess.run(
            ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        if not context.startswith("unix://"):
            raise ValueError("storage probe requires local Docker socket")
        lock_data = self.ctx.paths.image_lock.read_bytes()
        if hashlib.sha256(lock_data).hexdigest() != IMAGE_LOCK_SHA:
            raise ValueError("image lock changed")
        probe_name = "evalopt-storage-" + uuid.uuid4().hex
        argv = [
            "docker",
            "run",
            "--name",
            probe_name,
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "16",
            "--memory",
            "64m",
            "--cpus",
            "0.1",
            "--platform",
            "linux/amd64",
            "--entrypoint",
            "/bin/df",
            PROBE_IMAGE,
            "-Pk",
            "/",
        ]
        probe_path = self.root / (probe_name + ".json")
        write_once(probe_path, {"observed_at": now(), "argv": argv, "cleanup": "normal docker --rm only"})
        try:
            probe = subprocess.run(argv, check=True, capture_output=True, text=True, timeout=20)
        except Exception as exc:
            write_once(
                probe_path.with_suffix(".end.json"),
                {
                    "observed_at": now(),
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "container_absence_verified": False,
                    "next_admission": "blocked; inspect named probe during explicit operator review",
                },
            )
            raise
        write_once(
            probe_path.with_suffix(".end.json"),
            {
                "observed_at": now(),
                "status": "completed",
                "returncode": probe.returncode,
                "cleanup": "normal docker --rm completed; no separate cleanup command",
            },
        )
        rows = probe.stdout.splitlines()
        if len(rows) != 2 or len(rows[1].split()) != 6:
            raise ValueError("unexpected Docker df output")
        fields = rows[1].split()
        if fields[-1] != "/" or not fields[3].isdigit():
            raise ValueError("unexpected Docker filesystem")
        vm = {"free_bytes": int(fields[3]) * 1024, "monotonic": time.monotonic()}
        logical = allocated = 0

        def failed_walk(error):
            raise error

        for directory, dirs, files in os.walk(
            self.ctx.paths.campaign, followlinks=False, onerror=failed_walk
        ):
            for name in dirs + files:
                item = (Path(directory) / name).lstat()
                logical += item.st_size
                allocated += item.st_blocks * 512
        docker_raw = self.ctx.paths.docker_raw.stat()
        return {
            "host": host,
            "vm": vm,
            "campaign_logical_bytes": logical,
            "campaign_allocated_bytes": allocated,
            "docker_raw_logical_bytes": docker_raw.st_size,
            "docker_raw_allocated_bytes": docker_raw.st_blocks * 512,
        }


def process_table():
    result = subprocess.run(
        ["ps", "-axo", "pid=,ppid=,lstart=,command="], check=True, capture_output=True, text=True, timeout=10
    )
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split(None, 7)
        if len(parts) != 8 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError("unparseable process table")
        rows.append(
            {
                "pid": int(parts[0]),
                "ppid": int(parts[1]),
                "started": " ".join(parts[2:7]),
                "argv": shlex.split(parts[7]),
            }
        )
    return rows


def owner(ctx):
    rows = process_table()
    found = [r for r in rows if r["pid"] == os.getpid()]
    if len(found) != 1:
        raise ValueError("own process absent")
    row = found[0]
    if (
        str(ctx.code_root / "operator.py") not in row["argv"]
        or str(ctx.grant_path) not in row["argv"]
        or ctx.grant_sha256 not in row["argv"]
    ):
        raise ValueError("operator identity not exact")
    return {
        "pid": row["pid"],
        "started": row["started"],
        "argv_sha256": hashlib.sha256(json.dumps(row["argv"], separators=(",", ":")).encode()).hexdigest(),
    }


def validate_processes(ctx, rows, expected_owner, bridge_pid, parent_pid):
    matches = {r["pid"]: r for r in rows}
    if len(matches) != len(rows):
        raise ValueError("duplicate process identity")
    operator = matches.get(expected_owner["pid"])
    bridge = matches.get(bridge_pid)
    if (
        operator is None
        or bridge is None
        or parent_pid != operator["pid"]
        or bridge["ppid"] != operator["pid"]
        or operator["started"] != expected_owner["started"]
    ):
        raise ValueError("observer parent identity differs")
    if (
        hashlib.sha256(json.dumps(operator["argv"], separators=(",", ":")).encode()).hexdigest()
        != expected_owner["argv_sha256"]
    ):
        raise ValueError("operator command changed")
    for row, script in [(operator, "operator.py"), (bridge, "bridge.py")]:
        if (
            str(ctx.code_root / script) not in row["argv"]
            or str(ctx.grant_path) not in row["argv"]
            or ctx.grant_sha256 not in row["argv"]
        ):
            raise ValueError("observer self exclusion not exact")
    roots = [
        str(ctx.paths.source / "bench/harbor/skill-workflows-v1"),
        str(ctx.code_root.parent / "transfer-operator-v1"),
        str(ctx.code_root.parent / "transfer-continuation-v1"),
        str(ctx.code_root),
        str(ctx.paths.campaign),
    ]
    relevant = []
    for row in rows:
        if any(
            any(arg == root or arg.startswith(root + "/") for root in roots)
            or __import__("re").fullmatch(r"harbor-transfer-[0-9a-f]{16}__env", arg)
            for arg in row["argv"]
        ):
            relevant.append(row)
    if {r["pid"] for r in relevant} != {operator["pid"], bridge["pid"]}:
        raise ValueError("other owned controller process remains")
    return {
        "operator_pid": operator["pid"],
        "operator_started": operator["started"],
        "bridge_pid": bridge["pid"],
        "bridge_started": bridge["started"],
        "other_owned_controllers_absent": True,
    }


@contextmanager
def old_locks(ctx):
    streams = []
    try:
        for label in ("operator_receipts", "continuation_receipts"):
            path = safe(ctx.prefix["roots"][label]) / "operator.lock"
            stream = safe(path).open("r")
            streams.append(stream)
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        for stream in reversed(streams):
            fcntl.flock(stream, fcntl.LOCK_UN)
            stream.close()


def require_operator_lock(ctx):
    with safe(ctx.code_root / "receipts/operator.lock").open("r") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        fcntl.flock(stream, fcntl.LOCK_UN)
        raise ValueError("current operator has no exclusive lock")


def containers(ctx):
    if any(os.environ.get(k) for k in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY")):
        raise ValueError("ambiguous Docker backend")
    projects = set()
    for config in ctx.paths.campaign.glob("private-harbor/*/attempt-1/harbor-*/config.json"):
        name = config.parent.name
        if not __import__("re").fullmatch(r"harbor-transfer-[0-9a-f]{16}", name):
            raise ValueError("unexpected native project name")
        projects.add(name + "__env")
    output = subprocess.run(
        ["docker", "ps", "-aq"], check=True, capture_output=True, text=True, timeout=10
    ).stdout.splitlines()
    if len(set(output)) != len(output) or any(
        not __import__("re").fullmatch(r"[0-9a-f]{12,64}", x) for x in output
    ):
        raise ValueError("invalid container roster")
    owned = []
    for identifier in output:
        # Format deliberately excludes environment/config content.
        command = [
            "docker",
            "inspect",
            "--format",
            "{{json .Name}}\t{{json .Config.Labels}}\t{{json .State.Status}}",
            identifier,
        ]
        parts = (
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=10)
            .stdout.strip()
            .split("\t")
        )
        if len(parts) != 3:
            raise ValueError("invalid container metadata")
        name, labels, state = map(json.loads, parts)
        labels = labels or {}
        project = labels.get("com.docker.compose.project")
        if project in projects or any(name.lstrip("/").startswith(p + "-") for p in projects):
            owned.append({"id": identifier, "name": name, "project": project, "state": state})
    if owned:
        raise ValueError("owned container still exists")
    return {
        "project_count": len(projects),
        "owned_containers_absent": True,
        "all_container_count": len(output),
    }


def observe(ctx, expected_owner, *, phase):
    root = ctx.code_root / "receipts/observations"
    if not root.exists():
        mkdir(root)
    folder = root / uuid.uuid4().hex
    mkdir(folder)
    begun = time.monotonic()
    write_once(folder / "start.json", {"checked_at": now(), "phase": phase, "grant_sha256": ctx.grant_sha256})
    try:
        require_operator_lock(ctx)
        with old_locks(ctx):
            first = validate_processes(ctx, process_table(), expected_owner, os.getpid(), os.getppid())
            container = containers(ctx)
            storage = Storage(ctx, folder).storage()
            last = validate_processes(ctx, process_table(), expected_owner, os.getpid(), os.getppid())
            if first != last:
                raise ValueError("observer identities changed")
            reason = storage_reason(storage, time.monotonic())
            if reason:
                raise ValueError(reason)
            if time.monotonic() - begun > 60:
                raise ValueError("stale quiescence observations")
        result = {
            "schema_version": "evalopt.transfer-policy-v2.observation.v1",
            "checked_at": now(),
            "phase": phase,
            "grant_sha256": ctx.grant_sha256,
            "processes": last,
            "containers": container,
            "old_operator_locks_available": True,
            "new_operator_lock_held": True,
            "storage": storage,
            "elapsed_seconds": time.monotonic() - begun,
            "started_monotonic": begun,
            "status": "allowed",
        }
        write_once(folder / "result.json", result)
        return {
            "path": str(folder / "result.json"),
            "sha256": hashed(folder / "result.json"),
            "observed_monotonic": begun,
        }
    except BaseException as error:
        write_once(
            folder / "failure.json",
            {"checked_at": now(), "error_type": type(error).__name__, "status": "blocked"},
        )
        raise


def validate_observation(ctx, reference, *, phase, current_monotonic=None):
    path = safe(reference["path"])
    if (
        path.parent.parent != ctx.code_root / "receipts/observations"
        or path.name != "result.json"
        or not __import__("re").fullmatch(r"[0-9a-f]{32}", path.parent.name)
        or hashed(path) != reference["sha256"]
    ):
        raise ValueError("observation identity/ownership differs")
    value = read(path)
    if (
        value["schema_version"] != "evalopt.transfer-policy-v2.observation.v1"
        or value["status"] != "allowed"
        or value["grant_sha256"] != ctx.grant_sha256
        or value["phase"] != phase
        or value["processes"]["other_owned_controllers_absent"] is not True
        or value["containers"]["owned_containers_absent"] is not True
        or value["old_operator_locks_available"] is not True
        or value["new_operator_lock_held"] is not True
    ):
        raise ValueError("observation proof differs")
    start = value["started_monotonic"]
    elapsed = value["elapsed_seconds"]
    if (
        type(start) not in (int, float)
        or not math.isfinite(start)
        or start < 0
        or type(elapsed) not in (int, float)
        or not math.isfinite(elapsed)
        or not 0 <= elapsed <= 60
        or type(reference["observed_monotonic"]) not in (int, float)
        or not math.isfinite(reference["observed_monotonic"])
        or reference["observed_monotonic"] != start
    ):
        raise ValueError("observation clock differs")
    if current_monotonic is not None:
        if (
            type(current_monotonic) not in (int, float)
            or not math.isfinite(current_monotonic)
            or not 0 <= current_monotonic - start <= 60
        ):
            raise ValueError("stale final admission observation")
        reason = storage_reason(value["storage"], current_monotonic)
        if reason:
            raise ValueError(reason)
    else:
        reason = storage_reason(value["storage"], start + elapsed)
        if reason:
            raise ValueError(reason)
    return value
