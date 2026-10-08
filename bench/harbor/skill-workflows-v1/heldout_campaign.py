#!/usr/bin/env python3
"""Freeze and run the sealed authored comparison after a reviewed development pilot.

The review receipt is an explicit maintainer attestation bound to retained evidence,
not independent human validation or cryptographic reviewer authentication. No command
creates that attestation automatically. Task answers stay in the private registration.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.metadata
import json
import shutil
from collections import Counter
from functools import partial
from pathlib import Path, PurePosixPath

import campaign
from lib.common import bytes_digest, digest, exact, is_digest, read_json, safe_name, write_once
from lib.manifest import CATEGORIES, build_schedule, validate_manifest
from lib.store import CampaignStore
from runtime.controller import require_controller
from runtime.harbor_campaign import HERE, ROOT, execute_trial, image_identity, run, source_identity
from runtime.readiness import verify_readiness
from tasks.suite import file_manifest, load_task, task_ids

EXCLUDED = {"_qa", "author_tasks.py", "qa_controls.py", "README.md"}
REVIEW_CHECKS = {
    "skill_and_dependency_loading",
    "complete_usage_accounting",
    "grading_and_artifacts",
    "quota_behavior",
}
HELDOUT_FILES = (
    "registration-lock.json",
    "sealed-manifest.json",
    "sealed-snapshot.json",
    "pilot-review.json",
    "pilot-evidence.json",
    "freeze.json",
)


def _regular_tree(root: Path) -> None:
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError("sealed paths must not traverse symlinks")
    if not root.is_dir():
        raise ValueError("sealed root must be a directory")


def verify_sealed_tasks(root: Path, expected_manifest_sha256: str) -> dict:
    """Bind all files in exactly 48 task directories, excluding named author/QA material."""
    _regular_tree(root)
    manifest_path = root / "candidate-manifest.json"
    if not is_digest(expected_manifest_sha256) or manifest_path.is_symlink():
        raise ValueError("an explicit regular candidate manifest and SHA256 are required")
    if bytes_digest(manifest_path.read_bytes()) != expected_manifest_sha256:
        raise ValueError("sealed candidate manifest changed")
    manifest = exact(
        read_json(manifest_path), {"status", "task_count", "agent_trials", "tasks"}, "sealed manifest"
    )
    if (
        manifest["status"] != "review-candidate-not-campaign-freeze"
        or manifest["task_count"] != 48
        or type(manifest["agent_trials"]) is not int
        or manifest["agent_trials"] != 0
    ):
        raise ValueError("candidate must contain 48 tasks authored before agent trials")
    records = manifest.get("tasks", [])
    if not isinstance(records, list) or len(records) != 48:
        raise ValueError("heldout requires 48 independently identified tasks")
    ids, categories, clusters = set(), Counter(), {}
    for record in records:
        exact(record, {"id", "category", "source_family", "files"}, "sealed task")
        task_id = safe_name(record["id"])
        if task_id in ids:
            raise ValueError("duplicate sealed task")
        ids.add(task_id)
        category = record["category"].replace("-", "_")
        categories[category] += 1
        cluster = safe_name(record["source_family"])
        if cluster in clusters and clusters[cluster] != category:
            raise ValueError("source cluster crosses category strata")
        clusters[cluster] = category
        directory = root / task_id
        _regular_tree(directory)
        expected_files = record["files"]
        if not isinstance(expected_files, dict) or not {
            "task.json",
            "hidden_cases.json",
            "controls.json",
        } <= set(expected_files):
            raise ValueError("sealed task lacks contract, grader cases or controls")
        expected_directories = set()
        for name, checksum in expected_files.items():
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or str(relative) != name
                or not is_digest(checksum)
            ):
                raise ValueError("unsafe sealed file identity")
            expected_directories.update(str(p) for p in relative.parents if str(p) != ".")
        actual_files, actual_directories = {}, set()
        for path in directory.rglob("*"):
            name = path.relative_to(directory).as_posix()
            if path.is_symlink():
                raise ValueError("sealed task contains a symlink")
            if path.is_dir():
                actual_directories.add(name)
            elif path.is_file():
                actual_files[name] = bytes_digest(path.read_bytes())
            else:
                raise ValueError("sealed task contains a special node")
        if actual_files != expected_files or actual_directories != expected_directories:
            raise ValueError("sealed task file bytes or membership changed")
        task = load_task(task_id, task_root=root, split="heldout")
        if task["category"] != record["category"] or task["source_family"] != cluster:
            raise ValueError("sealed task metadata differs from its manifest")
        if "agent" not in actual_directories:
            raise ValueError("sealed task lacks an agent workspace")
    if categories != Counter(dict.fromkeys(CATEGORIES, 8)):
        raise ValueError("heldout requires eight tasks per category")
    if {path.name for path in root.iterdir()} - ids - EXCLUDED - {"candidate-manifest.json"}:
        raise ValueError("unexpected item outside sealed task directories")
    return manifest


def verify_pilot(pilot: Path, review_path: Path) -> dict:
    """Require 36 finished, graded, accounted trials and an exact export review receipt."""
    _regular_tree(pilot)
    _regular_tree(review_path.parent)
    review = read_json(review_path)
    keys = {"schema_version", "verdict", "pilot_registration_sha256", "pilot_export_id", "checks"}
    exact(
        review,
        keys | ({"grading_compatibility"} if "grading_compatibility" in review else set()),
        "pilot review",
    )
    if review["schema_version"] != "evalopt.pilot-review.v1" or review["verdict"] != "ready_for_heldout":
        raise ValueError("pilot review has not accepted progression to heldout")
    if (
        not isinstance(review["checks"], dict)
        or set(review["checks"]) != REVIEW_CHECKS
        or any(value is not True for value in review["checks"].values())
    ):
        raise ValueError("pilot review checks are incomplete")
    registration = read_json(pilot / "registration-lock.json")
    if (
        registration != campaign._registration_identity(pilot)
        or digest(registration) != review["pilot_registration_sha256"]
    ):
        raise ValueError("reviewed pilot registration changed")
    manifest = validate_manifest(read_json(pilot / "manifest.json"))
    if len(manifest["tasks"]) != 12 or {t["task_id"] for t in manifest["tasks"]} != set(task_ids()):
        raise ValueError("reviewed pilot must contain all twelve development tasks")
    for registered in manifest["tasks"]:
        actual = load_task(registered["task_id"])
        if (
            registered["task_sha256"] != source_identity(ROOT / "tasks/development" / registered["task_id"])
            or registered["category"] != actual["category"].replace("-", "_")
            or registered["cluster_id"] != actual["source_family"]
            or registered["grader_sha256"] != manifest["pins"]["grader_sha256"]
        ):
            raise ValueError("reviewed pilot task content or grading identity differs")
    conditions = _pilot_conditions(pilot, manifest, review)
    schedule = build_schedule(manifest["tasks"], "pilot")
    if len(schedule) != 36 or any(t["stage"] != "pilot" for t in manifest["tasks"]):
        raise ValueError("reviewed pilot must schedule 36 matched trials")
    store = CampaignStore(pilot / "evidence", schedule)
    for state in store.statuses():
        if state["status"] not in {"completed", "agent_failure", "timeout", "budget_exhausted"}:
            raise ValueError("all 36 pilot trials must have terminal agent outcomes")
        for attempt in range(1, state["attempts"] + 1):
            store.verify_attempt(state["trial_id"], attempt)
        path = store.root / "trials" / state["trial_id"] / f"attempt-{state['attempts']}"
        usage = read_json(path / "finish.json").get("usage") or {}
        if usage.get("child_usage_complete") is not True or usage.get("runtime_valid") is not True:
            raise ValueError("pilot telemetry and runtime observations must be complete")
        if not all(
            (path / name).is_file()
            for name in ("grade.json", "policies.json", "stopped.json", "visible.json")
        ):
            raise ValueError("pilot stopped outputs must have independent grades and replayable policies")
    export_id = review["pilot_export_id"]
    if not is_digest(export_id):
        raise ValueError("pilot review must identify an immutable report export")
    export = pilot / "exports" / export_id
    _regular_tree(export)
    checksums = read_json(export / "checksums.json")
    names = {"outcomes.json", "analysis.json", "kernel.json", "attempts.json", "scheduler-runs.json"}
    if set(checksums.get("files", {})) != names:
        raise ValueError("pilot export is incomplete")
    payloads = {}
    for name in names:
        path = export / name
        if path.is_symlink() or bytes_digest(path.read_bytes()) != checksums["files"][name]:
            raise ValueError("reviewed pilot export changed")
        payloads[name] = read_json(path)
    if digest(payloads) != export_id or checksums.get("schedule_sha256") != digest(schedule):
        raise ValueError("pilot export identity does not match reviewed registration")
    rows, _, attempts = campaign._report_rows(store, schedule)
    if payloads["outcomes.json"] != rows or payloads["attempts.json"] != attempts:
        raise ValueError("pilot outcomes changed after the reviewed export")
    return {
        "schema_version": "evalopt.pilot-evidence.v1",
        "registration_sha256": digest(registration),
        "export_id": export_id,
        "review_sha256": bytes_digest(review_path.read_bytes()),
        "task_clusters": sorted({t["cluster_id"] for t in manifest["tasks"]}),
        "scheduled_trials": 36,
        "candidate_conditions": conditions,
        "review_scope": "maintainer-run study with separated review; not independent human validation",
    }


def _pilot_conditions(pilot, manifest, review):
    sources = read_json(pilot / "readiness-sources.json")
    readiness = read_json(pilot / "readiness.json")
    preflight, controls = Path(sources["preflight"]), Path(sources["controls"])
    for root, key in ((preflight, "preflight_sha256"), (controls, "controls_sha256")):
        _regular_tree(root)
        if source_identity(root) != readiness[key]:
            raise ValueError("reviewed pilot capability/control evidence changed")
    probe = read_json(preflight / "summary.json")
    control = read_json(controls / "results.json")
    source_lock = read_json(pilot / "source-lock.json")
    runtime = read_json(pilot / "runtime.json")
    expected_skills = {"evalopt": source_lock["skill_sha256"], "upstream": source_lock["upstream_sha256"]}
    if (
        manifest["pins"]["skill_sha256"] != expected_skills["evalopt"]
        or probe["skill_sources"] != expected_skills
        or probe["image_id"] != runtime["agent_image"]
        or manifest["pins"]["environment_sha256"] != digest(runtime)
        or control["tasks_sha256"] != manifest["pins"]["grader_sha256"]
    ):
        raise ValueError("pilot conditions disagree with retained preflight or controls")
    previous_grading = {"suite": control["tasks_sha256"], "verifier": control["verify_sha256"]}
    current_grading = {
        "suite": source_identity(ROOT / "tasks"),
        "verifier": bytes_digest((HERE / "verify.py").read_bytes()),
    }
    compatibility = review.get("grading_compatibility")
    if previous_grading != current_grading or compatibility is not None:
        exact(compatibility, {"pilot", "current", "verdict", "reason"}, "grading compatibility review")
        if (
            compatibility["pilot"] != previous_grading
            or compatibility["current"] != current_grading
            or compatibility["verdict"] != "unchanged_semantics"
            or not isinstance(compatibility["reason"], str)
            or not compatibility["reason"].strip()
        ):
            raise ValueError("changed grading requires an exact unchanged-semantics review")
    return {
        "skill_sha256": source_lock["skill_sha256"],
        "upstream_sha256": source_lock["upstream_sha256"],
        "upstream_loader_sha256": source_lock["upstream_loader_sha256"],
        "config_sha256": probe["config_sha256"],
        "runtime": runtime,
        "pilot_grading": previous_grading,
        "reviewed_current_grading": current_grading,
    }


def _heldout_identity(destination: Path) -> dict:
    return {name: bytes_digest((destination / name).read_bytes()) for name in HELDOUT_FILES}


def freeze(
    destination,
    sealed_root,
    candidate_sha256,
    pilot,
    pilot_review,
    upstream,
    image,
    verifier,
    preflight,
    controls,
):
    require_controller()
    if destination.exists():
        raise ValueError("freeze requires a fresh private campaign directory")
    candidate = verify_sealed_tasks(sealed_root, candidate_sha256)
    pilot_evidence = verify_pilot(pilot, pilot_review)
    if {t["source_family"] for t in candidate["tasks"]} & set(pilot_evidence["task_clusters"]):
        raise ValueError("heldout shares a source cluster with development")
    if run(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip() != campaign.UPSTREAM_COMMIT:
        raise ValueError("upstream source differs from registered commit")
    runtime = {"agent_image": image_identity(image), "verifier_image": image_identity(verifier)}
    conditions = pilot_evidence["candidate_conditions"]
    current_sources = campaign._source_lock(upstream)
    if any(
        conditions[key] != current_sources[key]
        for key in ("skill_sha256", "upstream_sha256", "upstream_loader_sha256")
    ):
        raise ValueError("workflow candidate differs from the completed pilot; run a new development pilot")
    if conditions["runtime"] != runtime or conditions["config_sha256"] != bytes_digest(
        (HERE / "codex.toml").read_bytes()
    ):
        raise ValueError("agent configuration or runtime images differ from the completed pilot")
    readiness = verify_readiness(preflight, controls, runtime, upstream)
    grader = digest(
        {
            "suite": source_identity(ROOT / "tasks"),
            "verifier": bytes_digest((HERE / "verify.py").read_bytes()),
        }
    )
    tasks = [
        {
            "task_id": t["id"],
            "stage": "heldout",
            "category": t["category"].replace("-", "_"),
            "cluster_id": t["source_family"],
            "task_sha256": digest(t["files"]),
            "grader_sha256": grader,
            "agent_seconds": 600,
        }
        for t in candidate["tasks"]
    ]
    manifest = read_json(pilot / "manifest.json")
    manifest.update(study_id="skill-workflows-v1-heldout", tasks=tasks)
    manifest["pins"].update(
        skill_sha256=source_identity(campaign.REPO / "skills/eval-opt"),
        grader_sha256=grader,
        policy_sha256=source_identity(ROOT / "lib"),
        analysis_sha256=source_identity(ROOT / "lib"),
        environment_sha256=digest(runtime),
    )
    validate_manifest(manifest)
    if any(not is_digest(v, 40 if k.endswith("_commit") else 64) for k, v in manifest["pins"].items()):
        raise ValueError("heldout registration requires resolved pins")
    destination.mkdir(parents=True, mode=0o700)
    sealed = destination / "sealed-tasks"
    sealed.mkdir(mode=0o700)
    shutil.copyfile(sealed_root / "candidate-manifest.json", sealed / "candidate-manifest.json")
    for task in candidate["tasks"]:
        shutil.copytree(sealed_root / task["id"], sealed / task["id"])
    verify_sealed_tasks(sealed, candidate_sha256)
    write_once(destination / "manifest.json", manifest)
    write_once(destination / "runtime.json", runtime)
    write_once(destination / "readiness.json", readiness)
    write_once(
        destination / "readiness-sources.json",
        {"preflight": str(preflight.absolute()), "controls": str(controls.absolute())},
    )
    write_once(destination / "source-lock.json", campaign._source_lock(upstream))
    CampaignStore(destination / "evidence", build_schedule(tasks, "heldout"))
    write_once(destination / "registration-lock.json", campaign._registration_identity(destination))
    write_once(destination / "sealed-manifest.json", candidate)
    write_once(destination / "sealed-snapshot.json", file_manifest(sealed))
    # Retain the exact reviewed bytes, including the digest recorded in pilot-evidence.
    shutil.copyfile(pilot_review, destination / "pilot-review.json")
    write_once(destination / "pilot-evidence.json", pilot_evidence)
    write_once(
        destination / "freeze.json",
        {
            "schema_version": "evalopt.heldout-freeze.v1",
            "candidate_manifest_sha256": candidate_sha256,
            "scheduled_trials": 432,
            "seed": 20261008,
            "task_root": "sealed-tasks",
            "excluded_authoring_material": sorted(EXCLUDED),
            "frozen_at": campaign._now(),
        },
    )
    write_once(destination / "heldout-lock.json", _heldout_identity(destination))
    return {
        "status": "frozen_not_executed",
        "scheduled_trials": 432,
        "registration_sha256": digest(read_json(destination / "heldout-lock.json")),
    }


def verify_registration(destination: Path, upstream: Path, registration_sha256: str):
    require_controller()
    lock = read_json(destination / "heldout-lock.json")
    if (
        not is_digest(registration_sha256)
        or digest(lock) != registration_sha256
        or lock != _heldout_identity(destination)
    ):
        raise ValueError("heldout freeze differs from the explicit registration identity")
    if read_json(destination / "registration-lock.json") != campaign._registration_identity(destination):
        raise ValueError("heldout registration files changed")
    if read_json(destination / "source-lock.json") != campaign._source_lock(upstream):
        raise ValueError("source changed after heldout freeze; candidate tuning is forbidden")
    if importlib.metadata.version("harbor") != "0.24.0":
        raise ValueError("Harbor version differs from protocol")
    if run(["git", "-C", str(upstream), "rev-parse", "HEAD"]).stdout.strip() != campaign.UPSTREAM_COMMIT:
        raise ValueError("upstream source differs from registered commit")
    if run(
        [
            "git",
            "-C",
            str(campaign.REPO),
            "diff",
            "--name-only",
            campaign.KERNEL_COMMIT,
            "--",
            "src/evalopt_graph",
        ]
    ).stdout.strip():
        raise ValueError("stable kernel differs from frozen source commit")
    frozen = read_json(destination / "freeze.json")
    sealed = destination / "sealed-tasks"
    candidate = verify_sealed_tasks(sealed, frozen["candidate_manifest_sha256"])
    if candidate != read_json(destination / "sealed-manifest.json") or file_manifest(sealed) != read_json(
        destination / "sealed-snapshot.json"
    ):
        raise ValueError("sealed task nodes changed after freeze")
    manifest = validate_manifest(read_json(destination / "manifest.json"))
    schedule = build_schedule(manifest["tasks"], "heldout")
    if len(schedule) != 432 or len(manifest["tasks"]) != 48:
        raise ValueError("heldout registration must schedule 432 trials")
    runtime = read_json(destination / "runtime.json")
    if set(runtime) != {"agent_image", "verifier_image"} or any(
        image_identity(v) != v for v in runtime.values()
    ):
        raise ValueError("runtime image differs from frozen digest")
    sources = read_json(destination / "readiness-sources.json")
    if verify_readiness(
        Path(sources["preflight"]), Path(sources["controls"]), runtime, upstream
    ) != read_json(destination / "readiness.json"):
        raise ValueError("readiness evidence changed after freeze")
    store = CampaignStore(destination / "evidence", schedule)
    return manifest, runtime, schedule, store


async def run_heldout(destination, upstream, registration_sha256, **options):
    return await campaign.run_pilot(
        destination,
        upstream,
        verifier=partial(verify_registration, registration_sha256=registration_sha256),
        executor=partial(execute_trial, task_root=destination / "sealed-tasks", split="heldout"),
        reporter=campaign.report,
        **options,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("freeze-heldout")
    for name in ("directory", "sealed-root", "pilot", "pilot-review", "upstream", "preflight", "controls"):
        create.add_argument("--" + name, type=Path, required=True)
    create.add_argument("--candidate-sha256", required=True)
    create.add_argument("--image", required=True)
    create.add_argument("--verifier", required=True)
    execute = commands.add_parser("run-heldout")
    execute.add_argument("--directory", type=Path, required=True)
    execute.add_argument("--upstream", type=Path, required=True)
    execute.add_argument("--registration-sha256", required=True)
    execute.add_argument("--limit", type=int)
    for flag in ("retry-infrastructure", "resume-quota", "recover-interrupted"):
        execute.add_argument("--" + flag, action="store_true")
    args = vars(parser.parse_args(argv))
    command = args.pop("command")
    args["destination"] = args.pop("directory")
    result = freeze(**args) if command == "freeze-heldout" else asyncio.run(run_heldout(**args))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
