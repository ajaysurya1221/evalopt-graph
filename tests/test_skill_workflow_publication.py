"""Synthetic-only publication controls. No live outcomes, models or network calls."""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import zlib
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
try:
    SPEC = importlib.util.spec_from_file_location(
        "workflow_publication_under_test", BENCH / "publish_bundle.py"
    )
    assert SPEC is not None and SPEC.loader is not None
    publication = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(publication)
finally:
    sys.path.pop(0)


def _load_reporter(path):
    reporter = publication._import_reporter(path / "campaign.py", "synthetic_publication_reporter")
    reporter.ROOT = path
    return reporter


def _json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(publication.canonical_bytes(value) + b"\n")


@pytest.fixture
def recorded_campaign(tmp_path):
    def create(content=b"answer = 42\n", *, finalized=True, extra_nodes=None):
        frozen = tmp_path / "frozen-source"
        shutil.copytree(BENCH, frozen, ignore=shutil.ignore_patterns("__pycache__"))
        reporter = _load_reporter(frozen)
        destination = tmp_path / "recorded"
        tasks = []
        for task_id in reporter.task_ids():
            task = reporter.load_task(task_id)
            source = frozen / reporter.task_path(task).relative_to(BENCH)
            tasks.append(
                {
                    "task_id": task_id,
                    "stage": "pilot",
                    "category": task["category"].replace("-", "_"),
                    "cluster_id": task["source_family"],
                    "task_sha256": publication._tree_identity(source),
                    "grader_sha256": publication._tree_identity(frozen / "tasks"),
                    "agent_seconds": 600,
                }
            )
        runtime = {"agent_image": "sha256:" + "1" * 64, "verifier_image": "sha256:" + "2" * 64}
        manifest = {
            "schema_version": "evalopt.skill-workflows.v1",
            "study_id": "synthetic-publication-control",
            "seed": 20261008,
            "pins": {
                "upstream_commit": reporter.UPSTREAM_COMMIT,
                "kernel_commit": reporter.KERNEL_COMMIT,
                "terminal_bench_commit": "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c",
                "skill_sha256": "a" * 64,
                "grader_sha256": publication._tree_identity(frozen / "tasks"),
                "policy_sha256": publication._tree_identity(frozen / "lib"),
                "analysis_sha256": publication._tree_identity(frozen / "lib"),
                "environment_sha256": publication.digest(runtime),
            },
            "runtime": {
                "harbor_version": "0.24.0",
                "codex_version": "0.154.0",
                "model": "gpt-6-astra",
                "reasoning_effort": "ultra",
                "auth_route": "chatgpt_subscription",
            },
            "limits": {
                "primary_seconds": 600,
                "max_concurrent_trials": 2,
                "max_children": 2,
                "delegation_depth": 1,
                "infrastructure_retries": 1,
            },
            "tasks": tasks,
        }
        source_lock = {
            "campaign_sha256": publication._tree_identity(frozen),
            "skill_sha256": "a" * 64,
            "upstream_sha256": "b" * 64,
            "upstream_loader_sha256": "c" * 64,
            "kernel_source_sha256": publication._tree_identity(
                Path(publication.evalopt_graph.__file__).resolve().parent
            ),
        }
        for name, value in {
            "manifest.json": manifest,
            "runtime.json": runtime,
            "source-lock.json": source_lock,
            "readiness.json": {"evidence_class": "synthetic offline control"},
            "readiness-sources.json": {
                "preflight": "/" + "Users/private-test/preflight",
                "controls": "/" + "Users/private-test/controls",
            },
        }.items():
            _json(destination / name, value)
        schedule = publication.build_schedule(tasks, "pilot")
        store = publication.CampaignStore(destination / "evidence", schedule)
        _json(
            destination / "registration-lock.json",
            {
                name: publication.bytes_digest((destination / name).read_bytes())
                for name in publication.REGISTRATION_FILES
            },
        )
        trial_id = schedule[0]["trial_id"]
        attempt = store.start_attempt(trial_id)
        snapshot = {
            "schema_version": "evalopt.stopped-nodes.v1",
            "nodes": {"answer.py": {"type": "file", "mode": 420, "data": base64.b64encode(content).decode()}},
        }
        snapshot["nodes"].update(extra_nodes or {})
        stopped = store.capture_stopped(
            trial_id,
            attempt,
            {
                "snapshot.json": publication.canonical_bytes(snapshot),
                "node-manifest.json": publication.canonical_bytes(
                    {"answer.py": publication.bytes_digest(content)}
                ),
                "workflow-exposure.json": publication.canonical_bytes(
                    {"arm": schedule[0]["arm"], "source_files": {}, "verified_before_agent": True}
                ),
            },
        )
        log = b'{"outcome":"passed"}'
        store.record_visible(
            trial_id,
            attempt,
            {
                "schema_version": "evalopt.workflow-visible.v1",
                "trial_id": trial_id,
                "stopped_sha256": stopped,
                "observed_at": "2026-10-08T00:00:00+00:00",
                "required_gates": ["visible_check"],
                "gates": [
                    {
                        "name": "visible_check",
                        "status": "PASS",
                        "producer": "controller",
                        "evidence_sha256": publication.bytes_digest(log),
                    }
                ],
                "tests_weakened": False,
                "boundary_violations": [],
                "unsupported_claims": [],
            },
            {"visible-check.json": log},
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
            },
        )
        if finalized:
            store.finish_attempt(
                trial_id,
                attempt,
                "completed",
                usage={
                    "child_usage_complete": True,
                    "runtime_valid": True,
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "model_calls": 1,
                    "tool_calls": 1,
                    "wall_seconds": 3,
                    "agent_count": 1,
                    "aggregation": "agent_exclusive",
                    "returned_models": ["gpt-6-astra"],
                    "returned_efforts": ["ultra"],
                    "cli_versions": ["0.154.0"],
                },
            )
        reporter.report(destination)
        # Deliberately secret-shaped SYNTHETIC controls outside the publication whitelist.
        (destination / "private-harbor").mkdir()
        (destination / "private-harbor/auth.json").write_text('{"access_token":"synthetic-private-only"}')
        (destination / "auth.json").write_text('{"refresh_token":"synthetic-private-only"}')
        return destination, frozen, store, trial_id

    return create


def _source_hashes(path):
    return {
        item.relative_to(path).as_posix(): publication.bytes_digest(item.read_bytes())
        for item in path.rglob("*")
        if item.is_file()
    }


def test_public_bundle_is_reproducible_replayed_and_excludes_private_material(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    before = _source_hashes(source)
    first = publication.export_public_bundle(source, tmp_path / "public-a", frozen_source=frozen)
    second = publication.export_public_bundle(source, tmp_path / "public-b", frozen_source=frozen)
    assert first == second
    assert first["attempts_verified"] == 1
    assert first["policy_decisions_replayed"] == 3
    assert first["analysis_reproduced"] is True
    assert first["network_publication_performed"] is False
    assert _source_hashes(source) == before
    public = tmp_path / "public-a"
    assert not (public / "auth.json").exists()
    assert not (public / "private-harbor").exists()
    assert not (public / "readiness-sources.json").exists()
    assert "No comparative headline" in (public / "CLAIMS.md").read_text()
    assert "maintainer-run" in (public / "CLAIMS.md").read_text()
    assert list(public.rglob("workflow-exposure.json"))
    assert _source_hashes(public) == _source_hashes(tmp_path / "public-b")


@pytest.mark.parametrize(
    "content",
    [
        b"OPENAI_API_KEY=sk-proj-" + b"SYNTHETIC" * 6,
        b"ghp_" + b"SYNTHETIC" * 5,
        b"github_pat_" + b"SYNTHETIC" * 5,
        b".".join(
            base64.urlsafe_b64encode(part).rstrip(b"=")
            for part in (b'{"alg":"HS256"}', b'{"sub":"synthetic"}', b"syntheticSignature")
        ),
        b'{"refresh_token":"synthetic-refresh-control"}',
        b"local checkout /" + b"Users/private-test/Developer/repo",
        b"C:" + b"\\Users\\private-test\\workspace",
    ],
)
def test_decoded_snapshot_sensitive_content_fails_before_destination_creation(
    recorded_campaign, tmp_path, content
):
    source, frozen, _, _ = recorded_campaign(content)
    before = _source_hashes(source)
    destination = tmp_path / "sensitive-candidate"
    with pytest.raises(publication.PublicationError) as exc:
        publication.export_public_bundle(source, destination, frozen_source=frozen)
    assert "decoded file" in str(exc.value)
    assert "SYNTHETIC" not in str(exc.value)
    assert "private-test" not in str(exc.value)
    assert not destination.exists()
    assert _source_hashes(source) == before


def test_hash_bound_evidence_is_never_silently_redacted(recorded_campaign, tmp_path):
    source, frozen, store, trial_id = recorded_campaign()
    path = store.root / "trials" / trial_id / "attempt-1/agent/snapshot.json"
    path.write_bytes(b'{"changed":"after capture"}')
    with pytest.raises(ValueError, match="changed"):
        publication.export_public_bundle(source, tmp_path / "public", frozen_source=frozen)
    assert path.read_bytes() == b'{"changed":"after capture"}'
    assert not (tmp_path / "public").exists()


def test_unfinished_attempt_blocks_publication(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign(finalized=False)
    with pytest.raises(publication.PublicationError, match="not finalized"):
        publication.export_public_bundle(source, tmp_path / "public", frozen_source=frozen)


def test_export_requires_fresh_destination_and_rejects_symlinks(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(publication.PublicationError, match="fresh"):
        publication.export_public_bundle(source, existing, frozen_source=frozen)
    linked = tmp_path / "linked"
    linked.symlink_to(source, target_is_directory=True)
    with pytest.raises(publication.PublicationError, match="symlink"):
        publication.export_public_bundle(linked, tmp_path / "public", frozen_source=frozen)


def _rewrite_candidate_checksums(public):
    path = public / "CHECKSUMS.json"
    files = {
        item.relative_to(public).as_posix(): {
            "size": item.stat().st_size,
            "sha256": publication.bytes_digest(item.read_bytes()),
        }
        for item in public.rglob("*")
        if item.is_file() and item != path
    }
    _json(
        path,
        {
            "schema_version": "evalopt.public-checksums.v1",
            "bundle_id": publication.digest(files),
            "files": files,
        },
    )


def test_complete_candidate_validation_rejects_extra_private_file_even_with_recomputed_checksums(
    recorded_campaign, tmp_path
):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    (public / "raw-trajectory.jsonl").write_text('{"harmless":"still outside whitelist"}')
    _rewrite_candidate_checksums(public)
    with pytest.raises(publication.PublicationError, match="non-whitelisted"):
        publication.verify_public_bundle(public)


def test_complete_candidate_validation_rejects_unsupported_claim_table(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    (public / "CLAIMS.md").write_text("Universal superiority established.\n")
    _rewrite_candidate_checksums(public)
    with pytest.raises(publication.PublicationError, match="claim-to-evidence"):
        publication.verify_public_bundle(public)


def test_public_report_numbers_must_reproduce_evidence_even_if_checksums_are_recomputed(
    recorded_campaign, tmp_path
):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    report = publication.read_json(public / "reports/analysis.json")
    report["overall_upgrade_permitted"] = True
    _json(public / "reports/analysis.json", report)
    _rewrite_candidate_checksums(public)
    with pytest.raises(publication.PublicationError, match="does not reproduce"):
        publication.verify_public_bundle(public)


@pytest.mark.parametrize(
    "snapshot",
    [
        {
            "schema_version": "evalopt.stopped-nodes.v1",
            "nodes": {"../outside": {"type": "file", "data": "YWJj"}},
        },
        {
            "schema_version": "evalopt.stopped-nodes.v1",
            "nodes": {"file": {"type": "file", "data": "not base64!!!"}},
        },
    ],
)
def test_malformed_or_escaping_snapshot_is_not_publishable(snapshot):
    with pytest.raises(publication.PublicationError):
        publication.scan_public_file("evidence/snapshot.json", publication.canonical_bytes(snapshot))


def _git_node(content):
    data = b"blob " + str(len(content)).encode() + b"\0" + content
    identity = hashlib.sha1(data).hexdigest()
    return {
        ".git/objects/" + identity[:2] + "/" + identity[2:]: {
            "type": "file",
            "mode": 420,
            "data": base64.b64encode(zlib.compress(data)).decode(),
        }
    }


def test_clean_compressed_git_history_is_inspected_and_preserved(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign(extra_nodes=_git_node(b"clean historical version\n"))
    result = publication.export_public_bundle(source, tmp_path / "public", frozen_source=frozen)
    assert result["sensitive_scan_passed"] is True


def test_secret_only_in_compressed_git_history_blocks_export(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign(
        extra_nodes=_git_node(b'{"refresh_token":"SYNTHETIC-only-in-removed-file"}')
    )
    with pytest.raises(publication.PublicationError, match="decompressed Git object"):
        publication.export_public_bundle(source, tmp_path / "public", frozen_source=frozen)
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize(
    "name,data",
    [
        (".git/objects/pack/pack-example.pack", b"PACK-unsupported"),
        (".git/objects/" + "a" * 2 + "/" + "b" * 38, b"invalid-zlib"),
        (".git/objects/" + "a" * 2 + "/" + "b" * 38, zlib.compress(b"blob 1\0x")),
    ],
)
def test_uninspectable_git_storage_fails_closed(name, data):
    snapshot = {
        "schema_version": "evalopt.stopped-nodes.v1",
        "nodes": {name: {"type": "file", "mode": 420, "data": base64.b64encode(data).decode()}},
    }
    with pytest.raises(publication.PublicationError, match="Git object"):
        publication.scan_public_file("evidence/snapshot.json", publication.canonical_bytes(snapshot))


def test_git_object_expansion_is_bounded(monkeypatch):
    monkeypatch.setattr(publication, "MAX_GIT_OBJECT_BYTES", 30)
    snapshot = {"schema_version": "evalopt.stopped-nodes.v1", "nodes": _git_node(b"x" * 1000)}
    with pytest.raises(publication.PublicationError, match="oversized"):
        publication.scan_public_file("evidence/snapshot.json", publication.canonical_bytes(snapshot))


def test_checksum_envelope_cannot_hide_credentials(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    checksum = publication.read_json(public / "CHECKSUMS.json")
    checksum["private"] = {"access_token": "SYNTHETIC-review-token"}
    _json(public / "CHECKSUMS.json", checksum)
    with pytest.raises(publication.PublicationError, match="credential"):
        publication.verify_public_bundle(public)


@pytest.mark.parametrize(
    "target,key,value",
    [
        ("manifest.json", "model", "unregistered-model"),
        ("runtime.json", "agent_image", "sha256:" + "9" * 64),
    ],
)
def test_public_registration_cannot_change_with_only_recomputed_checksums(
    recorded_campaign, tmp_path, target, key, value
):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    record = publication.read_json(public / target)
    if target == "manifest.json":
        record["runtime"][key] = value
    else:
        record[key] = value
    _json(public / target, record)
    _rewrite_candidate_checksums(public)
    with pytest.raises(ValueError, match="registered|registration"):
        publication.verify_public_bundle(public)


def test_unscheduled_evidence_is_not_publishable(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    _json(public / "evidence/trials/not-scheduled/attempt-1/finish.json", {})
    _rewrite_candidate_checksums(public)
    with pytest.raises(publication.PublicationError, match="unexpected trial"):
        publication.verify_public_bundle(public)


def test_special_nodes_are_rejected_without_opening_them(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    os.mkfifo(public / "unlisted-pipe")
    with pytest.raises(publication.PublicationError, match="nonregular"):
        publication.verify_public_bundle(public)


def test_credentials_inside_json_stdout_are_scanned():
    data = json.dumps({"stdout": json.dumps({"refresh_token": "SYNTHETIC-private-refresh"})}).encode()
    with pytest.raises(publication.PublicationError, match="credential"):
        publication.scan_public_file("controller/visible-check.json", data)


def test_canonical_host_paths_remain_blocked_without_misclassifying_route_literals():
    publication.scan_public_file("route.py", b'route = "/users/a%20b"')
    for content in (
        b"/" + b"Users/person/repo",
        b"/" + b"home/person/repo",
        b"c:" + b"\\uSeRs\\person\\repo",
    ):
        with pytest.raises(publication.PublicationError, match="personal_host_path"):
            publication.scan_public_file("artifact.txt", content)


@pytest.mark.parametrize("stage", ["heldout", "transfer"])
def test_pilot_publisher_cannot_bypass_other_stage_release_gates(stage):
    with pytest.raises(publication.PublicationError, match="heldout_publish"):
        publication._require_pilot_publication([{"stage": stage}])


def test_nested_report_checksums_must_match_reproduced_reports(recorded_campaign, tmp_path):
    source, frozen, _, _ = recorded_campaign()
    public = tmp_path / "public"
    publication.export_public_bundle(source, public, frozen_source=frozen)
    checksum = publication.read_json(public / "reports/checksums.json")
    checksum["files"]["analysis.json"] = "0" * 64
    _json(public / "reports/checksums.json", checksum)
    _rewrite_candidate_checksums(public)
    with pytest.raises(publication.PublicationError, match="report checksum envelope"):
        publication.verify_public_bundle(public)
