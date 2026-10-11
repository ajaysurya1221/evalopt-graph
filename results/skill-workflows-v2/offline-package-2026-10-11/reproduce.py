#!/usr/bin/env python3
"""Reproduce the published offline receipt; never run candidate or test code."""

import hashlib
import json
from pathlib import Path


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    sums = json.loads((here / "checksums.json").read_bytes())
    for name, expected in sums.items():
        if Path(name).name != name or sha((here / name).read_bytes()) != expected:
            raise ValueError("public artifact checksum mismatch")
    receipt = json.loads((here / "controls.json").read_bytes())
    for name, record in receipt["source_inventory"].items():
        path = repo / name
        if (
            path.resolve() != path.absolute()
            or not path.is_file()
            or ".." in Path(name).parts
            or Path(name).is_absolute()
            or sha(path.read_bytes()) != record["sha256"]
            or bool(path.stat().st_mode & 0o100) != record["executable"]
        ):
            raise ValueError("reviewed source identity mismatch: " + name)
    cases = receipt["cases"]
    if len({(case["class"], case["name"]) for case in cases}) != len(cases):
        raise ValueError("duplicate offline case identity")
    summary = {
        "tests": len(cases),
        "subtests": receipt["subtests"],
        "failures": sum(case["outcome"] == "failed" for case in cases),
        "errors": sum(case["outcome"] == "error" for case in cases),
        "skips": sum(case["outcome"] == "skipped" for case in cases),
        "v1_files_preserved": receipt["preservation"]["baseline_files"],
        "live_trials_in_this_receipt": 0,
    }
    if any(case["outcome"] not in {"passed", "failed", "error", "skipped"} for case in cases):
        raise ValueError("invalid offline case outcome")
    if summary != receipt["summary"]:
        raise ValueError("offline summary mismatch")
    if receipt["preservation"]["status"] != "PASS":
        raise ValueError("v1 preservation did not pass")
    review = json.loads((here / "review.json").read_bytes())
    if review["verdict"] != "ACCEPT":
        raise ValueError("independent integration review did not accept")
    for name, expected in review["source_hashes"].items():
        if receipt["source_inventory"][name]["sha256"] != expected:
            raise ValueError("reviewed and tested source mismatch")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
