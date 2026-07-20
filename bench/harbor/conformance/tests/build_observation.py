#!/usr/bin/env python3
"""Build one controller-owned visible observation; never reads hidden grader output."""

import argparse
import hashlib
import json
from pathlib import Path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--visible-artifact", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--policy-source", type=Path, required=True)
    parser.add_argument("--candidate-commit", required=True)
    args = parser.parse_args()
    commit = args.candidate_commit.lower()
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise SystemExit("candidate commit must be a full hexadecimal commit")
    payload = json.loads(args.template.read_text())
    visible_pass = (
        args.visible_artifact.is_file()
        and args.visible_artifact.read_text().strip() == "kernel adapter ready"
    )
    payload["acceptance_input"]["gate_results"] = [["tests", "PASS" if visible_pass else "FAIL"]]
    payload["run_identity"] = {
        "schema_version": "evalopt.run-identity.v1",
        "candidate_commit": commit,
        "wheel_sha256": _sha(args.wheel),
        "policy_source_sha256": _sha(args.policy_source),
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
