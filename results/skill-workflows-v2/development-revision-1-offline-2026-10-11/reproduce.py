#!/usr/bin/env python3
"""Verify a source-bound offline receipt; no candidate code or model execution."""

import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    for name, expected in read(here / "checksums.json").items():
        if Path(name).name != name or sha(here / name) != expected:
            raise ValueError("receipt artifact checksum mismatch")
    receipt = read(here / "controls.json")
    for name, expected in receipt["source_inventory"].items():
        path = repo / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or path.resolve() != path.absolute()
            or sha(path) != expected["sha256"]
            or bool(path.stat().st_mode & 0o100) != expected["executable"]
        ):
            raise ValueError("tested source differs: " + name)
    cases = receipt["cases"]
    if len({(row["class"], row["name"]) for row in cases}) != len(cases):
        raise ValueError("duplicate test identity")
    if any(row["outcome"] != "passed" for row in cases):
        raise ValueError("required offline control did not pass")
    summary = receipt["summary"]
    if summary["tests"] != len(cases) or any(
        summary[k] != 0 for k in ("failures", "errors", "skips", "live_model_trials")
    ):
        raise ValueError("test summary differs")
    if receipt["preservation"]["status"] != "PASS":
        raise ValueError("preservation did not pass")
    review = read(here / "review.json")
    if review["verdict"] != "ACCEPT":
        raise ValueError("independent review has not accepted")
    for name, expected in review["source_hashes"].items():
        if receipt["source_inventory"][name]["sha256"] != expected:
            raise ValueError("review and controls cover different bytes")
    print(
        json.dumps(
            {"status": "PASS", **summary, "scope": "offline receipt consistency; no live model replication"},
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
