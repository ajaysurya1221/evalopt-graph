"""Harbor separate verifier entrypoint; expected values never enter candidate child."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

if __package__:
    from tasks.suite import evaluate_cases, file_manifest, grade_snapshot, load_task
else:
    from suite import evaluate_cases, file_manifest, grade_snapshot, load_task

CALL = """import importlib,json,sys
sys.path.insert(0, "/workspace")
request=json.loads(sys.stdin.read())
args=request["args"]
try:
    module=importlib.import_module(request["module"])
    result=getattr(module,request["function"])(*args)
    output={"result":result,"args":args}
except Exception as error:
    cls=type(error)
    name=cls.__name__ if cls.__module__=="builtins" else cls.__module__+"."+cls.__name__
    output={"error":name,"args":args}
print(json.dumps(output))
"""


def strict_json(data):
    def reject_constant(_):
        raise ValueError("nonfinite JSON value")

    value = json.loads(data, parse_constant=reject_constant)
    # Numeric overflow (for example 1e999) does not call parse_constant.
    json.dumps(value, allow_nan=False)
    return value


def invoke(request):
    result = subprocess.run(
        ["chroot", "--userspec=65534:65534", "/candidate-root", "/usr/bin/python3", "-I", "-B", "-c", CALL],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        timeout=5,
        env={"PATH": "/usr/sbin:/usr/bin:/bin"},
        check=False,
    )
    if result.returncode:
        raise ValueError("candidate failed to return a result")
    return strict_json(result.stdout)  # Empty exit-zero and extra forged output fail.


def collect_grade(task, config, stopped_manifest, response, invoke_case):
    """Retain verifier-owned inputs after policy freeze, including actual case replies."""
    records = []

    def observed_invoke(request):
        record = {"request": json.loads(json.dumps(request))}
        try:
            actual = invoke_case(request)
            actual = json.loads(json.dumps(actual, allow_nan=False))
        except (OSError, ValueError, TimeoutError, subprocess.SubprocessError):
            record["error"] = "candidate_invocation_failed"
            records.append(record)
            raise
        record["actual"] = actual
        records.append(record)
        return actual

    unsafe = config.get("unsafe_snapshot", False)
    hidden = False if unsafe else evaluate_cases(task, observed_invoke)
    grade = grade_snapshot(
        task,
        config["initial_manifest"],
        stopped_manifest,
        response,
        config["observations"],
        hidden_test_passed=hidden,
    )
    grade["reproduction_inputs"] = {
        "schema_version": "evalopt.grade-reproduction.v1",
        "task_id": task["id"],
        "split": task["split"],
        "initial_manifest": config["initial_manifest"],
        "stopped_manifest": stopped_manifest,
        "response": response,
        "observations": config["observations"],
        "unsafe_snapshot": unsafe,
        "hidden_test_passed": hidden,
        "hidden_case_records": records,
    }
    return grade


def main():
    root = Path("/tests")
    config = json.loads((root / "grading.json").read_text())
    stopped = root / "snapshot"
    task = load_task(config["task_id"], split=config.get("split", "development"))
    # Snapshot cannot introduce a link to grader files or write root-owned outputs.
    if any(path.is_symlink() for path in stopped.rglob("*")):
        raise ValueError("unsupported snapshot symlink")
    shutil.copytree(stopped, Path("/candidate-root/workspace"), dirs_exist_ok=True)
    for path in Path("/candidate-root/workspace").rglob("*"):
        os.chmod(path, 0o555 if path.is_dir() else 0o444)
    try:
        response = strict_json((stopped / "response.json").read_text())
    except (OSError, ValueError):
        response = None
    grade = collect_grade(
        task,
        config,
        config.get("stopped_manifest", file_manifest(stopped)),
        response,
        invoke,
    )
    output = Path("/logs/verifier")
    (output / "grade.json").write_text(json.dumps(grade, sort_keys=True) + "\n")
    (output / "reward.txt").write_text(str(int(grade["valid_completion"])) + "\n")


if __name__ == "__main__":
    main()
