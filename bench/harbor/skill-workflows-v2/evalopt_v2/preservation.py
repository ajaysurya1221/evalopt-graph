"""Verify every original tracked byte and mode against the approved v1 commit."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

from .records import digest

BASE = "2deb53feb2bf20061a754b80ff93fccafeac5af7"
ALLOWED_NEW = (
    "skills/eval-opt-v2/",
    "bench/harbor/skill-workflows-v2/",
    "results/skill-workflows-v2/",
    ".github/workflows/workflow-v2.yml",
)


def inventory(repo: Path, base: str = BASE) -> list[dict]:
    data = subprocess.run(
        ["git", "ls-tree", "-rz", "--full-tree", base], cwd=repo, check=True, capture_output=True
    ).stdout
    entries = []
    for raw in data.split(b"\0"):
        if not raw:
            continue
        meta, path = raw.split(b"\t", 1)
        mode, kind, oid = meta.decode("ascii").split()
        if kind != "blob":
            raise ValueError("unsupported baseline object")
        entries.append({"path": path.decode("utf-8"), "mode": mode, "git_blob": oid})
    if not entries:
        raise ValueError("empty preservation inventory")
    return entries


def verify(repo: Path, base: str = BASE) -> dict:
    repo = repo.resolve()
    entries = inventory(repo, base)
    violations = []
    for entry in entries:
        path = repo / entry["path"]
        try:
            if path.parent.resolve() != path.parent:
                raise ValueError("parent symlink")
            if entry["mode"] == "120000":
                if not path.is_symlink():
                    raise ValueError("symlink replaced")
                content = os.readlink(path).encode()
                mode = "120000"
            else:
                if path.is_symlink() or not path.is_file():
                    raise ValueError("file missing or replaced")
                # Reject a symlink in any directory leading to a preserved file.
                if path.resolve() != path:
                    raise ValueError("parent symlink")
                content = path.read_bytes()
                mode = "100755" if path.stat().st_mode & 0o100 else "100644"
            blob = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
            if blob != entry["git_blob"] or mode != entry["mode"]:
                violations.append(entry["path"])
        except (OSError, ValueError):
            violations.append(entry["path"])
    originals = {entry["path"] for entry in entries}
    indexed = {}
    for raw in subprocess.run(
        ["git", "ls-files", "-s", "-z"], cwd=repo, check=True, capture_output=True
    ).stdout.split(b"\0"):
        if not raw:
            continue
        metadata, path = raw.split(b"\t", 1)
        mode, oid, stage = metadata.decode("ascii").split()
        name = path.decode("utf-8")
        if stage != "0" or name in indexed:
            violations.append(name)
        indexed[name] = (mode, oid)
    for entry in entries:
        if indexed.get(entry["path"]) != (entry["mode"], entry["git_blob"]):
            violations.append(entry["path"])
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo,
        check=True,
        capture_output=True,
    ).stdout
    for raw in listed.split(b"\0"):
        if raw:
            name = raw.decode("utf-8")
            if name not in originals and not any(
                name.startswith(prefix) if prefix.endswith("/") else name == prefix for prefix in ALLOWED_NEW
            ):
                violations.append(name)
    result = {
        "base_commit": base,
        "baseline_files": len(entries),
        "baseline_inventory_sha256": digest(entries),
        "status": "PASS" if not violations else "FAIL",
        "violations": sorted(set(violations)),
    }
    return result
