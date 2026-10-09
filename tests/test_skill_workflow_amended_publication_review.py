"""Independent offline amendment-publication review; synthetic evidence only."""

from __future__ import annotations

import copy

import pytest

import test_skill_workflow_amended_publication as support

publication = support.publication


@pytest.fixture
def public_case(tmp_path):
    record = support.amended.__wrapped__(tmp_path)
    record["later_blocked"]()
    destination = tmp_path / "review-public"
    receipt = support.export(record, destination)
    return record, destination, receipt


def write(path, value):
    support.write_json(path, value)


def verify_rehashed(destination):
    support.rechecksum(destination)
    return publication.verify_public_bundle(destination)


def forbidden(*_args, **_kwargs):
    raise AssertionError("public arithmetic replay must not execute candidates or read private logs")


def test_review_public_replay_uses_retained_counters_and_never_private_native_logs(public_case, monkeypatch):
    record, destination, receipt = public_case
    before = support.hashes(record["source"] / "evidence")
    monkeypatch.setattr(support.controller, "derive_partial_usage", forbidden)
    monkeypatch.setattr(support.controller, "FrozenBridge", forbidden)
    result = publication.verify_public_bundle(
        destination, amendment_sha256=record["identity"], bundle_id=receipt["bundle_id"]
    )
    assert result["pilot_attempts_verified"] == 10
    assert result["policy_decisions_replayed"] == 30
    assert result["resource_arithmetic_reproduced"] is True
    assert result["raw_native_log_replay"] is False
    assert result["independent_authentication"] is False
    assert result["independent_replication"] is False
    assert result["efficiency_comparison_eligible"] is False
    assert support.hashes(record["source"] / "evidence") == before
    assert all(
        support.bytes_digest((destination / "pilot/evidence" / name).read_bytes()) == digest
        for name, digest in before.items()
    )
    report = support.read_json(destination / "resource-report.json")
    assert report["scheduled_trials"] == 36
    assert report["retained_attempts"] == 10
    assert report["pending_trials"] == 26
    assert sum(arm["scheduled_trials"] for arm in report["arms"].values()) == 36
    assert sum(arm["partial_attempts"] for arm in report["arms"].values()) == 1
    assert sum(arm["runtime_invalid_attempts"] for arm in report["arms"].values()) == 1
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in report["arms"].values()) == 110


@pytest.mark.parametrize("field", ["schema_version", "source_log_sha256", "complete_usage", "agents"])
def test_review_later_sidecar_cannot_change_beneath_completed_dispatch(public_case, field):
    record, destination, _ = public_case
    path = support.sidecar(destination, record, index=9)
    value = support.read_json(path)
    if field == "schema_version":
        value["derived_usage"][field] = "unregistered-schema"
    elif field == "source_log_sha256":
        value["derived_usage"][field] = ["e" * 64]
    elif field == "complete_usage":
        value["derived_usage"][field]["wall_seconds"] += 1
    else:
        value["derived_usage"][field][0]["agent_id"] = "native-private-identifier"
    write(path, value)
    with pytest.raises(ValueError):
        verify_rehashed(destination)


@pytest.mark.parametrize(
    "target", ["sidecar", "agent", "complete_usage", "permission", "completion", "publication"]
)
def test_review_unknown_private_fields_are_rejected_even_if_not_secret_pattern(public_case, target):
    record, destination, _ = public_case
    trial = record["schedule"][9]["trial_id"]
    if target in {"sidecar", "agent", "complete_usage"}:
        path = support.sidecar(destination, record, index=9)
        value = support.read_json(path)
        node = value
        if target == "agent":
            node = value["derived_usage"]["agents"][0]
        elif target == "complete_usage":
            node = value["derived_usage"]["complete_usage"]
    else:
        path = {
            "permission": destination / "runs/run-0001" / trial / "permission.json",
            "completion": destination / "runs/run-0001" / trial / "completed.json",
            "publication": destination / "PUBLICATION.json",
        }[target]
        value = support.read_json(path)
        node = value
    node["private_debug_context"] = "PRIVATE_SENTINEL_WITH_NO_CREDENTIAL_SHAPE"
    write(path, value)
    with pytest.raises(ValueError):
        verify_rehashed(destination)


@pytest.mark.parametrize("name", ["completed.json", "permission.json"])
def test_review_deleted_dispatch_identity_blocks_public_verification(public_case, name):
    record, destination, _ = public_case
    trial = record["schedule"][9]["trial_id"]
    (destination / "runs/run-0001" / trial / name).unlink()
    with pytest.raises(ValueError):
        verify_rehashed(destination)


def test_review_frozen_source_identity_cannot_be_replaced_by_installed_new_code(public_case, monkeypatch):
    _, destination, _ = public_case
    changed = copy.deepcopy(support.controller.code_identity())
    changed["runtime/partial_accounting.py"] = "f" * 64
    monkeypatch.setattr(support.controller, "code_identity", lambda: changed)
    with pytest.raises(ValueError, match="source or interpreter"):
        publication.verify_public_bundle(destination)


@pytest.mark.parametrize(
    "field", ["scheduled_trials", "retained_attempts", "pending_trials", "efficiency_comparison_eligible"]
)
def test_review_resource_coverage_and_eligibility_cannot_be_rewritten(public_case, field):
    _, destination, _ = public_case
    path = destination / "resource-report.json"
    value = support.read_json(path)
    value[field] = True if field == "efficiency_comparison_eligible" else value[field] + 1
    write(path, value)
    with pytest.raises(ValueError, match="arithmetic"):
        verify_rehashed(destination)


def test_review_sanitizer_scans_allowed_files_before_semantic_replay(public_case):
    record, destination, _ = public_case
    path = support.sidecar(destination, record, index=9)
    value = support.read_json(path)
    value["private_debug_context"] = {"refresh_token": "synthetic-sensitive-value"}
    write(path, value)
    with pytest.raises(ValueError, match="sensitive"):
        verify_rehashed(destination)


def test_review_publication_never_upgrades_arithmetic_to_raw_log_authentication(public_case):
    _, destination, _ = public_case
    path = destination / "PUBLICATION.json"
    value = support.read_json(path)
    value["raw_native_log_replay"] = True
    value["independent_authentication"] = True
    write(path, value)
    with pytest.raises(ValueError, match="scope"):
        verify_rehashed(destination)


def test_review_runtime_blocked_stop_cannot_be_relabelled_as_unblocked_limit(public_case):
    _, destination, _ = public_case
    path = destination / "runs/run-0001/end.json"
    value = support.read_json(path)
    value.update(status="limited", reason=None, trial_id=None)
    write(path, value)
    with pytest.raises(ValueError):
        verify_rehashed(destination)


def test_review_run_validator_rejects_dispatch_after_previously_bound_blocker(public_case):
    record, destination, _ = public_case
    amendment = support.read_json(destination / "amendment.json")
    sidecars = [support.read_json(support.sidecar(destination, record, index=i)) for i in range(10)]
    later = copy.deepcopy(sidecars[0])
    trial = record["schedule"][10]["trial_id"]
    later.update(trial_id=trial)
    sidecars.append(later)
    # Isolate dispatch semantics: outer grade/sidecar validation is covered by
    # full-bundle tests. This later receipt is internally bound but follows an
    # already retained runtime-invalid attempt, so dispatch must still fail.
    write(
        destination / "pilot/evidence/trials" / trial / "attempt-1/finish.json",
        {
            "status": "completed",
            "error_code": None,
        },
    )
    run = destination / "runs/run-0002"
    write(
        run / "start.json",
        {
            "schema_version": "evalopt.amended-run.v1",
            "amendment_sha256": record["identity"],
            "pending_at_start": [trial],
        },
    )
    write(
        run / "end.json",
        {
            "schema_version": "evalopt.amended-stop.v1",
            "status": "limited",
            "reason": None,
            "trial_id": None,
            "dispatched": [trial],
            "pending_trials": 25,
        },
    )
    write(
        run / trial / "permission.json",
        {
            "schema_version": "evalopt.amended-permission.v1",
            "trial_id": trial,
            "ordinary_usage_allowed": True,
            "state": "allowed",
        },
    )
    write(
        run / trial / "completed.json",
        {
            "schema_version": "evalopt.amended-completion.v1",
            "amendment_sha256": record["identity"],
            **support.controller._bound_attempt(later),
            "sidecar_sha256": support.digest(later),
        },
    )
    with pytest.raises(ValueError, match="after a retained continuation blocker"):
        publication._validate_runs(destination, amendment, sidecars, record["identity"])
