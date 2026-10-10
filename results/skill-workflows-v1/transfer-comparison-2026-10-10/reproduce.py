#!/usr/bin/env python3
"""Offline arithmetic and evidence replay; never execute stopped candidate code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import stat
import sys
import tempfile
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    require(stat.S_ISREG(path.lstat().st_mode), "nonregular evidence file")
    return path.read_bytes()


def parse(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite JSON number")
        return result

    def constant(_value):
        raise ValueError("nonfinite JSON constant")

    return json.loads(read(path), object_pairs_hook=pairs, parse_float=number, parse_constant=constant)


def files(root, *, ignore_cache=False):
    require(root.is_dir() and not root.is_symlink(), "missing or symlink evidence directory")
    result = {}
    for path in sorted(root.rglob("*")):
        if ignore_cache and "__pycache__" in path.relative_to(root).parts:
            continue
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "nonregular evidence node")
        if stat.S_ISREG(mode):
            result[path.relative_to(root).as_posix()] = read(path)
    return result


def verify_checksums(root, schema, *, expected=None):
    payloads = files(root)
    require("CHECKSUMS.json" in payloads, "final outer checksums are unavailable")
    envelope = parse(root / "CHECKSUMS.json")
    require(
        isinstance(envelope, dict)
        and set(envelope) == {"schema_version", "bundle_id", "files"}
        and envelope["schema_version"] == schema,
        "invalid checksum envelope",
    )
    actual = {
        name: {"sha256": sha(raw), "size": len(raw)}
        for name, raw in payloads.items()
        if name != "CHECKSUMS.json"
    }
    require(canonical(envelope["files"]) == canonical(actual), "checksum or file roster changed")
    require(envelope["bundle_id"] == sha(canonical(actual)), "checksum bundle identity changed")
    require(expected is None or envelope["bundle_id"] == expected, "unexpected retained bundle")
    return envelope["bundle_id"]


def tree_identity(root):
    manifest = {name: sha(raw) for name, raw in files(root, ignore_cache=True).items()}
    return sha(json.dumps(manifest, sort_keys=True).encode())


KERNEL_SHA = "461cdc169428470d578283171b3009b0f6dff0999801ed444e92fafde5c56700"


def reproduce(source):
    require(
        platform.python_implementation() == "CPython" and sys.version_info[:3] == (3, 13, 12),
        "CPython 3.13.12 is required",
    )
    require(sys.flags.isolated == 1, "run Python with -I")
    root = Path(__file__).resolve().parent
    outer_id = verify_checksums(root, "evalopt.transfer-release-checksums.v1")
    inner_id = verify_checksums(
        root / "bundle",
        "evalopt.transfer-public-checksums.v1",
        expected="6ac536cef0fa72f52dfd066e3c45861a61c5044ca3c7d0e82166b6ab1837e62d",
    )
    source = source.resolve(strict=True)
    benchmark = source / "bench/harbor/skill-workflows-v1"
    lock = parse(root / "bundle/source-lock.json")
    require(tree_identity(benchmark) == lock["campaign_sha256"], "use the registered benchmark source")
    require(
        tree_identity(benchmark / "lib") == lock["library_sha256"], "use the registered benchmark library"
    )
    require(tree_identity(source / "src/evalopt_graph") == KERNEL_SHA, "use the retained kernel source")
    with tempfile.TemporaryDirectory(prefix="evalopt-transfer-replay-") as temporary:
        sys.pycache_prefix = str(Path(temporary).resolve() / "pycache")
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(benchmark), str(source / "src")]
        import transfer_publish

        result = transfer_publish.verify_public_bundle(root / "bundle")
    rows = parse(root / "bundle/reports/outcomes.json")
    attempts = parse(root / "bundle/reports/attempts.json")
    require(
        result["bundle_id"] == inner_id and result["attempts_verified"] == len(attempts) == 58,
        "unexpected executed coverage",
    )
    require(
        len(rows) == 72 and sum(row["status"] == "pending" for row in rows) == 14,
        "unexpected scheduled coverage",
    )
    require(sum(row["upstream_reward"] is not None for row in rows) == 54, "unexpected reward coverage")
    return {
        "schema_version": "evalopt.transfer-release-replay.v1",
        "release_bundle_id": outer_id,
        "transfer": result,
        "scheduled_trials": 72,
        "executed_attempts": 58,
        "unstarted_rows": 14,
        "operational_note_scope": "File identities verified; private raw bytes, process observations and controller-journal reconstruction are not independently reexecuted by public replay.",
        "candidate_execution_performed": False,
        "independent_replication": False,
        "network_publication_performed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="trusted repository checkout")
    print(json.dumps(reproduce(parser.parse_args().source), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
