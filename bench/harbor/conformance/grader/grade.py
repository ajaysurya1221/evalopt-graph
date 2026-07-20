#!/usr/bin/env python3
"""Public conformance oracle, packaged outside Harbor's policy-verifier image."""

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    success = args.artifact.is_file() and args.artifact.read_text().strip() == "kernel adapter ready"
    args.output.write_text(
        json.dumps({"schema_version": "evalopt.conformance-grade.v1", "task_success": int(success)}) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
