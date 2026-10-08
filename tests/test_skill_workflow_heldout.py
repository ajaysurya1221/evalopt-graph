"""Offline held-out registration controls; synthetic data, never model trials."""

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
import heldout_campaign as heldout  # noqa: E402
from runtime import harbor_campaign  # noqa: E402
from tasks import suite  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "heldout_scheduler_controls", Path(__file__).with_name("test_skill_workflow_scheduler.py")
)
assert SPEC and SPEC.loader
helpers = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(helpers)


@pytest.fixture
def sealed(tmp_path):
    root = tmp_path / "sealed"
    root.mkdir()
    records = []
    for category in heldout.CATEGORIES:
        for number in range(8):
            task_id = f"{category.replace('_', '-')}-{number}"
            directory = root / task_id
            (directory / "agent").mkdir(parents=True)
            (directory / "agent/app.py").write_text("def run(): return None\n")
            (directory / "agent/verify.py").write_text("print('visible')\n")
            task = {
                "schema_version": 1,
                "id": task_id,
                "split": "heldout",
                "category": category.replace("_", "-"),
                "source_family": task_id,
                "instruction": "Implement the specified finite behavior.",
                "allowed_changes": ["app.py"],
                "visible_check": "python -B verify.py",
                "expected": {
                    "status": "completed",
                    "findings": [],
                    "blocker_resources": [],
                    "visible_outcome": "passed",
                },
                "git_operations": [],
            }
            (directory / "task.json").write_text(json.dumps(task))
            (directory / "hidden_cases.json").write_text(
                json.dumps(
                    [
                        {
                            "module": "app",
                            "function": "run",
                            "args": [],
                            "result": "HIDDEN_EXPECTED_SENTINEL",
                            "preserve_args": True,
                        }
                    ]
                )
            )
            (directory / "controls.json").write_text('{"private_control":"HIDDEN_CONTROL_SENTINEL"}')
            records.append(
                {
                    "id": task_id,
                    "category": task["category"],
                    "source_family": task_id,
                    "files": {
                        p.relative_to(directory).as_posix(): heldout.bytes_digest(p.read_bytes())
                        for p in directory.rglob("*")
                        if p.is_file()
                    },
                }
            )
    manifest = {
        "status": "review-candidate-not-campaign-freeze",
        "task_count": 48,
        "agent_trials": 0,
        "tasks": records,
    }
    (root / "candidate-manifest.json").write_text(json.dumps(manifest))
    (root / "_qa").mkdir()
    (root / "_qa/old-score.json").write_text('"excluded fixture"')
    return root, heldout.bytes_digest((root / "candidate-manifest.json").read_bytes())


def pilot_manifest():
    tasks = []
    for task_id in suite.task_ids():
        task = suite.load_task(task_id)
        tasks.append(
            {
                "task_id": task_id,
                "stage": "pilot",
                "category": task["category"].replace("-", "_"),
                "cluster_id": task["source_family"],
                "task_sha256": heldout.source_identity(suite.task_path(task)),
                "grader_sha256": heldout.source_identity(heldout.ROOT / "tasks"),
                "agent_seconds": 600,
            }
        )
    return {
        "schema_version": "evalopt.skill-workflows.v1",
        "study_id": "offline-pilot-control",
        "seed": 20261008,
        "pins": {
            "upstream_commit": heldout.campaign.UPSTREAM_COMMIT,
            "kernel_commit": heldout.campaign.KERNEL_COMMIT,
            "terminal_bench_commit": "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c",
            **dict.fromkeys(
                ("skill_sha256", "grader_sha256", "policy_sha256", "analysis_sha256", "environment_sha256"),
                "a" * 64,
            ),
            "skill_sha256": heldout.source_identity(heldout.campaign.REPO / "skills/eval-opt"),
            "grader_sha256": heldout.source_identity(heldout.ROOT / "tasks"),
            "environment_sha256": heldout.digest(
                {
                    "agent_image": "sha256:" + heldout.digest("agent"),
                    "verifier_image": "sha256:" + heldout.digest("verifier"),
                }
            ),
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


@pytest.fixture
def reviewed_pilot(tmp_path):
    pilot = tmp_path / "pilot"
    manifest = pilot_manifest()
    schedule = heldout.build_schedule(manifest["tasks"], "pilot")
    store = heldout.CampaignStore(pilot / "evidence", schedule)
    runtime = {
        "agent_image": "sha256:" + heldout.digest("agent"),
        "verifier_image": "sha256:" + heldout.digest("verifier"),
    }
    sources = {
        "evalopt": manifest["pins"]["skill_sha256"],
        "upstream": heldout.source_identity(tmp_path / "absent"),
    }
    preflight, controls = tmp_path / "preflight", tmp_path / "controls"
    heldout.write_once(
        preflight / "summary.json",
        {
            "config_sha256": heldout.bytes_digest((heldout.HERE / "codex.toml").read_bytes()),
            "image_id": runtime["agent_image"],
            "skill_sources": sources,
        },
    )
    heldout.write_once(
        controls / "results.json",
        {
            "tasks_sha256": manifest["pins"]["grader_sha256"],
            "verify_sha256": heldout.bytes_digest((heldout.HERE / "verify.py").read_bytes()),
        },
    )
    for name, value in {
        "manifest.json": manifest,
        "runtime.json": runtime,
        "readiness.json": {
            "preflight_sha256": heldout.source_identity(preflight),
            "controls_sha256": heldout.source_identity(controls),
        },
        "readiness-sources.json": {"preflight": str(preflight), "controls": str(controls)},
        "source-lock.json": {
            "campaign_sha256": heldout.source_identity(heldout.ROOT),
            "skill_sha256": sources["evalopt"],
            "upstream_sha256": sources["upstream"],
            "upstream_loader_sha256": heldout.bytes_digest(b"{}"),
        },
    }.items():
        heldout.write_once(pilot / name, value)
    heldout.write_once(pilot / "registration-lock.json", heldout.campaign._registration_identity(pilot))
    for row in schedule:
        helpers.finish_success(store, row)
    report = heldout.campaign.report(pilot)
    review = tmp_path / "pilot-review.json"
    heldout.write_once(
        review,
        {
            "schema_version": "evalopt.pilot-review.v1",
            "verdict": "ready_for_heldout",
            "pilot_registration_sha256": heldout.digest(heldout.read_json(pilot / "registration-lock.json")),
            "pilot_export_id": report["export_id"],
            "checks": dict.fromkeys(heldout.REVIEW_CHECKS, True),
        },
    )
    return pilot, review, store, schedule


def test_sealed_manifest_accepts_48_exact_tasks_and_excludes_qa(sealed):
    root, checksum = sealed
    assert len(heldout.verify_sealed_tasks(root, checksum)["tasks"]) == 48
    (root / "_qa/extra.json").write_text("{}")
    heldout.verify_sealed_tasks(root, checksum)


@pytest.mark.parametrize(
    "mutation", ["bytes", "extra-file", "empty-directory", "symlink", "special", "extra-root"]
)
def test_sealed_manifest_rejects_unregistered_nodes(sealed, mutation):
    root, checksum = sealed
    directory = next(path for path in root.iterdir() if path.name != "_qa" and path.is_dir())
    if mutation == "bytes":
        (directory / "agent/app.py").write_text("changed")
    elif mutation == "extra-file":
        (directory / "unexpected").write_text("extra")
    elif mutation == "empty-directory":
        (directory / "empty").mkdir()
    elif mutation == "symlink":
        (directory / "link").symlink_to(root / "candidate-manifest.json")
    elif mutation == "special":
        import os

        os.mkfifo(directory / "fifo")
    else:
        (root / "unexpected").mkdir()
    with pytest.raises(ValueError):
        heldout.verify_sealed_tasks(root, checksum)


def test_sealed_manifest_pin_and_split_are_required(sealed):
    root, checksum = sealed
    with pytest.raises(ValueError, match="manifest changed"):
        heldout.verify_sealed_tasks(root, "0" * 64)
    first = heldout.verify_sealed_tasks(root, checksum)["tasks"][0]
    with pytest.raises(ValueError, match="identity mismatch"):
        suite.load_task(first["id"], task_root=root)


def test_private_task_data_never_enters_agent_build_context(sealed, tmp_path, monkeypatch):
    root, checksum = sealed
    task_id = heldout.verify_sealed_tasks(root, checksum)["tasks"][0]["id"]
    task = suite.load_task(task_id, task_root=root, split="heldout")
    monkeypatch.setattr(harbor_campaign, "local_image_reference", lambda _: "offline:fixture")
    target = tmp_path / "materialized"
    harbor_campaign.materialize(
        task, target, agent_image="agent", verifier_image="verifier", arm="C", task_root=root
    )
    agent_bytes = b"\n".join(p.read_bytes() for p in (target / "environment").rglob("*") if p.is_file())
    assert b"HIDDEN_EXPECTED_SENTINEL" not in agent_bytes
    assert b"HIDDEN_CONTROL_SENTINEL" not in agent_bytes
    assert not (target / "environment/workspace/task.json").exists()
    assert (target / "tests/heldout" / task_id / "hidden_cases.json").is_file()
    assert "maintainer-authored held-out" in (target / "task.toml").read_text()
    seen = []
    assert suite.evaluate_cases(
        task,
        lambda request: seen.append(request) or {"result": "HIDDEN_EXPECTED_SENTINEL", "args": []},
        task_root=root,
    )
    assert seen == [{"module": "app", "function": "run", "args": []}]


def test_pilot_gate_binds_complete_trials_review_and_export(reviewed_pilot):
    pilot, review, _, _ = reviewed_pilot
    assert heldout.verify_pilot(pilot, review)["scheduled_trials"] == 36
    payload = heldout.read_json(review)
    payload["checks"]["quota_behavior"] = False
    review.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="review checks"):
        heldout.verify_pilot(pilot, review)


def test_pilot_gate_rejects_tampered_retained_artifacts(reviewed_pilot):
    pilot, review, store, schedule = reviewed_pilot
    path = store.root / "trials" / schedule[0]["trial_id"] / "attempt-1/agent/response.json"
    path.write_text("tampered")
    with pytest.raises(ValueError, match="artifact changed"):
        heldout.verify_pilot(pilot, review)


def test_pilot_gate_rejects_export_changed_after_review(reviewed_pilot):
    pilot, review, _, _ = reviewed_pilot
    export = pilot / "exports" / heldout.read_json(review)["pilot_export_id"]
    (export / "outcomes.json").write_text("[]")
    with pytest.raises(ValueError, match="export changed"):
        heldout.verify_pilot(pilot, review)


def test_pilot_task_identity_must_match_actual_content(reviewed_pilot, monkeypatch):
    pilot, review, _, schedule = reviewed_pilot
    original = heldout.source_identity
    changed = heldout.ROOT / "tasks/development" / schedule[0]["task_id"]
    monkeypatch.setattr(
        heldout, "source_identity", lambda path: "f" * 64 if path == changed else original(path)
    )
    with pytest.raises(ValueError, match="task content"):
        heldout.verify_pilot(pilot, review)


def test_grader_code_change_requires_explicit_bound_compatibility_review(reviewed_pilot, monkeypatch):
    pilot, review, _, _ = reviewed_pilot
    original = heldout.bytes_digest
    verifier_bytes = (heldout.HERE / "verify.py").read_bytes()
    monkeypatch.setattr(
        heldout, "bytes_digest", lambda data: "f" * 64 if data == verifier_bytes else original(data)
    )
    with pytest.raises(ValueError, match="grading compatibility"):
        heldout.verify_pilot(pilot, review)
    payload = heldout.read_json(review)
    previous = {
        "suite": heldout.source_identity(heldout.ROOT / "tasks"),
        "verifier": original(verifier_bytes),
    }
    payload["grading_compatibility"] = {
        "pilot": previous,
        "current": {**previous, "verifier": "f" * 64},
        "verdict": "unchanged_semantics",
        "reason": "Synthetic control of a separately reviewed loader-only change.",
    }
    review.write_text(json.dumps(payload))
    assert (
        heldout.verify_pilot(pilot, review)["candidate_conditions"]["reviewed_current_grading"]["verifier"]
        == "f" * 64
    )


def test_incomplete_pilot_cannot_be_accepted_by_review_flags(reviewed_pilot):
    pilot, review, store, schedule = reviewed_pilot
    # A retained terminal record cannot be removed without invalidating evidence.
    (store.root / "trials" / schedule[0]["trial_id"] / "attempt-1/finish.json").unlink()
    with pytest.raises(ValueError, match="terminal agent outcomes"):
        heldout.verify_pilot(pilot, review)


@pytest.fixture
def frozen(sealed, reviewed_pilot, tmp_path, monkeypatch):
    root, checksum = sealed
    pilot, review, *_ = reviewed_pilot
    upstream = tmp_path / "upstream"
    (upstream / ".claude-plugin").mkdir(parents=True)
    (upstream / ".claude-plugin/plugin.json").write_text("{}")
    (upstream / "skills").mkdir()
    monkeypatch.setattr(
        heldout,
        "run",
        lambda argv: SimpleNamespace(stdout=heldout.campaign.UPSTREAM_COMMIT if "rev-parse" in argv else ""),
    )
    monkeypatch.setattr(
        heldout,
        "image_identity",
        lambda name: name if name.startswith("sha256:") else "sha256:" + heldout.digest(name),
    )
    monkeypatch.setattr(heldout, "verify_readiness", lambda *_: {"offline": "fixture"})
    monkeypatch.setattr(heldout.importlib.metadata, "version", lambda _: "0.24.0")
    destination = tmp_path / "heldout"
    result = heldout.freeze(
        destination,
        root,
        checksum,
        pilot,
        review,
        upstream,
        "agent",
        "verifier",
        tmp_path / "preflight",
        tmp_path / "controls",
    )
    return destination, upstream, result["registration_sha256"]


def test_freeze_has_432_matched_trials_private_copy_and_no_attempts(frozen):
    destination, upstream, checksum = frozen
    _, _, schedule, store = heldout.verify_registration(destination, upstream, checksum)
    assert len(schedule) == 432
    assert {r["repetition"] for r in schedule} == {1, 2, 3}
    assert not (destination / "sealed-tasks/_qa").exists()
    assert all(s["attempts"] == 0 for s in store.statuses())
    assert (
        heldout.bytes_digest((destination / "pilot-review.json").read_bytes())
        == heldout.read_json(destination / "pilot-evidence.json")["review_sha256"]
    )
    with pytest.raises(ValueError, match="explicit registration"):
        heldout.verify_registration(destination, upstream, "0" * 64)


def test_frozen_task_mode_or_bytes_change_blocks_dispatch(frozen):
    destination, upstream, checksum = frozen
    task = next((destination / "sealed-tasks").glob("*/agent/app.py"))
    task.chmod(0o755)
    with pytest.raises(ValueError, match="nodes changed"):
        heldout.verify_registration(destination, upstream, checksum)


@pytest.mark.parametrize("changed", ["skill_sha256", "upstream_sha256", "upstream_loader_sha256", "runtime"])
def test_fresh_readiness_cannot_replace_candidate_that_completed_pilot(frozen, monkeypatch, changed):
    destination, upstream, _ = frozen
    root = destination.parent
    source = root / "sealed"
    candidate_sha = heldout.bytes_digest((source / "candidate-manifest.json").read_bytes())
    if changed == "runtime":
        original = heldout.image_identity
        monkeypatch.setattr(
            heldout,
            "image_identity",
            lambda name: "sha256:" + "f" * 64 if name == "agent" else original(name),
        )
    else:
        original = heldout.campaign._source_lock
        monkeypatch.setattr(
            heldout.campaign, "_source_lock", lambda path: {**original(path), changed: "f" * 64}
        )
    # The mocked fresh readiness check still passes; exact pilot conditions must reject.
    with pytest.raises(ValueError, match="completed pilot"):
        heldout.freeze(
            root / "replaced-candidate",
            source,
            candidate_sha,
            root / "pilot",
            root / "pilot-review.json",
            upstream,
            "agent",
            "verifier",
            root / "preflight",
            root / "controls",
        )
    assert not (root / "replaced-candidate").exists()


def test_heldout_reuses_scheduler_with_explicit_private_split(frozen, monkeypatch):
    destination, upstream, checksum = frozen
    received = {}

    async def scheduler(dest, source, **kwargs):
        received.update(kwargs)
        assert dest == destination and source == upstream
        return {"offline": True}

    monkeypatch.setattr(heldout.campaign, "run_pilot", scheduler)
    assert asyncio.run(heldout.run_heldout(destination, upstream, checksum, limit=1, resume_quota=True)) == {
        "offline": True
    }
    assert received["verifier"].keywords == {"registration_sha256": checksum}
    assert received["executor"].keywords == {"task_root": destination / "sealed-tasks", "split": "heldout"}
    assert received["limit"] == 1 and received["resume_quota"] is True


def test_heldout_subscription_guard_prevents_first_attempt(frozen, monkeypatch):
    destination, upstream, checksum = frozen
    monkeypatch.setattr(heldout.campaign, "subscription_environment", lambda: None)
    monkeypatch.setattr(
        heldout.campaign,
        "read_subscription_permission",
        lambda: {
            "schema_version": "evalopt.subscription-permission.v1",
            "ordinary_usage_allowed": False,
            "state": "exhausted",
        },
    )

    async def prohibited(*args, **kwargs):
        pytest.fail("a heldout model would have been invoked")

    monkeypatch.setattr(heldout, "execute_trial", prohibited)
    result = asyncio.run(heldout.run_heldout(destination, upstream, checksum, limit=1))
    assert result["scheduler"]["reason"] == "subscription_exhausted_before_dispatch"
    _, _, _, store = heldout.verify_registration(destination, upstream, checksum)
    assert all(s["attempts"] == 0 for s in store.statuses())
