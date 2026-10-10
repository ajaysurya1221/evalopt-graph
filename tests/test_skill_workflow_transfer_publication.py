"""Synthetic-only transfer projection and public-folder adversarial controls."""

from __future__ import annotations

import asyncio
import fcntl
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("tomllib", reason="transfer controller requires Python 3.13.12")
pytestmark = pytest.mark.skipif(
    sys.version_info[:3] != (3, 13, 12), reason="controller integration is pinned to CPython 3.13.12"
)
BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import transfer_publish as subject  # noqa: E402

import test_skill_workflow_transfer_campaign as support  # noqa: E402


@pytest.fixture
def recorded(tmp_path, monkeypatch):
    fixture = support.source_fixture.__wrapped__(tmp_path)
    fixture, directory, _ = support.registered.__wrapped__(fixture, monkeypatch)
    support.fake_execution(monkeypatch, [])
    asyncio.run(support.subject.run_campaign(directory, fixture.upstream, limit=1))
    return directory


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(subject.canonical_bytes(value) + b"\n")


def rehash(root):
    records = {
        path.relative_to(root).as_posix(): {
            "size": path.stat().st_size,
            "sha256": subject.bytes_digest(path.read_bytes()),
        }
        for path in root.rglob("*")
        if path.is_file() and path != root / "CHECKSUMS.json"
    }
    write_json(
        root / "CHECKSUMS.json",
        {
            "schema_version": "evalopt.transfer-public-checksums.v1",
            "bundle_id": subject.digest(records),
            "files": records,
        },
    )


def test_transfer_projection_reproduces_without_policies_or_private_archives(recorded, tmp_path):
    first = subject.export_public_bundle(recorded, tmp_path / "public-one")
    second = subject.export_public_bundle(recorded, tmp_path / "public-two")
    assert first == second
    assert first["attempts_verified"] == 1 and first["reward_analysis_reproduced"] is True
    assert first["policy_replay"] == "not applicable; no U/M/G"
    assert first["raw_archives_included"] is False and first["original_verifier_reexecuted"] is False
    assert not (tmp_path / "public-one/private-sources.json").exists()
    assert not list((tmp_path / "public-one").rglob("policies.json"))
    assert not list((tmp_path / "public-one").rglob("*.tar"))
    assert b"not an official leaderboard" in (tmp_path / "public-one/CLAIMS.md").read_bytes()


@pytest.mark.parametrize(
    "target", ["outer-secret", "report-envelope", "unsupported-score", "false-claim", "registered-runtime"]
)
def test_whole_transfer_candidate_validation_rejects_rehashed_mutations(recorded, tmp_path, target):
    public = tmp_path / "public"
    subject.export_public_bundle(recorded, public)
    if target == "outer-secret":
        data = subject.read_json(public / "CHECKSUMS.json")
        data["private"] = {"refresh_token": "SYNTHETIC-review-token"}
        write_json(public / "CHECKSUMS.json", data)
    else:
        if target == "report-envelope":
            path = public / "reports/checksums.json"
            data = subject.read_json(path)
            data["files"]["analysis.json"] = "0" * 64
            write_json(path, data)
        elif target == "unsupported-score":
            path = public / "reports/analysis.json"
            data = subject.read_json(path)
            data["headline_permitted"] = True
            write_json(path, data)
        elif target == "false-claim":
            (public / "CLAIMS.md").write_text("Independent universal superiority established.")
        else:
            path = public / "manifest.json"
            data = subject.read_json(path)
            data["runtime"]["model"] = "unregistered"
            write_json(path, data)
        rehash(public)
    with pytest.raises(ValueError):
        subject.verify_public_bundle(public)


@pytest.mark.parametrize("kind", ["unscheduled", "policy", "raw", "fifo"])
def test_public_transfer_whitelist_rejects_unscheduled_or_private_nodes(recorded, tmp_path, kind):
    public = tmp_path / "public"
    subject.export_public_bundle(recorded, public)
    if kind == "fifo":
        os.mkfifo(public / "pipe")
    else:
        paths = {
            "unscheduled": "evidence/trials/unknown/attempt-1/finish.json",
            "policy": "policies.json",
            "raw": "raw-output.tar",
        }
        write_json(public / paths[kind], {"synthetic": True})
        rehash(public)
    with pytest.raises(ValueError):
        subject.verify_public_bundle(public)


def test_transfer_export_refuses_active_controller(recorded, tmp_path):
    with (recorded / ".scheduler.lock").open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(subject.authored.PublicationError, match="active"):
            subject.export_public_bundle(recorded, tmp_path / "public")
        fcntl.flock(lock, fcntl.LOCK_UN)
    assert not (tmp_path / "public").exists()


def test_sensitive_hash_bound_transfer_artifact_is_not_silently_redacted(recorded, tmp_path):
    # Deliberately finish a synthetic classified interruption with an unsafe free-form
    # usage value. It remains retained privately and must block publication.
    manifest, _, schedule = support.subject.read_registration(recorded)
    store = support.subject.TransferStore(recorded / "evidence", schedule)
    trial_id = schedule[1]["trial_id"]
    attempt = store.start_attempt(trial_id)
    store.finish_attempt(
        trial_id,
        attempt,
        "infra_failure",
        error_code="controller_interrupted",
        usage={"refresh_token": "SYNTHETIC-unpublished-token"},
    )
    support.subject.report(recorded)
    with pytest.raises(subject.authored.PublicationError, match="credential"):
        subject.export_public_bundle(recorded, tmp_path / "public")
    assert not (tmp_path / "public").exists()
