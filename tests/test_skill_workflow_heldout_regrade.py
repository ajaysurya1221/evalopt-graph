"""Synthetic36 regrade integration; no model calls or actual campaign changes."""

from __future__ import annotations

import copy
import shutil
from types import SimpleNamespace

import pytest

import test_skill_workflow_accounting_policy_review as native
import test_skill_workflow_heldout as base
import test_skill_workflow_heldout_publication as public
import test_skill_workflow_pilot_regrade as adapter

heldout = base.heldout
write_json = public.write_json


@pytest.fixture
def reviewed_regrade(tmp_path, monkeypatch):
    """Real36 stores/regrades; isolate only separately tested amendment accounting."""
    source = adapter.regrade_source.__wrapped__(tmp_path, monkeypatch)
    pilot = source.pilot
    manifest = base.pilot_manifest()
    manifest["tasks"] = heldout.read_json(pilot / "manifest.json")["tasks"]
    manifest["pins"]["grader_sha256"] = heldout.digest("original-suite")
    skills = {
        "evalopt": manifest["pins"]["skill_sha256"],
        "upstream": heldout.source_identity(tmp_path / "absent"),
    }
    preflight, controls = tmp_path / "preflight", tmp_path / "controls"
    write_json(
        preflight / "summary.json",
        {
            "config_sha256": heldout.bytes_digest((heldout.HERE / "codex.toml").read_bytes()),
            "image_id": source.runtime["agent_image"],
            "skill_sources": skills,
        },
    )
    for name, value in {
        "manifest.json": manifest,
        "readiness.json": {
            "preflight_sha256": heldout.source_identity(preflight),
            "controls_sha256": heldout.source_identity(controls),
        },
        "readiness-sources.json": {"preflight": str(preflight), "controls": str(controls)},
        "source-lock.json": {
            "campaign_sha256": heldout.source_identity(heldout.ROOT),
            "skill_sha256": skills["evalopt"],
            "upstream_sha256": skills["upstream"],
            "upstream_loader_sha256": heldout.bytes_digest(b"{}"),
        },
    }.items():
        write_json(pilot / name, value)
    registration = heldout.campaign._registration_identity(pilot)
    write_json(pilot / "registration-lock.json", registration)
    source.info["registration_sha256"] = heldout.digest(registration)
    source.export_id = heldout.campaign.report(pilot)["export_id"]
    regrade_root, identity = adapter.prepared(source)
    receipt = adapter.regrade.execute(regrade_root, registration_sha256=identity, runner=adapter.fake_execute)
    review = tmp_path / "pilot-review.json"
    write_json(
        review,
        {
            "schema_version": "evalopt.pilot-review.v2",
            "verdict": "ready_for_heldout",
            "pilot_registration_sha256": source.info["registration_sha256"],
            "pilot_export_id": source.export_id,
            "checks": dict.fromkeys(heldout.REVIEW_CHECKS_V2, True),
            "accounting": {
                "amendment_sha256": source.amendment,
                "resource_report_sha256": heldout.digest("synthetic-accounting-report"),
                "rules_sha256": heldout.digest(heldout.RULES),
            },
            "grading_compatibility": {
                **receipt["grading"],
                "verdict": "regraded_stopped_outputs",
                "reason": "Invalid JSON scoring changed; all36 retained outputs regraded in isolation.",
                "regrade_registration_sha256": identity,
                "regrade_evidence_sha256": receipt["evidence_sha256"],
            },
        },
    )
    monkeypatch.setattr(
        heldout,
        "_verify_amended_pilot",
        lambda _, reviewed, *__: {
            **reviewed["accounting"],
            "complete_final_attempts": 36,
            "partial_final_attempts": 0,
            "retained_attempts": 36,
            "unavailable_attempts": 0,
        },
    )
    return SimpleNamespace(
        source=source, review=review, root=regrade_root, identity=identity, receipt=receipt
    )


@pytest.fixture
def frozen_regrade(reviewed_regrade, tmp_path, monkeypatch):
    item = reviewed_regrade
    sealed = public.sealed.__wrapped__(tmp_path)
    source = item.source
    frozen = base.frozen.__wrapped__(
        sealed, (source.pilot, item.review, source.store, source.schedule), tmp_path, monkeypatch
    )
    item.frozen = frozen
    return item


@pytest.fixture
def recorded_regrade(frozen_regrade, tmp_path, monkeypatch):
    item = frozen_regrade
    root, _, _ = item.frozen
    policy = heldout.read_accounting_policy(root)
    usage = native.observed(tmp_path / "synthetic-native", policy)
    finish = heldout.CampaignStore.finish_attempt

    def registered_usage(self, *args, **kwargs):
        kwargs["usage"] = usage
        return finish(self, *args, **kwargs)

    monkeypatch.setattr(heldout.CampaignStore, "finish_attempt", registered_usage)
    create = public.recorded.__wrapped__(item.frozen, tmp_path, monkeypatch)
    return item, create()


def test_review_and_freeze_bind_full36_without_changing_original_outcomes(frozen_regrade):
    item = frozen_regrade
    root, upstream, identity = item.frozen
    before = public.hashes(item.source.store.root)
    receipt = heldout.verify_pilot(item.source.pilot, item.review)
    assert receipt["candidate_conditions"]["grading_regrade"] == item.receipt
    assert item.receipt["changed_trial_count"] == 3
    assert item.receipt["original_policy_decisions_changed"] is False
    assert heldout.verify_retained_regrade(root) == item.receipt
    _, _, schedule, _ = heldout.verify_registration(root, upstream, identity)
    assert len(schedule) == 432
    assert set(heldout.REGRADE_FILES) <= set(heldout.read_json(root / "heldout-lock.json"))
    assert len(list((root / "pilot-regrade/results").glob("*.json"))) == 36
    assert not (root / "pilot-regrade/local-sources.json").exists()
    assert not (root / "pilot-regrade/private-execution").exists()
    assert public.hashes(item.source.store.root) == before
    assert public.hashes(root / "pilot-regrade") == {
        name: heldout.bytes_digest(raw)
        for name, raw in adapter.regrade.public_payloads(item.root / "registration.json").items()
    }


@pytest.mark.parametrize(
    "field",
    ["pilot", "current", "regrade_registration_sha256", "regrade_evidence_sha256", "missing", "extra"],
)
def test_review_rejects_unbound_or_ambiguous_grading_approval(reviewed_regrade, field):
    item = reviewed_regrade
    review = heldout.read_json(item.review)
    change = review["grading_compatibility"]
    if field == "missing":
        del change["regrade_evidence_sha256"]
    elif field == "extra":
        change["unreviewed_override"] = True
    elif field in {"pilot", "current"}:
        change[field]["suite"] = "f" * 64
    else:
        change[field] = "f" * 64
    write_json(item.review, review)
    with pytest.raises((ValueError, FileNotFoundError)):
        heldout.verify_pilot(item.source.pilot, item.review)


@pytest.mark.parametrize("field", ["amendment", "export", "registration", "schedule", "coverage"])
def test_receipt_cross_binding_rejects_another_reviewed_pilot(reviewed_regrade, field):
    item = reviewed_regrade
    receipt = copy.deepcopy(item.receipt)
    key = {
        "amendment": "accounting_amendment_sha256",
        "export": "pilot_export_id",
        "registration": "pilot_registration_sha256",
        "schedule": "schedule_sha256",
        "coverage": "regraded_attempts",
    }[field]
    receipt[key] = 35 if field == "coverage" else "f" * 64
    with pytest.raises(ValueError, match="reviewed identities"):
        heldout._match_regrade_receipt(
            receipt,
            heldout.read_json(item.review),
            receipt["grading"]["pilot"],
            receipt["grading"]["current"],
            heldout.digest(item.source.schedule),
        )


@pytest.mark.parametrize("mutation", ["missing_result", "original_grade", "current_grader"])
def test_private_review_requires_actual_complete_regrade_assets(reviewed_regrade, mutation):
    item = reviewed_regrade
    if mutation == "missing_result":
        next((item.root / "results").glob("*.json")).unlink()
    elif mutation == "original_grade":
        next((item.root / "inputs").glob("*/grade.json")).write_text("{}")
    else:
        registration = heldout.read_json(item.root / "registration.json")
        path = next(iter(registration["grader_files"]))
        (item.root / "grader" / path).write_text("changed grader")
    with pytest.raises((ValueError, FileNotFoundError)):
        heldout.verify_pilot(item.source.pilot, item.review)


@pytest.mark.parametrize("mutation", ["result", "receipt", "private", "empty_directory", "symlink", "mode"])
def test_frozen_tree_rejects_changes_even_after_node_manifest_rehash(frozen_regrade, mutation):
    root, _, _ = frozen_regrade.frozen
    tree = root / "pilot-regrade"
    result = next((tree / "results").glob("*.json"))
    if mutation == "result":
        value = heldout.read_json(result)
        value["current_effective_grade"]["valid_completion"] = not value["current_effective_grade"][
            "valid_completion"
        ]
        write_json(result, value)
    elif mutation == "receipt":
        receipt = heldout.read_json(root / "pilot-regrade-receipt.json")
        receipt["changed_trial_count"] = 0
        write_json(root / "pilot-regrade-receipt.json", receipt)
    elif mutation == "private":
        write_json(tree / "local-sources.json", {"extra": "not-public"})
    elif mutation == "empty_directory":
        (tree / "unregistered").mkdir()
    elif mutation == "symlink":
        result.unlink()
        result.symlink_to(root / "pilot-regrade-receipt.json")
    else:
        result.chmod(0o755)
    if mutation not in {"mode", "symlink"}:
        write_json(root / "pilot-regrade-manifest.json", heldout.regrade_nodes(tree))
    write_json(root / "heldout-lock.json", heldout._heldout_identity(root))
    with pytest.raises(ValueError):
        heldout.verify_retained_regrade(root)


def test_public_bundle_carries_and_replays_entire_regrade_without_private_sources(recorded_regrade, tmp_path):
    item, record = recorded_regrade
    destination = tmp_path / "public"
    before = public.hashes(record.root)
    result = public.export(record, destination)
    assert public.publication.verify_public_bundle(destination) == result
    assert public.hashes(record.root) == before
    assert (
        heldout.verify_retained_regrade(destination, source=destination / "benchmark-source") == item.receipt
    )
    assert public.hashes(destination / "pilot-regrade") == public.hashes(record.root / "pilot-regrade")
    assert not (destination / "pilot-regrade/local-sources.json").exists()
    assert not (destination / "pilot-regrade/private-execution").exists()
    assets = heldout.read_json(destination / "ASSETS.json")
    assert any(name.startswith("pilot-regrade/results/") for name in assets["nodes"])


def test_old_review_cannot_hide_retained_regrade_metadata(frozen_regrade):
    root, _, _ = frozen_regrade.frozen
    review = heldout.read_json(root / "pilot-review.json")
    compatibility = review["grading_compatibility"]
    compatibility["verdict"] = "unchanged_semantics"
    for key in heldout.REGRADE_PINS:
        compatibility.pop(key)
    write_json(root / "pilot-review.json", review)
    with pytest.raises(ValueError, match="explicit registered review"):
        heldout.verify_retained_regrade(root)


def test_public_regrade_tampering_fails_after_all_outer_envelopes_are_rehashed(recorded_regrade, tmp_path):
    _, record = recorded_regrade
    original = tmp_path / "original-public"
    public.export(record, original)
    for mutation in ("result", "receipt", "private", "missing_result"):
        target = tmp_path / ("tampered-" + mutation)
        shutil.copytree(original, target)
        tree = target / "pilot-regrade"
        result = next((tree / "results").glob("*.json"))
        if mutation == "result":
            value = heldout.read_json(result)
            value["current_effective_grade"]["functional_success"] = not value["current_effective_grade"][
                "functional_success"
            ]
            write_json(result, value)
        elif mutation == "receipt":
            value = heldout.read_json(target / "pilot-regrade-receipt.json")
            value["changed_trial_count"] = 0
            write_json(target / "pilot-regrade-receipt.json", value)
        elif mutation == "private":
            write_json(tree / "local-sources.json", {"private_execution": "unregistered"})
        else:
            result.unlink()
        # Recompute all transport/node/registration envelopes, without falsifying
        # the content identities explicitly approved by the original pilot review.
        write_json(target / "pilot-regrade-manifest.json", heldout.regrade_nodes(tree))
        assets = {}
        for origin, prefix in public.publication._asset_roots(target, target / "benchmark-source"):
            _, nodes = public.publication._asset_tree(origin, prefix)
            assets.update(nodes)
        write_json(target / "ASSETS.json", {"schema_version": "evalopt.heldout-assets.v1", "nodes": assets})
        lock = heldout._heldout_identity(target)
        write_json(target / "heldout-lock.json", lock)
        for name in ("PUBLICATION.json", "UNAVAILABLE.json"):
            value = heldout.read_json(target / name)
            value["heldout_registration_sha256"] = heldout.digest(lock)
            write_json(target / name, value)
        checksums = {
            path.relative_to(target).as_posix(): {
                "size": path.stat().st_size,
                "sha256": heldout.bytes_digest(path.read_bytes()),
            }
            for path in sorted(target.rglob("*"))
            if path.is_file() and path != target / "CHECKSUMS.json"
        }
        write_json(
            target / "CHECKSUMS.json",
            {
                "schema_version": "evalopt.heldout-public-checksums.v1",
                "bundle_id": heldout.digest(checksums),
                "files": checksums,
            },
        )
        with pytest.raises((ValueError, FileNotFoundError)):
            public.publication.verify_public_bundle(target)
