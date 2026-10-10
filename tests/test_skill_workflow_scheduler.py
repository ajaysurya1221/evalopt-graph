"""No-model scheduling tests: retained retries, quota pauses, identities, and exports."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
try:
    SPEC = importlib.util.spec_from_file_location("workflow_scheduler_under_test", BENCH / "campaign.py")
    assert SPEC is not None and SPEC.loader is not None
    campaign = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(campaign)
finally:
    sys.path.pop(0)


def usage(**changes):
    return {
        "input_tokens": 10,
        "output_tokens": 2,
        "model_calls": 1,
        "tool_calls": 1,
        "wall_seconds": 3.0,
        "agent_count": 1,
        "aggregation": "agent_exclusive",
        "child_usage_complete": True,
        "runtime_valid": True,
        **changes,
    }


def local_store(tmp_path):
    destination = tmp_path / "campaign"
    destination.mkdir()
    tasks = [
        {
            "task_id": f"task-{i}",
            "stage": "pilot",
            "category": "ordinary_bug_repair",
            "cluster_id": f"task-{i}",
            "agent_seconds": 600,
            "task_sha256": campaign.digest(f"task-{i}"),
            "grader_sha256": "b" * 64,
        }
        for i in range(2)
    ]
    schedule = campaign.build_schedule(tasks, "pilot")
    store = campaign.CampaignStore(destination / "evidence", schedule)
    return destination, schedule, store


@pytest.fixture
def scheduling(tmp_path, monkeypatch):
    destination, schedule, store = local_store(tmp_path)
    campaign.write_once(destination / "registration-lock.json", {"fixture": "offline only"})
    checks = []

    def verify(*_):
        checks.append(True)
        return {}, {"agent_image": "agent", "verifier_image": "verifier"}, schedule, store

    monkeypatch.setattr(campaign, "_verify_campaign", verify)
    monkeypatch.setattr(campaign, "subscription_environment", lambda: None)
    monkeypatch.setattr(
        campaign,
        "read_subscription_permission",
        lambda: {
            "schema_version": "evalopt.subscription-permission.v1",
            "ordinary_usage_allowed": True,
            "state": "allowed",
        },
    )
    monkeypatch.setattr(campaign, "report", lambda _: {"retained_trials": len(store.statuses())})
    return destination, schedule, store, checks


def executor(monkeypatch, results):
    called = []

    async def execute(row, store, *_):
        called.append(row["trial_id"])
        status, error_code, measured = results.pop(0) if results else ("agent_failure", None, usage())
        attempt = store.start_attempt(row["trial_id"])
        store.finish_attempt(row["trial_id"], attempt, status, error_code=error_code, usage=measured)
        return {
            **row,
            "status": status,
            "error_code": error_code,
            "valid_completion": False,
            "usage": measured,
        }

    monkeypatch.setattr(campaign, "execute_trial", execute)
    return called


def test_limited_run_resumes_without_repeating_agent_failures(scheduling, monkeypatch):
    destination, schedule, store, checks = scheduling
    called = executor(monkeypatch, [])
    first = asyncio.run(campaign.run_pilot(destination, Path("upstream"), limit=2))
    assert first["scheduler"]["status"] == "limited"
    second = asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert second["scheduler"]["status"] == "finished"
    assert called == [row["trial_id"] for row in schedule]
    assert all(state["attempts"] == 1 for state in store.statuses())
    assert len(checks) == 2 + 2 * len(schedule)  # Before and after every dispatch, plus each invocation.
    assert len(list((destination / "runs").glob("*/end.json"))) == 2


def test_only_explicit_resume_retries_infrastructure_once(scheduling, monkeypatch):
    destination, schedule, store, _ = scheduling
    called = executor(
        monkeypatch,
        [("infra_failure", "container_start", usage()), ("infra_failure", "container_transport", usage())],
    )
    first = asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert first["scheduler"]["reason"] == "infrastructure_failure_requires_inspection"
    second = asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert second["scheduler"]["reason"] == "infrastructure_retry_requires_explicit_resume"
    assert len(called) == 1
    third = asyncio.run(campaign.run_pilot(destination, Path("upstream"), retry_infrastructure=True))
    assert third["scheduler"]["status"] == "paused"
    assert store.statuses()[0]["attempts"] == 2
    asyncio.run(campaign.run_pilot(destination, Path("upstream"), retry_infrastructure=True))
    assert called.count(schedule[0]["trial_id"]) == 2
    assert store.verify_attempt(schedule[0]["trial_id"], 1)["verified"]


def test_quota_failure_blocks_new_trials_until_explicit_quota_resume(scheduling, monkeypatch):
    destination, schedule, store, _ = scheduling
    called = executor(
        monkeypatch, [("infra_failure", "subscription_exhausted", {"child_usage_complete": False})]
    )
    first = asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert first["scheduler"]["reason"] == "subscription_exhausted"
    second = asyncio.run(campaign.run_pilot(destination, Path("upstream"), retry_infrastructure=True))
    assert second["scheduler"]["reason"] == "subscription_exhausted"
    assert len(called) == 1
    third = asyncio.run(campaign.run_pilot(destination, Path("upstream"), limit=1, resume_quota=True))
    assert third["scheduler"]["status"] == "limited"
    assert called == [schedule[0]["trial_id"], schedule[0]["trial_id"]]
    assert store.statuses()[0]["attempts"] == 2


@pytest.mark.parametrize(
    "measured,reason",
    [
        (usage(runtime_valid=False), "runtime_identity_requires_remediation"),
        ({"child_usage_complete": False}, "usage_accounting_requires_remediation"),
    ],
)
def test_runtime_or_usage_failures_cannot_be_bypassed_with_retry_flags(
    scheduling, monkeypatch, measured, reason
):
    destination, _, store, _ = scheduling
    called = executor(monkeypatch, [("agent_failure", None, measured)])
    first = asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert first["scheduler"]["reason"] == reason
    second = asyncio.run(
        campaign.run_pilot(destination, Path("upstream"), retry_infrastructure=True, resume_quota=True)
    )
    assert second["scheduler"]["reason"] == reason
    assert len(called) == 1
    assert store.statuses()[0]["attempts"] == 1


def test_source_drift_after_dispatch_stops_before_next_trial(scheduling, monkeypatch):
    destination, schedule, store, _ = scheduling
    calls = []

    def verify(*_):
        calls.append(True)
        if len(calls) == 3:
            raise ValueError("source changed during trial")
        return {}, {"agent_image": "agent", "verifier_image": "verifier"}, schedule, store

    monkeypatch.setattr(campaign, "_verify_campaign", verify)
    executed = executor(monkeypatch, [])
    with pytest.raises(ValueError, match="source changed"):
        asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert len(executed) == 1
    stop = campaign.read_json(destination / "runs/run-0001/end.json")
    assert stop["status"] == "interrupted"
    assert stop["dispatched"] == executed


def test_no_second_scheduler_can_dispatch_same_campaign(scheduling):
    destination, *_ = scheduling
    with campaign._scheduler_lock(destination):
        with pytest.raises(ValueError, match="already running"):
            with campaign._scheduler_lock(destination):
                pytest.fail("second controller acquired the same campaign")


def test_unknown_interrupted_agent_is_not_reclassified_for_retry(scheduling, monkeypatch):
    destination, schedule, store, _ = scheduling
    store.start_attempt(schedule[0]["trial_id"])
    called = executor(monkeypatch, [])
    result = asyncio.run(
        campaign.run_pilot(destination, Path("upstream"), recover_interrupted=True, retry_infrastructure=True)
    )
    assert result["scheduler"]["reason"] == "interrupted_agent_requires_classification"
    assert not called
    assert store.statuses()[0]["attempts"] == 1


def finish_success(store, row):
    trial_id = row["trial_id"]
    attempt = store.start_attempt(trial_id)
    stopped = store.capture_stopped(trial_id, attempt, {"response.json": b'{"status":"done"}'})
    log = b"visible test passed"
    store.record_visible(
        trial_id,
        attempt,
        {
            "schema_version": "evalopt.workflow-visible.v1",
            "trial_id": trial_id,
            "stopped_sha256": stopped,
            "observed_at": "2026-10-08T00:00:00+00:00",
            "required_gates": ["tests"],
            "gates": [
                {
                    "name": "tests",
                    "status": "PASS",
                    "evidence_sha256": campaign.bytes_digest(log),
                    "producer": "controller",
                }
            ],
            "tests_weakened": False,
            "boundary_violations": [],
            "unsupported_claims": [],
        },
        {"tests.log": log},
    )
    store.decide(trial_id, attempt)
    store.record_grade(
        trial_id,
        attempt,
        {
            "valid_completion": True,
            "functional_success": True,
            "unsupported_success": False,
            "incorrect_refusal": False,
            "boundary_violation": False,
            "private_free_text": "must not export",
        },
    )
    store.finish_attempt(
        trial_id, attempt, "completed", usage={**usage(), "private_runtime_data": "must not export"}
    )


def test_reports_reproduce_immutable_exports_and_sanitize_nonmetric_fields(tmp_path):
    destination, schedule, store = local_store(tmp_path)
    finish_success(store, schedule[0])
    first = campaign.report(destination)
    second = campaign.report(destination)
    assert first["export_id"] == second["export_id"]
    previous = Path(first["export_directory"])
    rows = json.loads((previous / "outcomes.json").read_text())
    assert len(rows) == len(schedule)
    assert rows[0]["valid_completion"] is True
    assert "private_free_text" not in rows[0]
    assert "private_runtime_data" not in rows[0]["usage"]
    checksums = campaign.read_json(previous / "checksums.json")
    for name, expected in checksums["files"].items():
        assert campaign.bytes_digest((previous / name).read_bytes()) == expected
    finish_success(store, schedule[1])
    third = campaign.report(destination)
    assert third["export_id"] != first["export_id"]
    assert previous.is_dir()
    assert campaign.read_json(previous / "outcomes.json") == rows


def test_report_retains_artifact_failure_as_missing_not_a_dropped_trial(tmp_path):
    destination, schedule, store = local_store(tmp_path)
    finish_success(store, schedule[0])
    path = store.root / "trials" / schedule[0]["trial_id"] / "attempt-1/agent/response.json"
    path.write_bytes(b"changed after capture")
    result = campaign.report(destination)
    rows = campaign.read_json(Path(result["export_directory"]) / "outcomes.json")
    assert len(rows) == len(schedule)
    assert rows[0]["status"] == "artifact_failure"
    assert rows[0]["valid_completion"] is None
    assert result["attempts_recorded"] == 1
    assert not result["scoped_positive_headline_permitted"]


@pytest.mark.parametrize("terminal_status", ["timeout", "agent_failure", "budget_exhausted"])
def test_stopped_failure_preserves_independently_graded_functional_success(
    tmp_path, monkeypatch, terminal_status
):
    destination, schedule, store = local_store(tmp_path)
    original = store.finish_attempt

    def failed_finish(trial_id, attempt, _status, **kwargs):
        original(trial_id, attempt, terminal_status, **kwargs)

    monkeypatch.setattr(store, "finish_attempt", failed_finish)
    finish_success(store, schedule[0])
    result = campaign.report(destination)
    rows = campaign.read_json(Path(result["export_directory"]) / "outcomes.json")
    assert rows[0]["valid_completion"] is False
    assert rows[0]["functional_success"] is True
    metrics = result["stage_summaries"]["pilot"]["metrics"][schedule[0]["arm"]]
    assert metrics["valid_completion"]["category_macro_task_mean"] == 0
    assert metrics["functional_success"]["category_macro_task_mean"] == 1


def test_public_resources_retain_failed_attempt_consumption_without_double_counting(tmp_path):
    destination, schedule, store = local_store(tmp_path)
    trial_id = schedule[0]["trial_id"]
    attempt = store.start_attempt(trial_id)
    store.finish_attempt(
        trial_id,
        attempt,
        "infra_failure",
        error_code="verifier_infrastructure",
        usage=usage(input_tokens=100),
    )
    finish_success(store, schedule[0])
    result = campaign.report(destination)
    exported = Path(result["export_directory"])
    attempts = campaign.read_json(exported / "attempts.json")
    assert [item["usage"]["input_tokens"] for item in attempts] == [100, 10]
    rows = campaign.read_json(exported / "outcomes.json")
    assert rows[0]["usage"]["input_tokens"] == 10
    total = result["all_attempt_resources"]["arms"][schedule[0]["arm"]]
    assert total["totals"]["input_tokens"] == 110
    assert total["accounted_attempts"] == total["retained_attempts"] == 2


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    upstream = tmp_path / "upstream"
    (upstream / ".claude-plugin").mkdir(parents=True)
    (upstream / ".claude-plugin/plugin.json").write_text('{"skills":[]}')
    hashes = {}

    def identity(path):
        return hashes.get(str(path), campaign.digest(str(path)))

    monkeypatch.setattr(campaign, "source_identity", identity)
    monkeypatch.setattr(
        campaign,
        "run",
        lambda argv: SimpleNamespace(stdout=campaign.UPSTREAM_COMMIT if "rev-parse" in argv else ""),
    )
    monkeypatch.setattr(
        campaign,
        "image_identity",
        lambda name: name if name.startswith("sha256:") else "sha256:" + campaign.digest(name),
    )
    monkeypatch.setattr(campaign, "verify_readiness", lambda *_: {"fixture": "offline readiness controls"})
    monkeypatch.setattr(campaign.importlib.metadata, "version", lambda _: "0.24.0")
    destination = tmp_path / "prepared"
    campaign.prepare(
        destination, upstream, "agent", "verifier", tmp_path / "preflight", tmp_path / "controls"
    )
    return destination, upstream, hashes


def test_live_readiness_verifies_registration_source_and_loader_identities(prepared):
    destination, upstream, hashes = prepared
    assert len(campaign._verify_campaign(destination, upstream)[2]) == 36
    hashes[str(campaign.ROOT)] = "f" * 64
    with pytest.raises(ValueError, match="inputs changed"):
        campaign._verify_campaign(destination, upstream)
    hashes.clear()
    (upstream / ".claude-plugin/plugin.json").write_text('{"skills":["different"]}')
    with pytest.raises(ValueError, match="inputs changed"):
        campaign._verify_campaign(destination, upstream)


def test_registration_changes_fail_before_dispatch(prepared):
    destination, upstream, _ = prepared
    value = campaign.read_json(destination / "manifest.json")
    value["tasks"][0]["task_sha256"] = "f" * 64
    (destination / "manifest.json").write_text(json.dumps(value))
    with pytest.raises(ValueError, match="registration files changed"):
        campaign._verify_campaign(destination, upstream)


def test_invalid_limits_rejected_before_scheduler_dispatch(scheduling):
    destination, *_ = scheduling
    for limit in (0, -1, True):
        with pytest.raises(ValueError, match="positive"):
            asyncio.run(campaign.run_pilot(destination, Path("upstream"), limit))


@pytest.mark.parametrize(
    "permission,reason",
    [
        (
            {
                "schema_version": "evalopt.subscription-permission.v1",
                "ordinary_usage_allowed": False,
                "state": "exhausted",
            },
            "subscription_exhausted_before_dispatch",
        ),
        (
            {
                "schema_version": "evalopt.subscription-permission.v1",
                "ordinary_usage_allowed": False,
                "state": "unavailable",
            },
            "subscription_permission_unavailable",
        ),
        ({"ordinary_usage_allowed": True, "state": "allowed"}, "subscription_permission_unavailable"),
    ],
)
def test_subscription_permission_blocks_before_any_attempt(scheduling, monkeypatch, permission, reason):
    destination, _, store, _ = scheduling
    monkeypatch.setattr(
        campaign,
        "read_subscription_permission",
        lambda: {**permission, "private_balance": "must not persist"},
    )
    called = executor(monkeypatch, [])
    result = asyncio.run(
        campaign.run_pilot(destination, Path("upstream"), retry_infrastructure=True, resume_quota=True)
    )
    assert result["scheduler"]["reason"] == reason
    assert not called
    assert all(state["attempts"] == 0 for state in store.statuses())
    receipt = campaign.read_json(destination / "runs/run-0001/permission-0001.json")
    assert set(receipt["permission"]) == {"schema_version", "ordinary_usage_allowed", "state"}


def test_subscription_permission_is_refreshed_for_each_trial(scheduling, monkeypatch):
    destination, _, store, _ = scheduling
    permissions = [True, False]

    def probe():
        allowed = permissions.pop(0)
        return {
            "schema_version": "evalopt.subscription-permission.v1",
            "ordinary_usage_allowed": allowed,
            "state": "allowed" if allowed else "exhausted",
        }

    monkeypatch.setattr(campaign, "read_subscription_permission", probe)
    called = executor(monkeypatch, [])
    result = asyncio.run(campaign.run_pilot(destination, Path("upstream")))
    assert result["scheduler"]["reason"] == "subscription_exhausted_before_dispatch"
    assert len(called) == 1
    assert sum(state["attempts"] for state in store.statuses()) == 1
    assert len(list((destination / "runs/run-0001").glob("permission-*.json"))) == 2


def test_scheduler_accepts_explicit_stage_adapters_without_global_overrides(scheduling):
    destination, schedule, store, _ = scheduling
    called = []

    def verify(*_):
        return {}, {"agent_image": "agent", "verifier_image": "verifier"}, schedule, store

    async def execute(row, _store, *_):
        called.append(row["trial_id"])
        attempt = _store.start_attempt(row["trial_id"])
        _store.finish_attempt(row["trial_id"], attempt, "agent_failure", usage=usage())
        return {"status": "agent_failure", "valid_completion": False}

    result = asyncio.run(
        campaign.run_pilot(
            destination,
            Path("upstream"),
            limit=1,
            verifier=verify,
            executor=execute,
            reporter=lambda _: {"adapter": "stage-report"},
        )
    )
    assert called == [schedule[0]["trial_id"]]
    assert result["adapter"] == "stage-report"
