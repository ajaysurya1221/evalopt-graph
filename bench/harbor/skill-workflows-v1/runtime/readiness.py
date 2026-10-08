"""Readiness is checked from retained probes, not an operator-supplied ready flag."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.accounting import parse_native_usage, summarize_usage
from runtime.harbor_campaign import HERE, REPO, ROOT, source_identity

REQUIRED = {
    "image_present",
    "codex_version",
    "configuration_parses",
    "native_multi_agent_enabled",
    "subscription_auth",
    "live_exit_zero",
    "live_completion_marker",
    "model_identity",
    "reasoning_identity",
    "two_native_children",
    "skill_and_dependency_loading",
    "complete_usage_accounting",
}


def verify_readiness(preflight: Path, controls: Path, runtime: dict, upstream: Path) -> dict:
    probe = json.loads((preflight / "summary.json").read_text())
    if not all(probe.get("checks", {}).get(name) is True for name in REQUIRED):
        raise ValueError("native runtime/skill/accounting preflight is incomplete")
    if probe["image_id"] != runtime["agent_image"]:
        raise ValueError("agent image changed after preflight")
    if probe["config_sha256"] != hashlib.sha256((HERE / "codex.toml").read_bytes()).hexdigest():
        raise ValueError("runtime configuration changed after preflight")
    expected = {
        "upstream": source_identity(upstream / "skills"),
        "evalopt": source_identity(REPO / "skills" / "eval-opt"),
    }
    if probe.get("skill_sources") != expected:
        raise ValueError("workflow sources changed after loader preflight")
    usage = summarize_usage(parse_native_usage(preflight / "sessions"))
    if usage != probe.get("usage") or usage["agent_count"] != 3:
        raise ValueError("preflight accounting cannot be reproduced")
    tests = json.loads((controls / "results.json").read_text())
    from tasks.suite import task_ids

    actual = tests.get("controls", [])
    if (
        len(actual) != 12
        or {row["task_id"] for row in actual} != set(task_ids())
        or any(row.get("oracle_passed") is not True or row.get("exit_code") != 0 for row in actual)
    ):
        raise ValueError("all twelve separate-verifier oracle controls are required")
    if (
        tests.get("tasks_sha256") != source_identity(ROOT / "tasks")
        or tests.get("verify_sha256") != hashlib.sha256((HERE / "verify.py").read_bytes()).hexdigest()
    ):
        raise ValueError("tasks or verifier changed after controls")
    if (
        tests.get("agent_image") != runtime["agent_image"]
        or tests.get("verifier_image") != runtime["verifier_image"]
    ):
        raise ValueError("images changed after separate-verifier controls")
    return {
        "schema_version": "evalopt.campaign-readiness.v1",
        "preflight_sha256": source_identity(preflight),
        "controls_sha256": source_identity(controls),
        "runtime": runtime,
        "skill_sources": expected,
        "preflight_usage": usage,
    }
