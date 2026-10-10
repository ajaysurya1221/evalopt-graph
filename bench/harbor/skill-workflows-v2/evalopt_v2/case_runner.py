"""Fresh-process execution for trusted conformance fixtures, not a security sandbox.

The candidate never receives expected values. Production use with adversarial
code needs an OS/container boundary supplied by the host; ``-I`` is not one.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .records import canonical, digest

SCHEMA = "evalopt-workflows-v2/1"
MAX_OUTPUT = 262144
MAX_JSON_DEPTH = 768
BUILTIN_CATEGORIES = (
    "Exception",
    "ArithmeticError",
    "AssertionError",
    "AttributeError",
    "EOFError",
    "ImportError",
    "IndexError",
    "KeyError",
    "LookupError",
    "NameError",
    "OSError",
    "OverflowError",
    "RecursionError",
    "RuntimeError",
    "StopIteration",
    "SyntaxError",
    "TypeError",
    "UnicodeError",
    "UnicodeDecodeError",
    "ValueError",
    "ZeroDivisionError",
)

# Bind actual type objects and serialization before importing candidate code.
# Diagnostic names are never used as the exception-category authority.
CHILD = r"""import builtins, importlib, json, os, sys
try:
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
except ImportError:
    pass
is_instance = builtins.isinstance
get_type = builtins.type
base_exception = builtins.BaseException
emit = json.dumps
result_fd = int(os.environ.pop("EVALOPT_RESULT_FD"))
write = os.write
categories = {name: getattr(builtins, name) for name in CATEGORIES}
request = json.loads(sys.stdin.read())
args = request["args"]
sys.path.insert(0, ".")
try:
    module = importlib.import_module(request["module"])
    value = getattr(module, request["function"])(*args)
    output = {"state": "returned", "value": value, "args_after": args}
except base_exception as error:
    cls = get_type(error)
    output = {"state": "raised", "args_after": args, "exception": {
        "module": cls.__module__, "name": cls.__qualname__,
        "builtin_categories": sorted(name for name, category in categories.items()
            if is_instance(error, category))}}
write(result_fd, emit({"runner_completed": True, "result": output}, allow_nan=False, sort_keys=True).encode("utf-8"))
"""
CHILD = "CATEGORIES=" + repr(BUILTIN_CATEGORIES) + "\n" + CHILD


def strict_json(data):
    """Bound decoded nesting before JSON recursion, including candidate output."""
    text = data.decode("utf-8") if isinstance(data, bytes) else data
    if not isinstance(text, str):
        raise ValueError("JSON text required")
    depth, quoted, escaped = 0, False, False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError("JSON depth exceeded")
        elif character in "]}":
            depth -= 1

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("nonfinite JSON")

    try:
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=reject)
        canonical(value)
    except RecursionError as error:
        raise ValueError("JSON depth exceeded") from error
    return value


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {"module", "function", "args"}:
        raise ValueError("request must contain only module, function and args")
    for field in ("module", "function"):
        if not isinstance(request[field], str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", request[field]):
            raise ValueError("only a top-level module/function is supported")
    if not isinstance(request["args"], list) or len(canonical(request)) > 65536:
        raise ValueError("request arguments exceed the data-only limit")
    return strict_json(canonical(request))


def snapshot_manifest(snapshot):
    root = Path(snapshot)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("snapshot must be a regular directory")
    result = {}
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        name = path.relative_to(root).as_posix()
        if stat.S_ISDIR(info.st_mode):
            result[name] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
        elif stat.S_ISREG(info.st_mode):
            data = path.read_bytes()
            result[name] = {
                "kind": "file",
                "mode": stat.S_IMODE(info.st_mode),
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        else:
            raise ValueError("nonregular snapshot node")
    return result


def validate_invocation(record, request=None):
    if not isinstance(record, dict) or record.get("schema_version") != SCHEMA:
        raise ValueError("invalid invocation schema")
    if request is not None and canonical(record.get("request")) != canonical(request):
        raise ValueError("invocation request changed")
    state = record.get("state")
    if state not in {"returned", "raised", "timeout", "malformed", "error", "not_run"}:
        raise ValueError("invalid invocation state")
    if state == "returned":
        if "value" not in record or not isinstance(record.get("args_after"), list):
            raise ValueError("missing return evidence")
    if state == "raised":
        error = record.get("exception")
        if not isinstance(error, dict) or set(error) != {"module", "name", "builtin_categories"}:
            raise ValueError("malformed exception evidence")
        categories = error["builtin_categories"]
        if (
            not isinstance(categories, list)
            or any(type(x) is not str for x in categories)
            or categories != sorted(set(categories))
            or not set(categories) <= set(BUILTIN_CATEGORIES)
            or not all(isinstance(error[x], str) for x in ("module", "name"))
            or not isinstance(record.get("args_after"), list)
        ):
            raise ValueError("malformed builtin category evidence")
    canonical(record)
    return record


def execute_process(request, argv, *, cwd, timeout_seconds, record):
    """Caller owns argv, cwd and the OS boundary; stdout is only diagnostics.

    A separate inherited descriptor rejects ordinary stdout/early-exit forgery.
    It is not authentication against arbitrary introspection inside the Python
    interpreter. Production must also supply a fresh whole-container boundary.
    """
    request = validate_request(request)
    if (
        type(timeout_seconds) not in {int, float}
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError("invalid process timeout")
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err, tempfile.TemporaryFile() as result:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "EVALOPT_RESULT_FD": str(result.fileno())},
            pass_fds=(result.fileno(),),
            start_new_session=True,
        )
        timed_out = False
        try:
            process.communicate(canonical(request), timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            # Only this newly created process group; never a campaign process.
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait()
        out.seek(0)
        err.seek(0)
        stdout, stderr = out.read(MAX_OUTPUT + 1), err.read(MAX_OUTPUT + 1)
        result.seek(0)
        semantic = result.read(MAX_OUTPUT + 1)
    record.update(
        returncode=process.returncode,
        stdout_prefix_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_prefix_sha256=hashlib.sha256(stderr).hexdigest(),
        output_truncated=len(stdout) > MAX_OUTPUT or len(stderr) > MAX_OUTPUT,
        semantic_prefix_sha256=hashlib.sha256(semantic).hexdigest(),
        semantic_truncated=len(semantic) > MAX_OUTPUT,
    )
    if timed_out:
        record.update(state="timeout", reason="case_deadline")
    elif process.returncode != 0:
        record.update(state="error", reason="child_exit")
    else:
        try:
            if record["semantic_truncated"]:
                raise ValueError("output limit")
            envelope = strict_json(semantic)
            if (
                not isinstance(envelope, dict)
                or set(envelope) != {"runner_completed", "result"}
                or envelope["runner_completed"] is not True
            ):
                raise ValueError("runner did not complete")
            actual = envelope["result"]
            if not isinstance(actual, dict) or actual.get("state") not in {"returned", "raised"}:
                raise ValueError("invalid child result")
            keys = {"state", "args_after", "value" if actual["state"] == "returned" else "exception"}
            if set(actual) != keys:
                raise ValueError("unexpected child fields")
            validate_invocation({**record, **actual}, request)
            record.update(actual)
        except (UnicodeError, ValueError, TypeError, RecursionError):
            record.update(state="malformed", reason="invalid_child_json")
    return validate_invocation(record, request)


def run_case(snapshot, request, *, timeout_seconds=5, trusted_fixture=False, deadline=None):
    """Run a fixed data-only request in a new copied workspace and Python process.

    This function is for authored local controls. Its output is controller-owned
    only when obtained through this call, never by loading a candidate's file.
    """
    if trusted_fixture is not True:
        raise ValueError(
            "host subprocess execution requires explicit trusted_fixture=True; supply a sandbox invoker for untrusted candidates"
        )
    request = validate_request(request)
    if (
        type(timeout_seconds) not in {int, float}
        or not math.isfinite(timeout_seconds)
        or not 0 < timeout_seconds <= 120
    ):
        raise ValueError("invalid case timeout")
    snapshot = Path(snapshot)
    before = snapshot_manifest(snapshot)
    source = snapshot / (request["module"] + ".py")
    if not source.is_file():
        raise ValueError("requested module is absent from the snapshot")
    record = {
        "schema_version": SCHEMA,
        "record_type": "case_invocation",
        "request": request,
        "candidate_id": digest(before),
        "runner_sha256": hashlib.sha256(CHILD.encode()).hexdigest(),
        "isolation": "fresh_process_only_not_security_sandbox",
    }
    with tempfile.TemporaryDirectory(prefix="evalopt-v2-case-") as temporary:
        workspace = Path(temporary) / "workspace"
        shutil.copytree(snapshot, workspace)
        if snapshot_manifest(workspace) != before or snapshot_manifest(snapshot) != before:
            raise ValueError("snapshot changed during copy")
        # This also prevents ordinary fixture writes; it is not a malicious-code sandbox.
        for path in workspace.rglob("*"):
            path.chmod(0o555 if path.is_dir() else 0o444)
        if deadline is not None:
            if type(deadline) not in {int, float} or not math.isfinite(deadline):
                raise ValueError("invalid absolute case deadline")
            timeout_seconds = min(timeout_seconds, deadline - time.monotonic())
        if timeout_seconds <= 0:
            return {**record, "state": "not_run", "reason": "case_setup_deadline"}
        record = execute_process(
            request,
            [sys.executable, "-I", "-B", "-c", CHILD],
            cwd=workspace,
            timeout_seconds=timeout_seconds,
            record=record,
        )
    if snapshot_manifest(snapshot) != before:
        raise ValueError("original snapshot mutated")
    return validate_invocation(record, request)
