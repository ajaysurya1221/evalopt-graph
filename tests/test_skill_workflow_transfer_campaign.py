"""Offline transfer scheduling controls; no models, downloads, or credentials."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

pytest.importorskip("tomllib", reason="transfer controller requires Python 3.13.12")
pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 13, 12), reason="controller integration is pinned to CPython 3.13.12"
)
BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import transfer_campaign as subject  # noqa: E402

from test_skill_workflow_transfer import fixture as source_fixture  # noqa: E402,F401
from test_skill_workflow_transfer import prepare  # noqa: E402


def usage(**changes):
    return {
        "child_usage_complete": True,
        "runtime_valid": True,
        "input_tokens": 10,
        "output_tokens": 2,
        "tool_calls": 1,
        "model_calls": 1,
        "wall_seconds": 3,
        "agent_count": 1,
        "aggregation": "agent_exclusive",
        "workflow_exposure_verified": True,
        "native_agent_stopped": True,
        "entrypoint_load_observed": True,
        **changes,
    }


def result_for(row, *, status="completed", reward=1, error_code=None, measured=None):
    return {
        **row,
        "schema_version": "evalopt.transfer-trial.v1",
        "status": status,
        "error_code": error_code,
        "upstream_reward": reward,
        "functional_success": None if reward is None else bool(reward),
        "artifact_capture_complete": True,
        "runtime_evidence_complete": True,
        "execution_boundary_complete": True,
        "usage": usage() if measured is None else measured,
    }


@pytest.fixture
def registered(source_fixture, monkeypatch):  # noqa: F811
    fixture = source_fixture
    prepared, receipt = prepare(fixture)
    preflight = fixture.root / "preflight"
    preflight.mkdir()
    (preflight / "summary.json").write_text('{"scope":"synthetic offline probe"}')
    monkeypatch.setattr(
        subject.transfer,
        "validate_runtime_preflight",
        lambda root, _prepared: {
            "probe_sha256": subject.bytes_digest((root / "summary.json").read_bytes()),
            "usage": usage(),
        },
    )
    directory = fixture.root / "campaign"

    def primary(_heldout, registration, export_id, prepared, upstream):
        return {
            "schema_version": "evalopt.transfer-primary-evidence.v1",
            "heldout_registration_sha256": registration,
            "heldout_report_export_id": export_id,
            "scheduled_trials": 432,
            "candidate_conditions": {
                **prepared["skill_sources"],
                "config_sha256": prepared["config_sha256"],
                "upstream_loader_sha256": subject.bytes_digest(
                    (upstream / ".claude-plugin/plugin.json").read_bytes()
                ),
                "runtime": {
                    key: prepared[key]
                    for key in ("model", "reasoning_effort", "codex_version", "harbor_version")
                },
            },
            "terminal_statuses": {"completed": 432},
            "scope": "synthetic primary fixture",
        }

    monkeypatch.setattr(subject, "verify_primary", primary)
    frozen = subject.freeze(
        directory,
        prepared,
        receipt["preparation_sha256"],
        preflight,
        fixture.upstream,
        fixture.skill,
        heldout=fixture.root / "heldout",
        heldout_registration_sha256="1" * 64,
        heldout_export_id="2" * 64,
        runner=fixture.runtime.run,
    )
    original_verify = subject.verify_campaign
    monkeypatch.setattr(
        subject,
        "verify_campaign",
        lambda dest, upstream: original_verify(dest, upstream, runner=fixture.runtime.run),
    )
    monkeypatch.setattr(subject.campaign, "subscription_environment", lambda: None)
    monkeypatch.setattr(
        subject.campaign,
        "read_subscription_permission",
        lambda: {
            "schema_version": "evalopt.subscription-permission.v1",
            "ordinary_usage_allowed": True,
            "state": "allowed",
        },
    )
    return fixture, directory, frozen


def fake_execution(monkeypatch, responses):
    calls = []

    async def execute(row, *, directory, **kwargs):
        calls.append(row["trial_id"])
        result = result_for(row, **(responses.pop(0) if responses else {}))
        directory.mkdir(parents=True)
        for name, value in (("result.json", result), ("artifacts.json", {"private": "raw logs retained"})):
            (directory / name).write_text(json.dumps(value))
        return result

    monkeypatch.setattr(subject.transfer, "execute_transfer_trial", execute)
    return calls


def test_freeze_registers_72_seeded_original_limit_trials_without_models(registered):
    fixture, directory, frozen = registered
    assert frozen["scheduled_trials"] == 72 and frozen["agent_trials"] == 0
    manifest, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    assert len(schedule) == 72 and {row["arm"] for row in schedule} == {"B", "C"}
    assert {row["agent_seconds"] for row in schedule} == {900, 1800}
    assert all(row["status"] == "pending" for row in store.statuses())
    assert manifest["acceptance_policies"] == "not applicable; no U/M/G"
    assert schedule == subject.build_schedule(manifest["tasks"], "transfer", seed=20261008)


def test_completed_reward_needs_no_authored_policy_files(registered, monkeypatch):
    fixture, directory, _ = registered
    fake_execution(monkeypatch, [])
    result = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert result["scheduler"]["status"] == "limited"
    record = next((directory / "evidence/trials").glob("*/attempt-1/transfer-result.json"))
    assert json.loads(record.read_text())["upstream_reward"] == 1
    assert not list((directory / "evidence").rglob("policies.json"))
    assert not list((directory / "evidence").rglob("grade.json"))
    assert subject.report(directory)["headline_permitted"] is False


def test_timeout_preserves_original_reward_and_does_not_retry(registered, monkeypatch):
    fixture, directory, _ = registered
    calls = fake_execution(monkeypatch, [{"status": "timeout", "reward": 1}])
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    rows = subject.read_json(directory / "exports" / first["export_id"] / "outcomes.json")
    assert rows[0]["status"] == "timeout" and rows[0]["functional_success"] is True
    asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True))
    assert len(set(calls)) == 2


def test_explicit_infrastructure_retry_preserves_all_resources(registered, monkeypatch):
    fixture, directory, _ = registered
    calls = fake_execution(
        monkeypatch,
        [
            {
                "status": "infra_failure",
                "error_code": "verifier_infrastructure",
                "reward": None,
                "measured": usage(input_tokens=100),
            },
            {},
        ],
    )
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert first["scheduler"]["status"] == "paused"
    second = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert second["scheduler"]["reason"] == "infrastructure_retry_requires_explicit_resume"
    third = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True))
    assert calls[0] == calls[1] and len(calls) == 2
    assert (
        sum(arm["totals"]["input_tokens"] for arm in third["all_attempt_resources"]["arms"].values()) == 110
    )
    assert len(list((directory / "evidence/trials").glob("*/attempt-*/finish.json"))) == 2


def test_permission_failure_does_not_consume_attempt(registered, monkeypatch):
    fixture, directory, _ = registered
    calls = fake_execution(monkeypatch, [])
    monkeypatch.setattr(
        subject.campaign,
        "read_subscription_permission",
        lambda: {
            "schema_version": "evalopt.subscription-permission.v1",
            "ordinary_usage_allowed": False,
            "state": "exhausted",
        },
    )
    report = asyncio.run(subject.run_campaign(directory, fixture.upstream))
    assert report["scheduler"]["reason"] == "subscription_exhausted_before_dispatch"
    assert not calls and not list((directory / "evidence").rglob("start.json"))


@pytest.mark.parametrize("mutate", ["registration", "prepared", "preflight"])
def test_drift_blocks_before_dispatch(registered, monkeypatch, mutate):
    fixture, directory, _ = registered
    calls = fake_execution(monkeypatch, [])
    path = {
        "registration": directory / "manifest.json",
        "prepared": fixture.root / "prepared/B/build-pmars/instruction.md",
        "preflight": fixture.root / "preflight/summary.json",
    }[mutate]
    path.write_text("{}")
    with pytest.raises(ValueError, match="changed"):
        asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert not calls


def test_authored_policy_and_forged_result_identity_are_rejected(registered):
    fixture, directory, _ = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    row = schedule[0]
    attempt = store.start_attempt(row["trial_id"])
    with pytest.raises(ValueError, match="U/M/G"):
        store.decide(row["trial_id"], attempt)
    result = result_for(row)
    result["task_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="identity"):
        store.record_result(
            row["trial_id"],
            attempt,
            result,
            original_result_sha256="1" * 64,
            raw_artifact_manifest_sha256="2" * 64,
        )


def test_finalization_recovers_exact_reward_after_crash(registered, monkeypatch):
    fixture, directory, _ = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    row = schedule[0]
    attempt = store.start_attempt(row["trial_id"])
    store.record_result(
        row["trial_id"],
        attempt,
        result_for(row),
        original_result_sha256="1" * 64,
        raw_artifact_manifest_sha256="2" * 64,
    )
    original = store.recover_attempt
    monkeypatch.setattr(
        store, "recover_attempt", lambda *args: (_ for _ in ()).throw(OSError("simulated crash"))
    )
    with pytest.raises(OSError, match="crash"):
        store.finish_attempt(row["trial_id"], attempt, "completed", usage=usage())
    monkeypatch.setattr(store, "recover_attempt", original)
    assert store.recover_attempt(row["trial_id"], attempt)["original_reward_retained"] is True
    assert not list(store.root.rglob("policies.json"))
    with pytest.raises(ValueError, match="infrastructure"):
        store.start_attempt(row["trial_id"])


def _primary_context(fixture, monkeypatch, *, complete):
    from types import SimpleNamespace

    _, prepared_receipt = prepare(fixture)
    prepared = prepared_receipt["manifest"]
    primary = fixture.root / "primary"
    primary.mkdir()
    runtime = {key: prepared[key] for key in ("model", "reasoning_effort", "codex_version", "harbor_version")}
    runtime["auth_route"] = "chatgpt_subscription"
    sources = {
        "skill_sha256": prepared["skill_sources"]["evalopt"],
        "upstream_sha256": prepared["skill_sources"]["upstream"],
        "upstream_loader_sha256": subject.bytes_digest(
            (fixture.upstream / ".claude-plugin/plugin.json").read_bytes()
        ),
    }
    evidence = {"candidate_conditions": {**sources, "config_sha256": prepared["config_sha256"]}}
    for name, value in (("source-lock.json", sources), ("pilot-evidence.json", evidence)):
        (primary / name).write_text(json.dumps(value))
    tasks = [
        {
            "task_id": f"{category}-{number}",
            "stage": "heldout",
            "category": category,
            "cluster_id": f"{category}-{number}",
            "task_sha256": "1" * 64,
            "grader_sha256": "2" * 64,
            "agent_seconds": 600,
        }
        for category in subject.heldout_campaign.CATEGORIES
        for number in range(8)
    ]
    schedule = subject.build_schedule(tasks, "heldout")
    store = subject.campaign.CampaignStore(primary / "evidence", schedule)
    for row in schedule[: 432 if complete else 431]:
        attempt = store.start_attempt(row["trial_id"])
        store.finish_attempt(row["trial_id"], attempt, "infra_failure", error_code="container_start")
    monkeypatch.setattr(
        subject.heldout_campaign,
        "verify_registration",
        lambda *_: ({"runtime": runtime}, {}, schedule, store),
    )
    report = subject.campaign.report(primary)
    return SimpleNamespace(
        directory=primary,
        prepared=prepared,
        sources=sources,
        evidence=evidence,
        manifest={"runtime": runtime},
        report=report,
        store=store,
    )


def test_transfer_requires_complete_primary_before_registration(source_fixture, monkeypatch):  # noqa: F811
    primary = _primary_context(source_fixture, monkeypatch, complete=False)
    with pytest.raises(ValueError, match="accounted"):
        subject.verify_primary(
            primary.directory,
            "a" * 64,
            primary.report["export_id"],
            primary.prepared,
            source_fixture.upstream,
        )


def test_primary_report_binds_terminal_infrastructure_outcomes(source_fixture, monkeypatch):  # noqa: F811
    primary = _primary_context(source_fixture, monkeypatch, complete=True)
    result = subject.verify_primary(
        primary.directory, "a" * 64, primary.report["export_id"], primary.prepared, source_fixture.upstream
    )
    assert result["terminal_statuses"] == {"infra_failure": 432}
    path = primary.directory / "exports" / primary.report["export_id"] / "checksums.json"
    value = subject.read_json(path)
    value["files"]["analysis.json"] = "0" * 64
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="receipt"):
        subject.verify_primary(
            primary.directory,
            "a" * 64,
            primary.report["export_id"],
            primary.prepared,
            source_fixture.upstream,
        )


@pytest.mark.parametrize("key", ["evalopt", "upstream", "config", "model", "loader"])
def test_changed_transfer_candidate_cannot_bypass_reviewed_primary(source_fixture, monkeypatch, key):  # noqa: F811
    primary = _primary_context(source_fixture, monkeypatch, complete=False)
    prepared = json.loads(json.dumps(primary.prepared))
    if key in {"evalopt", "upstream"}:
        prepared["skill_sources"][key] = "0" * 64
    elif key == "config":
        prepared["config_sha256"] = "0" * 64
    elif key == "model":
        prepared["model"] = "different-model"
    else:
        (source_fixture.upstream / ".claude-plugin/plugin.json").write_text("{}")
    with pytest.raises(ValueError, match="differs|conditions"):
        subject.match_primary_candidate(
            prepared, primary.manifest, primary.sources, primary.evidence, source_fixture.upstream
        )


def test_reward_mutation_breaks_attempt_integrity(registered, monkeypatch):
    fixture, directory, _ = registered
    fake_execution(monkeypatch, [])
    asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    record = next((directory / "evidence/trials").glob("*/attempt-1/transfer-result.json"))
    value = json.loads(record.read_text())
    value["upstream_reward"] = 0
    record.write_text(json.dumps(value))
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    with pytest.raises(ValueError, match="changed"):
        store.verify_attempt(schedule[0]["trial_id"], 1)


def test_scored_reward_requires_established_execution_boundary(registered):
    fixture, directory, _ = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    row = schedule[0]
    attempt = store.start_attempt(row["trial_id"])
    result = result_for(row)
    result["execution_boundary_complete"] = False
    result["runtime_evidence_complete"] = False
    with pytest.raises(ValueError, match="unbounded"):
        store.record_result(
            row["trial_id"],
            attempt,
            result,
            original_result_sha256="1" * 64,
            raw_artifact_manifest_sha256="2" * 64,
        )
    result.update(status="timeout", upstream_reward=None, functional_success=None)
    store.record_result(
        row["trial_id"],
        attempt,
        result,
        original_result_sha256="1" * 64,
        raw_artifact_manifest_sha256="2" * 64,
    )
    store.finish_attempt(row["trial_id"], attempt, "timeout", usage=usage())
    assert store.verify_attempt(row["trial_id"], attempt)["original_reward_retained"] is True
    with pytest.raises(ValueError, match="infrastructure"):
        store.start_attempt(row["trial_id"])
