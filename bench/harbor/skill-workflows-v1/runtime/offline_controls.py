"""Exercise authored oracles through the actual isolated verifier, without models."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from runtime.harbor_campaign import HERE, ROOT, image_identity, materialize, source_identity, visible_check
from tasks.suite import load_task, task_ids, task_path


def controls(directory, image, verifier, *, task_root=None, split="development"):
    image, verifier = image_identity(image), image_identity(verifier)
    directory.mkdir(parents=True, exist_ok=False)
    rows = []
    for task_id in task_ids(task_root=task_root, split=split):
        task = load_task(task_id, task_root=task_root, split=split)
        target = directory / task_id
        initial = materialize(
            task, target, agent_image=image, verifier_image=verifier, arm="A", task_root=task_root
        )
        snapshot = target / "tests" / "snapshot"
        shutil.copytree(target / "environment" / "workspace", snapshot)
        oracle = task_path(task, task_root=task_root) / "oracle"
        if oracle.exists():
            shutil.copytree(oracle, snapshot, dirs_exist_ok=True)
        response = json.loads((task_path(task, task_root=task_root) / "controls.json").read_text())[
            "positive_response"
        ]
        (snapshot / "response.json").write_text(json.dumps(response))
        observation, _log = visible_check(snapshot.resolve(), task, image)
        (target / "tests" / "grading.json").write_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "split": split,
                    "initial_manifest": initial,
                    "observations": [observation],
                }
            )
        )
        out = target / "verifier-output"
        out.mkdir()
        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--cpus",
            "1",
            "--memory",
            "2g",
            "--mount",
            f"type=bind,src={(target / 'tests').resolve()},dst=/tests,readonly",
            "--mount",
            f"type=bind,src={out.resolve()},dst=/logs/verifier",
            verifier,
            "sh",
            "-c",
            "cd /tests && python3 -B verify.py",
        ]
        run = subprocess.run(command, text=True, capture_output=True, timeout=120, check=False)
        (target / "verifier-stderr.txt").write_text(run.stderr)
        grade_path = out / "grade.json"
        grade = json.loads(grade_path.read_text()) if grade_path.exists() else {}
        row = {
            "task_id": task_id,
            "exit_code": run.returncode,
            "oracle_passed": run.returncode == 0 and grade.get("valid_completion") is True,
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    result = {
        "schema_version": "evalopt.runtime-controls.v1",
        "agent_trials": 0,
        "all_passed": bool(rows) and all(r["oracle_passed"] for r in rows),
        "controls": rows,
        "verifier_source": str(HERE / "verify.py"),
        "tasks_sha256": source_identity(ROOT / "tasks"),
        "verify_sha256": __import__("hashlib").sha256((HERE / "verify.py").read_bytes()).hexdigest(),
        "agent_image": image,
        "verifier_image": verifier,
    }
    if split != "development" or task_root is not None:
        result.update(
            split=split,
            task_root_sha256=source_identity(task_root if task_root is not None else ROOT / "tasks" / split),
        )
    (directory / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--image", default="evalopt-workflows-runtime:dev")
    parser.add_argument("--verifier", default="evalopt-workflows-verifier:dev")
    parser.add_argument("--task-root", type=Path)
    parser.add_argument("--split", choices=("development", "heldout"), default="development")
    args = parser.parse_args()
    result = controls(args.directory, args.image, args.verifier, task_root=args.task_root, split=args.split)
    raise SystemExit(0 if result["all_passed"] else 1)
