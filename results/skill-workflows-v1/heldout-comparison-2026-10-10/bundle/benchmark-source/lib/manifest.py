"""Strict preregistration schema and deterministic matched trial schedules."""

from __future__ import annotations

import random
from collections import Counter
from typing import Any

from .common import digest, exact, is_digest, safe_name

CATEGORIES = (
    "ordinary_bug_repair",
    "bounded_implementation",
    "committed_patch_review",
    "mixed_workspace_review",
    "constraint_preservation",
    "unavailable_or_misleading_evidence",
)
STAGES = {"pilot": (12, "ABC", 1), "heldout": (48, "ABC", 3), "transfer": (12, "BC", 3)}
TASK_KEYS = {"task_id", "stage", "category", "cluster_id", "task_sha256", "grader_sha256", "agent_seconds"}
PIN_KEYS = {
    "upstream_commit",
    "terminal_bench_commit",
    "kernel_commit",
    "skill_sha256",
    "grader_sha256",
    "policy_sha256",
    "analysis_sha256",
    "environment_sha256",
}


def validate_manifest(value: dict, *, require_full: bool = False) -> dict:
    """Validate a draft or frozen manifest. A valid manifest does not prove runtime readiness."""
    exact(value, {"schema_version", "study_id", "seed", "pins", "runtime", "limits", "tasks"}, "manifest")
    if value["schema_version"] != "evalopt.skill-workflows.v1" or value["seed"] != 20261008:
        raise ValueError("unsupported schema or schedule seed")
    safe_name(value["study_id"])
    pins = exact(value["pins"], PIN_KEYS, "pins")
    for name, pin in pins.items():
        if pin is None and not require_full:
            continue
        if not is_digest(pin, 40 if name.endswith("_commit") else 64):
            raise ValueError(f"unresolved or invalid pin: {name}")
    for name, pinned in (
        ("upstream_commit", "b0618bc436ad893b3c5e84e55fba86586d34a404"),
        ("terminal_bench_commit", "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c"),
        ("kernel_commit", "fc3045dbda29c1d274747329ceb6724a783b0df7"),
    ):
        if pins[name] != pinned:
            raise ValueError(f"registered source pin changed: {name}")
    runtime = exact(
        value["runtime"],
        {"harbor_version", "codex_version", "model", "reasoning_effort", "auth_route"},
        "runtime",
    )
    expected = {
        "harbor_version": "0.24.0",
        "codex_version": "0.154.0",
        "model": "gpt-6-astra",
        "reasoning_effort": "ultra",
        "auth_route": "chatgpt_subscription",
    }
    if runtime != expected:
        raise ValueError("runtime differs from the registered subscription-only conditions")
    limits = exact(
        value["limits"],
        {
            "primary_seconds",
            "max_concurrent_trials",
            "max_children",
            "delegation_depth",
            "infrastructure_retries",
        },
        "limits",
    )
    if any(type(item) is not int for item in limits.values()) or limits != {
        "primary_seconds": 600,
        "max_concurrent_trials": 2,
        "max_children": 2,
        "delegation_depth": 1,
        "infrastructure_retries": 1,
    }:
        raise ValueError("registered limits changed")
    if not isinstance(value["tasks"], list):
        raise ValueError("tasks must be an array")
    identities: set[str] = set()
    cluster_stages = {}
    for task in value["tasks"]:
        exact(task, TASK_KEYS, "task")
        task_id = safe_name(task["task_id"])
        safe_name(task["cluster_id"])
        if task["cluster_id"] in cluster_stages and cluster_stages[task["cluster_id"]] != task["stage"]:
            raise ValueError("a source cluster cannot span development and evaluation stages")
        cluster_stages[task["cluster_id"]] = task["stage"]
        if task_id in identities:
            raise ValueError("duplicate task identity")
        identities.add(task_id)
        if task["stage"] not in STAGES:
            raise ValueError("unknown stage")
        if task["stage"] != "transfer" and task["category"] not in CATEGORIES:
            raise ValueError("unknown authored category")
        if task["stage"] == "transfer" and task["category"] not in {"software-engineering", "debugging"}:
            raise ValueError("unknown transfer category")
        for field in ("task_sha256", "grader_sha256"):
            if task[field] is None and not require_full:
                continue
            if not is_digest(task[field]):
                raise ValueError(f"unresolved task pin: {task_id}/{field}")
        seconds = task["agent_seconds"]
        if type(seconds) is not int or not 0 < seconds <= (1800 if task["stage"] == "transfer" else 600):
            raise ValueError("invalid trial time limit")
        if task["stage"] != "transfer" and seconds != 600:
            raise ValueError("authored trials require 600 seconds")
    if require_full:
        for stage, (count, _, _) in STAGES.items():
            subset = [task for task in value["tasks"] if task["stage"] == stage]
            if len(subset) != count:
                raise ValueError(f"{stage} requires {count} tasks")
            if stage == "heldout" and Counter(task["category"] for task in subset) != dict.fromkeys(
                CATEGORIES, 8
            ):
                raise ValueError("heldout requires eight tasks per category")
    return value


def build_schedule(tasks: list[dict], stage: str, *, seed: int = 20261008) -> list[dict[str, Any]]:
    """Randomize arms within task/repetition blocks, never treating repetitions as tasks."""
    if stage not in STAGES:
        raise ValueError("unknown stage")
    _, arms, repetitions = STAGES[stage]
    rng = random.Random(seed)
    selected = sorted((task for task in tasks if task["stage"] == stage), key=lambda task: task["task_id"])
    if len({task["task_id"] for task in selected}) != len(selected):
        raise ValueError("duplicate task identity")
    result = []
    for task in selected:
        safe_name(task["task_id"])
        for repetition in range(1, repetitions + 1):
            order = list(arms)
            rng.shuffle(order)
            for arm in order:
                result.append(
                    {
                        "trial_id": f"{stage}--{task['task_id']}--r{repetition}--{arm}",
                        "task_id": task["task_id"],
                        "stage": stage,
                        "category": task["category"],
                        "cluster_id": task["cluster_id"],
                        "arm": arm,
                        "repetition": repetition,
                        "agent_seconds": task["agent_seconds"],
                        "task_sha256": task["task_sha256"],
                        "grader_sha256": task["grader_sha256"],
                        "ordinal": len(result),
                    }
                )
    return result


def schedule_identity(schedule: list[dict]) -> str:
    if len({row["trial_id"] for row in schedule}) != len(schedule):
        raise ValueError("duplicate scheduled trial")
    return digest(schedule)
