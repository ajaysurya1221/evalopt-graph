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
PROPOSAL = "d8efb6f3543ef9372eb1d29323671c171d06ba1064ef888dd474eadd6f738864"
APPROVAL = "2bb805e5f8003aaa6ae89b9547b927bea2f70a1f0a7de33f46c77f7f62d31bcd"
PENDING = "84eaa47f64389a18eade5261b9f5463f15d6dd8a15262f92e7b538e7ffea9029"
PREFIX = "68c3715d7d470032a3dde67d9ce0c83cb3df040de0cd5e3327a2f82fa031125e"
STOP = "791a83b01b27f39f7c7c78664e6ebbfa79332ba833feec0abb0fa7d99b9e2d9c"
TRIAL = "transfer--make-doom-for-mips--r1--B"
OLD_CODE = {
    "operator.py": "6b9d464ad008f2c01d72993d8678e5f06571f67a1933f7422c712a7cc445feca",
    "bridge.py": "c098c00d195dff451cf64d10af40879d62209b70c3b077b4b7ba48280befc340",
}
CODE_FILES = ("amendment.py", "classifier.py", "observer.py", "bridge.py", "operator.py")
PROPOSAL_POLICY = "5548f7170ee8ecb737e0047faceadb324d7589253258ba17be21cb76f303882c"
SECOND = "transfer--make-doom-for-mips--r1--C"
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
        # Preserve venv executable semantics; only its parent must be canonical.
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
    proposal: dict


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
        "proposal_policy",
        "historical_controller_files",
    }
    if set(grant) != keys or grant["schema_version"] != "evalopt.transfer-policy-v2.grant.v1":
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
    if len(grant["pending_rows"]) != 16 or digest(grant["pending_rows"]) != PENDING:
        raise ValueError("pending full rows differ")
    code_root = safe(code_root or Path(__file__).resolve().parent)
    code = grant["controller_files"]
    if set(code) != set(CODE_FILES) or any(hashed(code_root / n) != code[n] for n in CODE_FILES):
        raise ValueError("controller identity differs")
    if grant["approval_receipt"]["sha256"] != APPROVAL:
        raise ValueError("approval identity differs")
    approval = receipt(grant["approval_receipt"])
    if (
        approval.get("schema_version") != "evalopt.transfer-policy-v2-authorization.v1"
        or approval.get("status") != "EXPLICIT_HUMAN_APPROVAL_RECEIVED"
        or approval.get("answer") != "Approve bounded continuation (Recommended)"
        or approval.get("pending_rows_sha256_canonical_json") != PENDING
        or approval["bound_input_files"].get("transfer-continuation-policy-v2-proposal/README.md") != PROPOSAL
        or approval["bound_input_files"].get("transfer-continuation-policy-v2-proposal/policy.json")
        != PROPOSAL_POLICY
    ):
        raise ValueError("approval scope differs")
    for name, expected in approval["bound_input_files"].items():
        if name.startswith("/") or ".." in name.split("/") or hashed(code_root.parent / name) != expected:
            raise ValueError("approved input file changed")
    if grant["proposal_policy"]["sha256"] != PROPOSAL_POLICY:
        raise ValueError("proposal policy identity differs")
    proposal = receipt(grant["proposal_policy"])
    for pin in proposal["historical_pins"].values():
        name = pin["path_relative_to_amendment_directory"]
        if (
            name.startswith("/")
            or ".." in name.split("/")
            or hashed(code_root.parent / name) != pin["sha256_bytes"]
        ):
            raise ValueError("historical review evidence changed")
    if grant["prefix_manifest"]["sha256"] != PREFIX:
        raise ValueError("historical prefix identity differs")
    prefix = receipt(grant["prefix_manifest"])
    if prefix["node_count"] != 6415 or prefix["original_prefix_changes"]:
        raise ValueError("historical prefix coverage differs")
    preflight = receipt(grant["quiescence_receipt"])
    if any(
        preflight.get(k) is not True
        for k in (
            "current_controller_absent",
            "old_operator_absent",
            "owned_container_absent",
            "scheduler_lock_free",
        )
    ) or not preflight.get("checked_at"):
        raise ValueError("preflight evidence missing")
    review = receipt(grant["independent_review_receipt"])
    if (
        review.get("verdict") != "ACCEPT"
        or digest(review.get("controller_files")) != digest(code)
        or review.get("offline_controls_passed") is not True
    ):
        raise ValueError("independent implementation review differs")
    old = grant["historical_controller_files"]
    required = {
        "transfer-operator-v1/operator.py": "6b9d464ad008f2c01d72993d8678e5f06571f67a1933f7422c712a7cc445feca",
        "transfer-operator-v1/bridge.py": "c098c00d195dff451cf64d10af40879d62209b70c3b077b4b7ba48280befc340",
        "transfer-continuation-v1/amendment.py": "6f58ba558027d0eee5efb4e015a76a073224aac23b9d665fa47d1b89c5da44c6",
        "transfer-continuation-v1/bridge.py": "50bcc877b6c2219d7505ccd28ff13eea60effc54295fe018b5a52e8462c5e9ba",
        "transfer-continuation-v1/operator.py": "574c5ab7f8dc75c7c8986aefad0c82232054a0afd54c07e7eb2cb41d35430fb2",
    }
    if set(old) != set(required):
        raise ValueError("historical source roster differs")
    for name, expected in required.items():
        if old[name]["sha256"] != expected:
            raise ValueError("historical source identity differs")
        if hashed(safe(old[name]["path"])) != expected:
            raise ValueError("historical source changed")
    return Context(
        path,
        expected_sha,
        grant,
        Paths.parse(grant["paths"]),
        prefix,
        grant["pending_rows"],
        code_root,
        proposal,
    )


def verify_context_identity(ctx):
    fresh = load_grant(ctx.grant_path, ctx.grant_sha256, code_root=ctx.code_root)
    if (
        digest(fresh.grant) != digest(ctx.grant)
        or digest(fresh.prefix) != digest(ctx.prefix)
        or digest(fresh.proposal) != digest(ctx.proposal)
        or fresh.paths != ctx.paths
        or digest(fresh.pending_rows) != digest(ctx.pending_rows)
    ):
        raise ValueError("loaded context drift")


def source_check(ctx):
    verify_context_identity(ctx)
    if sys.version_info[:3] != (3, 13, 12) or sys.implementation.name != "cpython":
        raise ValueError("requires CPython3.13.12")

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(ctx.paths.source), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    if git("rev-parse", "HEAD") != COMMIT or git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("frozen source changed")
    if (
        digest(read(ctx.paths.campaign / "registration-lock.json")) != REGISTRATION
        or digest(read(ctx.paths.campaign / "accounting-policy.json")) != POLICY
    ):
        raise ValueError("registered identity changed")


def nodes(root):
    found = {}

    def fail(error):
        raise error

    for directory, dirs, files in os.walk(safe(root), followlinks=False, onerror=fail):
        for name in dirs + files:
            path = Path(directory) / name
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode) or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise ValueError("unsafe retained node")
            found[path.relative_to(root).as_posix()] = path
    return found


def tree(root):
    result = {}
    for name, path in nodes(root).items():
        s = path.stat()
        value = {"kind": "directory" if stat.S_ISDIR(s.st_mode) else "file", "mode": stat.S_IMODE(s.st_mode)}
        if value["kind"] == "file":
            value.update(bytes=s.st_size, sha256=hashed(path))
        result[name] = value
    return result


def verify_prefix(ctx):
    expected = ctx.prefix["nodes"]
    actual = {}
    roots = ctx.prefix["roots"]
    if (
        set(roots)
        != {"campaign", "operator_receipts", "launch", "continuation_receipts", "continuation_launch"}
        or Path(roots["campaign"]) != ctx.paths.campaign
    ):
        raise ValueError("prefix root mapping differs")
    for label, root in roots.items():
        actual.update({label + "/" + n: p for n, p in nodes(safe(root)).items()})
    for name, node in expected.items():
        path = actual.get(name)
        if path is None:
            raise ValueError("historical node missing")
        s = path.stat()
        kind = "directory" if stat.S_ISDIR(s.st_mode) else "file"
        if (
            kind != node["kind"]
            or stat.S_IMODE(s.st_mode) != node["mode"]
            or (kind == "file" and (s.st_size != node["bytes"] or hashed(path) != node["sha256"]))
        ):
            raise ValueError("historical bytes/type/mode changed")
    pending = {r["trial_id"] for r in ctx.pending_rows}
    for name in set(actual) - set(expected):
        label, relative = name.split("/", 1)
        parts = relative.split("/")
        allowed = False
        if label == "campaign":
            if parts[:2] == ["evidence", "trials"] and len(parts) >= 3:
                allowed = parts[2] in pending and (len(parts) == 3 or parts[3] == "attempt-1")
            elif parts[0] == "private-harbor" and len(parts) >= 2:
                allowed = parts[1] in pending and (len(parts) == 2 or parts[2] == "attempt-1")
            elif parts[0] == "runs" and len(parts) >= 2:
                allowed = bool(re.fullmatch(r"run-\d{4}", parts[1])) and int(parts[1][4:]) >= 57
            elif parts[0] == "exports" and len(parts) >= 2:
                allowed = (
                    bool(re.fullmatch(r"[0-9a-f]{64}", parts[1]))
                    and "campaign/exports/" + parts[1] not in expected
                )
        if not allowed:
            raise ValueError("undeclared prefix addition")
    return {"sha256": PREFIX, "nodes": len(expected), "unchanged": True}


def validate_progress(ctx, schedule, store):
    if (
        len(schedule) != 72
        or digest(schedule[56:]) != PENDING
        or digest(schedule[56:]) != digest(ctx.pending_rows)
    ):
        raise ValueError("pending schedule differs")
    states = store.statuses()
    if [s["trial_id"] for s in states] != [r["trial_id"] for r in schedule]:
        raise ValueError("status roster differs")
    pending = False
    for index, s in enumerate(states):
        n = s["attempts"]
        if type(n) is not int or n not in (0, 1):
            raise ValueError("retry forbidden")
        if index < 56 and (n != 1 or s["status"] not in ("completed", "timeout")):
            raise ValueError("historical attempt differs")
        if n == 0:
            if s["status"] != "pending":
                raise ValueError("bad pending state")
            pending = True
        elif pending or s["status"] == "running_or_interrupted":
            raise ValueError("out-of-order/active attempt")
    return [r for r, s in zip(schedule, states, strict=True) if not s["attempts"]]


def historical_gate(ctx, record, policy, strict_gate, validate_attempt):
    validate_attempt(record, policy)
    matches = [e for e in ctx.proposal["historical_exceptions"] if e["trial_id"] == record.get("trial_id")]
    if not matches:
        return strict_gate(record, policy)
    exception = matches[0]
    if type(record.get("attempt")) is not int or record["attempt"] != 1:
        raise ValueError("historical attempt differs")
    folder = ctx.paths.campaign / "evidence/trials" / record["trial_id"] / "attempt-1"
    raw = ctx.paths.campaign / "private-harbor" / record["trial_id"] / "attempt-1"
    for name, expected in exception["finish_and_evidence_sha256_bytes"].items():
        path = raw / name[4:] if name.startswith("raw/") else folder / name
        if hashed(path) != expected:
            raise ValueError("historical exception bytes changed")
    finish = read(folder / "finish.json")
    if (
        digest({k: record.get(k) for k in finish}) != digest(finish)
        or record.get("artifact_valid") is not True
    ):
        raise ValueError("historical verified record differs")
    reason = (
        "runtime_identity_requires_remediation"
        if record["trial_id"] == TRIAL
        else "execution_boundary_requires_remediation"
    )
    if (
        finish["status"] != "timeout"
        or finish.get("error_code") is not None
        or strict_gate(record, policy) != reason
    ):
        raise ValueError("historical failure differs")
    return None


def sync_directory(path):
    fd = os.open(safe(path), os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def mkdir(path):
    safe(path).mkdir()
    sync_directory(path.parent)


def write_once(path, value):
    with safe(path).open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)
