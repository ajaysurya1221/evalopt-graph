#!/usr/bin/env python3
"""Offline arithmetic and evidence replay; never execute stopped candidate code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
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


def materialize_asset_modes(bundle, destination):
    """Restore hash-bound POSIX asset metadata that a Git checkout cannot retain."""
    shutil.copytree(bundle, destination)
    verify_checksums(
        destination,
        "evalopt.heldout-public-checksums.v1",
        expected="6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa",
    )
    assets = parse(destination / "ASSETS.json")["nodes"]
    for name, node in sorted(assets.items(), key=lambda item: len(Path(item[0]).parts)):
        relative = Path(name)
        require(not relative.is_absolute() and ".." not in relative.parts, "unsafe asset path")
        require(type(node["mode"]) is int and 0 <= node["mode"] <= 0o777, "unsafe asset mode")
        path = destination / relative
        if node["type"] == "directory":
            path.mkdir(parents=True, exist_ok=True)
            require(path.is_dir() and not path.is_symlink(), "invalid asset directory")
        else:
            require(node["type"] == "file" and stat.S_ISREG(path.lstat().st_mode), "invalid asset file")
    for name, node in sorted(assets.items(), key=lambda item: len(Path(item[0]).parts), reverse=True):
        (destination / name).chmod(node["mode"])
    return destination


def reproduce(source):
    require(
        platform.python_implementation() == "CPython" and sys.version_info[:3] == (3, 13, 12),
        "CPython 3.13.12 is required",
    )
    require(sys.flags.isolated == 1, "run Python with -I")
    root = Path(__file__).resolve().parent
    outer_id = verify_checksums(root, "evalopt.heldout-release-checksums.v1")
    verify_checksums(
        root / "bundle",
        "evalopt.heldout-public-checksums.v1",
        expected="6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa",
    )
    source = source.resolve(strict=True)
    benchmark = source / "bench/harbor/skill-workflows-v1"
    lock = parse(root / "bundle/source-lock.json")
    require(
        tree_identity(benchmark) == lock["campaign_sha256"], "use the trusted registered benchmark source"
    )
    require(
        tree_identity(source / "src/evalopt_graph") == lock["kernel_source_sha256"],
        "use the registered kernel source",
    )
    with tempfile.TemporaryDirectory(prefix="evalopt-heldout-replay-") as temporary:
        temporary = Path(temporary).resolve(strict=True)
        bundle = materialize_asset_modes(root / "bundle", temporary / "bundle")
        sys.pycache_prefix = str(temporary / "pycache")
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(benchmark), str(source / "src")]
        import heldout_publish

        result = heldout_publish.verify_public_bundle(bundle)
    require(
        result["bundle_id"] == "6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa",
        "unexpected heldout bundle",
    )
    require(
        result["scheduled_trials"] == result["grade_records_replayed"] == 432
        and result["released_tasks"] == 48
        and result["declared_unavailable_trials"] == 0,
        "unexpected final evidence coverage",
    )
    return {
        "schema_version": "evalopt.heldout-release-replay.v1",
        "release_bundle_id": outer_id,
        "heldout": result,
        "operational_note_scope": "File identities verified; private incident reconstruction is not independently reexecuted by public replay.",
        "asset_mode_scope": "Declared POSIX asset modes restored in a temporary hash-verified copy because Git does not preserve non-executable permission bits; checkout and frozen evidence bytes unchanged.",
        "candidate_execution_performed": False,
        "independent_replication": False,
        "network_publication_performed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="trusted repository checkout")
    args = parser.parse_args()
    print(json.dumps(reproduce(args.source), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
