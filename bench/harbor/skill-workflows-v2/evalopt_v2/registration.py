"""Prospective four-arm study contract; no imports from frozen v1 code."""

from __future__ import annotations

import random

from .records import digest

CATEGORIES = (
    "ordinary-bug-repair",
    "bounded-implementation",
    "committed-patch-review",
    "mixed-workspace-review",
    "constraint-preservation",
    "unavailable-or-misleading-evidence",
)
ORDINARY = CATEGORIES[:2]
ARMS = ("A", "B", "C", "D")
SEED = 20261008
RUNTIME = {
    "controller": "CPython 3.13.12",
    "harbor": "0.24.0",
    "codex": "0.154.0",
    "model": "gpt-6-astra",
    "effort": "ultra",
    "auth": "chatgpt",
    "seconds": 600,
    "verifier_seconds": 120,
    "case_seconds": 5,
    "cpus": 1,
    "memory_mb": 2048,
    "concurrent_trials": 1,
    "children": 2,
    "depth": 1,
}


def validate_tasks(tasks, stage):
    if stage not in {"development", "heldout"}:
        raise ValueError("unknown stage")
    expected = 12 if stage == "development" else 24
    if not isinstance(tasks, list) or len(tasks) != expected:
        raise ValueError(f"{stage} requires {expected} tasks")
    ids, clusters = set(), {}
    for task in tasks:
        if task.get("category") not in CATEGORIES or task.get("split") != stage:
            raise ValueError("invalid category or split")
        name = task.get("id")
        if (
            not isinstance(name, str)
            or not name
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)
            or name in ids
        ):
            raise ValueError("invalid or duplicate task id")
        ids.add(name)
        if type(task.get("evidence_opportunity")) is not bool:
            raise ValueError("evidence opportunity must be registered")
        cluster = task.get("source_cluster")
        if not isinstance(cluster, str) or not cluster:
            raise ValueError("source cluster required")
        if cluster in clusters and clusters[cluster] != task["category"]:
            raise ValueError("source cluster crosses category strata")
        clusters[cluster] = task["category"]
    for category in CATEGORIES:
        if sum(task["category"] == category for task in tasks) != expected // 6:
            raise ValueError("category allocation mismatch")
    if stage == "heldout" and sum(task["evidence_opportunity"] for task in tasks) != 12:
        raise ValueError("heldout requires 12 evidence opportunities")


def schedule(tasks, stage):
    validate_tasks(tasks, stage)
    rng = random.Random(SEED)
    blocks = [
        (task, repetition)
        for task in sorted(tasks, key=lambda item: item["id"])
        for repetition in range(1, (1 if stage == "development" else 3) + 1)
    ]
    rng.shuffle(blocks)
    rows = []
    for task, repetition in blocks:
        arms = list(ARMS)
        rng.shuffle(arms)
        for arm in arms:
            rows.append(
                {
                    "trial_id": f"{stage}--{task['id']}--r{repetition}--{arm}",
                    "task_id": task["id"],
                    "category": task["category"],
                    "source_cluster": task["source_cluster"],
                    "evidence_opportunity": task["evidence_opportunity"],
                    "repetition": repetition,
                    "arm": arm,
                }
            )
    return rows


def development_gate(tasks, rows, *, controls_passed, revision):
    expected = {row["trial_id"]: row for row in schedule(tasks, "development")}
    if type(revision) is not int or revision not in (0, 1):
        raise ValueError("only one development revision is permitted")
    if type(controls_passed) is not bool:
        raise ValueError("controls status must be boolean")
    seen = set()
    disputed = set()
    for row in rows:
        key = row.get("trial_id")
        if key in seen or key not in expected or any(row.get(k) != v for k, v in expected[key].items()):
            raise ValueError("duplicate or invalid development row")
        if type(row["valid_completion"]) is not bool and row["valid_completion"] is not None:
            raise ValueError("invalid completion")
        seen.add(key)
        if type(row.get("contract_dispute", False)) is not bool:
            raise ValueError("invalid dispute flag")
        if row.get("contract_dispute"):
            disputed.add(row["task_id"])
    complete = seen == set(expected)
    upstream = [row for row in rows if row["arm"] == "B"]
    successes = sum(row["valid_completion"] is True for row in upstream)
    ordinary = [row["valid_completion"] for row in upstream if row["category"] in ORDINARY]
    passed = (
        controls_passed
        and complete
        and not disputed
        and all(row["valid_completion"] is not None for row in rows)
        and 4 <= successes <= 10
        and True in ordinary
        and False in ordinary
    )
    return {
        "ready": passed,
        "upstream_successes": successes,
        "scheduled": 48,
        "recorded": len(rows),
        "disputed_tasks": sorted(disputed),
        "next": "freeze_heldout"
        if passed
        else ("development_revision" if revision == 0 else "development_not_ready"),
        "evidence_level": "difficulty headroom control; not a power calculation",
    }


def registration(tasks, stage, identities, *, development_admission=None):
    if stage == "heldout":
        if not isinstance(development_admission, dict) or set(development_admission) != {
            "tasks",
            "rows",
            "controls_passed",
            "revision",
            "result",
        }:
            raise ValueError("held-out registration requires retained development admission")
        gate = development_gate(
            development_admission["tasks"],
            development_admission["rows"],
            controls_passed=development_admission["controls_passed"],
            revision=development_admission["revision"],
        )
        if not gate["ready"] or gate != development_admission["result"]:
            raise ValueError("development has not passed admission")
        validate_fresh_heldout(
            tasks,
            development_admission["tasks"],
            forbidden_sources=(
                "exception-semantics",
                "object-copy",
                "binary-framing",
                "truncated-test-log",
                "wrong-architecture-binary",
            ),
        )
    elif development_admission is not None:
        raise ValueError("development cannot use a held-out admission record")
    required = {
        "tasks",
        "grader",
        "skill_c",
        "skill_d",
        "upstream",
        "parser",
        "continuation_policy",
        "agent_image",
        "verifier_image",
        "analysis",
        "source",
        "controller",
    }
    if set(identities) != required or any(
        not isinstance(v, str) or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
        for v in identities.values()
    ):
        raise ValueError("all frozen identities require sha256 digests")
    result = {
        "schema_version": "evalopt-workflows-v2/1",
        "stage": stage,
        "runtime": RUNTIME,
        "identities": dict(identities),
        "seed": SEED,
        "bootstrap_resamples": 20000,
        "tasks": tasks,
        "schedule": schedule(tasks, stage),
        "primary": "C-D",
        "gatekept_secondary": "C-B",
        "upstream_commit": "b0618bc436ad893b3c5e84e55fba86586d34a404",
        "development_admission": development_admission,
    }
    return {**result, "registration_sha256": digest(result)}


def validate_registration(value, *, expected_sha256):
    """Integrity and protocol checks; expected digest comes from the external freeze."""
    if value.get("registration_sha256") != expected_sha256:
        raise ValueError("registration differs from expected freeze")
    rebuilt = registration(
        value["tasks"],
        value["stage"],
        value["identities"],
        development_admission=value["development_admission"],
    )
    if value != rebuilt:
        raise ValueError("registration differs from protocol or deterministic schedule")
    return value


def validate_fresh_heldout(tasks, development, *, forbidden_ids=(), forbidden_sources=()):
    validate_tasks(tasks, "heldout")
    validate_tasks(development, "development")
    old_ids = {task["id"] for task in development} | set(forbidden_ids)
    old_sources = {task["source_cluster"] for task in development} | set(forbidden_sources)
    if any(task["id"] in old_ids or task["source_cluster"] in old_sources for task in tasks):
        raise ValueError("held-out tasks must have fresh task and source identities")
