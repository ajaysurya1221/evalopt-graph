#!/usr/bin/env python3
"""Prepare, run and reproduce the public development campaign through Harbor."""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import importlib.metadata
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from lib.analysis import METRICS, analyze_workflows, summarize_kernel
from lib.common import bytes_digest, canonical_bytes, digest, is_digest, read_json, write_once
from lib.manifest import build_schedule, validate_manifest
from lib.store import CampaignStore
from runtime.controller import require_controller
from runtime.harbor_campaign import (
    REPO,
    ROOT,
    execute_trial,
    image_identity,
    run,
    source_identity,
    subscription_environment,
)
from runtime.readiness import verify_readiness
from runtime.subscription import read_subscription_permission
from tasks.suite import load_task, task_ids, task_path

UPSTREAM_COMMIT = "b0618bc436ad893b3c5e84e55fba86586d34a404"
KERNEL_COMMIT = "fc3045dbda29c1d274747329ceb6724a783b0df7"
REGISTRATION_FILES = (
    "manifest.json",
    "runtime.json",
    "readiness.json",
    "readiness-sources.json",
    "source-lock.json",
    "evidence/schedule.json",
)


def _now():
    return datetime.now(timezone.utc).isoformat()


def _source_lock(upstream):
    return {
        "campaign_sha256": source_identity(ROOT),
        "skill_sha256": source_identity(REPO / "skills" / "eval-opt"),
        "upstream_sha256": source_identity(upstream / "skills"),
        "upstream_loader_sha256": bytes_digest((upstream / ".claude-plugin/plugin.json").read_bytes()),
        "kernel_source_sha256": source_identity(REPO / "src/evalopt_graph"),
    }


def _registration_identity(destination):
    return {name: bytes_digest((destination / name).read_bytes()) for name in REGISTRATION_FILES}


def _verify_campaign(destination, upstream):
    """Check actual pinned inputs before every dispatch; manifest assertions alone do not suffice."""
    require_controller()
    if importlib.metadata.version("harbor") != "0.24.0":
        raise ValueError("Harbor version differs from protocol")
    if read_json(destination / "registration-lock.json") != _registration_identity(destination):
        raise ValueError("campaign registration files changed")
    lock = read_json(destination / "source-lock.json")
    if lock != _source_lock(upstream):
        raise ValueError(
            "campaign inputs changed; preserve this campaign and prepare a new development version"
        )
    if run(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip() != UPSTREAM_COMMIT:
        raise ValueError("upstream commit differs from registration")
    if run(
        ["git", "-C", str(REPO), "diff", "--name-only", KERNEL_COMMIT, "--", "src/evalopt_graph"]
    ).stdout.strip():
        raise ValueError("stable kernel differs from its frozen source commit")
    manifest = validate_manifest(read_json(destination / "manifest.json"))
    if any(
        not is_digest(value, 40 if name.endswith("_commit") else 64)
        for name, value in manifest["pins"].items()
    ):
        raise ValueError("live campaign contains unresolved source pins")
    runtime = read_json(destination / "runtime.json")
    if set(runtime) != {"agent_image", "verifier_image"} or any(
        image_identity(value) != value for value in runtime.values()
    ):
        raise ValueError("runtime image does not match frozen digest")
    expected_pins = {
        "skill_sha256": lock["skill_sha256"],
        "grader_sha256": source_identity(ROOT / "tasks"),
        "policy_sha256": source_identity(ROOT / "lib"),
        "analysis_sha256": source_identity(ROOT / "lib"),
        "environment_sha256": digest(runtime),
    }
    if any(manifest["pins"][name] != value for name, value in expected_pins.items()):
        raise ValueError("manifest source pins do not match executable inputs")
    if len(manifest["tasks"]) != 12 or {task["task_id"] for task in manifest["tasks"]} != set(task_ids()):
        raise ValueError("pilot task set differs from reviewed development tasks")
    for task in manifest["tasks"]:
        if (
            task["stage"] != "pilot"
            or task["task_sha256"] != source_identity(task_path(load_task(task["task_id"])))
            or task["grader_sha256"] != expected_pins["grader_sha256"]
        ):
            raise ValueError("trial task or grader identity differs from frozen inputs")
    sources = read_json(destination / "readiness-sources.json")
    if verify_readiness(
        Path(sources["preflight"]), Path(sources["controls"]), runtime, upstream
    ) != read_json(destination / "readiness.json"):
        raise ValueError("readiness evidence changed")
    schedule = build_schedule(manifest["tasks"], "pilot")
    store = CampaignStore(destination / "evidence", schedule)
    return manifest, runtime, schedule, store


@contextmanager
def _scheduler_lock(destination):
    """One controller process per campaign; each dispatch uses a clean attempt directory."""
    with (destination / ".scheduler.lock").open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another controller is already running this campaign") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _new_run(destination, *, retry_infrastructure, resume_quota, recover_interrupted):
    runs = destination / "runs"
    runs.mkdir(exist_ok=True)
    index = 1
    while (runs / f"run-{index:04d}").exists():
        index += 1
    path = runs / f"run-{index:04d}"
    path.mkdir()
    write_once(
        path / "start.json",
        {
            "schema_version": "evalopt.scheduler-run.v1",
            "started_at": _now(),
            "registration_sha256": digest(read_json(destination / "registration-lock.json")),
            "retry_infrastructure": retry_infrastructure,
            "resume_quota": resume_quota,
            "recover_interrupted": recover_interrupted,
        },
    )
    return path


def _finish_record(store, state):
    if not state["attempts"]:
        return None
    path = store.root / "trials" / state["trial_id"] / f"attempt-{state['attempts']}" / "finish.json"
    return read_json(path) if path.is_file() else None


def _dispatch_queue(store, schedule, *, retry_infrastructure, resume_quota, recover_interrupted):
    states = store.statuses()
    for state in states:
        path = store.root / "trials" / state["trial_id"] / f"attempt-{state['attempts']}"
        incomplete_finalization = (path / "finalize.json").exists() and not (path / "manifest.json").exists()
        if state["status"] == "running_or_interrupted" or incomplete_finalization:
            if not recover_interrupted:
                return [], "interrupted_controller_requires_recovery", state["trial_id"]
            try:
                store.recover_attempt(state["trial_id"], state["attempts"])
            except ValueError:
                return [], "interrupted_agent_requires_classification", state["trial_id"]
    states = store.statuses()
    selected = set()
    for state in states:
        finish = _finish_record(store, state)
        if finish:
            usage = finish.get("usage") or {}
            if usage.get("runtime_valid") is False:
                return [], "runtime_identity_requires_remediation", state["trial_id"]
            if finish.get("error_code") == "subscription_exhausted":
                if not resume_quota:
                    return [], "subscription_exhausted", state["trial_id"]
                if state["attempts"] == 1:
                    selected.add(state["trial_id"])
                continue
            if finish["status"] == "infra_failure":
                if state["attempts"] == 1:
                    if not retry_infrastructure:
                        return [], "infrastructure_retry_requires_explicit_resume", state["trial_id"]
                    selected.add(state["trial_id"])
                continue
            if usage.get("child_usage_complete") is not True:
                return [], "usage_accounting_requires_remediation", state["trial_id"]
        elif state["status"] == "pending":
            selected.add(state["trial_id"])
    return [row for row in schedule if row["trial_id"] in selected], None, None


def prepare(destination, upstream, image, verifier, preflight, controls):
    require_controller()
    if destination.exists():
        raise ValueError("prepare requires a fresh campaign directory")
    upstream_sha = run(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip()
    if upstream_sha != "b0618bc436ad893b3c5e84e55fba86586d34a404":
        raise ValueError("upstream source does not match protocol")
    tasks = []
    for task_id in task_ids():
        task = load_task(task_id)
        tasks.append(
            {
                "task_id": task_id,
                "stage": "pilot",
                "category": task["category"].replace("-", "_"),
                "cluster_id": task["source_family"],
                "task_sha256": source_identity(task_path(task)),
                "grader_sha256": source_identity(ROOT / "tasks"),
                "agent_seconds": 600,
            }
        )
    if len(tasks) != 12:
        raise ValueError("pilot requires twelve reviewed tasks")
    runtime = {"agent_image": image_identity(image), "verifier_image": image_identity(verifier)}
    readiness = verify_readiness(preflight, controls, runtime, upstream)
    manifest = {
        "schema_version": "evalopt.skill-workflows.v1",
        "study_id": "skill-workflows-v1-pilot",
        "seed": 20261008,
        "pins": {
            "upstream_commit": upstream_sha,
            "terminal_bench_commit": "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c",
            "kernel_commit": "fc3045dbda29c1d274747329ceb6724a783b0df7",
            "skill_sha256": source_identity(REPO / "skills" / "eval-opt"),
            "grader_sha256": source_identity(ROOT / "tasks"),
            "policy_sha256": source_identity(ROOT / "lib"),
            "analysis_sha256": source_identity(ROOT / "lib"),
            "environment_sha256": digest(runtime),
        },
        "runtime": {
            "harbor_version": "0.24.0",
            "codex_version": "0.154.0",
            "model": "gpt-6-astra",
            "reasoning_effort": "ultra",
            "auth_route": "chatgpt_subscription",
        },
        "limits": {
            "primary_seconds": 600,
            "max_concurrent_trials": 2,
            "max_children": 2,
            "delegation_depth": 1,
            "infrastructure_retries": 1,
        },
        "tasks": tasks,
    }
    validate_manifest(manifest)
    schedule = build_schedule(tasks, "pilot")
    destination.mkdir(parents=True)
    destination.chmod(0o700)
    write_once(destination / "manifest.json", manifest)
    write_once(destination / "runtime.json", runtime)
    write_once(destination / "readiness.json", readiness)
    write_once(
        destination / "readiness-sources.json", {"preflight": str(preflight), "controls": str(controls)}
    )
    write_once(destination / "source-lock.json", _source_lock(upstream))
    CampaignStore(destination / "evidence", schedule)
    write_once(destination / "registration-lock.json", _registration_identity(destination))
    return {
        "manifest_sha256": digest(manifest),
        "scheduled_trials": len(schedule),
        "status": "prepared_development_only",
        "runtime": runtime,
    }


async def run_pilot(
    destination,
    upstream,
    limit=None,
    *,
    retry_infrastructure=False,
    resume_quota=False,
    recover_interrupted=False,
    verifier=None,
    executor=None,
    reporter=None,
):
    verify = _verify_campaign if verifier is None else verifier
    execute = execute_trial if executor is None else executor
    build_report = report if reporter is None else reporter
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit must be positive")
    with _scheduler_lock(destination):
        _, runtime, schedule, store = verify(destination, upstream)
        receipt = _new_run(
            destination,
            retry_infrastructure=retry_infrastructure,
            resume_quota=resume_quota,
            recover_interrupted=recover_interrupted,
        )
        dispatched = []
        reason = None
        blocked_trial = None
        try:
            subscription_environment()
            queue, reason, blocked_trial = _dispatch_queue(
                store,
                schedule,
                retry_infrastructure=retry_infrastructure,
                resume_quota=resume_quota,
                recover_interrupted=recover_interrupted,
            )
            if limit is not None:
                queue = queue[:limit]
            # Sequential dispatch is within the registered maximum of two trials.
            # A resumed invocation authorizes only pre-existing classified retries;
            # any fresh infrastructure or quota failure pauses again immediately.
            for row in queue:
                verify(destination, upstream)
                try:
                    permission = await asyncio.to_thread(read_subscription_permission)
                except (OSError, ValueError):
                    permission = {}
                valid_schema = (
                    isinstance(permission, dict)
                    and permission.get("schema_version") == "evalopt.subscription-permission.v1"
                )
                allowed = (
                    valid_schema
                    and permission.get("ordinary_usage_allowed") is True
                    and permission.get("state") == "allowed"
                )
                exhausted = (
                    valid_schema
                    and permission.get("ordinary_usage_allowed") is False
                    and permission.get("state") == "exhausted"
                )
                sanitized_permission = {
                    "schema_version": "evalopt.subscription-permission.v1",
                    "ordinary_usage_allowed": bool(allowed),
                    "state": "allowed" if allowed else ("exhausted" if exhausted else "unavailable"),
                }
                write_once(
                    receipt / f"permission-{len(dispatched) + 1:04d}.json",
                    {
                        "schema_version": "evalopt.scheduler-permission.v1",
                        "trial_id": row["trial_id"],
                        "checked_at": _now(),
                        "permission": sanitized_permission,
                    },
                )
                if not allowed:
                    reason = (
                        "subscription_exhausted_before_dispatch"
                        if exhausted
                        else "subscription_permission_unavailable"
                    )
                    blocked_trial = row["trial_id"]
                    break
                print(json.dumps({"event": "trial_start", "trial_id": row["trial_id"]}), flush=True)
                result = await execute(
                    row,
                    store,
                    destination / "private-harbor",
                    upstream,
                    runtime["agent_image"],
                    runtime["verifier_image"],
                )
                dispatched.append(row["trial_id"])
                state = next(item for item in store.statuses() if item["trial_id"] == row["trial_id"])
                finish = _finish_record(store, state)
                if finish is None or result["status"] != finish["status"]:
                    raise ValueError("runtime result does not match retained terminal attempt")
                print(
                    json.dumps(
                        {
                            "event": "trial_end",
                            "trial_id": row["trial_id"],
                            "status": result["status"],
                            "valid_completion": result.get("valid_completion"),
                        }
                    ),
                    flush=True,
                )
                usage = finish.get("usage") or {}
                if usage.get("runtime_valid") is False:
                    reason = "runtime_identity_requires_remediation"
                elif finish.get("error_code") == "subscription_exhausted":
                    reason = "subscription_exhausted"
                elif finish["status"] == "infra_failure":
                    reason = "infrastructure_failure_requires_inspection"
                elif usage.get("child_usage_complete") is not True:
                    reason = "usage_accounting_requires_remediation"
                if reason:
                    blocked_trial = row["trial_id"]
                    break
                verify(destination, upstream)
        except BaseException as exc:
            write_once(
                receipt / "end.json",
                {
                    "schema_version": "evalopt.scheduler-stop.v1",
                    "ended_at": _now(),
                    "status": "interrupted",
                    "reason": type(exc).__name__,
                    "dispatched": dispatched,
                },
            )
            raise
        summary = {
            "schema_version": "evalopt.scheduler-stop.v1",
            "ended_at": _now(),
            "status": "paused"
            if reason
            else (
                "limited" if any(state["status"] == "pending" for state in store.statuses()) else "finished"
            ),
            "reason": reason,
            "trial_id": blocked_trial,
            "dispatched": dispatched,
        }
        write_once(receipt / "end.json", summary)
        result = build_report(destination)
        result["scheduler"] = summary
        return result


def _report_rows(store, schedule):
    rows, kernel, attempts = [], [], []
    states = {state["trial_id"]: state for state in store.statuses()}
    usage_fields = {
        "schema_version",
        "input_tokens",
        "output_tokens",
        "model_calls",
        "tool_calls",
        "wall_seconds",
        "agent_count",
        "aggregation",
        "child_usage_complete",
        "accounting_status",
        "runtime_valid",
    }
    for scheduled in schedule:
        trial_id = scheduled["trial_id"]
        state = states[trial_id]
        row = {**scheduled, "status": state["status"], **dict.fromkeys(METRICS), "usage": None}
        decision_row = {"trial_id": trial_id, "artifact_valid": False, "valid_completion": None}
        if state["attempts"]:
            number = state["attempts"]
            path = store.root / "trials" / trial_id / f"attempt-{number}"
            try:
                store.verify_attempt(trial_id, number)
                finish = _finish_record(store, state)
                if finish:
                    row["status"] = finish["status"]
                    row["usage"] = {
                        key: value
                        for key, value in (finish.get("usage") or {}).items()
                        if key in usage_fields
                    }
                if (path / "grade.json").is_file():
                    grade = read_json(path / "grade.json")["grade"]
                    for name in METRICS:
                        value = grade.get(name)
                        if value is not None and type(value) is not bool:
                            raise ValueError("invalid grade metric")
                        row[name] = value
                if row["status"] in {"agent_failure", "timeout", "budget_exhausted"}:
                    row["valid_completion"] = False
                if row["status"] != "completed" and row["status"] not in {
                    "agent_failure",
                    "timeout",
                    "budget_exhausted",
                }:
                    row.update(dict.fromkeys(METRICS))
                if (path / "policies.json").is_file():
                    policy = read_json(path / "policies.json")
                    decision_row.update(
                        artifact_valid=True,
                        valid_completion=row["valid_completion"],
                        policies={name: policy[name] for name in "UMG"},
                        replay=dict.fromkeys("UMG", True),
                    )
            except (OSError, ValueError, KeyError, TypeError):
                row.update(status="artifact_failure", **dict.fromkeys(METRICS), usage=None)
            for attempt in range(1, number + 1):
                record = {"trial_id": trial_id, "attempt": attempt, "artifact_valid": False}
                try:
                    store.verify_attempt(trial_id, attempt)
                    finish_path = store.root / "trials" / trial_id / f"attempt-{attempt}" / "finish.json"
                    finish = read_json(finish_path) if finish_path.is_file() else {}
                    record.update(
                        artifact_valid=True,
                        status=finish.get("status", "running_or_interrupted"),
                        error_code=finish.get("error_code"),
                        usage={
                            key: value
                            for key, value in (finish.get("usage") or {}).items()
                            if key in usage_fields
                        },
                    )
                except (OSError, ValueError, KeyError, TypeError):
                    record["status"] = "artifact_failure"
                attempts.append(record)
        rows.append(row)
        kernel.append(decision_row)
    return rows, kernel, attempts


def _all_attempt_resources(attempts, schedule):
    """Total retained complete telemetry once per attempt, including failed infrastructure attempts."""
    arm_by_trial = {row["trial_id"]: row["arm"] for row in schedule}
    counters = ("input_tokens", "output_tokens", "model_calls", "tool_calls", "wall_seconds")
    result = {}
    for arm in sorted(set(arm_by_trial.values())):
        selected = [item for item in attempts if arm_by_trial[item["trial_id"]] == arm]
        complete = []
        for item in selected:
            measured = item.get("usage") or {}
            if item["artifact_valid"] and measured.get("child_usage_complete") is True:
                if all(
                    isinstance(measured.get(key), int | float)
                    and not isinstance(measured.get(key), bool)
                    and 0 <= measured[key] < float("inf")
                    for key in counters
                ):
                    complete.append(measured)
        result[arm] = {
            "retained_attempts": len(selected),
            "accounted_attempts": len(complete),
            "unavailable_attempts": len(selected) - len(complete),
            "totals": {key: sum(item[key] for item in complete) for key in counters},
        }
    return {
        "scope": "All retained attempts, including final attempts and infrastructure retries; do not add to final-attempt totals.",
        "arms": result,
        "dollar_cost": None,
    }


def _immutable_export(path, value):
    try:
        write_once(path, value)
    except FileExistsError:
        if read_json(path) != value:
            raise ValueError("existing export differs from reproducible report") from None


def report(destination):
    require_controller()
    if (destination / "registration-lock.json").exists():
        if read_json(destination / "registration-lock.json") != _registration_identity(destination):
            raise ValueError("campaign registration files changed before report")
        if read_json(destination / "source-lock.json")["campaign_sha256"] != source_identity(ROOT):
            raise ValueError("report source differs from registered campaign; reproduce with frozen source")
    registration = read_json(destination / "evidence" / "schedule.json")
    if registration["schedule_sha256"] != digest(registration["schedule"]):
        raise ValueError("registered schedule digest changed")
    store = CampaignStore(destination / "evidence", registration["schedule"])
    rows, kernel_rows, attempts = _report_rows(store, registration["schedule"])
    result = analyze_workflows(rows, schedule=registration["schedule"])
    result["all_attempt_resources"] = _all_attempt_resources(attempts, registration["schedule"])
    stages = {row["stage"] for row in registration["schedule"]}
    kernel_stage = "heldout" if "heldout" in stages else "pilot"
    kernel_ids = {row["trial_id"] for row in registration["schedule"] if row["stage"] == kernel_stage}
    kernel = summarize_kernel([row for row in kernel_rows if row["trial_id"] in kernel_ids])
    kernel["scope"] = (
        "held-out stopped-output decisions"
        if kernel_stage == "heldout"
        else ("development diagnostics" if "pilot" in stages else "not applicable to external transfer")
    )
    scheduler_runs = []
    for path in sorted((destination / "runs").glob("run-*")):
        scheduler_runs.append(
            {
                "run": path.name,
                "start": read_json(path / "start.json") if (path / "start.json").is_file() else None,
                "end": read_json(path / "end.json") if (path / "end.json").is_file() else None,
                "subscription_permissions": [
                    read_json(item) for item in sorted(path.glob("permission-*.json"))
                ],
            }
        )
    payloads = {
        "outcomes.json": rows,
        "analysis.json": result,
        "kernel.json": kernel,
        "attempts.json": attempts,
        "scheduler-runs.json": scheduler_runs,
    }
    export_id = digest(payloads)
    directory = destination / "exports" / export_id
    for name, value in payloads.items():
        _immutable_export(directory / name, value)
    _immutable_export(
        directory / "checksums.json",
        {
            "schema_version": "evalopt.report-export.v1",
            "schedule_sha256": registration["schedule_sha256"],
            "export_id": export_id,
            "files": {name: bytes_digest(canonical_bytes(value) + b"\n") for name, value in payloads.items()},
        },
    )
    # Generated convenience views are replaceable; digest-named exports remain intact.
    for name, value in payloads.items():
        temporary = destination / f".{name}.latest"
        temporary.write_bytes(canonical_bytes(value) + b"\n")
        os.replace(temporary, destination / name)
    result = {
        **result,
        "export_directory": str(directory),
        "export_id": export_id,
        "attempts_recorded": len(attempts),
        "infrastructure_retries": sum(item["attempt"] == 2 for item in attempts),
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("prepare-pilot")
    create.add_argument("--directory", type=Path, required=True)
    create.add_argument("--upstream", type=Path, required=True)
    create.add_argument("--image", default="evalopt-workflows-runtime:dev")
    create.add_argument("--verifier", default="evalopt-workflows-verifier:dev")
    create.add_argument("--preflight", type=Path, required=True)
    create.add_argument("--controls", type=Path, required=True)
    execute = commands.add_parser("run-pilot")
    execute.add_argument("--directory", type=Path, required=True)
    execute.add_argument("--upstream", type=Path, required=True)
    execute.add_argument("--limit", type=int)
    execute.add_argument(
        "--retry-infrastructure",
        action="store_true",
        help="Retry previously classified non-quota infrastructure failures once, retaining the original attempt",
    )
    execute.add_argument(
        "--resume-quota",
        action="store_true",
        help="Explicitly resume after subscription quota recovery; never buys credits or changes billing routes",
    )
    execute.add_argument(
        "--recover-interrupted",
        action="store_true",
        help="Recover frozen finalization or an empty predispatch attempt after its controller stopped",
    )
    replay = commands.add_parser("report")
    replay.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    directory = args.directory.resolve()
    if args.command == "prepare-pilot":
        result = prepare(
            directory,
            args.upstream.resolve(),
            args.image,
            args.verifier,
            args.preflight.resolve(),
            args.controls.resolve(),
        )
    elif args.command == "run-pilot":
        if args.limit is not None and args.limit <= 0:
            raise ValueError("limit must be positive")
        result = asyncio.run(
            run_pilot(
                directory,
                args.upstream.resolve(),
                args.limit,
                retry_infrastructure=args.retry_infrastructure,
                resume_quota=args.resume_quota,
                recover_interrupted=args.recover_interrupted,
            )
        )
    else:
        with _scheduler_lock(directory):
            result = report(directory)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if result.get("scheduler", {}).get("status") == "paused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
