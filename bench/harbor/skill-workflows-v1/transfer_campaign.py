#!/usr/bin/env python3
"""Freeze, schedule and reproduce the separate Terminal-Bench feasibility stage."""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from pathlib import Path

import campaign
import heldout_campaign
from lib.analysis import analyze_workflows, summarize_kernel
from lib.common import bytes_digest, canonical_bytes, digest, exact, is_digest, read_json, write_once
from lib.manifest import build_schedule
from runtime import accounting_policy as accounting
from runtime import transfer
from runtime.controller import require_controller
from runtime.harbor_campaign import source_identity
from transfer_store import TransferStore, safe_usage

ROOT = Path(__file__).resolve().parent
REGISTERED_FILES = (
    "manifest.json",
    "preparation.json",
    "readiness.json",
    "source-lock.json",
    "private-sources.json",
    "primary-evidence.json",
    "evidence/schedule.json",
)
RUNTIME = {
    "harbor_version": "0.24.0",
    "codex_version": "0.154.0",
    "model": "gpt-6-astra",
    "reasoning_effort": "ultra",
    "auth_route": "chatgpt_subscription",
    "controller": {"implementation": "CPython", "version": "3.13.12"},
}
LIMITS = {
    "max_concurrent_trials": 2,
    "max_children": 2,
    "delegation_depth": 1,
    "infrastructure_retries": 1,
    "time_limits": "original agent and verifier limits",
}


def _safe_tree(root):
    root = Path(root).absolute()
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("transfer campaign paths may not traverse symlinks")
    return root


def task_records(prepared):
    return [
        {
            "task_id": row["task_id"],
            "stage": "transfer",
            "category": row["category"],
            "cluster_id": row["task_id"],
            "agent_seconds": row["agent_seconds"],
            "task_sha256": digest(prepared["tasks"][row["task_id"]]["original_tree"]),
            "grader_sha256": digest(
                {
                    name: item
                    for name, item in prepared["tasks"][row["task_id"]]["original_tree"].items()
                    if name == "tests" or name.startswith("tests/")
                }
            ),
        }
        for row in prepared["catalog"]["selection"]["selected"]
    ]


def validate_manifest(manifest, preparation):
    version_two = manifest.get("schema_version") == "evalopt.transfer-campaign.v2"
    exact(
        manifest,
        {
            "schema_version",
            "study_id",
            "seed",
            "evidence_class",
            "preparation_sha256",
            "runtime",
            "limits",
            "tasks",
            "scoring",
            "acceptance_policies",
            "primary_registration_sha256",
            "primary_report_export_id",
        }
        | ({"accounting_policy_sha256"} if version_two else set()),
        "transfer manifest",
    )
    if (
        manifest["schema_version"] not in {"evalopt.transfer-campaign.v1", "evalopt.transfer-campaign.v2"}
        or manifest["study_id"] != "skill-workflows-v1-transfer"
        or manifest["seed"] != 20261008
        or manifest["evidence_class"] != transfer.EVIDENCE_CLASS
        or manifest["runtime"] != RUNTIME
        or manifest["limits"] != LIMITS
        or manifest["scoring"] != "original binary upstream verifier reward"
        or manifest["acceptance_policies"] != "not applicable; no U/M/G"
        or not is_digest(manifest["preparation_sha256"])
        or not is_digest(manifest["primary_registration_sha256"])
        or not is_digest(manifest["primary_report_export_id"])
    ):
        raise ValueError("transfer registered conditions changed")
    if version_two and not is_digest(manifest["accounting_policy_sha256"]):
        raise ValueError("transfer accounting policy identity is unresolved")
    if (
        preparation.get("source_commit") != transfer.SOURCE_PIN
        or preparation.get("upstream_commit") != transfer.UPSTREAM_PIN
        or preparation.get("model") != RUNTIME["model"]
        or preparation.get("reasoning_effort") != RUNTIME["reasoning_effort"]
        or preparation.get("codex_version") != RUNTIME["codex_version"]
        or preparation.get("harbor_version") != RUNTIME["harbor_version"]
    ):
        raise ValueError("prepared transfer has different source or runtime pins")
    tasks = task_records(preparation)
    if (
        len(tasks) != 12
        or {task["task_id"] for task in tasks} != set(transfer.ENTRYPOINTS)
        or manifest["tasks"] != tasks
    ):
        raise ValueError("transfer requires the frozen twelve-task feasibility subset")
    schedule = build_schedule(tasks, "transfer", seed=manifest["seed"])
    if len(schedule) != 72:
        raise ValueError("transfer must register 72 trials")
    return schedule


def match_primary_candidate(prepared, manifest, source_lock, pilot_evidence, upstream):
    expected = {"evalopt": source_lock["skill_sha256"], "upstream": source_lock["upstream_sha256"]}
    conditions = pilot_evidence["candidate_conditions"]
    if prepared["skill_sources"] != expected or any(
        conditions[key] != source_lock[key]
        for key in ("skill_sha256", "upstream_sha256", "upstream_loader_sha256")
    ):
        raise ValueError("transfer workflow candidate differs from reviewed pilot and heldout")
    if (
        bytes_digest((upstream / ".claude-plugin/plugin.json").read_bytes())
        != source_lock["upstream_loader_sha256"]
    ):
        raise ValueError("transfer upstream dependency loader differs from heldout")
    if conditions["config_sha256"] != prepared["config_sha256"]:
        raise ValueError("transfer agent configuration differs from reviewed heldout candidate")
    for key in ("harbor_version", "codex_version", "model", "reasoning_effort"):
        if prepared[key] != manifest["runtime"][key]:
            raise ValueError("transfer model or CLI conditions differ from heldout")
    return {
        **expected,
        "upstream_loader_sha256": source_lock["upstream_loader_sha256"],
        "config_sha256": prepared["config_sha256"],
        "runtime": manifest["runtime"],
    }


def verify_primary(heldout, registration_sha256, export_id, prepared, upstream):
    """Require the exact primary candidate and all 432 terminal retained outcomes."""
    manifest, _, schedule, store = heldout_campaign.verify_registration(
        heldout, upstream, registration_sha256
    )
    conditions = match_primary_candidate(
        prepared,
        manifest,
        read_json(heldout / "source-lock.json"),
        read_json(heldout / "pilot-evidence.json"),
        upstream,
    )
    if not is_digest(export_id) or len(schedule) != 432:
        raise ValueError("transfer requires an explicit 432-trial primary report identity")
    for state in store.statuses():
        if not state["attempts"]:
            raise ValueError("transfer dispatch requires every heldout trial to be accounted for")
        for number in range(1, state["attempts"] + 1):
            store.verify_attempt(state["trial_id"], number)
            path = store.root / "trials" / state["trial_id"] / f"attempt-{number}" / "finish.json"
            if not path.is_file() or read_json(path)["status"] not in {
                "completed",
                "timeout",
                "agent_failure",
                "budget_exhausted",
                "infra_failure",
            }:
                raise ValueError("transfer cannot dispatch while a heldout outcome is pending or running")
    policy = accounting.read_accounting_policy(heldout)
    rows, kernel_rows, attempts = campaign._report_rows(
        store, schedule, **({"accounting_policy": policy} if policy is not None else {})
    )
    if any(not item["artifact_valid"] for item in attempts):
        raise ValueError("heldout attempt integrity failed before transfer")
    analysis = analyze_workflows(rows, schedule=schedule)
    analysis["all_attempt_resources"] = (
        campaign._all_attempt_resources(attempts, schedule, accounting_policy=policy)
        if policy is not None
        else campaign._all_attempt_resources(attempts, schedule)
    )
    kernel = summarize_kernel(kernel_rows)
    kernel["scope"] = "held-out stopped-output decisions"
    runs = [
        {
            "run": path.name,
            "start": read_json(path / "start.json"),
            "end": read_json(path / "end.json") if (path / "end.json").is_file() else None,
            "subscription_permissions": [read_json(item) for item in sorted(path.glob("permission-*.json"))],
        }
        for path in sorted((heldout / "runs").glob("run-*"))
    ]
    payloads = {
        "outcomes.json": rows,
        "analysis.json": analysis,
        "kernel.json": kernel,
        "attempts.json": attempts,
        "scheduler-runs.json": runs,
    }
    if digest(payloads) != export_id:
        raise ValueError("primary report identity does not reproduce retained heldout evidence")
    export = heldout / "exports" / export_id
    expected_checksums = {
        "schema_version": "evalopt.report-export.v1",
        "export_id": export_id,
        "schedule_sha256": digest(schedule),
        "files": {name: bytes_digest(canonical_bytes(value) + b"\n") for name, value in payloads.items()},
    }
    if read_json(export / "checksums.json") != expected_checksums or any(
        (export / name).read_bytes() != canonical_bytes(value) + b"\n" for name, value in payloads.items()
    ):
        raise ValueError("primary score report receipt changed")
    return {
        "schema_version": "evalopt.transfer-primary-evidence." + ("v2" if policy is not None else "v1"),
        "heldout_registration_sha256": registration_sha256,
        "heldout_report_export_id": export_id,
        "scheduled_trials": 432,
        "candidate_conditions": conditions,
        "terminal_statuses": dict(Counter(row["status"] for row in rows)),
        "scope": "same reviewed B/C candidate; completed primary schedule including explicit unresolved infrastructure outcomes",
        **(
            {
                "accounting_policy_sha256": digest(policy),
                "accounting_policy_file_sha256": bytes_digest(
                    (heldout / "accounting-policy.json").read_bytes()
                ),
            }
            if policy is not None
            else {}
        ),
    }


def registration_identity(destination):
    return {
        name: bytes_digest((destination / name).read_bytes())
        for name in registered_files(read_json(destination / "manifest.json"))
    }


def registered_files(manifest):
    return REGISTERED_FILES + (
        ("accounting-policy.json",)
        if manifest.get("schema_version") == "evalopt.transfer-campaign.v2"
        else ()
    )


def read_accounting_policy(destination, manifest=None):
    """Transfer v2 copies the exact primary policy; v1 never infers permission."""
    manifest = manifest or read_json(destination / "manifest.json")
    path = _safe_tree(destination / "accounting-policy.json")
    if manifest.get("schema_version") != "evalopt.transfer-campaign.v2":
        if path.exists():
            raise ValueError("unregistered accounting policy in strict transfer campaign")
        return None
    policy = accounting.validate_policy(read_json(path), manifest.get("accounting_policy_sha256"))
    receipt = read_json(destination / "primary-evidence.json")
    if receipt.get("accounting_policy_sha256") != digest(policy) or receipt.get(
        "accounting_policy_file_sha256"
    ) != bytes_digest(path.read_bytes()):
        raise ValueError("transfer accounting policy differs from the exact primary policy bytes")
    return policy


def validate_primary_receipt(receipt, manifest, prepared):
    version_two = manifest.get("schema_version") == "evalopt.transfer-campaign.v2"
    exact(
        receipt,
        {
            "schema_version",
            "heldout_registration_sha256",
            "heldout_report_export_id",
            "scheduled_trials",
            "candidate_conditions",
            "terminal_statuses",
            "scope",
        }
        | ({"accounting_policy_sha256", "accounting_policy_file_sha256"} if version_two else set()),
        "primary receipt",
    )
    conditions = receipt["candidate_conditions"]
    if (
        receipt["schema_version"] != "evalopt.transfer-primary-evidence." + ("v2" if version_two else "v1")
        or receipt["heldout_registration_sha256"] != manifest["primary_registration_sha256"]
        or receipt["heldout_report_export_id"] != manifest["primary_report_export_id"]
        or receipt["scheduled_trials"] != 432
        or not isinstance(receipt["terminal_statuses"], dict)
        or set(receipt["terminal_statuses"])
        - {"completed", "timeout", "agent_failure", "budget_exhausted", "infra_failure"}
        or any(type(value) is not int or value < 0 for value in receipt["terminal_statuses"].values())
        or sum(receipt["terminal_statuses"].values()) != 432
        or {key: conditions[key] for key in ("evalopt", "upstream")} != prepared["skill_sources"]
        or conditions["config_sha256"] != prepared["config_sha256"]
        or not is_digest(conditions["upstream_loader_sha256"])
        or any(
            conditions["runtime"][key] != prepared[key]
            for key in ("model", "reasoning_effort", "codex_version", "harbor_version")
        )
    ):
        raise ValueError("transfer primary-study receipt differs from candidate or complete schedule")
    if version_two and (
        receipt["accounting_policy_sha256"] != manifest["accounting_policy_sha256"]
        or not is_digest(receipt["accounting_policy_file_sha256"])
    ):
        raise ValueError("transfer primary accounting-policy receipt changed")
    return receipt


def freeze(
    destination,
    prepared_root,
    preparation_sha256,
    preflight,
    upstream,
    evalopt_skill,
    *,
    heldout,
    heldout_registration_sha256,
    heldout_export_id,
    runner=transfer._run,
):
    """Create the complete frozen schedule without agent execution or image pulls."""
    require_controller()
    destination, prepared_root, preflight, evalopt_skill = map(
        _safe_tree, (destination, prepared_root, preflight, evalopt_skill)
    )
    if destination.exists():
        raise ValueError("transfer freeze requires a fresh destination")
    prepared = transfer.validate_prepared(
        prepared_root, preparation_sha256, upstream=upstream, evalopt_skill=evalopt_skill, runner=runner
    )
    readiness = transfer.validate_runtime_preflight(preflight, prepared)
    primary = verify_primary(heldout, heldout_registration_sha256, heldout_export_id, prepared, upstream)
    policy_raw = None
    if primary["schema_version"] == "evalopt.transfer-primary-evidence.v2":
        policy_raw = _safe_tree(Path(heldout) / "accounting-policy.json").read_bytes()
        policy = accounting.validate_policy(
            read_json(Path(heldout) / "accounting-policy.json"), primary["accounting_policy_sha256"]
        )
        if bytes_digest(policy_raw) != primary["accounting_policy_file_sha256"]:
            raise ValueError("primary accounting policy changed during transfer freeze")
    else:
        policy = None
    manifest = {
        "schema_version": "evalopt.transfer-campaign." + ("v2" if policy is not None else "v1"),
        "study_id": "skill-workflows-v1-transfer",
        "seed": 20261008,
        "evidence_class": transfer.EVIDENCE_CLASS,
        "preparation_sha256": preparation_sha256,
        "runtime": RUNTIME.copy(),
        "limits": LIMITS.copy(),
        "tasks": task_records(prepared),
        "scoring": "original binary upstream verifier reward",
        "acceptance_policies": "not applicable; no U/M/G",
        "primary_registration_sha256": heldout_registration_sha256,
        "primary_report_export_id": heldout_export_id,
        **({"accounting_policy_sha256": digest(policy)} if policy is not None else {}),
    }
    schedule = validate_manifest(manifest, prepared)
    validate_primary_receipt(primary, manifest, prepared)
    source_lock = {
        "campaign_sha256": source_identity(ROOT),
        "prepared_sha256": source_identity(prepared_root),
        "preflight_sha256": source_identity(preflight),
        "library_sha256": source_identity(ROOT / "lib"),
    }
    destination.mkdir(parents=True)
    destination.chmod(0o700)
    for name, value in {
        "manifest.json": manifest,
        "readiness.json": readiness,
        "source-lock.json": source_lock,
        "primary-evidence.json": primary,
        "private-sources.json": {
            "prepared": str(prepared_root),
            "preflight": str(preflight),
            "evalopt_skill": str(evalopt_skill),
            "heldout": str(_safe_tree(heldout)),
        },
    }.items():
        write_once(destination / name, value)
    # Preparation file identity is over the original serialized file, not our copy.
    with (destination / "preparation.json").open("xb") as stream:
        stream.write((prepared_root / "preparation.json").read_bytes())
    if policy_raw is not None:
        with (destination / "accounting-policy.json").open("xb") as stream:
            stream.write(policy_raw)
    TransferStore(destination / "evidence", schedule, accounting_policy=policy)
    write_once(destination / "registration-lock.json", registration_identity(destination))
    return {
        "schema_version": "evalopt.transfer-freeze." + ("v2" if policy is not None else "v1"),
        "scheduled_trials": len(schedule),
        "registration_sha256": digest(read_json(destination / "registration-lock.json")),
        "agent_trials": 0,
    }


def read_registration(destination):
    destination = _safe_tree(destination)
    if read_json(destination / "registration-lock.json") != registration_identity(destination):
        raise ValueError("transfer registration changed")
    manifest, prepared = read_json(destination / "manifest.json"), read_json(destination / "preparation.json")
    if bytes_digest((destination / "preparation.json").read_bytes()) != manifest["preparation_sha256"]:
        raise ValueError("registered preparation identity differs")
    schedule = validate_manifest(manifest, prepared)
    validate_primary_receipt(read_json(destination / "primary-evidence.json"), manifest, prepared)
    read_accounting_policy(destination, manifest)
    expected = {
        "schema_version": "evalopt.workflow-schedule.v1",
        "schedule": schedule,
        "schedule_sha256": digest(schedule),
    }
    if read_json(destination / "evidence/schedule.json") != expected:
        raise ValueError("transfer schedule differs from frozen registration")
    return manifest, prepared, schedule


def verify_campaign(destination, upstream, *, runner=transfer._run):
    require_controller()
    manifest, prepared, schedule = read_registration(destination)
    sources, lock = (
        read_json(destination / "private-sources.json"),
        read_json(destination / "source-lock.json"),
    )
    prepared_root, preflight, skill = (
        Path(sources[key]) for key in ("prepared", "preflight", "evalopt_skill")
    )
    if lock != {
        "campaign_sha256": source_identity(ROOT),
        "prepared_sha256": source_identity(prepared_root),
        "preflight_sha256": source_identity(preflight),
        "library_sha256": source_identity(ROOT / "lib"),
    }:
        raise ValueError("transfer source, prepared task, or preflight content changed")
    actual = transfer.validate_prepared(
        prepared_root, manifest["preparation_sha256"], upstream=upstream, evalopt_skill=skill, runner=runner
    )
    if actual != prepared or transfer.validate_runtime_preflight(preflight, prepared) != read_json(
        destination / "readiness.json"
    ):
        raise ValueError("transfer capability or preparation evidence changed")
    if verify_primary(
        Path(sources["heldout"]),
        manifest["primary_registration_sha256"],
        manifest["primary_report_export_id"],
        prepared,
        upstream,
    ) != read_json(destination / "primary-evidence.json"):
        raise ValueError("primary study identity or accounted outcomes changed before transfer dispatch")
    return (
        manifest,
        {"agent_image": None, "verifier_image": None},
        schedule,
        TransferStore(
            destination / "evidence",
            schedule,
            accounting_policy=read_accounting_policy(destination, manifest),
        ),
    )


async def execute_registered(row, store, private_root, upstream, _agent_image, _verifier_image):
    destination = store.root.parent
    manifest = read_json(destination / "manifest.json")
    sources = read_json(destination / "private-sources.json")
    policy = read_accounting_policy(destination, manifest)
    attempt = store.start_attempt(row["trial_id"])
    output = private_root / row["trial_id"] / f"attempt-{attempt}"
    result = await transfer.execute_transfer_trial(
        row,
        prepared_root=Path(sources["prepared"]),
        preparation_sha256=manifest["preparation_sha256"],
        directory=output,
        upstream=upstream,
        evalopt_skill=Path(sources["evalopt_skill"]),
        runtime_preflight=Path(sources["preflight"]),
        **({"accounting_policy": policy} if policy is not None else {}),
    )
    # Do not let a substituted return value overrule the retained runtime summary.
    if result != read_json(output / "result.json"):
        raise ValueError("transfer runtime return differs from retained controller result")
    store.record_result(
        row["trial_id"],
        attempt,
        result,
        original_result_sha256=bytes_digest((output / "result.json").read_bytes()),
        raw_artifact_manifest_sha256=bytes_digest((output / "artifacts.json").read_bytes()),
    )
    store.finish_attempt(
        row["trial_id"],
        attempt,
        result["status"],
        error_code=result["error_code"],
        usage=safe_usage(result.get("usage"), policy),
    )
    return result


async def run_campaign(destination, upstream, limit=None, **options):
    policy = read_accounting_policy(destination)
    if policy is not None:
        options["usage_gate"] = lambda finish: transfer_usage_reason(finish, policy)
    return await campaign.run_pilot(
        destination,
        upstream,
        limit,
        verifier=verify_campaign,
        executor=execute_registered,
        reporter=report,
        **options,
    )


def transfer_usage_reason(finish, policy):
    """Partial usage approval never establishes a native execution boundary."""
    accounting.validate_policy(policy)
    usage = finish.get("usage") or {}
    try:
        derived = accounting.validate_attempt(finish, policy)
    except (KeyError, TypeError, ValueError):
        return "accounting_policy_evidence_requires_remediation"
    if derived is None:
        # Only the shared helper's verified recovery/pre-agent missing-evidence
        # exception applies. This permits classified retry, not runtime proof.
        reason = accounting.continuation_reason(finish, policy)
        if reason:
            return reason
        if usage.get("agent_started") is True:
            return "execution_boundary_requires_remediation"
        return None
    if (
        finish.get("artifact_valid") is True
        and finish.get("status") == "infra_failure"
        and finish.get("error_code") == "container_start"
        and usage.get("agent_started") is False
        and usage.get("runtime_valid") is None
        and usage.get("native_agent_stopped") is False
        and usage.get("execution_boundary_complete") is False
        and all(usage.get(key) == [] for key in ("returned_models", "returned_efforts", "cli_versions"))
        and derived["accounting_status"] == "unavailable"
        and derived["provenance_status"] == "unavailable"
        and derived["source_log_sha256"] == []
        and derived["completeness_reasons"]
        in (
            ["native_log_directory_missing"],
            ["native_session_logs_missing"],
        )
    ):
        return None
    reason = accounting.continuation_reason(finish, policy)
    if reason:
        return reason
    if usage.get("agent_started") is not True:
        return "agent_start_requires_remediation"
    if usage.get("native_agent_stopped") is not True or usage.get("execution_boundary_complete") is not True:
        return "execution_boundary_requires_remediation"
    if usage.get("workflow_exposure_verified") is not True:
        return "workflow_exposure_requires_remediation"
    if usage.get("entrypoint_load_observed") is not True:
        return "entrypoint_load_requires_remediation"
    return None


def report_payloads(store, schedule, runs):
    policy = getattr(store, "accounting_policy", None)
    rows, attempts = [], []
    states = {row["trial_id"]: row for row in store.statuses()}
    for scheduled in schedule:
        trial_id, state = scheduled["trial_id"], states[scheduled["trial_id"]]
        row = {
            **scheduled,
            "status": state["status"],
            "upstream_reward": None,
            "functional_success": None,
            "artifact_capture_complete": None,
            "runtime_evidence_complete": None,
            "execution_boundary_complete": None,
            "usage": None,
        }
        if policy is not None:
            row["runtime_admissible"] = None
        for attempt in range(1, state["attempts"] + 1):
            record = {"trial_id": trial_id, "attempt": attempt, "artifact_valid": False}
            path = store.root / "trials" / trial_id / f"attempt-{attempt}"
            try:
                store.verify_attempt(trial_id, attempt)
                finish = read_json(path / "finish.json")
                record.update(
                    artifact_valid=True,
                    status=finish["status"],
                    error_code=finish["error_code"],
                    usage=safe_usage(finish.get("usage"), policy),
                )
                if policy is not None:
                    record["accounting_context"] = {
                        "stopped_output_retained": (path / "transfer-result.json").is_file(),
                        "grade_retained": False,
                    }
                    record["runtime_admissible"] = (
                        record["usage"].get("agent_started") is True
                        and transfer_usage_reason({**finish, **record}, policy) is None
                    )
                if attempt == state["attempts"]:
                    row.update(status=finish["status"], usage=record["usage"])
                    if policy is not None:
                        row["runtime_admissible"] = record["runtime_admissible"]
                    if (path / "transfer-result.json").is_file():
                        result = read_json(path / "transfer-result.json")
                        row.update(
                            {
                                key: result[key]
                                for key in (
                                    "upstream_reward",
                                    "functional_success",
                                    "artifact_capture_complete",
                                    "runtime_evidence_complete",
                                    "execution_boundary_complete",
                                )
                            }
                        )
            except (OSError, ValueError, KeyError, TypeError):
                record["status"] = "artifact_failure"
                if attempt == state["attempts"]:
                    row.update(
                        status="artifact_failure", upstream_reward=None, functional_success=None, usage=None
                    )
            attempts.append(record)
        rows.append(row)
    arms = {}
    for arm in ("B", "C"):
        selected = [row for row in rows if row["arm"] == arm]
        available = [row for row in selected if row["upstream_reward"] is not None]
        successes = sum(row["upstream_reward"] for row in available)
        missing = len(selected) - len(available)
        arms[arm] = {
            "scheduled": len(selected),
            "reward_available": len(available),
            "missing_reward": missing,
            "successes": successes,
            "observed_success_rate": successes / len(available) if available else None,
            "missing_outcome_bounds": [successes / len(selected), (successes + missing) / len(selected)],
            "all_three_success_tasks": sum(
                all(row["upstream_reward"] == 1 for row in selected if row["task_id"] == task)
                for task in {row["task_id"] for row in selected}
            ),
            "artifact_capture_complete": sum(row["artifact_capture_complete"] is True for row in selected),
            "runtime_evidence_complete": sum(row["runtime_evidence_complete"] is True for row in selected),
            "execution_boundary_complete": sum(
                row["execution_boundary_complete"] is True for row in selected
            ),
            "statuses": dict(Counter(row["status"] for row in selected)),
        }
        if policy is not None:
            arms[arm]["runtime_admissible"] = sum(row["runtime_admissible"] is True for row in selected)
    resources = campaign._all_attempt_resources(
        attempts, schedule, **({"accounting_policy": policy} if policy is not None else {})
    )
    if policy is not None:
        registered = resources["registered_accounting"]
        registered["efficiency_comparison_eligible"] &= all(
            row.get("runtime_admissible") is True for row in attempts
        )
        registered["transfer_execution_scope"] = (
            "efficiency additionally requires verified native stop, execution boundary and workflow exposure "
            "for every retained attempt; runtime-blocked known counters remain included"
        )
    summary = {
        "schema_version": "evalopt.transfer-report." + ("v2" if policy is not None else "v1"),
        "evidence_class": transfer.EVIDENCE_CLASS,
        "arms": arms,
        "headline_permitted": False,
        "acceptance_policies": "not applicable; no U/M/G",
        "paired_difference_missing_bounds": [
            arms["C"]["missing_outcome_bounds"][0] - arms["B"]["missing_outcome_bounds"][1],
            arms["C"]["missing_outcome_bounds"][1] - arms["B"]["missing_outcome_bounds"][0],
        ],
        "all_attempt_resources": resources,
        "scoring": "Original binary upstream verifier rewards are preserved, including rewards after timeouts. Repetitions are not additional independent tasks.",
        "reproduction_scope": "retained reward aggregation and artifact integrity; private archives and original verifiers are not re-executed",
    }
    if policy is not None:
        summary["accounting_policy_sha256"] = digest(policy)
    return {
        "outcomes.json": rows,
        "analysis.json": summary,
        "attempts.json": attempts,
        "scheduler-runs.json": runs,
    }


def report(destination):
    require_controller()
    _, _, schedule = read_registration(destination)
    if read_json(destination / "source-lock.json")["campaign_sha256"] != source_identity(ROOT):
        raise ValueError("reproduce transfer report with registered campaign source")
    store = TransferStore(
        destination / "evidence", schedule, accounting_policy=read_accounting_policy(destination)
    )
    runs = [
        {
            "run": path.name,
            "start": read_json(path / "start.json"),
            "end": read_json(path / "end.json") if (path / "end.json").is_file() else None,
            "subscription_permissions": [read_json(item) for item in sorted(path.glob("permission-*.json"))],
        }
        for path in sorted((destination / "runs").glob("run-*"))
    ]
    payloads = report_payloads(store, schedule, runs)
    export_id = digest(payloads)
    export = destination / "exports" / export_id
    for name, value in payloads.items():
        campaign._immutable_export(export / name, value)
    campaign._immutable_export(
        export / "checksums.json",
        {
            "schema_version": "evalopt.transfer-export.v1",
            "export_id": export_id,
            "schedule_sha256": digest(schedule),
            "files": {name: bytes_digest(canonical_bytes(value) + b"\n") for name, value in payloads.items()},
        },
    )
    return {
        **payloads["analysis.json"],
        "export_id": export_id,
        "attempts_recorded": len(payloads["attempts.json"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    freeze_cmd = commands.add_parser("freeze")
    for name in ("directory", "prepared", "preflight", "upstream", "evalopt-skill"):
        freeze_cmd.add_argument("--" + name, type=Path, required=True)
    freeze_cmd.add_argument("--preparation-sha256", required=True)
    freeze_cmd.add_argument("--heldout", type=Path, required=True)
    freeze_cmd.add_argument("--heldout-registration-sha256", required=True)
    freeze_cmd.add_argument("--heldout-export-id", required=True)
    run_cmd = commands.add_parser("run")
    run_cmd.add_argument("--directory", type=Path, required=True)
    run_cmd.add_argument("--upstream", type=Path, required=True)
    run_cmd.add_argument("--limit", type=int)
    for flag in ("retry-infrastructure", "resume-quota", "recover-interrupted"):
        run_cmd.add_argument("--" + flag, action="store_true")
    report_cmd = commands.add_parser("report")
    report_cmd.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        result = freeze(
            args.directory,
            args.prepared,
            args.preparation_sha256,
            args.preflight,
            args.upstream,
            args.evalopt_skill,
            heldout=args.heldout,
            heldout_registration_sha256=args.heldout_registration_sha256,
            heldout_export_id=args.heldout_export_id,
        )
    elif args.command == "run":
        result = asyncio.run(
            run_campaign(
                args.directory,
                args.upstream,
                args.limit,
                retry_infrastructure=args.retry_infrastructure,
                resume_quota=args.resume_quota,
                recover_interrupted=args.recover_interrupted,
            )
        )
    else:
        result = report(args.directory)
    print(canonical_bytes(result).decode())
    return 2 if result.get("scheduler", {}).get("status") == "paused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
