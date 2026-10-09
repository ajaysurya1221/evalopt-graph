"""Versioned authored accounting integration; no native agents or model calls."""

from __future__ import annotations

import asyncio
import copy
import sys
from functools import partial
from pathlib import Path

import pytest

from test_skill_workflow_partial_accounting import native_session, write_sessions
from test_skill_workflow_scheduler import campaign, executor
from test_skill_workflow_scheduler import scheduling as scheduling_fixture

scheduling = scheduling_fixture
BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
from runtime import accounting_policy as policy  # noqa: E402
from runtime import harbor_campaign  # noqa: E402


@pytest.fixture
def registered():
    return policy.build_policy(
        {
            "schema_version": "evalopt.pilot-evidence.v2",
            "registration_sha256": "a" * 64,
            "accounting": {
                "rules_sha256": policy.digest(policy.RULES),
                "amendment_sha256": "b" * 64,
                "resource_report_sha256": "c" * 64,
            },
        },
        "d" * 64,
    )


def usage(root, registered, *, complete=False, runtime=True):
    write_sessions(root, native_session("root", ending="task_complete" if complete else "turn_aborted"))
    return {**policy.collect_usage(root, registered), "runtime_valid": runtime}


def test_collection_keeps_strict_totals_or_only_partial_lower_bounds(tmp_path, registered):
    complete = usage(tmp_path / "complete", registered, complete=True)
    partial_usage = usage(tmp_path / "partial", registered)
    assert complete["input_tokens"] == 10 and complete["child_usage_complete"] is True
    assert "input_tokens" not in partial_usage and partial_usage["child_usage_complete"] is False
    assert partial_usage["accounting"]["derived"]["lower_bounds"]["input_tokens"] == 10
    assert policy.continuation_reason({"usage": partial_usage}, registered) is None
    assert policy.validate_usage(complete, registered)["accounting_status"] == "complete"


def test_legacy_queue_stays_strict_and_registered_gate_applies_on_resume(scheduling, tmp_path, registered):
    destination, schedule, store, _ = scheduling
    attempt = store.start_attempt(schedule[0]["trial_id"])
    store.finish_attempt(
        schedule[0]["trial_id"], attempt, "agent_failure", usage=usage(tmp_path / "sessions", registered)
    )
    options = {"retry_infrastructure": False, "resume_quota": False, "recover_interrupted": False}
    assert campaign._dispatch_queue(store, schedule, **options)[1] == "usage_accounting_requires_remediation"
    queue, reason, _ = campaign._dispatch_queue(
        store, schedule, usage_gate=partial(policy.continuation_reason, policy=registered), **options
    )
    assert reason is None and schedule[0] not in queue
    assert len(queue) == len(schedule) - 1


def test_registered_gate_applies_after_every_dispatch(scheduling, monkeypatch, tmp_path, registered):
    destination, schedule, _, _ = scheduling
    good = usage(tmp_path / "partial", registered)
    bad = copy.deepcopy(good)
    bad["accounting"]["policy_sha256"] = "f" * 64
    called = executor(monkeypatch, [("agent_failure", None, good), ("agent_failure", None, bad)])
    result = asyncio.run(
        campaign.run_pilot(
            destination, Path("upstream"), usage_gate=partial(policy.continuation_reason, policy=registered)
        )
    )
    assert called == [row["trial_id"] for row in schedule[:2]]
    assert result["scheduler"]["reason"] == "accounting_policy_evidence_requires_remediation"
    again = asyncio.run(
        campaign.run_pilot(
            destination, Path("upstream"), usage_gate=partial(policy.continuation_reason, policy=registered)
        )
    )
    assert again["scheduler"]["reason"] == result["scheduler"]["reason"]
    assert len(called) == 2


def test_classified_infrastructure_retry_remains_explicit_and_once(
    scheduling, monkeypatch, tmp_path, registered
):
    destination, schedule, store, _ = scheduling
    measured = usage(tmp_path / "partial", registered)
    called = executor(
        monkeypatch, [("infra_failure", "container_start", {}), ("agent_failure", None, measured)]
    )
    gate = partial(policy.continuation_reason, policy=registered)
    assert (
        asyncio.run(campaign.run_pilot(destination, Path("upstream"), usage_gate=gate))["scheduler"]["reason"]
        == "infrastructure_failure_requires_inspection"
    )
    assert (
        asyncio.run(campaign.run_pilot(destination, Path("upstream"), usage_gate=gate))["scheduler"]["reason"]
        == "infrastructure_retry_requires_explicit_resume"
    )
    asyncio.run(
        campaign.run_pilot(destination, Path("upstream"), limit=1, usage_gate=gate, retry_infrastructure=True)
    )
    assert called == [schedule[0]["trial_id"]] * 2
    assert store.statuses()[0]["attempts"] == 2


def test_policy_source_rejects_before_runtime_dependency_or_attempt_creation(tmp_path, registered):
    registered["source_pins"]["strict_parser_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="source"):
        asyncio.run(
            harbor_campaign.execute_trial(
                {}, None, tmp_path, tmp_path, "image", "verifier", accounting_policy=registered
            )
        )
    assert list(tmp_path.iterdir()) == []


def test_rules_have_strict_boolean_types_and_no_mutable_alias(registered):
    registered["rules"]["runtime_valid_required"] = 1
    with pytest.raises(ValueError, match="unsupported"):
        policy.validate_policy(registered)
    assert policy.RULES["runtime_valid_required"] is True
    registered["rules"]["accepted_accounting"].append("unavailable")
    assert policy.RULES["accepted_accounting"] == ["complete", "partial"]


def test_resource_extension_counts_retries_partial_and_runtime_blocked_usage_once(tmp_path, registered):
    complete = usage(tmp_path / "complete", registered, complete=True)
    partial_usage = usage(tmp_path / "partial", registered, runtime=False)
    schedule = [{"trial_id": "task", "arm": "C"}, {"trial_id": "pending", "arm": "C"}]
    attempts = [
        {
            "trial_id": "task",
            "attempt": 1,
            "artifact_valid": True,
            "status": "infra_failure",
            "error_code": "controller_interrupted",
            "usage": {},
            "accounting_context": {"stopped_output_retained": False, "grade_retained": False},
        },
        {
            "trial_id": "task",
            "attempt": 2,
            "artifact_valid": True,
            "status": "agent_failure",
            "error_code": None,
            "usage": partial_usage,
        },
    ]
    report = campaign._all_attempt_resources(attempts, schedule, accounting_policy=registered)[
        "registered_accounting"
    ]
    arm = report["arms"]["C"]
    assert arm["retained_attempts"] == 2 and arm["unavailable_accounting_attempts"] == 1
    assert arm["observed_lower_bounds"]["input_tokens"] == 10
    assert arm["partial_attempts_lower_bounds"]["input_tokens"] == 10
    assert arm["trials_without_attempts"] == 1
    assert arm["runtime_unverified_attempts"] == 2
    assert not report["efficiency_comparison_eligible"]
    attempts[1]["usage"] = complete
    assert (
        policy.summarize_resources(attempts, schedule, policy.digest(registered))["arms"]["C"][
            "complete_attempts_exact_totals"
        ]["input_tokens"]
        == 10
    )
    with pytest.raises(ValueError, match="duplicate"):
        policy.summarize_resources(attempts + attempts[1:], schedule, policy.digest(registered))


@pytest.mark.parametrize(
    "status,error,stopped,graded",
    [
        ("completed", None, True, True),
        ("timeout", None, True, True),
        ("infra_failure", "verifier_infrastructure", True, False),
        ("infra_failure", "container_start", True, False),
        ("infra_failure", "controller_interrupted", True, True),
    ],
)
def test_missing_nested_accounting_is_not_a_general_infrastructure_exception(
    registered, status, error, stopped, graded
):
    row = {
        "artifact_valid": True,
        "status": status,
        "error_code": error,
        "usage": {},
        "accounting_context": {"stopped_output_retained": stopped, "grade_retained": graded},
    }
    with pytest.raises(ValueError):
        policy.validate_attempt(row, registered)


def test_present_malformed_accounting_never_uses_recovery_exception(registered):
    row = {
        "artifact_valid": True,
        "status": "infra_failure",
        "error_code": "controller_interrupted",
        "usage": {"accounting": None},
        "accounting_context": {"stopped_output_retained": False, "grade_retained": False},
    }
    with pytest.raises(ValueError):
        policy.validate_attempt(row, registered)


def test_context_is_derived_from_verified_store_without_changing_legacy_output(scheduling, registered):
    _, schedule, store, _ = scheduling
    trial = schedule[0]["trial_id"]
    path = store.root / "trials" / trial / "attempt-1"
    path.mkdir(parents=True)
    store.recover_attempt(trial, 1)
    _, _, legacy = campaign._report_rows(store, schedule)
    _, _, current = campaign._report_rows(store, schedule, accounting_policy=registered)
    assert "accounting_context" not in legacy[0]
    assert current[0]["accounting_context"] == {"stopped_output_retained": False, "grade_retained": False}
    assert policy.validate_attempt(current[0], registered) is None
    before = campaign._all_attempt_resources(legacy, schedule)
    after = campaign._all_attempt_resources(current, schedule, accounting_policy=registered)
    assert {key: value for key, value in after.items() if key != "registered_accounting"} == before


def test_infrastructure_retry_cannot_bypass_present_invalid_provenance(
    scheduling, monkeypatch, tmp_path, registered
):
    destination, schedule, store, _ = scheduling
    bad = usage(tmp_path / "bad", registered)
    bad["accounting"]["derived"]["delegation_boundary_status"] = "unverified"
    called = executor(monkeypatch, [("infra_failure", "container_transport", bad)])
    gate = partial(policy.continuation_reason, policy=registered)
    result = asyncio.run(campaign.run_pilot(destination, Path("upstream"), usage_gate=gate))
    assert result["scheduler"]["reason"] == "accounting_policy_evidence_requires_remediation"
    again = asyncio.run(
        campaign.run_pilot(
            destination, Path("upstream"), usage_gate=gate, retry_infrastructure=True, resume_quota=True
        )
    )
    assert again["scheduler"]["reason"] == result["scheduler"]["reason"]
    assert called == [schedule[0]["trial_id"]]
    assert store.statuses()[0]["attempts"] == 1


def test_all_retained_attempts_are_checked_before_pending_dispatch(scheduling, tmp_path, registered):
    _, schedule, store, _ = scheduling
    trial = schedule[0]["trial_id"]
    first = store.start_attempt(trial)
    store.finish_attempt(
        trial, first, "infra_failure", error_code="verifier_infrastructure", usage={"runtime_valid": True}
    )
    second = store.start_attempt(trial)
    store.finish_attempt(trial, second, "agent_failure", usage=usage(tmp_path / "good", registered))
    queue, reason, blocked = campaign._dispatch_queue(
        store,
        schedule,
        retry_infrastructure=True,
        resume_quota=True,
        recover_interrupted=False,
        usage_gate=partial(policy.continuation_reason, policy=registered),
    )
    assert queue == [] and blocked == trial
    assert reason == "accounting_policy_evidence_requires_remediation"


def test_complete_counter_boolean_cannot_alias_integer(tmp_path, registered):
    measured = usage(tmp_path / "complete", registered, complete=True)
    measured["model_calls"] = True
    with pytest.raises(ValueError, match="top-level exact usage"):
        policy.validate_usage(measured, registered)
