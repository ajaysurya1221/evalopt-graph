"""Adversarial tests for benchmark-only custody, scheduling and inference boundaries."""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
SPEC = importlib.util.spec_from_file_location(
    "workflow_campaign_lib", BENCH / "lib/__init__.py", submodule_search_locations=[str(BENCH / "lib")]
)
assert SPEC is not None and SPEC.loader is not None
PACKAGE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PACKAGE
SPEC.loader.exec_module(PACKAGE)

import workflow_campaign_lib.store as storage  # noqa: E402
from workflow_campaign_lib.accounting import parse_native_usage, summarize_usage  # noqa: E402
from workflow_campaign_lib.analysis import analyze_workflows, summarize_kernel  # noqa: E402
from workflow_campaign_lib.common import bytes_digest, digest  # noqa: E402
from workflow_campaign_lib.manifest import CATEGORIES, build_schedule, validate_manifest  # noqa: E402
from workflow_campaign_lib.policies import evaluate_policies, replay_policies  # noqa: E402
from workflow_campaign_lib.store import CampaignStore  # noqa: E402


def task(name="one", stage="pilot", category=CATEGORIES[0], cluster=None):
    return {
        "task_id": name,
        "stage": stage,
        "category": category,
        "cluster_id": cluster or name,
        "task_sha256": digest(name),
        "grader_sha256": "b" * 64,
        "agent_seconds": 600,
    }


def manifest():
    tasks = [task(f"pilot-{i}", category=CATEGORIES[i % 6]) for i in range(12)]
    tasks += [
        task(f"heldout-{c}-{i}", "heldout", category)
        for c, category in enumerate(CATEGORIES)
        for i in range(8)
    ]
    tasks += [task(f"transfer-{i}", "transfer", "debugging") for i in range(12)]
    return {
        "schema_version": "evalopt.skill-workflows.v1",
        "study_id": "test",
        "seed": 20261008,
        "pins": {
            "upstream_commit": "b0618bc436ad893b3c5e84e55fba86586d34a404",
            "terminal_bench_commit": "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c",
            "kernel_commit": "fc3045dbda29c1d274747329ceb6724a783b0df7",
            **dict.fromkeys(
                ("skill_sha256", "grader_sha256", "policy_sha256", "analysis_sha256", "environment_sha256"),
                "a" * 64,
            ),
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


def visible(trial_id="pilot--one--r1--A", stopped_sha256="a" * 64):
    return {
        "schema_version": "evalopt.workflow-visible.v1",
        "trial_id": trial_id,
        "stopped_sha256": stopped_sha256,
        "observed_at": "2026-10-08T00:00:00+00:00",
        "required_gates": ["tests"],
        "gates": [
            {
                "name": "tests",
                "status": "PASS",
                "evidence_sha256": bytes_digest(b"check passed"),
                "producer": "controller",
            }
        ],
        "tests_weakened": False,
        "boundary_violations": [],
        "unsupported_claims": [],
    }


def store(tmp_path):
    schedule = build_schedule([task()], "pilot")
    result = CampaignStore(tmp_path / "campaign", schedule)
    return result, schedule[0]["trial_id"]


def completed_store(tmp_path):
    result, trial_id = store(tmp_path)
    number = result.start_attempt(trial_id)
    stopped = result.capture_stopped(trial_id, number, {"patch.diff": b"diff", "final.txt": b"done"})
    observation = visible(trial_id, stopped)
    result.record_visible(trial_id, number, observation, {"tests.log": b"check passed"})
    result.decide(trial_id, number)
    result.record_grade(trial_id, number, {"valid_completion": True, "functional_success": True})
    result.finish_attempt(trial_id, number, "completed")
    return result, trial_id


def test_schedule_has_registered_sizes_repetitions_and_matched_blocks():
    value = manifest()
    assert validate_manifest(value, require_full=True) == value
    schedules = {stage: build_schedule(value["tasks"], stage) for stage in ("pilot", "heldout", "transfer")}
    assert {stage: len(rows) for stage, rows in schedules.items()} == {
        "pilot": 36,
        "heldout": 432,
        "transfer": 72,
    }
    assert schedules["pilot"] == build_schedule(list(reversed(value["tasks"])), "pilot")
    rows = schedules["heldout"]
    for offset in range(0, len(rows), 3):
        block = rows[offset : offset + 3]
        assert {row["arm"] for row in block} == set("ABC")
        assert len({(row["task_id"], row["repetition"]) for row in block}) == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(hidden_grade=True),
        lambda value: value["runtime"].update(auth_route="api"),
        lambda value: value["runtime"].update(reasoning_effort="high"),
        lambda value: value["tasks"].append(value["tasks"][0]),
        lambda value: value["limits"].update(infrastructure_retries=2),
        lambda value: value["pins"].update(skill_sha256=None),
        lambda value: value["tasks"][0].update(task_id="../outside"),
        lambda value: value["tasks"][0].update(agent_seconds=True),
    ],
)
def test_manifest_rejects_drift_and_unresolved_freeze(change):
    value = manifest()
    change(value)
    with pytest.raises(ValueError):
        validate_manifest(value, require_full=True)


def test_draft_allows_unresolved_content_but_never_changed_source():
    value = manifest()
    value["pins"]["skill_sha256"] = None
    validate_manifest(value)
    value["pins"]["upstream_commit"] = "c" * 40
    with pytest.raises(ValueError, match="source pin"):
        validate_manifest(value)


def test_original_and_one_infrastructure_retry_are_retained(tmp_path):
    campaign, trial_id = store(tmp_path)
    assert campaign.start_attempt(trial_id) == 1
    with pytest.raises(ValueError, match="running"):
        campaign.start_attempt(trial_id)
    campaign.finish_attempt(trial_id, 1, "infra_failure", error_code="controller_interrupted")
    assert campaign.start_attempt(trial_id) == 2
    campaign.finish_attempt(trial_id, 2, "infra_failure", error_code="container_start")
    with pytest.raises(FileExistsError):
        campaign.start_attempt(trial_id)
    assert campaign.verify_attempt(trial_id, 1)["verified"]
    assert campaign.verify_attempt(trial_id, 2)["verified"]
    resumed = CampaignStore(campaign.root, list(campaign.trials.values()))
    assert resumed.statuses()[0]["attempts"] == 2


@pytest.mark.parametrize("failure_file", ["finish.json", "manifest.json"])
def test_interrupted_finalization_replays_frozen_intent_without_losing_attempt(
    tmp_path, monkeypatch, failure_file
):
    campaign, trial_id = store(tmp_path)
    campaign.start_attempt(trial_id)
    original = storage.write_once

    def interrupted(path, value):
        if path.name == failure_file:
            raise RuntimeError("simulated controller interruption")
        original(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(storage, "write_once", interrupted)
        with pytest.raises(RuntimeError, match="interruption"):
            campaign.finish_attempt(trial_id, 1, "infra_failure", error_code="controller_interrupted")
    intent_path = campaign.root / "trials" / trial_id / "attempt-1/finalize.json"
    frozen_intent = intent_path.read_bytes()
    resumed = CampaignStore(campaign.root, list(campaign.trials.values()))
    assert resumed.recover_attempt(trial_id, 1)["verified"]
    assert intent_path.read_bytes() == frozen_intent
    assert resumed.start_attempt(trial_id) == 2
    assert resumed.export_rows()[0]["status"] == "running_or_interrupted"


def test_interrupted_finalization_recovery_rejects_changed_original_evidence(tmp_path, monkeypatch):
    campaign, trial_id = store(tmp_path)
    campaign.start_attempt(trial_id)
    campaign.capture_stopped(trial_id, 1, {"candidate.txt": b"original"})
    original = storage.write_once

    def interrupted(path, value):
        if path.name == "manifest.json":
            raise RuntimeError("simulated controller interruption")
        original(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(storage, "write_once", interrupted)
        with pytest.raises(RuntimeError):
            campaign.finish_attempt(trial_id, 1, "infra_failure", error_code="controller_interrupted")
    candidate = campaign.root / "trials" / trial_id / "attempt-1/agent/candidate.txt"
    candidate.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed"):
        campaign.recover_attempt(trial_id, 1)
    with pytest.raises(ValueError, match="changed"):
        campaign.start_attempt(trial_id)


def test_interruption_between_attempt_directory_and_start_record_is_recoverable(tmp_path, monkeypatch):
    campaign, trial_id = store(tmp_path)
    original = storage.write_once

    def interrupted(path, value):
        if path.name == "start.json":
            raise RuntimeError("simulated controller interruption")
        original(path, value)

    with monkeypatch.context() as patch:
        patch.setattr(storage, "write_once", interrupted)
        with pytest.raises(RuntimeError):
            campaign.start_attempt(trial_id)
    assert campaign.recover_attempt(trial_id, 1)["verified"]
    attempt = campaign.root / "trials" / trial_id / "attempt-1"
    assert json.loads((attempt / "start.json").read_text())["recovered_before_dispatch"]
    assert json.loads((attempt / "finish.json").read_text())["error_code"] == "controller_interrupted"
    assert campaign.start_attempt(trial_id) == 2


@pytest.mark.parametrize("status", ["agent_failure", "timeout", "budget_exhausted"])
def test_agent_failure_never_retries(tmp_path, status):
    campaign, trial_id = store(tmp_path)
    campaign.start_attempt(trial_id)
    campaign.finish_attempt(trial_id, 1, status)
    with pytest.raises(ValueError, match="infrastructure"):
        campaign.start_attempt(trial_id)
    assert campaign.export_rows()[0]["valid_completion"] is False


def test_grade_cannot_precede_policy_and_missing_logs_cannot_authenticate(tmp_path):
    campaign, trial_id = store(tmp_path)
    campaign.start_attempt(trial_id)
    stopped = campaign.capture_stopped(trial_id, 1, {"success.json": b'{"passed":true}'})
    with pytest.raises(FileNotFoundError):
        campaign.record_grade(trial_id, 1, {"valid_completion": True})
    with pytest.raises(ValueError, match="log missing"):
        campaign.record_visible(trial_id, 1, visible(trial_id, stopped), {})
    with pytest.raises(ValueError, match="lacks"):
        campaign.finish_attempt(trial_id, 1, "completed")


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(hidden_grade={"success": True}),
        lambda value: value["gates"][0].update(producer="agent"),
        lambda value: value["gates"].append(copy.deepcopy(value["gates"][0])),
        lambda value: value["gates"][0].update(official_task_success=True),
        lambda value: value.update(required_gates=[]),
    ],
)
def test_hidden_grade_or_agent_authority_cannot_enter_policy(change):
    value = visible()
    change(value)
    with pytest.raises(ValueError):
        evaluate_policies(value)


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(tests_weakened=True),
        lambda value: value.update(boundary_violations=["frozen-file-changed"]),
        lambda value: value.update(unsupported_claims=["unrun-test-success"]),
        lambda value: value["gates"][0].update(status="FAIL"),
        lambda value: value.update(gates=[]),
    ],
)
def test_minimal_baseline_is_not_weakened_to_favor_kernel(change):
    value = visible()
    change(value)
    result = evaluate_policies(value)
    assert result["U"]["accepted"] is True
    assert result["M"]["accepted"] is False
    assert result["G"]["accepted"] is False
    assert replay_policies(value, result)


def test_completed_evidence_replays_and_mutation_is_detected(tmp_path):
    campaign, trial_id = completed_store(tmp_path)
    assert campaign.verify_attempt(trial_id, 1)["kernel_replay"] is True
    assert campaign.export_rows()[0]["valid_completion"] is True
    path = campaign.root / "trials" / trial_id / "attempt-1" / "agent/patch.diff"
    path.write_bytes(b"mutated")
    with pytest.raises(ValueError, match="changed"):
        campaign.verify_attempt(trial_id, 1)


def test_missing_artifact_duplicate_trial_and_changed_schedule_fail(tmp_path):
    campaign, trial_id = completed_store(tmp_path)
    with pytest.raises(ValueError, match="infrastructure"):
        campaign.start_attempt(trial_id)
    (campaign.root / "trials" / trial_id / "attempt-1/controller/tests.log").unlink()
    with pytest.raises(ValueError, match="missing"):
        campaign.verify_attempt(trial_id, 1)
    schedule = list(campaign.trials.values())
    schedule[0] = {**schedule[0], "agent_seconds": 500}
    with pytest.raises(ValueError, match="schedule changed"):
        CampaignStore(campaign.root, schedule)


def event(agent_id="root", parent_id=None, scope="agent_exclusive", roster=None):
    return {
        "agent_id": agent_id,
        "parent_id": parent_id,
        "scope": scope,
        "input_tokens": 10,
        "output_tokens": 3,
        "model_calls": 1,
        "tool_calls": 2,
        "wall_seconds": 5.0,
        "roster": roster or ["root", "child"],
        "complete": True,
    }


def test_child_usage_is_complete_and_never_double_counted():
    events = [event(), event("child", "root")]
    assert summarize_usage(events)["input_tokens"] == 20
    events[0]["scope"] = "trial_inclusive"
    events[0]["input_tokens"] = 20
    assert summarize_usage(events)["input_tokens"] == 20
    events[0]["scope"] = "agent_exclusive"
    with pytest.raises(ValueError, match="missing child"):
        summarize_usage(events[:1])
    with pytest.raises(ValueError, match="duplicate"):
        summarize_usage(events + [events[1]])
    events[1]["scope"] = "trial_inclusive"
    with pytest.raises(ValueError, match="overlapping"):
        summarize_usage(events)


def native_log(agent_id, parent=None, spawn_child=None, copied_usage=None):
    source = (
        "exec"
        if parent is None
        else {
            "subagent": {
                "thread_spawn": {"parent_thread_id": parent, "depth": 1, "agent_path": "/root/child"}
            }
        }
    )
    records = [
        {
            "timestamp": "2026-10-08T00:00:00Z",
            "type": "session_meta",
            "payload": {"id": agent_id, "source": source},
        }
    ]
    if copied_usage:
        records += copied_usage
    records.append(
        {
            "timestamp": "2026-10-08T00:00:00Z",
            "type": "event_msg",
            "payload": {"type": "task_started", "turn_id": agent_id},
        }
    )
    if spawn_child:
        records += [
            {
                "type": "response_item",
                "payload": {"type": "function_call", "name": "spawn_agent", "call_id": "spawn-1"},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "spawn-1",
                    "output": json.dumps({"task_name": "/root/child"}),
                },
            },
        ]
    records += [
        {
            "type": "token_usage_record",
            "payload": {
                "thread_id": agent_id,
                "turn_id": agent_id,
                "response_id": f"response-{agent_id}",
                "usage": {"input_tokens": 10, "output_tokens": 2},
            },
        },
        {
            "type": "event_msg",
            "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 999999}}},
        },
        {
            "timestamp": "2026-10-08T00:00:04Z",
            "type": "event_msg",
            "payload": {"type": "task_complete", "turn_id": agent_id},
        },
    ]
    return records


def test_native_logs_exclude_inherited_usage_and_detect_missing_child(tmp_path):
    root = native_log("root", spawn_child=True)
    child = native_log("child", "root", copied_usage=root)
    for name, records in (("root", root), ("child", child)):
        (tmp_path / f"{name}.jsonl").write_text("\n".join(json.dumps(row) for row in records))
    summary = summarize_usage(parse_native_usage(tmp_path))
    assert summary["input_tokens"] == 20
    assert summary["model_calls"] == 2
    assert summary["tool_calls"] == 1
    (tmp_path / "child.jsonl").unlink()
    with pytest.raises(ValueError, match="roster"):
        parse_native_usage(tmp_path)


def test_native_completed_unmetered_followup_fails_accounting(tmp_path):
    records = native_log("root")
    records += [
        {
            "timestamp": "2026-10-08T00:00:05Z",
            "type": "event_msg",
            "payload": {"type": "task_started", "turn_id": "unmetered-turn"},
        },
        {"type": "turn_context", "payload": {"turn_id": "unmetered-turn"}},
        {
            "type": "response_item",
            "payload": {"type": "function_call", "name": "exec_command", "call_id": "omitted-call"},
        },
        {
            "timestamp": "2026-10-08T00:00:10Z",
            "type": "event_msg",
            "payload": {"type": "task_complete", "turn_id": "unmetered-turn"},
        },
    ]
    (tmp_path / "root.jsonl").write_text("\n".join(json.dumps(row) for row in records))
    with pytest.raises(ValueError, match="owned turn roster"):
        parse_native_usage(tmp_path)


@pytest.mark.parametrize(
    "field,new_value",
    [("task_sha256", "f" * 64), ("grader_sha256", "e" * 64), ("agent_seconds", 599), ("ordinal", 999)],
)
def test_analysis_rejects_changed_content_or_execution_identity(field, new_value):
    schedule = build_schedule(manifest()["tasks"], "heldout")
    rows = outcome_rows(schedule)
    rows[0][field] = new_value
    with pytest.raises(ValueError, match="identity"):
        analyze_workflows(rows, schedule, resamples=100)


def outcome_rows(schedule, *, uniform=None):
    rows = []
    for row in schedule:
        i = int(row["task_id"].split("-")[-1])
        # Heterogeneous positive task effects, while ordinary capability has small two-sided variation.
        valid = uniform if uniform is not None else (i % 4 == 0 if row["arm"] == "B" else i % 4 != 3)
        functional = (i % 5 != 0) if row["arm"] == "B" else (i % 5 != 1)
        rows.append(
            {
                **row,
                "status": "completed",
                "valid_completion": valid,
                "functional_success": functional,
                "unsupported_success": False,
                "incorrect_refusal": False,
                "boundary_violation": False,
            }
        )
    return rows


def test_analysis_task_pairing_is_deterministic_and_missing_sensitivity_is_unfavorable():
    schedule = build_schedule(manifest()["tasks"], "heldout")
    rows = outcome_rows(schedule)
    first = analyze_workflows(rows, schedule, resamples=300)
    assert first == analyze_workflows(list(reversed(rows)), schedule, resamples=300)
    assert first["primary"]["tasks"] == 48
    assert first["primary"]["difference"] == 0.5
    assert not first["scoped_positive_headline_permitted"]  # Nonregistered resample count.
    for row in rows:
        if row["arm"] == "C" and row["task_id"].endswith("-1"):
            row["status"] = "infra_failure"
    changed = analyze_workflows(rows, schedule, resamples=300)
    assert changed["conservative_missing_C_fail_B_pass"]["difference"] < first["primary"]["difference"]
    assert changed["metrics"]["C"]["valid_completion"]["missing_trials"] == 18


def test_degenerate_perfect_evidence_does_not_permit_headline():
    schedule = build_schedule(manifest()["tasks"], "heldout")
    rows = outcome_rows(schedule, uniform=True)
    result = analyze_workflows(rows, schedule, resamples=100)
    assert result["primary"]["degenerate"]
    assert not result["overall_upgrade_permitted"]
    assert not result["scoped_positive_headline_permitted"]
    with pytest.raises(ValueError, match="duplicate"):
        analyze_workflows(rows + [rows[0]], schedule, resamples=100)


def test_repeated_attempts_are_not_independent_tasks_and_cluster_strata_cannot_cross():
    schedule = build_schedule(manifest()["tasks"], "heldout")
    rows = outcome_rows(schedule)
    for row in rows:
        if row["category"] == CATEGORIES[0]:
            row["cluster_id"] = "one-shared-source"
    result = analyze_workflows(rows, resamples=100)
    assert result["primary"]["clusters"] == 41
    assert not result["primary"]["sufficient"]
    for row in rows:
        row["cluster_id"] = "same-source"
    with pytest.raises(ValueError, match="crosses"):
        analyze_workflows(rows, resamples=100)


def test_registered_positive_rule_and_ordinary_guardrail_are_separate():
    schedule = build_schedule(manifest()["tasks"], "heldout")
    rows = outcome_rows(schedule)
    result = analyze_workflows(rows, schedule)
    assert result["registered_analysis_conditions"]
    assert result["scoped_positive_headline_permitted"]
    assert not result["overall_upgrade_permitted"]  # Ordinary NI is not demonstrated.
    assert result["ordinary_functional_noninferiority"]["tasks"] == 16


def test_agent_failure_does_not_overwrite_hidden_functional_grade():
    schedule = build_schedule(manifest()["tasks"], "heldout")
    rows = outcome_rows(schedule)
    for row in rows:
        row["functional_success"] = True
    rows[0]["status"] = "timeout"
    result = analyze_workflows(rows, schedule, resamples=100)
    assert result["metrics"][rows[0]["arm"]]["functional_success"]["category_macro_task_mean"] == 1


def test_kernel_reject_everything_has_zero_coverage_and_full_false_rejection():
    rejected = {policy: {"accepted": False, "status": "UNVERIFIED"} for policy in "UMG"}
    rows = [
        {
            "trial_id": "one",
            "policies": rejected,
            "valid_completion": True,
            "artifact_valid": True,
            "replay": dict.fromkeys("UMG", True),
        },
        {
            "trial_id": "two",
            "policies": rejected,
            "valid_completion": False,
            "artifact_valid": True,
            "replay": dict.fromkeys("UMG", True),
        },
        {"trial_id": "missing", "artifact_valid": False},
    ]
    result = summarize_kernel(rows)["policies"]["G"]
    assert result["approval_coverage"] == 0
    assert result["false_rejection_rate"] == 1
    assert result["artifact_failures"] == 1
    assert result["abstentions"] == 2
    assert result["replay_fidelity"] == 1
