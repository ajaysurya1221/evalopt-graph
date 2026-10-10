"""Independent public held-out accounting receipt consistency controls."""

from __future__ import annotations

import pytest

import test_skill_workflow_heldout_accounting_publication as support
from test_skill_workflow_heldout_accounting_publication import (  # noqa: F401
    frozen,
    recorded,
    reviewed_pilot,
    sealed,
)

publication = support.publication
amended_record = support.amended_record


def relock(record):
    lock = publication.heldout_campaign._heldout_identity(record.root)
    support.write_json(record.root / "heldout-lock.json", lock)
    record.registration = publication.digest(lock)
    receipt = publication.read_json(record.receipt)
    receipt["heldout_registration_sha256"] = record.registration
    support.write_json(record.receipt, receipt)


@pytest.mark.parametrize(
    "field,value",
    [
        ("complete_final_attempts", 0),
        ("partial_final_attempts", True),
        ("retained_attempts", 35),
        ("unavailable_attempts", 1),
        ("private_context", "PRIVATE_NONCREDENTIAL_SENTINEL"),
    ],
)
def test_review_relocked_pilot_accounting_receipt_cannot_claim_inconsistent_coverage(
    amended_record, tmp_path, field, value
):
    record = amended_record()
    path = record.root / "pilot-evidence.json"
    evidence = publication.read_json(path)
    evidence["accounting"][field] = value
    support.write_json(path, evidence)
    relock(record)
    with pytest.raises(ValueError):
        support.base.export(record, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_review_v2_policy_is_required_even_if_lock_is_recomputed(amended_record, tmp_path):
    record = amended_record()
    (record.root / "accounting-policy.json").unlink()
    with pytest.raises((ValueError, OSError)):
        relock(record)
        support.base.export(record, tmp_path / "rejected")
    assert not (tmp_path / "rejected").exists()


def test_review_public_partial_accounting_preserves_valid_completion_denominator(amended_record, tmp_path):
    record = amended_record()
    destination = tmp_path / "public"
    result = support.base.export(record, destination)
    rows = publication.read_json(destination / "reports/outcomes.json")
    assert len(rows) == 432
    selected = next(row for row in rows if row["trial_id"] == record.trial["trial_id"])
    assert selected["valid_completion"] is True
    assert selected["usage"]["child_usage_complete"] is False
    report = publication.read_json(destination / "reports/analysis.json")
    resources = report["all_attempt_resources"]["registered_accounting"]
    assert sum(arm["scheduled_trials"] for arm in resources["arms"].values()) == 432
    assert sum(arm["retained_attempts"] for arm in resources["arms"].values()) == 1
    assert sum(arm["trials_without_attempts"] for arm in resources["arms"].values()) == 431
    assert resources["efficiency_comparison_eligible"] is False
    metadata = publication.read_json(destination / "PUBLICATION.json")
    assert metadata["accounting"]["raw_native_log_replay"] is False
    assert publication.verify_public_bundle(destination) == result
