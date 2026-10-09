"""Independent transfer v2 gates; synthetic telemetry, no models or containers."""

from __future__ import annotations

import asyncio
import copy
import sys
from types import SimpleNamespace

import pytest

import test_skill_workflow_transfer_accounting as support

subject = support.subject
accounting = support.accounting
publication = support.publication
registered = support.registered


def retained_result(registered, *, partial=True, **changes):
    fixture, directory, _, policy = registered
    _, _, schedule, store = subject.verify_campaign(directory, fixture.upstream)
    usage = support.observed(fixture.root / "review-sessions", policy, partial=partial)
    result = support.support.result_for(schedule[0], measured=usage)
    result["runtime_evidence_complete"] = not partial
    result.update(changes)
    trial = schedule[0]["trial_id"]
    attempt = store.start_attempt(trial)
    return store, trial, attempt, result


def retain(store, trial, attempt, result):
    store.record_result(
        trial,
        attempt,
        result,
        original_result_sha256="1" * 64,
        raw_artifact_manifest_sha256="2" * 64,
    )


@pytest.mark.parametrize("flag", [None, False, 1, "true"])
def test_review_agent_started_is_explicit_and_cannot_be_inferred_from_model_telemetry(registered, flag):
    store, trial, attempt, result = retained_result(registered)
    if flag is None:
        result["usage"].pop("agent_started")
    else:
        result["usage"]["agent_started"] = flag
    with pytest.raises(ValueError):
        retain(store, trial, attempt, result)


def test_review_partial_usage_cannot_promote_completeness_even_without_exact_counters(registered):
    store, trial, attempt, result = retained_result(registered)
    assert not any(key in result["usage"] for key in accounting.COUNTERS)
    result["runtime_evidence_complete"] = True
    with pytest.raises(ValueError, match="runtime completeness"):
        retain(store, trial, attempt, result)


@pytest.mark.parametrize("mutation", ["usage", "status", "error"])
def test_review_finish_cannot_disagree_with_retained_original_result(registered, mutation):
    store, trial, attempt, result = retained_result(registered)
    retain(store, trial, attempt, result)
    usage = copy.deepcopy(result["usage"])
    status, error = result["status"], result["error_code"]
    if mutation == "usage":
        usage["workflow_exposure_verified"] = False
    elif mutation == "status":
        status = "timeout"
    else:
        status, error = "infra_failure", "subscription_exhausted"
    with pytest.raises(ValueError, match="differs from original result"):
        store.finish_attempt(trial, attempt, status, error_code=error, usage=usage)
    path = store.root / "trials" / trial / f"attempt-{attempt}"
    assert not (path / "finish.json").exists()


@pytest.mark.parametrize("reward", [0, 1])
def test_review_partial_timeout_preserves_original_reward_and_is_not_retried(
    registered, monkeypatch, tmp_path, reward
):
    fixture, directory, _, policy = registered
    measured = support.observed(fixture.root / "review-timeout", policy)
    calls = support.fake_execution(
        monkeypatch,
        [{"measured": measured, "status": "timeout", "reward": reward}, {"measured": measured}],
    )
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=1))
    second = asyncio.run(
        subject.run_campaign(
            directory, fixture.upstream, limit=1, retry_infrastructure=True, resume_quota=True
        )
    )
    assert first["scheduler"]["status"] == second["scheduler"]["status"] == "limited"
    assert calls[0][0] != calls[1][0]
    public = tmp_path / "public"
    receipt = publication.export_public_bundle(directory, public)
    assert publication.verify_public_bundle(public) == receipt
    row = next(
        row for row in subject.read_json(public / "reports/outcomes.json") if row["trial_id"] == calls[0][0]
    )
    assert row["status"] == "timeout" and row["upstream_reward"] == reward
    assert row["runtime_admissible"] is True and row["runtime_evidence_complete"] is False
    assert row["functional_success"] is bool(reward)
    metadata = subject.read_json(public / "PUBLICATION.json")
    assert metadata["efficiency_comparison_eligible"] is False
    assert "no raw native log replay" in metadata["accounting_reproduction"]


def test_review_missing_entrypoint_proof_blocks_next_dispatch_but_preserves_known_cost_and_reward(
    registered, monkeypatch, tmp_path
):
    fixture, directory, _, policy = registered
    measured = support.observed(fixture.root / "review-no-entry", policy, entrypoint_load_observed=False)
    calls = support.fake_execution(monkeypatch, [{"measured": measured}])
    first = asyncio.run(subject.run_campaign(directory, fixture.upstream, limit=2))
    assert first["scheduler"]["reason"] == "entrypoint_load_requires_remediation"
    again = asyncio.run(
        subject.run_campaign(directory, fixture.upstream, retry_infrastructure=True, resume_quota=True)
    )
    assert again["scheduler"]["reason"] == first["scheduler"]["reason"] and len(calls) == 1
    public = tmp_path / "public"
    publication.export_public_bundle(directory, public)
    row = next(row for row in subject.read_json(public / "reports/outcomes.json") if row["usage"])
    assert row["upstream_reward"] == 1 and row["runtime_admissible"] is False
    assert row["runtime_evidence_complete"] is False
    resources = subject.read_json(public / "reports/analysis.json")["all_attempt_resources"][
        "registered_accounting"
    ]
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in resources["arms"].values()) == 20
    assert sum(arm["trials_without_attempts"] for arm in resources["arms"].values()) == 71
    assert resources["efficiency_comparison_eligible"] is False


@pytest.mark.parametrize("cause", ["container_start", "controller_interrupted"])
def test_review_missing_telemetry_recovery_cannot_erase_observed_bad_runtime(cause):
    finish = {
        "status": "infra_failure",
        "error_code": cause,
        "usage": {"runtime_valid": False},
        "artifact_valid": True,
        "accounting_context": {"stopped_output_retained": False, "grade_retained": False},
    }
    assert subject.transfer_usage_reason(finish, support.policy()) == "runtime_identity_requires_remediation"


@pytest.mark.parametrize("started", [None, True])
def test_review_unavailable_logs_do_not_prove_agent_never_started(tmp_path, started):
    policy = support.policy()
    usage = {
        **accounting.collect_usage(tmp_path / "missing", policy),
        "runtime_valid": None,
        "native_agent_stopped": False,
        "execution_boundary_complete": False,
        "returned_models": [],
        "returned_efforts": [],
        "cli_versions": [],
    }
    if started is not None:
        usage["agent_started"] = started
    assert (
        subject.transfer_usage_reason(
            {
                "artifact_valid": True,
                "status": "infra_failure",
                "error_code": "container_start",
                "usage": usage,
            },
            policy,
        )
        is not None
    )


@pytest.mark.parametrize("start_hook", [False, True])
def test_review_real_adapter_observes_agent_start_before_any_workflow_exposure_failure(
    tmp_path, monkeypatch, start_hook
):
    """Run actual adapter hooks against a no-model Harbor-shaped lifecycle double."""
    transfer = subject.transfer
    from runtime import harbor_campaign

    class Trial:
        def __init__(self):
            self.hooks = {}
            self.paths = SimpleNamespace(agent_dir=tmp_path / "no-native-logs")
            self.agent_environment = None
            self.agent = SimpleNamespace(_build_register_skills_command=lambda: "register")

        @classmethod
        async def create(cls, _config):
            return cls()

        def add_hook(self, event, callback):
            self.hooks[event] = callback

        async def run(self):
            if start_hook:
                with pytest.raises(ValueError, match="exposure deliberately unavailable"):
                    await self.hooks["start"](None)
            return SimpleNamespace(
                exception_info=SimpleNamespace(exception_type="RuntimeError"), verifier_result=None
            )

    async def unavailable_exposure(*_args):
        raise ValueError("exposure deliberately unavailable")

    monkeypatch.setitem(
        sys.modules,
        "harbor.models.trial.config",
        SimpleNamespace(TrialConfig=SimpleNamespace(model_validate=lambda value: value)),
    )
    monkeypatch.setitem(
        sys.modules,
        "harbor.trial.hooks",
        SimpleNamespace(TrialEvent=SimpleNamespace(AGENT_START="start", AGENT_END="end")),
    )
    monkeypatch.setitem(sys.modules, "harbor.trial.trial", SimpleNamespace(Trial=Trial))
    monkeypatch.setattr(transfer, "verify_harbor_version", lambda: "0.24.0")
    prepared = {
        "image_lock": {"images": {"build-pmars": {"local_reference": "fixture", "image_id": "fixture"}}},
    }
    monkeypatch.setattr(transfer, "validate_prepared", lambda *_args, **_kwargs: prepared)
    monkeypatch.setattr(transfer, "validate_runtime_preflight", lambda *_args: {})
    monkeypatch.setattr(transfer, "trial_configuration", lambda *_args: {"agent": {"skills": []}})
    monkeypatch.setattr(transfer, "_inspect", lambda *_args: {"Id": "fixture"})
    monkeypatch.setattr(harbor_campaign, "subscription_environment", lambda: None)
    monkeypatch.setattr(transfer, "verify_workflow_exposure", unavailable_exposure)
    policy = support.policy()
    summary = asyncio.run(
        transfer.execute_transfer_trial(
            {"stage": "transfer", "task_id": "build-pmars", "arm": "C"},
            prepared_root=tmp_path,
            preparation_sha256="fixture",
            directory=tmp_path / "attempt",
            upstream=tmp_path,
            evalopt_skill=tmp_path,
            runtime_preflight=tmp_path,
            accounting_policy=policy,
        )
    )
    assert summary["usage"]["agent_started"] is start_hook
    assert summary["usage"]["accounting"]["derived"]["accounting_status"] == "unavailable"
    assert summary["upstream_reward"] is None and summary["runtime_evidence_complete"] is False
    reason = subject.transfer_usage_reason({**summary, "artifact_valid": True}, policy)
    assert (reason is None) is (not start_hook)
