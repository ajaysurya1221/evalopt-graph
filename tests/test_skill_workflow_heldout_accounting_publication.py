"""Publication controls for explicitly registered partial usage, never model results."""

from __future__ import annotations

import pytest

import test_skill_workflow_accounting_policy_review as native
import test_skill_workflow_heldout_publication as base

publication = base.publication
policy_module = native.policy
write_json = base.write_json


@pytest.fixture
def sealed(tmp_path):
    return base.sealed.__wrapped__(tmp_path)


@pytest.fixture
def reviewed_pilot(tmp_path):
    return base.reviewed_pilot.__wrapped__(tmp_path)


@pytest.fixture
def frozen(sealed, reviewed_pilot, tmp_path, monkeypatch):
    return base.frozen.__wrapped__(sealed, reviewed_pilot, tmp_path, monkeypatch)


@pytest.fixture
def recorded(frozen, tmp_path, monkeypatch):
    return base.recorded.__wrapped__(frozen, tmp_path, monkeypatch)


@pytest.fixture
def amended_record(recorded, frozen, tmp_path, monkeypatch):
    root, _, _ = frozen
    review = publication.read_json(root / "pilot-review.json")
    review.update(
        schema_version="evalopt.pilot-review.v2",
        checks=dict.fromkeys(publication.heldout_campaign.REVIEW_CHECKS_V2, True),
        accounting={
            "amendment_sha256": publication.digest("synthetic-amendment"),
            "resource_report_sha256": publication.digest("synthetic-report"),
            "rules_sha256": publication.digest(policy_module.RULES),
        },
    )
    write_json(root / "pilot-review.json", review)
    evidence = publication.read_json(root / "pilot-evidence.json")
    evidence.update(
        schema_version="evalopt.pilot-evidence.v2",
        review_sha256=publication.bytes_digest((root / "pilot-review.json").read_bytes()),
        accounting={
            **review["accounting"],
            "complete_final_attempts": 35,
            "partial_final_attempts": 1,
            "retained_attempts": 36,
            "unavailable_attempts": 0,
        },
    )
    write_json(root / "pilot-evidence.json", evidence)
    policy = policy_module.build_policy(evidence, evidence["review_sha256"])
    write_json(root / "accounting-policy.json", policy)
    freeze = publication.read_json(root / "freeze.json")
    freeze.update(
        schema_version="evalopt.heldout-freeze.v2",
        accounting_policy_sha256=publication.digest(policy),
    )
    write_json(root / "freeze.json", freeze)
    lock = publication.heldout_campaign._heldout_identity(root)
    write_json(root / "heldout-lock.json", lock)
    registration = publication.digest(lock)
    usage = native.observed(tmp_path / "native-synthetic", policy)
    finish = publication.heldout_campaign.CampaignStore.finish_attempt

    def finish_partial(self, *args, **kwargs):
        kwargs["usage"] = usage
        return finish(self, *args, **kwargs)

    monkeypatch.setattr(publication.heldout_campaign.CampaignStore, "finish_attempt", finish_partial)

    def create(mutate=None):
        if mutate:
            mutate(usage)
        record = recorded()
        record.registration = registration
        record.accounting_policy = policy
        receipt = publication.read_json(record.receipt)
        receipt["heldout_registration_sha256"] = registration
        write_json(record.receipt, receipt)
        return record

    return create


def test_v2_release_retains_policy_lower_bounds_and_original_grade(amended_record, tmp_path):
    record = amended_record()
    attempt = record.store.root / "trials" / record.trial["trial_id"] / "attempt-1"
    original_grade = (attempt / "grade.json").read_bytes()
    before = base.hashes(record.root)
    result = base.export(record, tmp_path / "public")
    assert result["grade_records_replayed"] == 1
    assert base.hashes(record.root) == before
    assert (attempt / "grade.json").read_bytes() == original_grade
    public = tmp_path / "public"
    assert (public / "accounting-policy.json").read_bytes() == (
        record.root / "accounting-policy.json"
    ).read_bytes()
    analysis = publication.read_json(public / "reports/analysis.json")
    accounting = analysis["all_attempt_resources"]["registered_accounting"]
    assert accounting["efficiency_comparison_eligible"] is False
    assert accounting["arms"]["A"]["partial_attempts"] == 1
    assert accounting["arms"]["A"]["observed_lower_bounds"]["input_tokens"] == 20
    assert accounting["arms"]["A"]["complete_attempts_exact_totals"]["input_tokens"] == 0
    assert publication.verify_public_bundle(public) == result


@pytest.mark.parametrize("mutation", ["missing", "different_policy", "forged_complete", "private_field"])
def test_v2_release_rejects_unregistered_or_malformed_usage(amended_record, tmp_path, mutation):
    def mutate(usage):
        if mutation == "missing":
            usage.pop("accounting")
        elif mutation == "different_policy":
            usage["accounting"]["policy_sha256"] = "f" * 64
        elif mutation == "forged_complete":
            usage["child_usage_complete"] = True
        else:
            usage["accounting"]["derived"]["private_context"] = "PRIVATE_SENTINEL"

    record = amended_record(mutate)
    with pytest.raises(ValueError):
        base.export(record, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_v2_release_binds_policy_approval_to_the_retained_review(amended_record, tmp_path):
    record = amended_record()
    review = publication.read_json(record.root / "pilot-review.json")
    review["accounting"]["resource_report_sha256"] = "f" * 64
    write_json(record.root / "pilot-review.json", review)
    evidence = publication.read_json(record.root / "pilot-evidence.json")
    evidence["review_sha256"] = publication.bytes_digest((record.root / "pilot-review.json").read_bytes())
    write_json(record.root / "pilot-evidence.json", evidence)
    lock = publication.heldout_campaign._heldout_identity(record.root)
    write_json(record.root / "heldout-lock.json", lock)
    record.registration = publication.digest(lock)
    with pytest.raises(ValueError, match="approval"):
        base.export(record, tmp_path / "rejected")


def test_v1_release_cannot_smuggle_in_a_partial_accounting_policy(recorded, tmp_path):
    record = recorded()
    write_json(record.root / "accounting-policy.json", {"unexpected": True})
    with pytest.raises(ValueError, match="legacy|not registered"):
        base.export(record, tmp_path / "rejected")
