#!/usr/bin/env python3
"""Apply the prospective patch only in a fresh copy; run data-only controls.

No working source is changed. Git objects and payload bytes are hash checked.
This is not a model trial, a regrade, or validation of an experimental improvement.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

BASE_COMMIT = "f36088d17adcbfdfe24ec2a15d1268fd539daae6"
PREFIX = "bench/harbor/skill-workflows-v3/"


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate manifest field")
            result[key] = value
        return result

    return json.loads(
        path.read_bytes(),
        object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite manifest")),
    )


def safe_relative(name):
    require(
        type(name) is str
        and name
        and not name.startswith("/")
        and all(part not in {"", ".", ".."} for part in name.split("/")),
        "unsafe relative path",
    )
    return name


def git(repo, *arguments):
    return subprocess.run(
        ["git", "-C", str(repo), *arguments], capture_output=True, check=True, timeout=30
    ).stdout


def apply_to_fresh(repo, output, bundle):
    repo, bundle = Path(repo).absolute(), Path(bundle).absolute()
    require(
        repo.resolve(strict=True) == repo and bundle.resolve(strict=True) == bundle,
        "real source paths required",
    )
    output = Path(output).absolute()
    require(
        not output.exists() and output.parent.resolve(strict=True) == output.parent,
        "fresh output directory required",
    )
    require(
        not output.is_relative_to(bundle) and not bundle.is_relative_to(output),
        "output cannot overlap patch bundle",
    )
    require(
        output != repo
        and not (repo / PREFIX).is_relative_to(output)
        and not output.is_relative_to(repo / PREFIX),
        "output cannot overlap working source",
    )
    manifest = read(bundle / "manifest.json")
    require(
        manifest["base_commit"] == BASE_COMMIT
        and manifest["package_prefix"] == PREFIX
        and manifest["prospective_only"] is True
        and manifest["live_trials"] == 0,
        "wrong prospective base or scope",
    )
    require(git(repo, "rev-parse", BASE_COMMIT).decode().strip() == BASE_COMMIT, "base commit unavailable")
    source_names = (
        git(repo, "ls-tree", "-r", "--name-only", BASE_COMMIT, "--", PREFIX + "evalopt_v3")
        .decode()
        .splitlines()
    )
    require(
        set(manifest["base_source_sha256"]) == {name for name in source_names if name.endswith(".py")},
        "incomplete base source roster",
    )
    originals, current_before = {}, {}
    for name, expected in manifest["base_source_sha256"].items():
        safe_relative(name)
        require(name.startswith(PREFIX + "evalopt_v3/") and name.endswith(".py"), "unexpected base source")
        raw = git(repo, "show", BASE_COMMIT + ":" + name)
        require(sha(raw) == expected, "base source hash mismatch")
        originals[name] = raw
        current = repo / name
        require(current.is_file() and not current.is_symlink(), "working source unavailable")
        current_before[name] = sha(current.read_bytes())
    changes, diffs = {}, []
    for name, change in sorted(manifest["changes"].items()):
        safe_relative(name)
        require(
            name.startswith(PREFIX) and set(change) == {"before_sha256", "after_sha256", "payload"},
            "invalid patch target",
        )
        payload = bundle / safe_relative(change["payload"])
        require(payload.resolve(strict=True) == payload and payload.is_file(), "unsafe payload")
        raw = payload.read_bytes()
        require(sha(raw) == change["after_sha256"], "patched payload hash mismatch")
        before = originals.get(name)
        require(
            (sha(before) if before is not None else None) == change["before_sha256"], "patch base mismatch"
        )
        changes[name] = raw
        diffs.extend(
            difflib.unified_diff(
                (before or b"").decode().splitlines(keepends=True),
                raw.decode().splitlines(keepends=True),
                fromfile="a/" + name if before is not None else "/dev/null",
                tofile="b/" + name,
            )
        )
    patch = "".join(diffs).encode()
    require(
        sha(patch) == manifest["patch_sha256"] and patch == (bundle / "response-contract.patch").read_bytes(),
        "review patch differs from payload",
    )
    require(
        set(changes)
        == {
            PREFIX + "evalopt_v3/" + name
            for name in ("grading.py", "reporting.py", "materialize.py", "response_contract.py")
        }
        | {PREFIX + "tests/test_response_contract.py"},
        "patch scope changed",
    )
    output.mkdir()
    for name, raw in originals.items():
        relative = Path(name).relative_to(PREFIX)
        for layer in ("original", "patched"):
            target = output / layer / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
    for name, raw in changes.items():
        target = output / "patched" / Path(name).relative_to(PREFIX)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    return manifest, current_before


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    require(
        platform.python_implementation() == "CPython"
        and sys.version_info[:3] == (3, 13, 12)
        and sys.flags.isolated
        and sys.dont_write_bytecode,
        "CPython3.13.12 -I -B required",
    )
    bundle = Path(__file__).resolve().parent
    manifest, before = apply_to_fresh(args.repo, args.output_dir, bundle)
    output = args.output_dir.absolute()
    command = [sys.executable, "-I", "-B", str(output / "patched/tests/test_response_contract.py")]
    control = subprocess.run(
        command,
        capture_output=True,
        timeout=60,
        check=False,
        cwd=output,
        env={"PATH": os.environ.get("PATH", ""), "EVALOPT_ORIGINAL_ROOT": str(output / "original")},
    )
    (output / "controls.stdout").write_bytes(control.stdout)
    (output / "controls.stderr").write_bytes(control.stderr)
    after = {name: sha((args.repo / name).read_bytes()) for name in before}
    preserved = before == after
    receipt = dict(
        schema_version="evalopt.prospective-response-contract-fix.v1",
        base_commit=BASE_COMMIT,
        status="PASS" if control.returncode == 0 and preserved else "FAIL",
        manifest_sha256=sha((bundle / "manifest.json").read_bytes()),
        patch_sha256=manifest["patch_sha256"],
        source_preserved=preserved,
        controls_returncode=control.returncode,
        controls_stdout_sha256=sha(control.stdout),
        controls_stderr_sha256=sha(control.stderr),
        model_calls=0,
        candidate_executions=0,
        docker_calls=0,
        frozen_results_changed=False,
        scope="Prospective prompt completeness and pure validator parity on synthetic data; no live validation or original regrade.",
    )
    (output / "receipt.json").write_bytes(canonical(receipt))
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
