"""Registered transfer accounting controls using synthetic native logs only."""

from __future__ import annotations

import asyncio
import copy
import json
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 13, 12), reason="controller integration is pinned to CPython 3.13.12"
)
BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import transfer_campaign as subject  # noqa: E402
import transfer_publish as publication  # noqa: E402
from runtime import accounting_policy as accounting  # noqa: E402

import test_skill_workflow_amendment_review as native  # noqa: E402
import test_skill_workflow_transfer as runtime_support  # noqa: E402
import test_skill_workflow_transfer_campaign as support  # noqa: E402
from test_skill_workflow_transfer_publication import rehash, write_json  # noqa: E402


def policy():
    return accounting.validate_policy(
        {
            "schema_version": "evalopt.campaign-accounting-policy.v1",
            "rules": copy.deepcopy(accounting.RULES),
            "source_pins": accounting.source_pins(),
            "approval": {
                key: subject.digest(key)
                for key in (
                    "pilot_registration_sha256",
                    "pilot_review_sha256",
                    "accounting_amendment_sha256",
                    "accounting_report_sha256",
                )
            },
        }
    )


def observed(root, registered, *, partial=True, boundary=True, ended=True, **changes):
    logs = {"parent": native.session("parent", children=("child",))}
    logs["child"] = native.session(
        "child", parent="parent", start=2, end=8 if ended else None, aborted=partial
    )
    native.write_sessions(root, logs)
    return {
        **accounting.collect_usage(root, registered),
        "runtime_valid": True,
        "agent_started": True,
        "workflow_exposure_verified": True,
        "native_agent_stopped": True,
        "execution_boundary_complete": boundary,
        "entrypoint_load_observed": True,
        **changes,
    }


@pytest.fixture
def registered(tmp_path, monkeypatch):
    fixture = support.source_fixture.__wrapped__(tmp_path)
    prepared, receipt = support.prepare(fixture)
    preflight = fixture.root / "preflight"
    preflight.mkdir()
    write_json(preflight / "summary.json", {"scope": "synthetic complete runtime probe"})
    monkeypatch.setattr(
        subject.transfer,
        "validate_runtime_preflight",
        lambda root, _prepared: {
            "probe_sha256": subject.bytes_digest((root / "summary.json").read_bytes()),
            "usage": support.usage(),
        },
    )
    registered_policy = policy()
    heldout = fixture.root / "heldout"
    # Noncanonical formatting demonstrates exact primary policy byte preservation.
    heldout.mkdir()
    (heldout / "accounting-policy.json").write_text(json.dumps(registered_policy, indent=2) + "\n")

    def primary(_heldout, registration, export_id, preparation, upstream):
        return {
            "schema_version": "evalopt.transfer-primary-evidence.v2",
            "heldout_registration_sha256": registration,
            "heldout_report_export_id": export_id,
            "scheduled_trials": 432,
            "candidate_conditions": {
                **preparation["skill_sources"],
                "config_sha256": preparation["config_sha256"],
                "upstream_loader_sha256": subject.bytes_digest(
                    (upstream / ".claude-plugin/plugin.json").read_bytes()
                ),
                "runtime": {
                    key: preparation[key]
                    for key in ("model", "reasoning_effort", "codex_version", "harbor_version")
                },
            },
            "terminal_statuses": {"completed": 432},
            "scope": "synthetic primary fixture",
            "accounting_policy_sha256": subject.digest(registered_policy),
            "accounting_policy_file_sha256": subject.bytes_digest(
                (heldout / "accounting-policy.json").read_bytes()
            ),
        }

    monkeypatch.setattr(subject, "verify_primary", primary)
    directory = fixture.root / "campaign"
    frozen = subject.freeze(
        directory,
        prepared,
        receipt["preparation_sha256"],
        preflight,
        fixture.upstream,
        fixture.skill,
        heldout=heldout,
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
    return fixture, directory, frozen, registered_policy


def fake_execution(monkeypatch, responses):
    calls = []

    async def execute(row, *, directory, accounting_policy, **kwargs):
        calls.append((row["trial_id"], subject.digest(accounting_policy)))
        options = responses.pop(0)
        measured = options.pop("measured")
        result = support.result_for(row, measured=measured, **options)
        result["execution_boundary_complete"] = measured["execution_boundary_complete"]
        result["runtime_evidence_complete"] = result["execution_boundary_complete"] and all(
            measured.get(key) is True
            for key in (
                "child_usage_complete",
                "runtime_valid",
                "workflow_exposure_verified",
                "native_agent_stopped",
                "entrypoint_load_observed",
            )
        )
        directory.mkdir(parents=True)
        write_json(directory / "result.json", result)
        write_json(directory / "artifacts.json", {"scope": "synthetic private artifact identity"})
        return result

    monkeypatch.setattr(subject.transfer, "execute_transfer_trial", execute)
    return calls


def test_transfer_copies_identical_primary_policy_and_binds_all_sources(registered):
    fixture, directory, frozen, registered_policy = registered
    assert frozen["schema_version"] == "evalopt.transfer-freeze.v2"
    assert (directory / "accounting-policy.json").read_bytes() == (
        fixture.root / "heldout/accounting-policy.json"
    ).read_bytes()
    assert subject.read_accounting_policy(directory) == registered_policy
    manifest, _, _, _ = subject.verify_campaign(directory, fixture.upstream)
    _, prepared, _ = subject.read_registration(directory)
    assert manifest["accounting_policy_sha256"] == subject.digest(registered_policy)
    assert {"runtime/accounting_policy.py", "runtime/partial_accounting.py"} <= set(
        prepared["runtime_sources"]
    )


@pytest.mark.parametrize("mutation", ["bytes", "hash", "unregistered", "primary"])
def test_registered_policy_mismatch_blocks_before_trial(registered, monkeypatch, mutation):
    fixture, directory, _, _ = registered
    if mutation == "bytes":
        with (directory / "accounting-policy.json").open("a") as stream:
            stream.write("\n")
    elif mutation == "hash":
        manifest = subject.read_json(directory / "manifest.json")
        manifest["accounting_policy_sha256"] = "f" * 64
        write_json(directory / "manifest.json", manifest)
    elif mutation == "unregistered":
        manifest = subject.read_json(directory / "manifest.json")
        manifest["schema_version"] = "evalopt.transfer-campaign.v1"
        del manifest["accounting_policy_sha256"]
        write_json(directory / "manifest.json", manifest)
    else:
        with (fixture.root / "heldout/accounting-policy.json").open("a") as stream:
            stream.write("\n")
    calls = fake_execution(monkeypatch, [])
    with pytest.raises(ValueError):
        asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert not calls and not list((directory / "evidence").rglob("start.json"))


def test_partial_trial_preserves_reward_without_promoting_evidence_completeness(registered, monkeypatch):
    fixture, directory, _, registered_policy = registered
    measured = observed(fixture.root / "sessions", registered_policy)
    calls = fake_execution(monkeypatch, [{"measured": measured}])
    report = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert report["scheduler"]["status"] == "limited"
    assert calls[0][1] == subject.digest(registered_policy)
    row = subject.read_json(directory / "exports" / report["export_id"] / "outcomes.json")[0]
    assert row["upstream_reward"] == 1 and row["runtime_admissible"] is True
    assert row["runtime_evidence_complete"] is False and row["execution_boundary_complete"] is True
    assert not any(key in row["usage"] for key in accounting.COUNTERS)
    resource = report["all_attempt_resources"]["registered_accounting"]
    assert resource["efficiency_comparison_eligible"] is False
    assert sum(arm["partial_attempts"] for arm in resource["arms"].values()) == 1
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in resource["arms"].values()) == 20


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"boundary": False}, "execution_boundary_requires_remediation"),
        ({"native_agent_stopped": False}, "execution_boundary_requires_remediation"),
        ({"workflow_exposure_verified": False}, "workflow_exposure_requires_remediation"),
        ({"entrypoint_load_observed": False}, "entrypoint_load_requires_remediation"),
        ({"runtime_valid": None}, "runtime_identity_requires_remediation"),
        ({"ended": False}, "delegation_boundary_requires_remediation"),
    ],
)
def test_partial_approval_does_not_establish_identity_or_execution_boundary(
    registered, monkeypatch, changes, reason
):
    fixture, directory, _, registered_policy = registered
    measured = observed(fixture.root / "sessions", registered_policy, **changes)
    calls = fake_execution(monkeypatch, [{"measured": measured, "status": "timeout", "reward": None}])
    result = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert result["scheduler"]["status"] == "paused" and result["scheduler"]["reason"] == reason
    again = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True))
    assert again["scheduler"]["reason"] == reason and len(calls) == 1
    resource = result["all_attempt_resources"]["registered_accounting"]
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in resource["arms"].values()) == 20
    assert resource["efficiency_comparison_eligible"] is False


def test_partial_timeout_is_result_and_infrastructure_retry_counts_each_attempt(registered, monkeypatch):
    fixture, directory, _, registered_policy = registered
    partial = observed(fixture.root / "partial", registered_policy)
    complete = observed(fixture.root / "complete", registered_policy, partial=False)
    calls = fake_execution(
        monkeypatch,
        [
            {
                "measured": partial,
                "status": "infra_failure",
                "error_code": "verifier_infrastructure",
                "reward": None,
            },
            {"measured": complete, "status": "timeout", "reward": 1},
            {"measured": complete},
        ],
    )
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert first["scheduler"]["status"] == "paused"
    refused = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert refused["scheduler"]["reason"] == "infrastructure_retry_requires_explicit_resume"
    second = asyncio.run(
        subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True)
    )
    resources = second["all_attempt_resources"]["registered_accounting"]
    assert calls[0][0] == calls[1][0]
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in resources["arms"].values()) == 40
    assert (
        sum(arm["complete_attempts_exact_totals"]["input_tokens"] for arm in resources["arms"].values()) == 20
    )
    assert resources["efficiency_comparison_eligible"] is False
    asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True))
    assert calls[2][0] != calls[1][0]


def test_partial_policy_cannot_bypass_subscription_permission(registered, monkeypatch):
    fixture, directory, _, _ = registered
    monkeypatch.setattr(
        subject.campaign,
        "read_subscription_permission",
        lambda: {
            "schema_version": "evalopt.subscription-permission.v1",
            "ordinary_usage_allowed": False,
            "state": "exhausted",
        },
    )
    calls = fake_execution(monkeypatch, [])
    report = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert report["scheduler"]["reason"] == "subscription_exhausted_before_dispatch"
    assert not calls and not list((directory / "evidence").rglob("start.json"))


@pytest.mark.parametrize("failure", ["infra", "quota"])
def test_explicit_retry_or_quota_resume_cannot_waive_bad_boundary(registered, monkeypatch, failure):
    fixture, directory, _, registered_policy = registered
    measured = observed(fixture.root / "sessions", registered_policy, boundary=False)
    calls = fake_execution(
        monkeypatch,
        [
            {
                "measured": measured,
                "status": "infra_failure",
                "reward": None,
                "error_code": "subscription_exhausted" if failure == "quota" else "verifier_infrastructure",
            }
        ],
    )
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert first["scheduler"]["reason"] == "execution_boundary_requires_remediation"
    again = asyncio.run(
        subject.run_campaign(
            directory, fixture.upstream, limit=1, retry_infrastructure=True, resume_quota=True
        )
    )
    assert again["scheduler"]["reason"] == "execution_boundary_requires_remediation"
    assert len(calls) == 1


def test_proven_pre_agent_failure_can_retry_without_claiming_runtime_or_zero_usage(registered, monkeypatch):
    fixture, directory, _, registered_policy = registered
    unavailable = {
        **accounting.collect_usage(fixture.root / "missing-native-logs", registered_policy),
        "agent_started": False,
        "runtime_valid": None,
        "returned_models": [],
        "returned_efforts": [],
        "cli_versions": [],
        "workflow_exposure_verified": False,
        "native_agent_stopped": False,
        "execution_boundary_complete": False,
        "entrypoint_load_observed": False,
    }
    complete = observed(fixture.root / "complete", registered_policy, partial=False)
    calls = fake_execution(
        monkeypatch,
        [
            {
                "measured": unavailable,
                "status": "infra_failure",
                "error_code": "container_start",
                "reward": None,
            },
            {"measured": complete},
        ],
    )
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert first["scheduler"]["reason"] == "infrastructure_failure_requires_inspection"
    row = subject.read_json(directory / "exports" / first["export_id"] / "outcomes.json")[0]
    assert row["runtime_admissible"] is False and row["runtime_evidence_complete"] is False
    assert all(value is None for value in row["usage"]["accounting"]["derived"]["lower_bounds"].values())
    second = asyncio.run(
        subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True)
    )
    assert second["scheduler"]["status"] == "limited" and calls[0][0] == calls[1][0]
    resources = second["all_attempt_resources"]["registered_accounting"]
    assert sum(arm["unavailable_accounting_attempts"] for arm in resources["arms"].values()) == 1
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in resources["arms"].values()) == 20
    assert resources["efficiency_comparison_eligible"] is False


def test_pre_agent_exception_never_waives_a_real_runtime_contradiction(registered, monkeypatch):
    fixture, directory, _, registered_policy = registered
    unavailable = {
        **accounting.collect_usage(fixture.root / "missing-native-logs", registered_policy),
        "agent_started": False,
        "runtime_valid": False,
        "returned_models": ["unregistered-model"],
        "returned_efforts": [],
        "cli_versions": [],
        "workflow_exposure_verified": False,
        "native_agent_stopped": False,
        "execution_boundary_complete": False,
        "entrypoint_load_observed": False,
    }
    calls = fake_execution(
        monkeypatch,
        [
            {
                "measured": unavailable,
                "status": "infra_failure",
                "error_code": "container_start",
                "reward": None,
            }
        ],
    )
    report = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    assert report["scheduler"]["reason"] == "runtime_identity_requires_remediation"
    asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True))
    assert len(calls) == 1


@pytest.mark.parametrize("mutation", ["count", "complete", "policy", "private", "boundary", "start"])
def test_store_rejects_forged_partial_projection(registered, mutation):
    fixture, directory, _, registered_policy = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    measured = observed(fixture.root / "sessions", registered_policy)
    result = support.result_for(schedule[0], measured=measured)
    result["runtime_evidence_complete"] = False
    if mutation == "count":
        measured["accounting"]["derived"]["lower_bounds"]["input_tokens"] += 1
    elif mutation == "complete":
        result["runtime_evidence_complete"] = True
        measured["input_tokens"] = 20
    elif mutation == "policy":
        measured["accounting"]["policy_sha256"] = "f" * 64
    elif mutation == "private":
        measured["accounting"]["derived"]["agents"][0]["private"] = "not public"
    elif mutation == "boundary":
        measured["execution_boundary_complete"] = False
    else:
        measured["agent_started"] = False
    attempt = store.start_attempt(schedule[0]["trial_id"])
    with pytest.raises(ValueError):
        store.record_result(
            schedule[0]["trial_id"],
            attempt,
            result,
            original_result_sha256="1" * 64,
            raw_artifact_manifest_sha256="2" * 64,
        )


def test_missing_interrupted_usage_remains_unavailable_without_breaking_resource_report(registered):
    fixture, directory, _, _ = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    trial = schedule[0]["trial_id"]
    store.start_attempt(trial)
    store.finish_attempt(trial, 1, "infra_failure", error_code="controller_interrupted")
    report = subject.report(directory)
    resources = report["all_attempt_resources"]["registered_accounting"]
    assert sum(arm["unavailable_accounting_attempts"] for arm in resources["arms"].values()) == 1
    assert resources["efficiency_comparison_eligible"] is False


@pytest.mark.parametrize(
    "measured,reason",
    [
        ({"runtime_valid": False}, "runtime_identity_requires_remediation"),
        ({"agent_started": True}, "execution_boundary_requires_remediation"),
    ],
)
def test_missing_recovery_projection_does_not_erase_known_contradictions(
    registered, monkeypatch, measured, reason
):
    fixture, directory, _, _ = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    trial = schedule[0]["trial_id"]
    store.start_attempt(trial)
    store.finish_attempt(trial, 1, "infra_failure", error_code="controller_interrupted", usage=measured)
    calls = fake_execution(monkeypatch, [])
    report = asyncio.run(
        subject.run_campaign(directory, fixture.upstream, limit=1, retry_infrastructure=True)
    )
    assert report["scheduler"]["reason"] == reason and not calls


@pytest.mark.parametrize("expired", [False, True])
def test_runtime_partial_collection_never_unblocks_unresolved_verifier_boundary(
    tmp_path, monkeypatch, expired
):
    registered_policy = policy()
    logs = tmp_path / "unused-agent-logs"
    logs.mkdir()
    observed(logs / "sessions", registered_policy)
    original_execute = subject.transfer.execute_transfer_trial
    summaries = []

    async def with_registered_policy(*args, **kwargs):
        result = await original_execute(*args, **kwargs, accounting_policy=registered_policy)
        summaries.append(result)
        return result

    monkeypatch.setattr(subject.transfer, "execute_transfer_trial", with_registered_policy)
    runtime_support.test_unresolved_execution_boundary_blocks_harbor_verifier(tmp_path, monkeypatch, expired)
    summary = summaries[0]
    assert summary["usage"]["agent_started"] is True
    assert summary["usage"]["accounting"]["derived"]["accounting_status"] == "partial"
    assert summary["usage"]["accounting"]["derived"]["lower_bounds"]["input_tokens"] == 20
    assert summary["upstream_reward"] is None and summary["runtime_evidence_complete"] is False


def test_legacy_transfer_rejects_unregistered_policy_projection(tmp_path):
    measured = observed(tmp_path / "sessions", policy())
    with pytest.raises(ValueError, match="registered"):
        subject.safe_usage(measured)


def test_primary_v2_resource_receipt_reproduces_all_432_attempts(tmp_path, monkeypatch):
    fixture = support.source_fixture.__wrapped__(tmp_path)
    primary = support._primary_context(fixture, monkeypatch, complete=True)
    root = primary.directory
    registered_policy = policy()
    approval = registered_policy["approval"]
    accounting_evidence = {
        "amendment_sha256": approval["accounting_amendment_sha256"],
        "resource_report_sha256": approval["accounting_report_sha256"],
        "rules_sha256": subject.digest(accounting.RULES),
    }
    review = {
        "schema_version": "evalopt.pilot-review.v2",
        "pilot_registration_sha256": approval["pilot_registration_sha256"],
        "accounting": accounting_evidence,
    }
    write_json(root / "pilot-review.json", review)
    approval["pilot_review_sha256"] = subject.bytes_digest((root / "pilot-review.json").read_bytes())
    evidence = subject.read_json(root / "pilot-evidence.json")
    evidence.update(
        schema_version="evalopt.pilot-evidence.v2",
        registration_sha256=approval["pilot_registration_sha256"],
        review_sha256=approval["pilot_review_sha256"],
        scheduled_trials=36,
        accounting={
            **accounting_evidence,
            "complete_final_attempts": 35,
            "partial_final_attempts": 1,
            "retained_attempts": 36,
            "unavailable_attempts": 0,
        },
    )
    write_json(root / "pilot-evidence.json", evidence)
    write_json(root / "accounting-policy.json", registered_policy)
    write_json(
        root / "freeze.json",
        {
            "schema_version": "evalopt.heldout-freeze.v2",
            "accounting_policy_sha256": subject.digest(registered_policy),
        },
    )
    write_json(
        root / "heldout-lock.json",
        {"accounting-policy.json": subject.bytes_digest((root / "accounting-policy.json").read_bytes())},
    )
    report = subject.campaign.report(root)
    receipt = subject.verify_primary(root, "1" * 64, report["export_id"], primary.prepared, fixture.upstream)
    assert receipt["schema_version"] == "evalopt.transfer-primary-evidence.v2"
    assert receipt["accounting_policy_sha256"] == subject.digest(registered_policy)
    assert receipt["terminal_statuses"] == {"infra_failure": 432}
    assert (
        sum(
            row["unavailable_accounting_attempts"]
            for row in report["all_attempt_resources"]["registered_accounting"]["arms"].values()
        )
        == 432
    )


@pytest.fixture
def recorded(registered, monkeypatch):
    fixture, directory, _, registered_policy = registered
    fake_execution(monkeypatch, [{"measured": observed(fixture.root / "sessions", registered_policy)}])
    asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    return directory


def test_public_transfer_replays_partial_arithmetic_and_preserves_policy_bytes(recorded, tmp_path):
    public = tmp_path / "public"
    result = publication.export_public_bundle(recorded, public)
    assert result["attempts_verified"] == 1 and result["raw_archives_included"] is False
    assert (public / "accounting-policy.json").read_bytes() == (
        recorded / "accounting-policy.json"
    ).read_bytes()
    metadata = subject.read_json(public / "PUBLICATION.json")
    assert metadata["schema_version"] == "evalopt.transfer-public-evidence.v2"
    assert metadata["efficiency_comparison_eligible"] is False
    assert "not raw native logs" in (public / "CLAIMS.md").read_text()
    before = {
        item.relative_to(recorded).as_posix(): item.read_bytes()
        for item in (recorded / "evidence").rglob("*.json")
    }
    assert publication.verify_public_bundle(public) == result
    assert all((recorded / name).read_bytes() == raw for name, raw in before.items())


@pytest.mark.parametrize(
    "mutation", ["count", "complete", "efficiency", "policy-bytes", "private", "delete-policy"]
)
def test_public_partial_projection_rejects_rehashed_mutations(recorded, tmp_path, mutation):
    public = tmp_path / "public"
    publication.export_public_bundle(recorded, public)
    if mutation in {"count", "complete"}:
        target = next(public.glob("evidence/trials/*/attempt-1/transfer-result.json"))
        value = subject.read_json(target)
        if mutation == "count":
            value["usage"]["accounting"]["derived"]["lower_bounds"]["input_tokens"] += 1
        else:
            value["runtime_evidence_complete"] = True
        write_json(target, value)
    elif mutation == "efficiency":
        target = public / "reports/analysis.json"
        value = subject.read_json(target)
        value["all_attempt_resources"]["registered_accounting"]["efficiency_comparison_eligible"] = True
        write_json(target, value)
    elif mutation == "policy-bytes":
        with (public / "accounting-policy.json").open("a") as stream:
            stream.write("\n")
    elif mutation == "private":
        value = subject.read_json(public / "accounting-policy.json")
        value["private"] = {"refresh_token": "SYNTHETIC-unpublished-token"}
        write_json(public / "accounting-policy.json", value)
    else:
        (public / "accounting-policy.json").unlink()
    rehash(public)
    with pytest.raises((ValueError, FileNotFoundError)):
        publication.verify_public_bundle(public)
