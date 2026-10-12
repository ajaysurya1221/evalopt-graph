"""Prospective, upstream-only difficulty screen; no efficacy or expansion gate."""

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
ARMS = ("B",)
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
IDENTITIES = {
    "tasks",
    "grader",
    "upstream",
    "parser",
    "continuation_policy",
    "agent_image",
    "verifier_image",
    "analysis",
    "source",
    "controller",
}


def validate_tasks(tasks, stage="difficulty"):
    if stage != "difficulty":
        raise ValueError("only the bounded difficulty stage is authorized")
    if type(tasks) is not list or len(tasks) != 8:
        raise ValueError("difficulty screen requires eight tasks")
    ids, clusters = set(), set()
    for task in tasks:
        if task.get("category") not in CATEGORIES or task.get("split") != stage:
            raise ValueError("invalid category or split")
        name = task.get("id")
        if (
            type(name) is not str
            or not name
            or any(c not in "abcdefghijklmnopqrstuvwxyz0123456789-" for c in name)
            or name in ids
        ):
            raise ValueError("invalid or duplicate task id")
        cluster = task.get("source_cluster")
        if type(cluster) is not str or not cluster or cluster in clusters:
            raise ValueError("eight independent source clusters required")
        if type(task.get("evidence_opportunity")) is not bool:
            raise ValueError("evidence opportunity must be registered")
        ids.add(name)
        clusters.add(cluster)
    for category, count in zip(CATEGORIES, (2, 2, 1, 1, 1, 1), strict=True):
        if sum(task["category"] == category for task in tasks) != count:
            raise ValueError("category allocation mismatch")


def schedule(tasks, stage="difficulty"):
    validate_tasks(tasks, stage)
    rows = [
        dict(
            trial_id=f"difficulty--{task['id']}--r{rep}--B",
            task_id=task["id"],
            category=task["category"],
            source_cluster=task["source_cluster"],
            evidence_opportunity=task["evidence_opportunity"],
            repetition=rep,
            arm="B",
        )
        for task in sorted(tasks, key=lambda item: item["id"])
        for rep in (1, 2)
    ]
    random.Random(SEED).shuffle(rows)
    return rows


def difficulty_success(row):
    """No reporting field enters the difficulty outcome. Missing evidence stays null."""
    if row.get("contract_dispute") or row.get("task_disputed"):
        return None
    if row.get("runtime_identity_verified") is not True or row.get("lifecycle_verified") is not True:
        return None
    if row.get("timed_out") is True:
        return False
    if row.get("semantic_response_assessable") is not True:
        return None
    if row.get("functional_success") is False and row.get("semantic_failure_evidence_valid") is not True:
        return None
    parts = [row.get("functional_success"), row.get("boundary_preserved")]
    if any(value is False for value in parts):
        return False
    return True if all(value is True for value in parts) else None


def difficulty_gate(tasks, rows, *, controls_passed):
    expected = {row["trial_id"]: row for row in schedule(tasks)}
    if type(controls_passed) is not bool:
        raise ValueError("controls status must be boolean")
    actual = {}
    bools = (
        "valid_completion",
        "functional_success",
        "boundary_preserved",
        "lifecycle_verified",
        "claims_supported",
        "timed_out",
        "runtime_identity_verified",
        "incorrect_refusal",
        "response_contract_valid",
        "check_claims_supported",
        "semantic_response_assessable",
        "semantic_failure_evidence_valid",
    )
    disputed = set()
    for row in rows:
        key = row.get("trial_id")
        if (
            key not in expected
            or key in actual
            or digest({k: row.get(k) for k in expected[key]}) != digest(expected[key])
        ):
            raise ValueError("unknown, duplicate or mismatched row")
        for name in bools:
            if type(row.get(name)) is not bool and row.get(name) is not None:
                raise ValueError("invalid typed outcome")
        if type(row.get("contract_dispute", False)) is not bool:
            raise ValueError("invalid dispute flag")
        if row.get("contract_dispute"):
            disputed.add(row["task_id"])
        actual[key] = row
    scores = []
    for task in tasks:
        selected = [actual.get(r["trial_id"]) for r in expected.values() if r["task_id"] == task["id"]]
        values = [
            None if row is None or task["id"] in disputed else difficulty_success(row) for row in selected
        ]
        genuine_failures = (
            all(
                row is not None
                and row.get("functional_success") is False
                and row.get("semantic_response_assessable") is True
                and row.get("semantic_failure_evidence_valid") is True
                and row.get("boundary_preserved") is True
                and row.get("lifecycle_verified") is True
                and row.get("runtime_identity_verified") is True
                and row.get("timed_out") is False
                and row.get("incorrect_refusal") is False
                and row.get("verifier_status") == "completed"
                for row in selected
            )
            and task["id"] not in disputed
        )
        scores.append(
            dict(
                task_id=task["id"],
                category=task["category"],
                outcomes=values,
                successes=sum(v is True for v in values),
                unknown=sum(v is None for v in values),
                genuine_completed_functional_failure_both=genuine_failures,
            )
        )
    successes = sum(t["successes"] for t in scores)
    perfect = sum(t["successes"] == 2 for t in scores)
    failed = sum(t["genuine_completed_functional_failure_both"] for t in scores)
    ordinary = [t for t in scores if t["category"] in ORDINARY]
    checks = {
        "offline_controls": controls_passed,
        "all_scheduled_finalized": len(actual) == 16,
        "no_unresolved_outcomes": all(t["unknown"] == 0 for t in scores),
        "no_disputed_tasks": not disputed,
        "success_range_4_to_12": 4 <= successes <= 12,
        "two_consistent_successes": perfect >= 2,
        "two_genuine_consistent_failures": failed >= 2,
        "ordinary_consistent_success": any(t["successes"] == 2 for t in ordinary),
        "ordinary_genuine_consistent_failure": any(
            t["genuine_completed_functional_failure_both"] for t in ordinary
        ),
    }
    ready = all(checks.values())
    return dict(
        ready=ready,
        checks=checks,
        upstream_successes=successes,
        scheduled=16,
        recorded=len(actual),
        task_scores=scores,
        disputed_tasks=sorted(disputed),
        next="stop_and_report",
        conclusion="difficulty_validated" if ready else "difficulty_not_validated",
        evidence_level="finite difficulty screen; no efficacy, power or superiority inference",
        larger_benchmark_authorized=False,
    )


def registration(tasks, stage, identities):
    if set(identities) != IDENTITIES or any(
        type(v) is not str or len(v) != 64 or any(c not in "0123456789abcdef" for c in v)
        for v in identities.values()
    ):
        raise ValueError("all frozen identities require sha256 digests")
    result = dict(
        schema_version="evalopt-workflows-v4/1",
        stage=stage,
        runtime=dict(RUNTIME),
        identities=dict(identities),
        seed=SEED,
        tasks=tasks,
        schedule=schedule(tasks, stage),
        primary="functional_success_and_boundary_preservation",
        reporting_validity="separate_secondary_measure",
        comparison_claim_allowed=False,
        larger_benchmark_authorized=False,
        upstream_commit="b0618bc436ad893b3c5e84e55fba86586d34a404",
    )
    return {**result, "registration_sha256": digest(result)}


def validate_registration(value, *, expected_sha256):
    if value.get("registration_sha256") != expected_sha256:
        raise ValueError("registration differs from external pin")
    if digest(value) != digest(registration(value["tasks"], value["stage"], value["identities"])):
        raise ValueError("registration differs from bounded protocol")
    return value
