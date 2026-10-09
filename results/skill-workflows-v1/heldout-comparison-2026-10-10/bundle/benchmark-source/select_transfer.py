"""Score-blind Terminal-Bench feasibility subset selection (Python 3.11+)."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import tomllib

PIN = "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c"


def select(repository):
    sha = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], check=True, text=True, capture_output=True
    ).stdout.strip()
    if sha != PIN:
        raise ValueError("Terminal-Bench checkout differs from registered pin")
    eligible = []
    for path in sorted(repository.glob("*/task.toml")):
        data = tomllib.loads(path.read_text())
        metadata, environment = data["metadata"], data["environment"]
        if metadata.get("category") not in {"software-engineering", "debugging"}:
            continue
        if (
            environment.get("cpus", 1) > 1
            or environment.get("memory") != "2G"
            or environment.get("gpus", 0) != 0
        ):
            continue
        if data["agent"]["timeout_sec"] > 1800 or data["verifier"]["timeout_sec"] > 1800:
            continue
        if set(metadata.get("tags", [])) & {"ocr", "images", "no-verified-solution"}:
            continue
        eligible.append(
            {
                "task_id": path.parent.name,
                "category": metadata["category"],
                "agent_seconds": data["agent"]["timeout_sec"],
                "verifier_seconds": data["verifier"]["timeout_sec"],
                "image_source": environment.get("docker_image"),
                "task_toml_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if len(eligible) < 12:
        raise ValueError("fewer than twelve eligible tasks; no unregistered substitutions")
    return {
        "schema_version": "evalopt.transfer-selection.v1",
        "source_commit": PIN,
        "evidence_class": "score-blind feasibility subset; not leaderboard",
        "eligible": eligible,
        "selected": eligible[:12],
        "images_resolved": False,
        "trials_run": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = select(args.repository)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")
