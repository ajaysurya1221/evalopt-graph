#!/usr/bin/env python3
"""Verify release version identity and, for tag builds, Git provenance."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import tomllib
from verify_installed_release import verify

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--tag")
    parser.add_argument("--main-ref")
    parser.add_argument("--require-annotated-tag", action="store_true")
    args = parser.parse_args()

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["name"] == "evalopt-graph"
    assert project["version"] == args.expected_version
    assert project["dependencies"] == [], "the stable kernel must have zero runtime dependencies"
    assert project["requires-python"] == ">=3.10"
    verify(args.expected_version)

    if args.tag:
        expected_tag = f"v{args.expected_version}"
        assert args.tag == expected_tag, f"tag {args.tag!r} does not match {expected_tag!r}"
        tag_type = git("cat-file", "-t", args.tag)
        if args.require_annotated_tag:
            assert tag_type == "tag", f"{args.tag} must be an annotated tag, found {tag_type!r}"
        tag_commit = git("rev-parse", f"{args.tag}^{{commit}}")
        head_commit = git("rev-parse", "HEAD")
        assert tag_commit == head_commit, "checked-out commit is not the tagged commit"
        if args.main_ref:
            main_commit = git("rev-parse", f"{args.main_ref}^{{commit}}")
            assert tag_commit == main_commit, (
                f"tag commit {tag_commit} is not the exact {args.main_ref} commit {main_commit}"
            )

    print(f"release identity verified for evalopt-graph {args.expected_version}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, subprocess.CalledProcessError) as exc:
        print(f"release verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
