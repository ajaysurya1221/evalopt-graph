"""Source-bound offline reexecution of all36 stopped development pilot outputs.

Original grades, model outcomes and U/M/G bytes are preserved. Public verification
replays supplied hidden replies; it is distinct from the recorded Docker execution.
"""

from __future__ import annotations

import argparse
import base64
import json
import shutil
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath

import amended_pilot
import campaign
from lib.common import bytes_digest, canonical_bytes, digest, exact, is_digest, write_once
from lib.manifest import build_schedule
from lib.store import CampaignStore
from runtime.controller import require_controller
from runtime.harbor_campaign import image_identity, source_identity
from runtime.verify import strict_json
from tasks import suite

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
INPUT_FILES = (
    "start.json",
    "stopped.json",
    "visible.json",
    "policies.json",
    "grade.json",
    "finish.json",
    "manifest.json",
    "finalize.json",
    "controller-artifacts.json",
    "agent/snapshot.json",
    "agent/node-manifest.json",
    "agent/workflow-exposure.json",
    "controller/visible-check.json",
)
METRICS = (
    "valid_completion",
    "functional_success",
    "unsupported_success",
    "incorrect_refusal",
    "boundary_violation",
)
REPRO_KEYS = {
    "schema_version",
    "task_id",
    "split",
    "initial_manifest",
    "stopped_manifest",
    "response",
    "observations",
    "unsafe_snapshot",
    "hidden_test_passed",
    "hidden_case_records",
}
TERMINAL = {"completed", "agent_failure", "timeout", "budget_exhausted"}
SCOPE = "current-grader isolated stopped-output reexecution; original live pilot outcomes and policies remain unchanged; public replay uses supplied hidden replies, not independent execution or authentication"


def _safe(path):
    path = Path(path).absolute()
    if any(node.is_symlink() for node in (path, *path.parents)):
        raise ValueError("regrade path must not traverse symlinks")
    return path


def _read(path):
    path = _safe(path)
    if not stat.S_ISREG(path.stat().st_mode):
        raise ValueError("regrade artifact must be regular")
    return path.read_bytes()


def _json(path):
    return strict_json(_read(path))


def _name(value):
    if not isinstance(value, str) or not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("invalid regrade record identity")
    return value


def _copy(source, destination):
    raw = _read(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        stream.write(raw)
    return bytes_digest(raw)


def grading_identity():
    return {
        "suite": source_identity(ROOT / "tasks"),
        "verifier": bytes_digest(_read(ROOT / "runtime/verify.py")),
    }


def source_pins():
    return {
        "controller_sha256": bytes_digest(_read(Path(__file__))),
        "baseline_bridge_sha256": bytes_digest(_read(ROOT / "runtime/regrade_bridge.py")),
        "benchmark_source_sha256": source_identity(ROOT),
    }


def _native_baseline(request):
    with tempfile.TemporaryDirectory(prefix="evalopt-regrade-baseline-") as temporary:
        root = Path(temporary)
        data = {**request, "destination": str(root / "materialized"), "result": str(root / "result.json")}
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-X",
                "pycache_prefix=" + str(root / "empty-cache"),
                str(ROOT / "runtime/regrade_bridge.py"),
            ],
            input=canonical_bytes(data),
            capture_output=True,
            timeout=120,
            check=False,
        )
        if result.returncode != 0 or not (root / "result.json").is_file():
            raise ValueError("trusted frozen baseline reconstruction failed")
        return _json(root / "result.json")["initial_manifest"]


def _snapshot(value):
    exact(value, {"schema_version", "nodes"}, "stopped snapshot")
    if value["schema_version"] != "evalopt.stopped-nodes.v1" or not isinstance(value["nodes"], dict):
        raise ValueError("unsupported stopped snapshot")
    unsafe = False
    for name, node in value["nodes"].items():
        path = PurePosixPath(name)
        if (
            not isinstance(name, str)
            or not name
            or path.is_absolute()
            or path.as_posix() != name
            or any(part in {".", ".."} for part in path.parts)
            or "\\" in name
        ):
            raise ValueError("unsafe stopped snapshot path")
        if not isinstance(node, dict) or type(node.get("mode")) is not int or not 0 <= node["mode"] <= 0o7777:
            raise ValueError("invalid stopped snapshot mode")
        kind = node.get("type")
        if kind == "file":
            exact(node, {"type", "mode", "data"}, "snapshot file")
            base64.b64decode(node["data"], validate=True)
        elif kind == "directory":
            exact(node, {"type", "mode"}, "snapshot directory")
        elif kind == "symlink":
            exact(node, {"type", "mode", "target"}, "snapshot link")
            if not isinstance(node["target"], str):
                raise ValueError("invalid stopped link target")
            unsafe = True
        elif kind == "special":
            exact(node, {"type", "mode", "device", "file_type"}, "snapshot special node")
            if any(type(node[key]) is not int for key in ("device", "file_type")):
                raise ValueError("invalid special-node metadata")
            unsafe = True
        else:
            raise ValueError("invalid snapshot node type")
        for parent in path.parents:
            if (
                parent.as_posix() != "."
                and value["nodes"].get(parent.as_posix(), {}).get("type") != "directory"
            ):
                raise ValueError("snapshot lacks an explicit directory ancestor")
    return unsafe


def _decode(value, destination):
    if _snapshot(value):
        raise ValueError("unsafe stopped nodes must not be materialized")
    destination.mkdir(parents=True)
    nodes = value["nodes"]
    for name, node in sorted(nodes.items(), key=lambda item: (len(PurePosixPath(item[0]).parts), item[0])):
        path = destination / name
        if node["type"] == "directory":
            path.mkdir()
        else:
            with path.open("xb") as stream:
                stream.write(base64.b64decode(node["data"], validate=True))
            path.chmod(node["mode"])
    for name, node in sorted(nodes.items(), reverse=True):
        if node["type"] == "directory":
            (destination / name).chmod(node["mode"])


def _observation(visible, task):
    gates = [gate for gate in visible["gates"] if gate["name"] == "visible_check"]
    if len(gates) != 1:
        raise ValueError("one frozen visible observation is required")
    return [
        {
            "command": task["visible_check"],
            "source": "controller",
            "outcome": {"PASS": "passed", "FAIL": "failed", "NOT_CONFIGURED": "unavailable"}[
                gates[0]["status"]
            ],
        }
    ]


def _grader_files():
    result = {"suite.py": ROOT / "tasks/suite.py", "verify.py": ROOT / "runtime/verify.py"}
    for task_id in suite.task_ids():
        for name in ("task.json", "hidden_cases.json"):
            result[f"development/{task_id}/{name}"] = ROOT / "tasks/development" / task_id / name
    return result


def prepare(pilot, destination, *, amendment_sha256, pilot_export_id, verifier_image, bridge=None):
    """Freeze regrade inputs; requires complete pilot and no agent/controller in flight."""
    require_controller()
    pilot, destination = _safe(pilot), _safe(destination)
    if destination.exists() or destination.is_relative_to(pilot) or pilot.is_relative_to(destination):
        raise ValueError("regrade preparation requires a fresh separate directory")
    builder = _native_baseline if bridge is None else bridge
    with amended_pilot._lock(pilot):
        verified = amended_pilot.verify(pilot, amendment_sha256)
        states, schedule = verified["info"]["states"], verified["info"]["schedule"]
        if len(states) != 36 or any(row["status"] not in TERMINAL or row["attempts"] != 1 for row in states):
            raise ValueError("regrade requires all36 terminal first-attempt pilot outcomes")
        if len(schedule) != 36 or len({row["trial_id"] for row in schedule}) != 36:
            raise ValueError("invalid original36 schedule")
        if not is_digest(pilot_export_id):
            raise ValueError("original pilot export identity required")
        original_export = pilot / "exports" / pilot_export_id
        envelope = _json(original_export / "checksums.json")
        payloads = {name: _json(original_export / name) for name in envelope["files"]}
        if digest(payloads) != pilot_export_id or any(
            bytes_digest(_read(original_export / name)) != value for name, value in envelope["files"].items()
        ):
            raise ValueError("original pilot export changed")
        store = CampaignStore(pilot / "evidence", schedule)
        rows, _, attempts = campaign._report_rows(store, schedule)
        if payloads["outcomes.json"] != rows or payloads["attempts.json"] != attempts:
            raise ValueError("original export does not cover current36 attempts")
        runtime = _json(pilot / "runtime.json")
        if image_identity(verifier_image) != verifier_image or verifier_image != runtime["verifier_image"]:
            raise ValueError("regrade uses the original pinned verifier base image")
        source = Path(verified["local"]["frozen_source"])
        manifest = _json(pilot / "manifest.json")
        registered_tasks = {row["task_id"]: row for row in manifest["tasks"]}
        destination.mkdir(parents=True, mode=0o700)
        local = {"pilot": str(pilot), "frozen_source": str(source)}
        write_once(destination / "local-sources.json", local)
        registrations = []
        for row in schedule:
            trial = _name(row["trial_id"])
            original = store.root / "trials" / trial / "attempt-1"
            store.verify_attempt(trial, 1)
            task = suite.load_task(row["task_id"])
            task_sha = source_identity(ROOT / "tasks/development" / row["task_id"])
            if task_sha != registered_tasks[row["task_id"]]["task_sha256"]:
                raise ValueError("development task contract differs from original pilot")
            request = {
                "frozen_source": str(source),
                "frozen_source_sha256": verified["info"]["source_lock"]["campaign_sha256"],
                "task_id": row["task_id"],
                "arm": row["arm"],
                **runtime,
            }
            initial = builder(request)
            private_context = _json(pilot / "private-harbor" / trial / "attempt-1/task/tests/grading.json")
            stopped_manifest = _json(original / "agent/node-manifest.json")
            snapshot = _json(original / "agent/snapshot.json")
            unsafe = _snapshot(snapshot)
            context = {
                "task_id": row["task_id"],
                "split": "development",
                "initial_manifest": initial,
                "stopped_manifest": stopped_manifest,
                "observations": _observation(_json(original / "visible.json"), task),
                "unsafe_snapshot": unsafe,
            }
            if private_context != {key: value for key, value in context.items() if key != "split"}:
                raise ValueError("retained grading context differs from reconstructed frozen inputs")
            if not unsafe:
                with tempfile.TemporaryDirectory(prefix="evalopt-regrade-nodes-") as temporary:
                    decoded = Path(temporary) / "snapshot"
                    _decode(snapshot, decoded)
                    if suite.file_manifest(decoded) != stopped_manifest:
                        raise ValueError("stopped node manifest differs from preserved snapshot")
            target = destination / "inputs" / trial
            hashes = {name: _copy(original / name, target / name) for name in INPUT_FILES}
            write_once(target / "context.json", context)
            registrations.append(
                {
                    "trial_id": trial,
                    "task_id": row["task_id"],
                    "arm": row["arm"],
                    "attempt": 1,
                    "status": _json(original / "finish.json")["status"],
                    "task_sha256": task_sha,
                    "original_files": hashes,
                    "context_sha256": digest(context),
                }
            )
        grader_files = {
            name: _copy(path, destination / "grader" / name) for name, path in _grader_files().items()
        }
        readiness_sources = _json(pilot / "readiness-sources.json")
        original_controls = _json(Path(readiness_sources["controls"]) / "results.json")
        registration = {
            "schema_version": "evalopt.pilot-regrade-registration.v1",
            "pilot_registration_sha256": verified["info"]["registration_sha256"],
            "schedule_sha256": verified["info"]["schedule_sha256"],
            "pilot_export_id": pilot_export_id,
            "accounting_amendment_sha256": amendment_sha256,
            "source_pins": {
                **source_pins(),
                "frozen_benchmark_sha256": verified["info"]["source_lock"]["campaign_sha256"],
            },
            "grading": {
                "pilot": {
                    "suite": original_controls["tasks_sha256"],
                    "verifier": original_controls["verify_sha256"],
                },
                "current": grading_identity(),
            },
            "runtime": {
                "controller": require_controller(),
                "verifier_image": verifier_image,
                "cpus": 1,
                "memory_mb": 2048,
                "network": "none",
                "seconds": 120,
            },
            "local_sources_sha256": digest(local),
            "schedule": schedule,
            "attempts": registrations,
            "grader_files": grader_files,
        }
        # Verify again before committing the regrade registration; originals were never modified.
        after = amended_pilot.verify(pilot, amendment_sha256)
        if verified["info"] != after["info"]:
            raise ValueError("pilot changed while preparing regrade")
        write_once(destination / "registration.json", registration)
        verify_registration(destination / "registration.json", digest(registration))
        canonical = pilot / "qa-regrades" / digest(registration)
        if canonical.exists():
            raise ValueError("regrade registration already exists; do not replace it")
        shutil.copytree(destination, canonical)
        return {
            "registration_sha256": digest(registration),
            "registration_path": str(canonical / "registration.json"),
            "scheduled_trials": 36,
            "agent_trials": 0,
        }


def verify_registration(registration_path, registration_sha256, *, current_grading=None):
    require_controller()
    registration_path = _safe(registration_path)
    root = registration_path.parent
    registration = _json(registration_path)
    exact(
        registration,
        {
            "schema_version",
            "pilot_registration_sha256",
            "schedule_sha256",
            "pilot_export_id",
            "accounting_amendment_sha256",
            "source_pins",
            "grading",
            "runtime",
            "local_sources_sha256",
            "schedule",
            "attempts",
            "grader_files",
        },
        "regrade registration",
    )
    if (
        not is_digest(registration_sha256)
        or digest(registration) != registration_sha256
        or registration["schema_version"] != "evalopt.pilot-regrade-registration.v1"
    ):
        raise ValueError("regrade registration identity changed")
    for key in (
        "pilot_registration_sha256",
        "schedule_sha256",
        "pilot_export_id",
        "accounting_amendment_sha256",
        "local_sources_sha256",
    ):
        if not is_digest(registration[key]):
            raise ValueError("unresolved regrade identity")
    expected_sources = source_pins()
    if (
        set(registration["source_pins"]) != {*expected_sources, "frozen_benchmark_sha256"}
        or any(registration["source_pins"].get(key) != value for key, value in expected_sources.items())
        or not is_digest(registration["source_pins"]["frozen_benchmark_sha256"])
    ):
        raise ValueError("regrade controller source changed")
    grading = exact(registration["grading"], {"pilot", "current"}, "regrade grader identities")
    for value in grading.values():
        exact(value, {"suite", "verifier"}, "grader identity")
        if any(not is_digest(item) for item in value.values()):
            raise ValueError("unresolved grader identity")
    if grading["current"] != grading_identity() or (
        current_grading is not None and grading["current"] != current_grading
    ):
        raise ValueError("current grading differs from regrade registration")
    runtime = exact(
        registration["runtime"],
        {"controller", "verifier_image", "cpus", "memory_mb", "network", "seconds"},
        "regrade runtime",
    )
    if (
        digest({key: value for key, value in runtime.items() if key != "verifier_image"})
        != digest(
            {
                "controller": require_controller(),
                "cpus": 1,
                "memory_mb": 2048,
                "network": "none",
                "seconds": 120,
            }
        )
        or not isinstance(runtime["verifier_image"], str)
        or not runtime["verifier_image"].startswith("sha256:")
        or not is_digest(runtime["verifier_image"][7:])
    ):
        raise ValueError("regrade execution conditions changed")
    schedule = registration["schedule"]
    if (
        not isinstance(schedule, list)
        or len(schedule) != 36
        or digest(schedule) != registration["schedule_sha256"]
    ):
        raise ValueError("regrade requires frozen36 schedule")
    expected_tasks = []
    for task_id in suite.task_ids():
        task = suite.load_task(task_id)
        expected_tasks.append(
            {
                "task_id": task_id,
                "stage": "pilot",
                "category": task["category"].replace("-", "_"),
                "cluster_id": task["source_family"],
                "agent_seconds": 600,
                "task_sha256": source_identity(suite.task_path(task)),
                "grader_sha256": grading["pilot"]["suite"],
            }
        )
    if len(expected_tasks) != 12 or digest(schedule) != digest(build_schedule(expected_tasks, "pilot")):
        raise ValueError("regrade schedule differs from seeded12-task three-arm pilot")
    scheduled = {row["trial_id"]: row for row in schedule}
    if len(scheduled) != 36 or any(row["stage"] != "pilot" for row in schedule):
        raise ValueError("duplicate or non-pilot regrade trial")
    if not isinstance(registration["attempts"], list) or [
        row["trial_id"] for row in registration["attempts"]
    ] != [row["trial_id"] for row in schedule]:
        raise ValueError("regrade attempt roster or ordering changed")
    expected_grader = {name: bytes_digest(_read(path)) for name, path in _grader_files().items()}
    if registration["grader_files"] != expected_grader:
        raise ValueError("registered grader assets changed")
    for name, sha in expected_grader.items():
        if bytes_digest(_read(root / "grader" / name)) != sha:
            raise ValueError("retained grader asset changed")
    from lib.policies import replay_policies

    for row in registration["attempts"]:
        exact(
            row,
            {
                "trial_id",
                "task_id",
                "arm",
                "attempt",
                "status",
                "task_sha256",
                "original_files",
                "context_sha256",
            },
            "regrade attempt",
        )
        trial = _name(row["trial_id"])
        original = root / "inputs" / trial
        scheduled_row = scheduled[trial]
        if (
            row["task_id"] != scheduled_row["task_id"]
            or row["arm"] != scheduled_row["arm"]
            or type(row["attempt"]) is not int
            or row["attempt"] != 1
            or row["status"] not in TERMINAL
            or row["task_sha256"] != scheduled_row["task_sha256"]
            or row["task_sha256"] != source_identity(ROOT / "tasks/development" / row["task_id"])
        ):
            raise ValueError("regrade attempt changes the original task or status")
        if set(row["original_files"]) != set(INPUT_FILES):
            raise ValueError("original attempt artifacts incomplete")
        for name, sha in row["original_files"].items():
            if bytes_digest(_read(original / name)) != sha:
                raise ValueError("original retained regrade input changed")
        manifest = _json(original / "manifest.json")
        if {item["path"] for item in manifest["artifacts"]} != set(INPUT_FILES) - {"manifest.json"}:
            raise ValueError("original attempt manifest roster differs")
        CampaignStore._verify_artifacts(original, manifest["artifacts"])
        for name in ("stopped.json", "controller-artifacts.json"):
            value = _json(original / name)
            CampaignStore._verify_artifacts(original, value["artifacts"] if name == "stopped.json" else value)
        stopped, visible, policies = [
            _json(original / name) for name in ("stopped.json", "visible.json", "policies.json")
        ]
        grade = _json(original / "grade.json")
        finish = _json(original / "finish.json")
        finalization = _json(original / "finalize.json")
        if (
            finalization.get("schema_version") != "evalopt.workflow-finalize.v1"
            or finalization.get("trial_id") != trial
            or finalization.get("attempt") != 1
            or finalization.get("schedule_sha256") != registration["schedule_sha256"]
            or digest(finalization.get("finish")) != digest(finish)
        ):
            raise ValueError("original finalization no longer binds the preserved finish")
        CampaignStore._verify_artifacts(original, finalization["artifacts"])
        if (
            stopped["trial_id"] != trial
            or stopped["attempt"] != 1
            or visible["trial_id"] != trial
            or visible["stopped_sha256"] != digest(stopped)
            or grade["trial_id"] != trial
            or grade["stopped_sha256"] != digest(stopped)
            or grade["policies_sha256"] != digest(policies)
            or not replay_policies(visible, policies)
            or finish["status"] != row["status"]
            or finish["trial_id"] != trial
            or finish["attempt"] != 1
        ):
            raise ValueError("original outcome/policy linkage changed")
        context = _json(original / "context.json")
        exact(
            context,
            {"task_id", "split", "initial_manifest", "stopped_manifest", "observations", "unsafe_snapshot"},
            "regrade context",
        )
        task = suite.load_task(row["task_id"])
        if (
            digest(context) != row["context_sha256"]
            or context["task_id"] != row["task_id"]
            or context["split"] != "development"
            or type(context["unsafe_snapshot"]) is not bool
            or context["unsafe_snapshot"] is not _snapshot(_json(original / "agent/snapshot.json"))
            or context["stopped_manifest"] != _json(original / "agent/node-manifest.json")
            or context["observations"] != _observation(visible, task)
        ):
            raise ValueError("regrade context differs from frozen controller evidence")
        for key in ("initial_manifest", "stopped_manifest"):
            if not isinstance(context[key], dict) or any(
                not isinstance(k, str) or not isinstance(v, str) for k, v in context[key].items()
            ):
                raise ValueError("invalid regrade node manifest")
        changed = {
            name
            for name in context["initial_manifest"].keys() | context["stopped_manifest"].keys()
            if context["initial_manifest"].get(name) != context["stopped_manifest"].get(name)
        }
        if (
            sorted(changed - set(task["allowed_changes"]) - {"response.json"})
            != visible["boundary_violations"]
        ):
            raise ValueError("reconstructed baseline contradicts original visible boundaries")
    return registration


def _effective(grade, status):
    value = {key: item for key, item in grade.items() if key != "reproduction_inputs"}
    value["boundary_violation"] = not value["boundaries_preserved"]
    if status == "timeout":
        value["valid_completion"] = False
    return value


def _outcome_metrics(grade, status):
    value = {key: grade[key] for key in METRICS}
    if status in {"agent_failure", "timeout", "budget_exhausted"}:
        value["valid_completion"] = False
    return value


def _replay(root, row, grade):
    original = root / "inputs" / row["trial_id"]
    context = _json(original / "context.json")
    inputs = exact(grade.get("reproduction_inputs"), REPRO_KEYS, "regrade reproduction inputs")
    if (
        inputs["schema_version"] != "evalopt.grade-reproduction.v1"
        or any(inputs[key] != context[key] for key in context)
        or type(inputs["hidden_test_passed"]) is not bool
        or not isinstance(inputs["hidden_case_records"], list)
    ):
        raise ValueError("new grader inputs differ from registered original context")
    node = _json(original / "agent/snapshot.json")["nodes"].get("response.json")
    response = None
    if not context["unsafe_snapshot"] and node is not None and node["type"] == "file":
        try:
            # The pinned verifier reads UTF-8 text before parsing; parsing bytes
            # would additionally accept BOM/UTF-16 encodings that it rejects.
            response = strict_json(base64.b64decode(node["data"], validate=True).decode("utf-8"))
        except (ValueError, TypeError):
            pass
    if digest(response) != digest(inputs["response"]):
        raise ValueError("new grader response differs from stopped output under current parser")
    records, consumed = inputs["hidden_case_records"], 0

    def invoke(request):
        nonlocal consumed
        if consumed >= len(records):
            raise RuntimeError("regrade hidden reply missing")
        record = records[consumed]
        consumed += 1
        if not isinstance(record, dict) or digest(record.get("request")) != digest(request):
            raise RuntimeError("regrade hidden request or order changed")
        if set(record) == {"request", "error"} and record["error"] == "candidate_invocation_failed":
            raise ValueError("recorded isolated candidate invocation failed")
        if set(record) != {"request", "actual"}:
            raise RuntimeError("invalid hidden regrade reply")
        return record["actual"]

    task = suite.load_task(row["task_id"])
    hidden = False if context["unsafe_snapshot"] else suite.evaluate_cases(task, invoke)
    if consumed != len(records) or hidden is not inputs["hidden_test_passed"]:
        raise ValueError("regrade hidden reply coverage differs")
    replayed = suite.grade_snapshot(
        task,
        context["initial_manifest"],
        context["stopped_manifest"],
        response,
        context["observations"],
        hidden_test_passed=hidden,
    )
    if digest(replayed) != digest(
        {key: value for key, value in grade.items() if key != "reproduction_inputs"}
    ):
        raise ValueError("new grade cannot replay from supplied isolated replies")
    return replayed


def _result(root, registration, row, grade, *, execution):
    _replay(root, row, grade)
    old = _json(root / "inputs" / row["trial_id"] / "grade.json")["grade"]
    old_effective, new_effective = _effective(old, row["status"]), _effective(grade, row["status"])
    return {
        "schema_version": "evalopt.pilot-regrade-result.v1",
        "registration_sha256": digest(registration),
        "trial_id": row["trial_id"],
        "attempt": 1,
        "original_status": row["status"],
        "original_grade_sha256": row["original_files"]["grade.json"],
        "original_policies_sha256": row["original_files"]["policies.json"],
        "context_sha256": row["context_sha256"],
        "execution": execution,
        "current_verifier_grade": grade,
        "original_effective_grade": old_effective,
        "current_effective_grade": new_effective,
        "original_outcome_metrics": _outcome_metrics(old_effective, row["status"]),
        "current_outcome_metrics": _outcome_metrics(new_effective, row["status"]),
        "changed_fields": {
            key: {"original": old_effective.get(key), "regraded": new_effective.get(key)}
            for key in sorted(set(old_effective) | set(new_effective))
            if digest(old_effective.get(key)) != digest(new_effective.get(key))
        },
    }


def _execute_one(root, registration, row):
    work = root / "private-execution" / row["trial_id"]
    work.mkdir(parents=True, exist_ok=False)
    tests, output = work / "tests", work / "output"
    shutil.copytree(root / "grader", tests)
    output.mkdir()
    context = _json(root / "inputs" / row["trial_id"] / "context.json")
    write_once(tests / "grading.json", context)
    snapshot = _json(root / "inputs" / row["trial_id"] / "agent/snapshot.json")
    if context["unsafe_snapshot"]:
        (tests / "snapshot").mkdir()
    else:
        _decode(snapshot, tests / "snapshot")
        if suite.file_manifest(tests / "snapshot") != context["stopped_manifest"]:
            raise ValueError("decoded regrade snapshot metadata changed")
    container = "evalopt-regrade-" + uuid.uuid4().hex[:12]
    command = [
        "docker",
        "run",
        "--pull",
        "never",
        "--rm",
        "--name",
        container,
        "--network",
        "none",
        "--cpus",
        "1",
        "--memory",
        "2g",
        "--security-opt",
        "no-new-privileges",
        "--mount",
        f"type=bind,src={tests},dst=/tests,readonly",
        "--mount",
        f"type=bind,src={output},dst=/logs/verifier",
        registration["runtime"]["verifier_image"],
        "sh",
        "-c",
        "cd /tests && python3 -B /tests/verify.py",
    ]
    try:
        result = subprocess.run(command, capture_output=True, timeout=120, check=False)
        (work / "stdout.bin").write_bytes(result.stdout)
        (work / "stderr.bin").write_bytes(result.stderr)
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30, check=False)
    if result.returncode != 0 or not (output / "grade.json").is_file():
        raise ValueError("isolated regrade failed; retained private execution requires inspection")
    return _json(output / "grade.json"), {
        "mode": "isolated_docker_chroot",
        "exit_code": result.returncode,
        "verifier_image": registration["runtime"]["verifier_image"],
        "stdout_sha256": bytes_digest(result.stdout),
        "stderr_sha256": bytes_digest(result.stderr),
        "agent_trials": 0,
    }


def execute(directory, *, registration_sha256, runner=None):
    root = _safe(directory)
    registration = verify_registration(root / "registration.json", registration_sha256)
    local = _json(root / "local-sources.json")
    if digest(local) != registration["local_sources_sha256"]:
        raise ValueError("private regrade source binding changed")
    pilot = _safe(local["pilot"])
    run = _execute_one if runner is None else runner
    with amended_pilot._lock(pilot):
        verified = amended_pilot.verify(pilot, registration["accounting_amendment_sha256"])
        if verified["info"]["registration_sha256"] != registration["pilot_registration_sha256"]:
            raise ValueError("original pilot registration changed")
        if (
            image_identity(registration["runtime"]["verifier_image"])
            != registration["runtime"]["verifier_image"]
        ):
            raise ValueError("regrade image drift")
        for row in registration["attempts"]:
            verify_registration(root / "registration.json", registration_sha256)
            for name, sha in row["original_files"].items():
                if (
                    bytes_digest(_read(pilot / "evidence/trials" / row["trial_id"] / "attempt-1" / name))
                    != sha
                ):
                    raise ValueError("original pilot attempt changed before regrade")
            path = root / "results" / (row["trial_id"] + ".json")
            if path.exists():
                recorded = _json(path)
                if recorded != _result(
                    root,
                    registration,
                    row,
                    recorded["current_verifier_grade"],
                    execution=recorded["execution"],
                ):
                    raise ValueError("existing regrade result changed")
                continue
            grade, execution = run(root, registration, row)
            write_once(path, _result(root, registration, row, grade, execution=execution))
        evidence = _evidence(root, registration)
        if (root / "evidence.json").exists():
            if digest(_json(root / "evidence.json")) != digest(evidence):
                raise ValueError("retained regrade evidence changed")
        else:
            write_once(root / "evidence.json", evidence)
        return verify_evidence(
            root / "registration.json",
            registration_sha256=registration_sha256,
            evidence_sha256=digest(evidence),
        )


def _evidence(root, registration):
    records, changed, metrics = {}, 0, dict.fromkeys(METRICS, 0)
    for row in registration["attempts"]:
        result = _json(root / "results" / (row["trial_id"] + ".json"))
        execution = exact(
            result.get("execution"),
            {"mode", "exit_code", "verifier_image", "stdout_sha256", "stderr_sha256", "agent_trials"},
            "regrade execution receipt",
        )
        if (
            execution["mode"] != "isolated_docker_chroot"
            or type(execution["exit_code"]) is not int
            or execution["exit_code"] != 0
            or execution["agent_trials"] != 0
            or type(execution["agent_trials"]) is not int
            or execution["verifier_image"] != registration["runtime"]["verifier_image"]
            or not all(is_digest(execution[key]) for key in ("stdout_sha256", "stderr_sha256"))
        ):
            raise ValueError("regrade execution receipt lacks pinned isolated success")
        expected = _result(root, registration, row, result["current_verifier_grade"], execution=execution)
        if digest(result) != digest(expected):
            raise ValueError("regrade outcome/status/delta differs from reproduced grade")
        records[row["trial_id"]] = digest(result)
        changed += bool(result["changed_fields"])
        for key in METRICS:
            metrics[key] += (
                result["original_outcome_metrics"][key] is not result["current_outcome_metrics"][key]
            )
    if {path.stem for path in (root / "results").glob("*.json")} != set(records):
        raise ValueError("unregistered regrade result")
    return {
        "schema_version": "evalopt.pilot-regrade-evidence.v1",
        "registration_sha256": digest(registration),
        "scheduled_trials": 36,
        "regraded_attempts": len(records),
        "records": records,
        "changed_trial_count": changed,
        "metric_changes": metrics,
        "original_policy_decisions_changed": False,
        "agent_trials": 0,
        "scope": SCOPE,
    }


def verify_evidence(registration_path, *, registration_sha256, evidence_sha256, current_grading=None):
    registration_path = _safe(registration_path)
    registration = verify_registration(
        registration_path, registration_sha256, current_grading=current_grading
    )
    evidence = _json(registration_path.parent / "evidence.json")
    expected = _evidence(registration_path.parent, registration)
    if (
        not is_digest(evidence_sha256)
        or digest(evidence) != evidence_sha256
        or digest(evidence) != digest(expected)
    ):
        raise ValueError("regrade evidence identity or complete coverage changed")
    return {
        "schema_version": "evalopt.pilot-regrade-receipt.v1",
        "registration_sha256": registration_sha256,
        "evidence_sha256": evidence_sha256,
        "pilot_registration_sha256": registration["pilot_registration_sha256"],
        "schedule_sha256": registration["schedule_sha256"],
        "pilot_export_id": registration["pilot_export_id"],
        "accounting_amendment_sha256": registration["accounting_amendment_sha256"],
        "scheduled_trials": 36,
        "regraded_attempts": 36,
        "grading": registration["grading"],
        "source_pins": registration["source_pins"],
        "verifier_image": registration["runtime"]["verifier_image"],
        "changed_trial_count": evidence["changed_trial_count"],
        "metric_changes": evidence["metric_changes"],
        "original_policy_decisions_changed": False,
        "agent_trials": 0,
        "scope": SCOPE,
    }


def public_payloads(registration_path):
    """Exact public whitelist; excludes local sources and raw Docker diagnostics."""
    root = _safe(registration_path).parent
    registration = _json(root / "registration.json")
    names = {"registration.json", "evidence.json"}
    names.update("grader/" + name for name in registration["grader_files"])
    for row in registration["attempts"]:
        trial = _name(row["trial_id"])
        names.update(f"inputs/{trial}/{name}" for name in (*INPUT_FILES, "context.json"))
        names.add(f"results/{trial}.json")
    return {name: _read(root / name) for name in sorted(names)}


def export_evidence(
    registration_path, destination, *, registration_sha256, evidence_sha256, current_grading=None
):
    receipt = verify_evidence(
        registration_path,
        registration_sha256=registration_sha256,
        evidence_sha256=evidence_sha256,
        current_grading=current_grading,
    )
    source, destination = _safe(registration_path).parent, _safe(destination)
    if destination.exists() or destination.is_relative_to(source) or source.is_relative_to(destination):
        raise ValueError("regrade export requires a fresh separate destination")
    from publish_bundle import scan_public_file

    payloads = public_payloads(registration_path)
    for name, raw in payloads.items():
        scan_public_file(name, raw)
    for name, raw in payloads.items():
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        target.chmod(stat.S_IMODE((source / name).stat().st_mode))
    if (
        verify_evidence(
            destination / "registration.json",
            registration_sha256=registration_sha256,
            evidence_sha256=evidence_sha256,
            current_grading=current_grading,
        )
        != receipt
    ):
        raise ValueError("public regrade differs from verified source")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    for key in ("pilot", "destination"):
        prepare_parser.add_argument("--" + key, type=Path, required=True)
    for key in ("amendment-sha256", "pilot-export-id", "verifier-image"):
        prepare_parser.add_argument("--" + key, required=True)
    execute_parser = commands.add_parser("execute")
    execute_parser.add_argument("directory", type=Path)
    execute_parser.add_argument("--registration-sha256", required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("registration_path", type=Path)
    verify_parser.add_argument("--registration-sha256", required=True)
    verify_parser.add_argument("--evidence-sha256", required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    result = {"prepare": prepare, "execute": execute, "verify": verify_evidence}[command](**args)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
