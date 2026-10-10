"""Sequential frozen dispatcher and retained-record replay, outside candidates."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from .accounting import derive_usage
from .analysis import reconcile, report
from .capture import LABEL
from .case_runner import snapshot_manifest
from .descriptive import kernel_metrics, outcomes, resources
from .framing import strict_json
from .freeze import verify_frozen
from .git_index import workspace_manifest
from .harbor_bridge import execute_one, lifecycle_observation
from .lifecycle import continuation_decision, read_record
from .materialize import boundary_violations
from .policies import evaluate_visible
from .preflight import PreDispatchInfrastructureError, runtime_observations, subscription_permission
from .records import digest, task_outcome
from .registration import development_gate
from .replay_grade import replay_grade
from .snapshot import final_response, session_files
from .store import exclusive_json, read_json

MINIMUM_FREE_BYTES = 2 * 1024**3


def _now():
    return datetime.now(timezone.utc).isoformat()


def admission_environment(root):
    """A fresh read-only guard under the native campaign lock, before ownership."""
    free = shutil.disk_usage(root).free
    if free < MINIMUM_FREE_BYTES:
        raise ValueError("insufficient_capture_storage")
    result = subprocess.run(
        ["docker", "ps", "--filter", "label=" + LABEL, "--format", "{{.ID}}"],
        capture_output=True,
        timeout=15,
        check=True,
    )
    if result.stdout.strip():
        raise ValueError("previous_owned_container_still_running")
    return {
        "observed_at": _now(),
        "free_bytes": free,
        "minimum_free_bytes": MINIMUM_FREE_BYTES,
        "running_owned_containers": 0,
    }


def _missing_visible(task, attempt_id):
    return {
        "schema_version": "evalopt-workflows-v2/1",
        "kind": "stopped_visible_evidence",
        "attempt_id": attempt_id,
        "task_contract": task["task_contract"],
        "snapshot_sha256": None,
        "observations": [
            {
                "schema_version": "evalopt-workflows-v2/1",
                "record_type": "command",
                "attempt_id": attempt_id,
                "candidate_id": "unavailable",
                "command": task["visible_command"],
                "execution_state": "not_run",
                "exit_code": None,
                "evidence_availability": "unavailable",
                "artifact_refs": [],
                "asserted_claim": None,
            }
        ],
        "response": None,
        "response_capture": {"status": "missing", "response": None},
        "boundaries_preserved": None,
        "boundary_violations": [],
        "execution_boundary": "unconfirmed",
        "snapshot_status": "unavailable",
    }


def unavailable_grade(task, attempt_id, reason, *, timed_out=False):
    outcome = task_outcome(
        attempt_id,
        task["task_contract"],
        functional_success=None,
        verifier_status="not_run",
        timed_out=timed_out,
    )
    return {
        "outcome": outcome,
        "reason": reason,
        "raw_verification": None,
        "unrun_case_roster": [
            {"case_id": case["case_id"], "execution_state": "not_run", "reason": reason}
            for case in task.get("cases", [])
        ],
    }


def project_result(task, result, permission):
    verification = result["verification"]
    if verification is None:
        grade = unavailable_grade(
            task,
            result["attempt_id"],
            "required_evidence_unavailable",
            timed_out=result["status"] == "timeout",
        )
    else:
        raw = verification["grade"]
        grade = {"outcome": raw["outcome"], "raw_verification": verification}
    grade["runtime_identity_verified"] = result["runtime_identity"]["verified"] is True
    continuation = continuation_decision(
        result["closure"],
        result["usage"],
        runtime_identity_verified=grade["runtime_identity_verified"],
        quota_allowed=permission["ordinary_usage_allowed"],
    )
    reasons = list(continuation["reasons"])
    if result.get("capture_error_type"):
        reasons.append("snapshot_extraction_failed")
    if result.get("case_boundary_confirmed") is not True:
        reasons.append("verifier_boundary_unconfirmed")
    if reasons:
        continuation.update(decision="stop", reasons=sorted(set(reasons)))
    return grade, continuation


def outcome_row(scheduled, grade):
    """Keep task checks intact; runtime eligibility is a separate experiment gate."""
    outcome = grade["outcome"]
    raw = (grade.get("raw_verification") or {}).get("grade", {})
    eligible = grade.get("runtime_identity_verified") is True
    # An observed time-budget failure remains a failure even with missing model
    # telemetry. Other ineligible executions do not establish task performance.
    valid = outcome["valid_completion"] if eligible or outcome["timed_out"] else None
    row = {
        **scheduled,
        "valid_completion": valid,
        "functional_success": outcome["functional_success"] if eligible else None,
        "contract_dispute": outcome["contract_dispute"],
        "unsupported_success": raw.get("unsupported_success") if eligible else None,
        "incorrect_refusal": raw.get("incorrect_refusal") if eligible else None,
        "boundary_violation": None
        if outcome["boundary_preserved"] is None
        else not outcome["boundary_preserved"],
        "raw_valid_completion": outcome["valid_completion"],
        "raw_functional_success": outcome["functional_success"],
        "runtime_identity_verified": eligible,
    }
    if valid is None:
        row["missing_reason"] = grade.get("reason") or "unresolved_required_evidence"
    return row


def _failure(path, error):
    # Never retain exception messages: subprocess failures may contain auth or
    # private paths. The unfinalized attempt blocks admission on every restart.
    exclusive_json(
        path / "controller-failure.json",
        {
            "kind": "controller_failure",
            "error_type": type(error).__name__,
            "observed_at": _now(),
            "automatic_retry_allowed": False,
        },
    )


async def execute_campaign(root, *, expected_sha256, limit):
    if type(limit) is not int or limit < 1:
        raise ValueError("positive dispatch limit required")
    root = Path(root).absolute()
    store = verify_frozen(root, expected_sha256=expected_sha256)
    if Path(__file__).resolve() != root / "frozen/harness/evalopt_v2/campaign.py":
        raise ValueError("dispatch must execute the frozen controller copy")
    frozen, completed = root / "frozen", 0
    with store.lock():
        while completed < limit:
            verify_frozen(root, expected_sha256=expected_sha256)
            permission = await asyncio.to_thread(subscription_permission)
            entries = store._pause_entries()
            pending_pause = bool(entries and not (entries[-1] / "resume.json").exists())
            if permission["ordinary_usage_allowed"] is not True:
                if not pending_pause:
                    store.pause_subscription(permission)
                return {"state": "paused_subscription", "executed_this_run": completed}
            if pending_pause:
                store.resume_subscription(permission)
            row = store.next_row()
            if row is None:
                return {"state": "complete", "executed_this_run": completed}
            environment = await asyncio.to_thread(admission_environment, root)
            path = store.start(row["trial_id"])
            start = read_json(path / "start.json")
            dispatch_row = dict(row, attempt_id=start["attempt_id"])
            task_dir = frozen / "tasks" / store.registration["stage"] / row["task_id"]
            task = strict_json((task_dir / "task.json").read_bytes())
            if task["id"] != row["task_id"] or task["category"] != row["category"]:
                raise ValueError("task does not match frozen schedule")

            async def freeze_visible(bundle, task=task, start=start, row=row):
                policy = evaluate_visible(
                    bundle,
                    check_roster=[{"check_id": "required", "command": task["visible_command"]}],
                    attempt_id=start["attempt_id"],
                    candidate_id=bundle["snapshot_sha256"],
                    observed_at=_now(),
                )
                return store.record_visible(row["trial_id"], bundle, policy)

            exclusive_json(path / "admission-permission.json", permission)
            exclusive_json(path / "admission-environment.json", environment)
            began = time.monotonic()
            try:
                result = await execute_one(
                    dispatch_row,
                    task_dir,
                    path / "runtime",
                    frozen / "upstream",
                    frozen / "skill-c",
                    frozen / "skill-d",
                    "sha256:" + store.registration["identities"]["agent_image"],
                    "sha256:" + store.registration["identities"]["verifier_image"],
                    freeze_visible=freeze_visible,
                )
            except PreDispatchInfrastructureError as error:
                if (
                    error.proof
                    != {
                        "phase": "read_only_image_preflight",
                        "containers_created": False,
                        "agent_dispatched": False,
                    }
                    or (path / "runtime").exists()
                ):
                    _failure(path, error)
                    return {
                        "state": "stopped_unfinalized",
                        "trial_id": row["trial_id"],
                        "executed_this_run": completed,
                    }
                await freeze_visible(_missing_visible(task, start["attempt_id"]))
                grade = unavailable_grade(
                    task, start["attempt_id"], "docker_inspection_before_container_creation"
                )
                exclusive_json(
                    path / "infrastructure.json",
                    {
                        "classification": "docker_inspection_before_container_creation",
                        "attempt_id": start["attempt_id"],
                        "agent_dispatched": False,
                        "container_creation_attempted": False,
                    },
                )
                exclusive_json(path / "usage.json", derive_usage({}))
                store.record_grade(row["trial_id"], grade)
                store.finalize(
                    row["trial_id"],
                    grade["outcome"],
                    {"decision": "stop", "reasons": ["docker_inspection_before_container_creation"]},
                )
                if start["attempt"] == 1:
                    store.authorize_infrastructure_retry(row["trial_id"])
                    continue
                return {"state": "stopped_infrastructure_retry_exhausted", "executed_this_run": completed}
            except Exception as error:
                _failure(path, error)
                return {
                    "state": "stopped_unfinalized",
                    "trial_id": row["trial_id"],
                    "executed_this_run": completed,
                }
            verify_frozen(root, expected_sha256=expected_sha256)
            post_permission = await asyncio.to_thread(subscription_permission)
            exclusive_json(path / "post-permission.json", post_permission)
            grade, continuation = project_result(task, result, post_permission)
            exclusive_json(
                path / "timing.json",
                {
                    "controller_wall_seconds": time.monotonic() - began,
                    "scope": "setup_agent_capture_visible_and_hidden_verification",
                },
            )
            exclusive_json(path / "usage.json", result["usage"])
            store.record_grade(row["trial_id"], grade)
            store.finalize(row["trial_id"], grade["outcome"], continuation)
            completed += 1
            if continuation["reasons"] == ["subscription_permission_unavailable"]:
                store.pause_subscription(post_permission, stopped_trial_id=row["trial_id"])
            if continuation["decision"] == "stop":
                return {
                    "state": "stopped",
                    "trial_id": row["trial_id"],
                    "reasons": continuation["reasons"],
                    "executed_this_run": completed,
                }
        return {"state": "dispatch_limit_reached", "executed_this_run": completed}


def validate_retained_grade(store, trial_id, grade):
    """Recompute the grade from independently retained records, never candidates."""
    path = store.path(trial_id)
    start = read_json(path / "start.json")
    task_dir = store.root / "frozen/tasks" / store.registration["stage"] / start["row"]["task_id"]
    task = dict(strict_json((task_dir / "task.json").read_bytes()), attempt_id=start["attempt_id"])
    if (path / "infrastructure.json").exists():
        expected = unavailable_grade(task, start["attempt_id"], "docker_inspection_before_container_creation")
        if grade != expected:
            raise ValueError("infrastructure grade changed")
        return
    runtime = path / "runtime"
    result = read_record(runtime / "result.json")
    if result["attempt_id"] != start["attempt_id"]:
        raise ValueError("runtime attempt identity changed")
    expected, continuation = project_result(task, result, read_json(path / "post-permission.json"))
    if grade != expected or continuation != read_json(path / "final.json")["continuation"]:
        raise ValueError("grade or continuation projection changed")
    visible = read_json(path / "visible-policy.json")["visible"]
    if visible != result["visible_bundle"] or visible != read_record(runtime / "visible-bundle.json"):
        raise ValueError("visible evidence copies disagree")
    if read_json(path / "usage.json") != result["usage"]:
        raise ValueError("usage copies disagree")
    closure = read_record(runtime / "supervisor/closure/closure.json")
    if closure != result["closure"]:
        raise ValueError("retained closure disagrees")
    files = session_files(runtime / "native-sessions") if (runtime / "native-sessions").is_dir() else {}
    if (
        derive_usage(files) != result["usage"]
        or lifecycle_observation(result["usage"]) != result["native_lifecycle"]
    ):
        raise ValueError("native accounting or lifecycle is not reproducible")
    if files:
        if (
            runtime_observations(files) != result["runtime_identity"]
            or final_response(files) != result["response_capture"]
        ):
            raise ValueError("runtime identity or final response is not reproducible")
    if visible["snapshot_status"] == "complete":
        stopped_manifest = workspace_manifest(runtime / "stopped")
        violations = boundary_violations(
            workspace_manifest(runtime / "initial"), stopped_manifest, task.get("allowed_changes", [])
        )
        if (
            digest(stopped_manifest) != visible["snapshot_sha256"]
            or violations != visible["boundary_violations"]
        ):
            raise ValueError("stopped snapshot or boundary evidence changed")
    verification = result["verification"]
    if verification is None:
        return
    verifier = runtime / "verifier"
    if verification != read_record(verifier / "verification.json"):
        raise ValueError("verification copies disagree")
    records = [read_record(record) for record in sorted(verifier.glob("case-*.json"))]
    oracle = task_dir / "oracle_cases.json"
    replay_grade(
        task,
        verification,
        visible_candidate_id=visible["snapshot_sha256"],
        response=visible["response"],
        observations=visible["observations"],
        boundary_violations=visible["boundary_violations"],
        lifecycle_verified=result["native_lifecycle"]["lifecycle_verified"],
        timed_out=result["status"] == "timeout",
        retained_records=records,
        oracle_cases=strict_json(oracle.read_bytes()) if oracle.exists() else None,
        baseline_manifest=snapshot_manifest(task_dir / "baseline")
        if task["task_contract"] == "review"
        else None,
        candidate_manifest=snapshot_manifest(runtime / "stopped"),
    )


def kernel_ground_truth(stopped, resolved):
    """Apply task-wide disputes to policy labels as well as workflow contrasts."""
    lookup = {row["trial_id"]: row for row in resolved}
    if len(lookup) != len(resolved):
        raise ValueError("duplicate reconciled outcome")
    return [
        {
            **row,
            "raw_valid_completion": row["valid_completion"],
            "valid_completion": lookup[row["trial_id"]]["reported_valid_completion"],
        }
        for row in stopped
    ]


def replay(root, *, expected_sha256):
    """Consume retained records and immutable manifests; never execute candidate code."""
    store = verify_frozen(root, expected_sha256=expected_sha256)
    rows, attempts, stopped, unfinalized = [], [], [], []
    total_seconds, timed_attempts = 0, 0
    for trial_id, scheduled in store.scheduled.items():
        trial = store.trial_root(trial_id)
        if not trial.exists():
            continue
        number = store.attempt_number(trial_id)
        path = store.path(trial_id)
        finalized = (path / "final.json").exists()
        if finalized:
            store.verify_trial(trial_id)
            grade = read_json(path / "grade.json")
            validate_retained_grade(store, trial_id, grade)
            row = outcome_row(scheduled, grade)
            visible = read_json(path / "visible-policy.json")
            rows.append(row)
            stopped.append(
                {
                    "trial_id": trial_id,
                    "valid_completion": row["valid_completion"],
                    "policies": visible["decisions"],
                }
            )
        else:
            unfinalized.append(trial_id)
        for attempt in range(1, number + 1):
            attempt_path = store.path(trial_id, attempt)
            if (attempt_path / "final.json").exists():
                store._verify_attempt(trial_id, attempt)
                usage = read_json(attempt_path / "usage.json")
            else:
                # Without a sealed manifest, even plausible counters are not
                # authenticated accounting. Preserve them privately; report null.
                usage = derive_usage({})
            attempts.append({"trial_id": trial_id, "attempt": attempt, "usage": usage})
            if (attempt_path / "final.json").exists() and (attempt_path / "timing.json").exists():
                total_seconds += read_json(attempt_path / "timing.json")["controller_wall_seconds"]
                timed_attempts += 1
    tasks, stage = store.registration["tasks"], store.registration["stage"]
    resolved = reconcile(tasks, rows, stage)
    result = (
        report(tasks, rows, registration_record=store.registration)
        if stage == "heldout"
        else {
            "stage": stage,
            "scheduled_rows": resolved,
            "secondary_outcomes": outcomes(resolved),
            "gate": development_gate(
                tasks,
                rows,
                controls_passed=True,
                revision=read_json(store.root / "admission.json")["development_round"]["revision"],
            ),
            "conclusion": "development_only",
        }
    )
    result.update(
        resources=resources(store.registration["schedule"], attempts),
        kernel=kernel_metrics(kernel_ground_truth(stopped, resolved)),
        registration_sha256=expected_sha256,
        retained_attempts=len(attempts),
        finalized_rows=len(rows),
        unfinalized_trials=unfinalized,
        controller_time={
            "observed_seconds": total_seconds if timed_attempts else None,
            "known_attempts": timed_attempts,
            "retained_attempts": len(attempts),
            "scope": "setup_agent_capture_visible_and_hidden_verification",
        },
    )
    return result
