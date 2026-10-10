"""Explicit external admission amendment. Frozen evidence and functions stay unchanged."""

import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

COMMIT = "31231949412ea6d0101331720c0f0ed2d9f50b46"
REGISTRATION = "1f3116fe8af392300a225ab79bfefb7278942dd48999f5875cfdc0bf757dc32f"
POLICY = "cde084b941e27504f7960fba48eb38b7a11213f949626b1383b422b335801b1c"
PROPOSAL = "05bcf48c1e20f38b9067781a4c6bf8a2cc9c682999844f25efb765035e19386e"
APPROVAL = "ad4c31a139d421468858ea8a2bef8671ceae622e0dcd1d79888ab7ee8e7da721"
PENDING = "0fb4fbea1e1b088cbaabac3d42b33c3054a104070f690bed06350e31142c751a"
PREFIX = "58764d677d1a4f38bea64df45888a54a39cb3df33a99cdc84d11c7abf5e94b52"
STOP = "791a83b01b27f39f7c7c78664e6ebbfa79332ba833feec0abb0fa7d99b9e2d9c"
TRIAL = "transfer--make-doom-for-mips--r1--B"
OLD_CODE = {
    "operator.py": "6b9d464ad008f2c01d72993d8678e5f06571f67a1933f7422c712a7cc445feca",
    "bridge.py": "c098c00d195dff451cf64d10af40879d62209b70c3b077b4b7ba48280befc340",
}
CODE_FILES = ("amendment.py", "bridge.py", "operator.py")
WAIVER_FILES = {
    "finish.json": "b6f344f92faa9cf72990f756b543187e1f8ab88fdc096fd4a4f5670037c88dcc",
    "manifest.json": "7980f5e7e73dabd27ad86e6a585dd21dad01f9675f56bd99f2544335d9ca1eb0",
    "transfer-result.json": "f26cb2a5450274e191e1c82ecd91ac06b02e339113fcf111a7d91b7b876762cd",
    "raw/result.json": "abf30c07c317ba87fa3b3187ef955c99f8b5f31ef91da6c4417dc984fbccf000",
    "raw/artifacts.json": "738258bc4a30486e52b4a81b25bff16cab9ac5faa6586d203462c4d78544446e",
}


def safe(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("unsafe path")
    return path


def hashed(path):
    path = safe(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("expected regular file")
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    return json.loads(
        safe(path).read_text(),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")),
    )


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Paths:
    source: Path
    campaign: Path
    upstream: Path
    old_receipts: Path
    old_launch: Path
    python: Path
    image_lock: Path
    docker_raw: Path

    @classmethod
    def parse(cls, value):
        if set(value) != set(cls.__dataclass_fields__):
            raise ValueError("wrong path roster")
        paths = cls(**{k: (Path(v) if k == "python" else safe(v)) for k, v in value.items()})
        safe(paths.python.parent)
        if not paths.python.is_absolute() or not paths.python.is_file():
            raise ValueError("invalid controller interpreter")
        # Runtime executable commonly is a symlink inside a venv: use its canonical target only.
        return paths


@dataclass(frozen=True)
class Context:
    grant_path: Path
    grant_sha256: str
    grant: dict
    paths: Paths
    prefix: dict
    pending_rows: list
    code_root: Path


def receipt(value):
    if set(value) != {"path", "sha256"}:
        raise ValueError("wrong receipt reference")
    path = safe(value["path"])
    if hashed(path) != value["sha256"]:
        raise ValueError("receipt hash differs")
    return read(path)


def load_grant(path, expected_sha, *, code_root=None):
    path = safe(path)
    if hashed(path) != expected_sha:
        raise ValueError("grant hash differs")
    grant = read(path)
    keys = {
        "schema_version",
        "source_commit",
        "registration_sha256",
        "accounting_policy_sha256",
        "proposal_sha256",
        "pending_rows_sha256",
        "pending_rows",
        "paths",
        "controller_files",
        "prefix_manifest",
        "approval_receipt",
        "quiescence_receipt",
        "independent_review_receipt",
        "waiver",
        "reporting_obligations",
    }
    if set(grant) != keys or grant["schema_version"] != "evalopt.transfer-continuation-grant.v1":
        raise ValueError("unsupported grant schema")
    for key, expected in {
        "source_commit": COMMIT,
        "registration_sha256": REGISTRATION,
        "accounting_policy_sha256": POLICY,
        "proposal_sha256": PROPOSAL,
        "pending_rows_sha256": PENDING,
    }.items():
        if grant[key] != expected:
            raise ValueError("grant identity differs: " + key)
    pending = grant["pending_rows"]
    if len(pending) != 17 or digest(pending) != PENDING:
        raise ValueError("pending full-row roster differs")
    if digest(grant["waiver"]) != digest(
        {"trial_id": TRIAL, "attempt": 1, "files": WAIVER_FILES, "old_stop_sha256": STOP}
    ):
        raise ValueError("historical waiver differs")
    if grant["reporting_obligations"] != [
        "disclose_post_freeze_admission_amendment",
        "preserve_original_failure_and_missing_capture",
        "bind_new_external_journal",
        "no_efficiency_or_retroactive_boundary_claim",
    ]:
        raise ValueError("reporting obligations differ")
    code_root = safe(code_root or Path(__file__).resolve().parent)
    code = grant["controller_files"]
    if set(code) != set(CODE_FILES) or any(hashed(code_root / n) != code[n] for n in CODE_FILES):
        raise ValueError("controller code identity differs")
    if grant["approval_receipt"]["sha256"] != APPROVAL:
        raise ValueError("unrecognized human approval")
    approval = receipt(grant["approval_receipt"])
    scope = {
        "frozen_per_trial_conditions_unchanged": True,
        "future_strict_gates_unchanged": True,
        "historical_exception": TRIAL + "/attempt-1",
        "implementation_independent_review_and_tests_required_before_dispatch": True,
        "no_retry": True,
        "public_disclosure_required": True,
        "unstarted_rows": 17,
    }
    if (
        approval["schema"] != "evalopt-transfer-continuation-human-approval/v1"
        or approval["answer"] != "Approve narrow continuation amendment (Recommended)"
        or approval["proposal_sha256"] != PROPOSAL
        or digest(approval["approved_scope"]) != digest(scope)
    ):
        raise ValueError("approval scope differs")
    preflight = receipt(grant["quiescence_receipt"])
    if (
        preflight["schema_version"] != "evalopt.transfer-continuation-preflight.v1"
        or any(
            preflight.get(k) is not True
            for k in (
                "current_controller_absent",
                "old_operator_absent",
                "owned_container_absent",
                "scheduler_lock_free",
            )
        )
        or not preflight.get("checked_at")
    ):
        raise ValueError("quiescence evidence missing")
    review = receipt(grant["independent_review_receipt"])
    if (
        review.get("verdict") != "ACCEPT"
        or review.get("controller_files") != code
        or review.get("offline_controls_passed") is not True
    ):
        raise ValueError("independent code review missing or differs")
    if grant["prefix_manifest"]["sha256"] != PREFIX:
        raise ValueError("historical prefix identity differs")
    prefix = receipt(grant["prefix_manifest"])
    paths = Paths.parse(grant["paths"])
    return Context(path, expected_sha, grant, paths, prefix, pending, code_root)


def verify_context_identity(ctx):
    observed = load_grant(ctx.grant_path, ctx.grant_sha256, code_root=ctx.code_root)
    if (
        digest(observed.grant) != digest(ctx.grant)
        or observed.paths != ctx.paths
        or digest(observed.prefix) != digest(ctx.prefix)
        or digest(observed.pending_rows) != digest(ctx.pending_rows)
    ):
        raise ValueError("loaded amendment context differs from immutable grant")


def source_check(ctx):
    verify_context_identity(ctx)
    if sys.version_info[:3] != (3, 13, 12) or sys.implementation.name != "cpython":
        raise ValueError("requires CPython 3.13.12")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(ctx.paths.source), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    if git("rev-parse", "HEAD") != COMMIT or git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("frozen source identity differs")
    if digest(read(ctx.paths.campaign / "registration-lock.json")) != REGISTRATION:
        raise ValueError("registration differs")
    if digest(read(ctx.paths.campaign / "accounting-policy.json")) != POLICY:
        raise ValueError("policy differs")


def _nodes(root):
    found = {}

    def fail(error):
        raise error

    for directory, dirs, files in os.walk(safe(root), followlinks=False, onerror=fail):
        for name in dirs + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                raise ValueError("unsafe retained node")
            found[path.relative_to(root).as_posix()] = path
    return found


def _addition_allowed(relative, pending):
    parts = relative.split("/")
    if parts[:2] == ["evidence", "trials"] and len(parts) >= 3:
        return parts[2] in pending and (len(parts) == 3 or parts[3] == "attempt-1")
    if parts[0] == "private-harbor" and len(parts) >= 2:
        return parts[1] in pending and (len(parts) == 2 or parts[2] == "attempt-1")
    if parts[0] == "runs" and len(parts) >= 2:
        return bool(re.fullmatch(r"run-\d{4}", parts[1])) and int(parts[1][4:]) >= 56
    if parts[0] == "exports" and len(parts) >= 2:
        return bool(re.fullmatch(r"[0-9a-f]{64}", parts[1]))
    return False


def verify_prefix(ctx):
    """Stream all original byte hashes; do not silently exclude old raw captures."""
    roots = {
        "campaign": ctx.paths.campaign,
        "operator_receipts": ctx.paths.old_receipts,
        "launch": ctx.paths.old_launch,
    }
    expected = ctx.prefix["nodes"]
    actual = {
        label + "/" + name: path for label, root in roots.items() for name, path in _nodes(root).items()
    }
    for name, node in expected.items():
        path = actual.get(name)
        if path is None:
            raise ValueError("historical prefix node missing")
        observed = path.lstat()
        kind = "directory" if stat.S_ISDIR(observed.st_mode) else "file"
        if kind != node["kind"] or stat.S_IMODE(observed.st_mode) != node["mode"]:
            raise ValueError("historical prefix type/mode changed")
        if kind == "file" and (observed.st_size != node["bytes"] or hashed(path) != node["sha256"]):
            raise ValueError("historical prefix bytes changed")
    pending = {row["trial_id"] for row in ctx.pending_rows}
    for name in set(actual) - set(expected):
        label, relative = name.split("/", 1)
        parts = relative.split("/")
        old_export = parts[0] == "exports" and len(parts) >= 2 and "campaign/exports/" + parts[1] in expected
        if label != "campaign" or old_export or not _addition_allowed(relative, pending):
            raise ValueError("undeclared historical-prefix addition")
    for name, expected_hash in OLD_CODE.items():
        if hashed(ctx.paths.old_receipts.parent / name) != expected_hash:
            raise ValueError("old operator source changed")
    if hashed(ctx.paths.old_receipts / "STOP.json") != STOP:
        raise ValueError("old STOP changed")
    return {"sha256": PREFIX, "nodes": len(expected), "unchanged": True}


def validate_progress(ctx, schedule, store):
    if (
        len(schedule) != 72
        or digest(schedule[55:]) != PENDING
        or digest(schedule[55:]) != digest(ctx.pending_rows)
    ):
        raise ValueError("full pending schedule differs")
    states = store.statuses()
    if [s["trial_id"] for s in states] != [r["trial_id"] for r in schedule]:
        raise ValueError("status roster differs")
    pending_seen = False
    for index, state in enumerate(states):
        n = state["attempts"]
        if type(n) is not int or n not in (0, 1):
            raise ValueError("attempt retry forbidden")
        if index < 55 and (n != 1 or state["status"] not in {"completed", "timeout"}):
            raise ValueError("historical attempt changed")
        if index >= 55:
            if n == 0:
                if state["status"] != "pending":
                    raise ValueError("invalid pending state")
                pending_seen = True
            elif pending_seen or state["status"] == "running_or_interrupted":
                raise ValueError("out-of-order or active continuation attempt")
    remaining = [row for row, state in zip(schedule, states, strict=True) if not state["attempts"]]
    return remaining


def verify_waiver(ctx, record, policy, strict_gate, validate_attempt):
    """Structural validation always runs; only a byte-pinned historical record is waived."""
    validate_attempt(record, policy)
    if record.get("trial_id") != TRIAL:
        return strict_gate(record, policy)
    if type(record.get("attempt")) is not int or record["attempt"] != 1:
        raise ValueError("historical attempt identity differs")
    folder = ctx.paths.campaign / "evidence/trials" / TRIAL / "attempt-1"
    raw = ctx.paths.campaign / "private-harbor" / TRIAL / "attempt-1"
    for name, expected in WAIVER_FILES.items():
        path = raw / name[4:] if name.startswith("raw/") else folder / name
        if hashed(path) != expected:
            raise ValueError("historical waiver file differs")
    finish = read(folder / "finish.json")
    if digest({k: record.get(k) for k in finish}) != digest(finish):
        raise ValueError("historical gate record differs")
    if (
        record.get("artifact_valid") is not True
        or finish["status"] != "timeout"
        or finish.get("error_code") is not None
        or strict_gate(record, policy) != "runtime_identity_requires_remediation"
    ):
        raise ValueError("historical failure context differs")
    return None
