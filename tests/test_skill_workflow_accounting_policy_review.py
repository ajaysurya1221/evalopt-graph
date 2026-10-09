"""Independent later-stage accounting gates; synthetic logs, no model calls."""

from __future__ import annotations

import asyncio
import copy
import shutil
import sys
from pathlib import Path

import pytest

import test_skill_workflow_amendment_review as native
import test_skill_workflow_heldout as heldout_support
import test_skill_workflow_scheduler as scheduling_support

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
from lib.common import bytes_digest, canonical_bytes, digest  # noqa: E402
from runtime import accounting_policy as policy  # noqa: E402


@pytest.fixture
def registered_policy():
    return policy.validate_policy(
        {
            "schema_version": "evalopt.campaign-accounting-policy.v1",
            "rules": copy.deepcopy(policy.RULES),
            "source_pins": policy.source_pins(),
            "approval": {
                key: digest(key)
                for key in (
                    "pilot_registration_sha256",
                    "pilot_review_sha256",
                    "accounting_amendment_sha256",
                    "accounting_report_sha256",
                )
            },
        }
    )


def observed(root, registered, *, ending=8, child=True, metered=True):
    logs = {"parent": native.session("parent", children=("child",) if child else (), aborted=not child)}
    if child:
        logs["child"] = native.session(
            "child", parent="parent", start=2, end=ending, aborted=True, metered=metered
        )
    native.write_sessions(root, logs)
    return {**policy.collect_usage(root, registered), "runtime_valid": True}


def test_review_partial_permission_has_one_explicit_policy_and_preserves_lower_bounds(
    tmp_path, registered_policy
):
    usage = observed(tmp_path, registered_policy)
    value = policy.validated_projection(usage, digest(registered_policy))
    assert value["accounting_status"] == "partial"
    assert value["lower_bounds"]["input_tokens"] == 20
    assert value["child_usage_complete"] is False
    assert value["efficiency_eligible"] is False
    assert all(key not in usage for key in (*policy.COUNTERS, "wall_seconds"))
    assert policy.continuation_reason({"usage": usage}, registered_policy) is None


@pytest.mark.parametrize(
    "source", ["partial_parser_sha256", "strict_parser_sha256", "admission_helper_sha256"]
)
def test_review_every_parser_or_admission_source_pin_is_required(registered_policy, source):
    registered_policy["source_pins"][source] = "f" * 64
    with pytest.raises(ValueError, match="source"):
        policy.validate_policy(registered_policy)


@pytest.mark.parametrize("mutation", ["missing", "different"])
def test_review_heldout_freeze_must_pin_accounting_identity_explicitly(tmp_path, registered_policy, mutation):
    content = canonical_bytes(registered_policy) + b"\n"
    (tmp_path / "accounting-policy.json").write_bytes(content)
    freeze = {"schema_version": "evalopt.heldout-freeze.v2"}
    if mutation == "different":
        freeze["accounting_policy_sha256"] = "f" * 64
    (tmp_path / "freeze.json").write_bytes(canonical_bytes(freeze))
    (tmp_path / "heldout-lock.json").write_bytes(
        canonical_bytes({"accounting-policy.json": bytes_digest(content)})
    )
    with pytest.raises(ValueError):
        policy.read_accounting_policy(tmp_path)


def test_review_valid_policy_cannot_be_injected_into_legacy_freeze(tmp_path, registered_policy):
    (tmp_path / "freeze.json").write_bytes(canonical_bytes({"schema_version": "evalopt.heldout-freeze.v1"}))
    assert policy.read_accounting_policy(tmp_path) is None
    (tmp_path / "accounting-policy.json").write_bytes(canonical_bytes(registered_policy))
    with pytest.raises(ValueError, match="not registered"):
        policy.read_accounting_policy(tmp_path)


def test_review_owned_aborted_reason_cannot_be_hidden_behind_forged_complete_flags(
    tmp_path, registered_policy
):
    usage = observed(tmp_path, registered_policy)
    value = usage["accounting"]["derived"]
    for agent in value["agents"]:
        agent["complete"] = True
    value.update(
        accounting_status="complete",
        child_usage_complete=True,
        efficiency_eligible=True,
        completeness_reasons=[],
    )
    value["complete_usage"] = {
        "schema_version": "evalopt.workflow-usage.v1",
        **value["lower_bounds"],
        "wall_seconds": 9,
        "agent_count": 2,
        "aggregation": "agent_exclusive",
        "child_usage_complete": True,
    }
    usage.update(value["complete_usage"])
    with pytest.raises(ValueError):
        policy.validated_projection(usage, digest(registered_policy))
    assert policy.continuation_reason({"usage": usage}, registered_policy) is not None


def test_review_child_without_end_cannot_claim_verified_delegation(tmp_path, registered_policy):
    usage = observed(tmp_path, registered_policy, ending=None)
    value = usage["accounting"]["derived"]
    assert value["delegation_boundary_status"] == "unverified"
    value["delegation_boundary_status"] = "verified"
    value["completeness_reasons"].remove("child_concurrency_unverified")
    with pytest.raises(ValueError):
        policy.validated_projection(usage, digest(registered_policy))


def test_review_zero_response_records_cannot_carry_positive_token_bounds(tmp_path, registered_policy):
    usage = observed(tmp_path, registered_policy, metered=False)
    value = usage["accounting"]["derived"]
    assert value["agents"][1]["lower_bounds"]["model_calls"] == 0
    value["agents"][1]["lower_bounds"]["input_tokens"] = 50
    value["lower_bounds"]["input_tokens"] += 50
    with pytest.raises(ValueError):
        policy.validated_projection(usage, digest(registered_policy))


@pytest.mark.parametrize("where", ["trial", "agent"])
def test_review_unregistered_reason_text_is_not_a_public_accounting_field(tmp_path, registered_policy, where):
    usage = observed(tmp_path, registered_policy)
    value = usage["accounting"]["derived"]
    reasons = (
        value["completeness_reasons"] if where == "trial" else value["agents"][1]["completeness_reasons"]
    )
    reasons.append("PRIVATE_NONCREDENTIAL_CONTEXT")
    reasons.sort()
    with pytest.raises(ValueError):
        policy.validated_projection(usage, digest(registered_policy))


@pytest.mark.parametrize("identity", [None, False, 1, "true"])
def test_review_partial_policy_requires_positive_observed_runtime_identity(
    tmp_path, registered_policy, identity
):
    usage = observed(tmp_path, registered_policy)
    usage["runtime_valid"] = identity
    assert (
        policy.continuation_reason({"usage": usage}, registered_policy)
        == "runtime_identity_requires_remediation"
    )


def test_review_other_policy_identity_cannot_admit_otherwise_valid_partial_usage(tmp_path, registered_policy):
    usage = observed(tmp_path, registered_policy)
    usage["accounting"]["policy_sha256"] = "f" * 64
    assert (
        policy.continuation_reason({"usage": usage}, registered_policy)
        == "accounting_policy_evidence_requires_remediation"
    )


def test_review_runtime_blocked_consumption_stays_in_all_attempt_resources(tmp_path, registered_policy):
    usage = observed(tmp_path, registered_policy)
    usage["runtime_valid"] = False
    schedule = [
        {"trial_id": "heldout--one--r1--B", "arm": "B"},
        {"trial_id": "heldout--one--r1--C", "arm": "C"},
    ]
    attempts = [{"trial_id": schedule[0]["trial_id"], "attempt": 1, "artifact_valid": True, "usage": usage}]
    report = policy.summarize_resources(attempts, schedule, digest(registered_policy))
    assert report["arms"]["B"]["observed_lower_bounds"]["input_tokens"] == 20
    assert report["arms"]["B"]["runtime_unverified_attempts"] == 1
    assert report["arms"]["C"]["trials_without_attempts"] == 1
    assert report["efficiency_comparison_eligible"] is False


def test_review_duplicate_attempts_cannot_inflate_known_consumption(tmp_path, registered_policy):
    usage = observed(tmp_path, registered_policy)
    schedule = [{"trial_id": "heldout--one--r1--C", "arm": "C"}]
    row = {"trial_id": schedule[0]["trial_id"], "attempt": 1, "artifact_valid": True, "usage": usage}
    with pytest.raises(ValueError, match="duplicate"):
        policy.summarize_resources([row, copy.deepcopy(row)], schedule, digest(registered_policy))


@pytest.fixture
def scheduler(tmp_path, monkeypatch):
    return scheduling_support.scheduling.__wrapped__(tmp_path, monkeypatch)


def gate(registered):
    return lambda finish: policy.continuation_reason(finish, registered)


def test_review_legacy_queue_still_rejects_partial_without_registered_gate(
    scheduler, tmp_path, registered_policy
):
    destination, schedule, store, _ = scheduler
    usage = observed(tmp_path / "logs", registered_policy)
    trial_id = schedule[0]["trial_id"]
    attempt = store.start_attempt(trial_id)
    store.finish_attempt(trial_id, attempt, "agent_failure", usage=usage)
    campaign = scheduling_support.campaign
    queue, reason, blocked = campaign._dispatch_queue(
        store,
        schedule,
        retry_infrastructure=False,
        resume_quota=False,
        recover_interrupted=False,
    )
    assert queue == [] and reason == "usage_accounting_requires_remediation" and blocked == trial_id
    queue, reason, blocked = campaign._dispatch_queue(
        store,
        schedule,
        retry_infrastructure=False,
        resume_quota=False,
        recover_interrupted=False,
        usage_gate=gate(registered_policy),
    )
    assert queue == schedule[1:] and reason is None and blocked is None
    assert store.statuses()[0]["attempts"] == 1


def test_review_policy_runs_both_after_dispatch_and_before_any_resume(
    scheduler, tmp_path, registered_policy, monkeypatch
):
    destination, schedule, store, _ = scheduler
    allowed = observed(tmp_path / "allowed", registered_policy)
    unknown = copy.deepcopy(allowed)
    unknown["runtime_valid"] = None
    called = scheduling_support.executor(
        monkeypatch,
        [
            ("agent_failure", None, allowed),
            ("agent_failure", None, unknown),
        ],
    )
    campaign = scheduling_support.campaign
    result = asyncio.run(
        campaign.run_pilot(destination, Path("upstream"), usage_gate=gate(registered_policy))
    )
    assert called == [row["trial_id"] for row in schedule[:2]]
    assert result["scheduler"]["reason"] == "runtime_identity_requires_remediation"
    result = asyncio.run(
        campaign.run_pilot(
            destination,
            Path("upstream"),
            usage_gate=gate(registered_policy),
            retry_infrastructure=True,
            resume_quota=True,
        )
    )
    assert len(called) == 2
    assert result["scheduler"]["reason"] == "runtime_identity_requires_remediation"
    assert all(row["attempts"] == 1 for row in store.statuses()[:2])


@pytest.mark.parametrize(
    "cause,expected",
    [
        ("container_start", "infrastructure_failure_requires_inspection"),
        ("subscription_exhausted", "subscription_exhausted"),
    ],
)
def test_review_preagent_failure_keeps_classification_and_requires_explicit_retry(
    scheduler, tmp_path, registered_policy, monkeypatch, cause, expected
):
    destination, schedule, store, _ = scheduler
    measured = (
        {"child_usage_complete": False}
        if cause == "container_start"
        else observed(tmp_path / "quota-logs", registered_policy)
    )
    called = scheduling_support.executor(monkeypatch, [("infra_failure", cause, measured)])
    campaign = scheduling_support.campaign
    contexts = []

    def checked_gate(finish):
        contexts.append(finish["accounting_context"])
        assert finish["artifact_valid"] is True
        assert finish["trial_id"] == schedule[0]["trial_id"]
        assert finish["attempt"] == 1
        return policy.continuation_reason(finish, registered_policy)

    result = asyncio.run(campaign.run_pilot(destination, Path("upstream"), usage_gate=checked_gate))
    assert result["scheduler"]["reason"] == expected
    queue, reason, _ = campaign._dispatch_queue(
        store,
        schedule,
        retry_infrastructure=False,
        resume_quota=False,
        recover_interrupted=False,
        usage_gate=checked_gate,
    )
    assert not queue and reason in {"infrastructure_retry_requires_explicit_resume", "subscription_exhausted"}
    queue, reason, _ = campaign._dispatch_queue(
        store,
        schedule,
        retry_infrastructure=True,
        resume_quota=True,
        recover_interrupted=False,
        usage_gate=checked_gate,
    )
    assert reason is None and queue[0]["trial_id"] == called[0]
    assert store.statuses()[0]["attempts"] == 1
    assert contexts == [{"stopped_output_retained": False, "grade_retained": False}] * 3


@pytest.mark.parametrize("cause", ["container_start", "subscription_exhausted", "controller_interrupted"])
def test_review_present_invalid_accounting_cannot_use_infrastructure_retry_exception(
    scheduler, tmp_path, registered_policy, monkeypatch, cause
):
    destination, schedule, store, _ = scheduler
    measured = observed(tmp_path / "invalid-infra", registered_policy)
    measured["accounting"]["policy_sha256"] = "f" * 64
    called = scheduling_support.executor(monkeypatch, [("infra_failure", cause, measured)])
    campaign = scheduling_support.campaign
    for _ in range(2):
        result = asyncio.run(
            campaign.run_pilot(
                destination,
                Path("upstream"),
                retry_infrastructure=True,
                resume_quota=True,
                usage_gate=gate(registered_policy),
            )
        )
        assert result["scheduler"]["reason"] == "accounting_policy_evidence_requires_remediation"
    assert called == [schedule[0]["trial_id"]]
    assert store.statuses()[0]["attempts"] == 1


@pytest.mark.parametrize("malformed", [[], "", 0, False])
def test_review_malformed_present_usage_is_not_absent_startup_telemetry(registered_policy, malformed):
    finish = {
        "status": "infra_failure",
        "error_code": "container_start",
        "artifact_valid": True,
        "accounting_context": {"stopped_output_retained": False, "grade_retained": False},
        "usage": malformed,
    }
    assert (
        policy.continuation_reason(finish, registered_policy)
        == "accounting_policy_evidence_requires_remediation"
    )
    with pytest.raises(ValueError):
        policy.validate_attempt(finish, registered_policy)


def test_review_invalid_first_attempt_cannot_hide_behind_valid_final_retry(
    scheduler, tmp_path, registered_policy
):
    _, schedule, store, _ = scheduler
    trial_id = schedule[0]["trial_id"]
    invalid = observed(tmp_path / "first", registered_policy)
    invalid["accounting"]["policy_sha256"] = "f" * 64
    first = store.start_attempt(trial_id)
    store.finish_attempt(trial_id, first, "infra_failure", error_code="container_start", usage=invalid)
    last = store.start_attempt(trial_id)
    store.finish_attempt(
        trial_id, last, "agent_failure", usage=observed(tmp_path / "second", registered_policy)
    )
    queue, reason, blocked = scheduling_support.campaign._dispatch_queue(
        store,
        schedule,
        retry_infrastructure=True,
        resume_quota=True,
        recover_interrupted=False,
        usage_gate=gate(registered_policy),
    )
    assert queue == [] and reason == "accounting_policy_evidence_requires_remediation"
    assert blocked == trial_id and store.statuses()[0]["attempts"] == 2


def test_review_strict_resource_schema_is_unchanged_without_new_policy():
    campaign = scheduling_support.campaign
    schedule = [{"trial_id": "pilot--one--r1--A", "arm": "A"}]
    rows = [
        {
            "trial_id": schedule[0]["trial_id"],
            "attempt": 1,
            "artifact_valid": True,
            "usage": scheduling_support.usage(),
        }
    ]
    expected = {
        "scope": "All retained attempts, including final attempts and infrastructure retries; do not add to final-attempt totals.",
        "arms": {
            "A": {
                "retained_attempts": 1,
                "accounted_attempts": 1,
                "unavailable_attempts": 0,
                "totals": {
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "model_calls": 1,
                    "tool_calls": 1,
                    "wall_seconds": 3.0,
                },
            }
        },
        "dollar_cost": None,
    }
    assert canonical_bytes(campaign._all_attempt_resources(rows, schedule)) == canonical_bytes(expected)


@pytest.fixture
def reviewed_v2_pilot(tmp_path, monkeypatch):
    import amended_pilot

    heldout = heldout_support.heldout
    original_finish = heldout.CampaignStore.finish_attempt
    finished = []

    def first_partial(self, trial_id, attempt, status, **kwargs):
        if not finished:
            kwargs["usage"] = {
                "child_usage_complete": False,
                "runtime_valid": True,
                "accounting_status": "unavailable",
            }
        finished.append(trial_id)
        return original_finish(self, trial_id, attempt, status, **kwargs)

    monkeypatch.setattr(heldout.CampaignStore, "finish_attempt", first_partial)
    pilot, review_path, store, schedule = heldout_support.reviewed_pilot.__wrapped__(tmp_path)
    review = heldout.read_json(review_path)
    identity = digest("independently constructed synthetic accounting amendment")
    root = pilot / amended_pilot.AMENDMENT
    sidecars = []
    for index, row in enumerate(schedule):
        trial_id = row["trial_id"]
        logs = pilot / "private-harbor" / trial_id / "attempt-1/harbor-synthetic/agent/sessions"
        logs.mkdir(parents=True)
        events = native.session("parent", end=3, aborted=index == 0)
        events.insert(
            3,
            native.record("response_item", {"type": "function_call", "name": "exec", "call_id": "tool-1"}, 1),
        )
        native.write_sessions(logs, {"parent": events})
        attempt = store.root / "trials" / trial_id / "attempt-1"
        finish = heldout.read_json(attempt / "finish.json")
        record = {
            "trial_id": trial_id,
            "attempt": 1,
            **finish,
            "finish_sha256": bytes_digest((attempt / "finish.json").read_bytes()),
            "manifest_sha256": bytes_digest((attempt / "manifest.json").read_bytes()),
        }
        sidecar = amended_pilot._derive(pilot, record, identity)
        assert sidecar["continuation_admissible"] is True
        heldout.write_once(root / "usage" / trial_id / "attempt-1.json", sidecar)
        sidecars.append(sidecar)

    def verified_boundary(actual_pilot, actual_identity):
        # The isolated bridge/journal is independently exercised by amendment
        # controls. Here all36 real synthetic store grades/UMG/resource records
        # remain available while only that prior verification boundary is stubbed.
        assert actual_pilot == pilot and actual_identity == identity
        return {
            "amendment": {
                "pilot_registration_sha256": review["pilot_registration_sha256"],
                "policy": amended_pilot.POLICY,
            },
            "info": {"schedule": schedule, "states": store.statuses()},
        }

    monkeypatch.setattr(amended_pilot, "verify", verified_boundary)
    report = amended_pilot.summarize_resources(
        identity,
        review["pilot_registration_sha256"],
        schedule,
        store.statuses(),
        sidecars,
        review["pilot_export_id"],
    )
    resource_identity = digest(report)
    heldout.write_once(root / "reports" / resource_identity / "resource-report.json", report)
    review.update(
        schema_version="evalopt.pilot-review.v2",
        checks=dict.fromkeys(heldout.REVIEW_CHECKS_V2, True),
        accounting={
            "amendment_sha256": identity,
            "resource_report_sha256": resource_identity,
            "rules_sha256": digest(policy.RULES),
        },
    )
    review_path.write_bytes(canonical_bytes(review))
    return heldout, pilot, review_path, store, schedule, root


def test_review_v2_pilot_requires_all36_real_graded_outcomes_and_preserves_partial_status(reviewed_v2_pilot):
    heldout, pilot, review, _, _, _ = reviewed_v2_pilot
    evidence = heldout.verify_pilot(pilot, review)
    assert evidence["schema_version"] == "evalopt.pilot-evidence.v2"
    assert evidence["scheduled_trials"] == 36
    assert evidence["accounting"]["complete_final_attempts"] == 35
    assert evidence["accounting"]["partial_final_attempts"] == 1
    assert evidence["accounting"]["unavailable_attempts"] == 0
    assert evidence["accounting"]["retained_attempts"] == 36


@pytest.mark.parametrize(
    "missing", ["pending", "grade.json", "policies.json", "visible.json", "stopped.json"]
)
def test_review_v2_review_flags_cannot_waive_pending_or_missing_grade_and_policy_evidence(
    reviewed_v2_pilot, missing
):
    heldout, pilot, review, store, schedule, _ = reviewed_v2_pilot
    attempt = store.root / "trials" / schedule[0]["trial_id"] / "attempt-1"
    if missing == "pending":
        shutil.rmtree(attempt)
    else:
        (attempt / missing).unlink()
    with pytest.raises((ValueError, OSError)):
        heldout.verify_pilot(pilot, review)


def test_review_v1_cannot_inherit_v2_partial_permission(reviewed_v2_pilot):
    heldout, pilot, review_path, _, _, _ = reviewed_v2_pilot
    review = heldout.read_json(review_path)
    review.update(schema_version="evalopt.pilot-review.v1", checks=dict.fromkeys(heldout.REVIEW_CHECKS, True))
    review.pop("accounting")
    review_path.write_bytes(canonical_bytes(review))
    with pytest.raises(ValueError, match="telemetry"):
        heldout.verify_pilot(pilot, review_path)


def test_review_v2_rejects_a_sidecar_marked_inadmissible(reviewed_v2_pilot):
    heldout, pilot, review, _, schedule, root = reviewed_v2_pilot
    path = root / "usage" / schedule[0]["trial_id"] / "attempt-1.json"
    value = heldout.read_json(path)
    value.update(
        continuation_admissible=False, continuation_blocker="delegation_boundary_requires_remediation"
    )
    path.write_bytes(canonical_bytes(value))
    with pytest.raises(ValueError, match="blocked"):
        heldout.verify_pilot(pilot, review)


def test_review_v2_rejects_rehashed_resource_report_with_wrong_denominator(reviewed_v2_pilot):
    heldout, pilot, review_path, _, _, root = reviewed_v2_pilot
    review = heldout.read_json(review_path)
    original = root / "reports" / review["accounting"]["resource_report_sha256"] / "resource-report.json"
    report = heldout.read_json(original)
    report["pending_trials"] = 1
    new_identity = digest(report)
    heldout.write_once(root / "reports" / new_identity / "resource-report.json", report)
    review["accounting"]["resource_report_sha256"] = new_identity
    review_path.write_bytes(canonical_bytes(review))
    with pytest.raises(ValueError, match="resource report"):
        heldout.verify_pilot(pilot, review_path)
