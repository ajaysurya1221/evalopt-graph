"""Deprecated host-planning shim.

The governance kernel does not select tools, invoke CLIs, inspect remotes, or choose containers.
Hosts may still request this serializable no-op decision during the compatibility cycle.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass, field
from typing import Any


def resolve_binary(name: str, *, prefer_homebrew: bool = True) -> tuple[str | None, bool]:
    candidates = [name, "sg"] if name == "ast-grep" else [name]
    for candidate in candidates:
        homebrew = os.path.join("/opt/homebrew/bin", candidate)
        if prefer_homebrew and os.path.isfile(homebrew) and os.access(homebrew, os.X_OK):
            return homebrew, True
        if resolved := shutil.which(candidate):
            return resolved, True
    return None, False


def classify_changes(changed_files: list[str], **_ignored: Any) -> dict[str, bool]:
    files = [path.replace("\\", "/").lower() for path in changed_files if path]
    return {
        "any_files_changed": bool(files),
        "shell_files_changed": any(path.endswith((".sh", ".bash", ".zsh")) for path in files),
        "dockerfile_changed": any(os.path.basename(path).startswith("dockerfile") for path in files),
        "compose_changed": any(os.path.basename(path) in {"compose.yml", "compose.yaml"} for path in files),
        "github_actions_changed": any(path.startswith(".github/workflows/") for path in files),
        "dependency_or_lockfile_changed": any(
            os.path.basename(path) in {"pyproject.toml", "uv.lock", "package.json", "package-lock.json"}
            or path.endswith(".lock")
            for path in files
        ),
        "iac_changed": any(path.endswith((".tf", ".tf.json")) for path in files),
        "docker_or_iac_changed": any(
            os.path.basename(path).startswith("dockerfile") or path.endswith((".tf", ".tf.json"))
            for path in files
        ),
        "ui_or_web_surface_changed": any(path.endswith((".html", ".css", ".jsx", ".tsx")) for path in files),
        "auth_or_security_touched": False,
        "input_or_deserialization_touched": False,
        "claude_code_config_touched": any(path.startswith(".claude/") for path in files),
    }


def detect_task_signals(
    task: str, acceptance_criteria: list[str] | None, *, risk: str = "low"
) -> dict[str, bool]:
    text = " ".join((task, *(acceptance_criteria or ()))).lower()
    return {
        "risk_high": risk == "high",
        "structural_refactor": "refactor" in text,
        "codemod_task": "codemod" in text,
        "perf_acceptance_criterion_present": any(
            word in text for word in ("performance", "latency", "benchmark")
        ),
        "ui_acceptance_criterion_present": any(word in text for word in ("browser", "render", "screenshot")),
        "library_api_uncertain": any(word in text for word in ("library", "framework", "sdk", "api")),
        "auth_security_in_task": False,
        "input_deser_in_task": False,
        "claude_code_in_task": "claude code" in text,
        "external_docs_needed": any(word in text for word in ("latest", "current docs", "release notes")),
    }


@dataclass(frozen=True)
class GateSpec:
    name: str
    reason: str
    argv: list[str] = field(default_factory=list)
    blocking: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Skip:
    name: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouterDecision:
    diff_base: str | None = None
    changed_files: list[str] = field(default_factory=list)
    categories: dict[str, bool] = field(default_factory=dict)
    task_signals: dict[str, bool] = field(default_factory=dict)
    selected_gates: list[GateSpec] = field(default_factory=list)
    skipped_gates: list[Skip] = field(default_factory=list)
    research_tools: list[GateSpec] = field(default_factory=list)
    browser_checks: list[GateSpec] = field(default_factory=list)
    github_observability: dict[str, Any] = field(default_factory=dict)
    codex: dict[str, Any] = field(default_factory=dict)
    verification_mode: str = "host"
    verification_reason: str = "host runtime owns tool and environment selection"
    binaries: dict[str, str | None] = field(default_factory=dict)
    blocking_gates: list[str] = field(default_factory=list)
    notes: list[str] = field(
        default_factory=lambda: ["optional routing removed from kernel compatibility path"]
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def selected_gate_names(self) -> list[str]:
        return []


@dataclass(frozen=True)
class RouterConfig:
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RouterConfig:
        return cls(data=dict(data or {}))

    @property
    def enabled(self) -> bool:
        return bool(self.data.get("tool_router", {}).get("enabled", True))

    @property
    def router(self) -> dict[str, Any]:
        return self.data.get("tool_router", {})


def plan(
    *,
    task: str,
    acceptance_criteria: list[str] | None = None,
    changed_files: list[str] | None = None,
    risk: str = "low",
    diff_base: str | None = None,
    **_host_inputs: Any,
) -> RouterDecision:
    changed = sorted(set(changed_files or ()))
    return RouterDecision(
        diff_base=diff_base,
        changed_files=changed,
        categories=classify_changes(changed),
        task_signals=detect_task_signals(task, acceptance_criteria, risk=risk),
    )


def plan_from_state(
    state: dict[str, Any],
    *,
    changed_files: list[str] | None = None,
    diff_base: str | None = None,
    risk: str = "low",
    **host_inputs: Any,
) -> RouterDecision:
    return plan(
        task=state.get("task", ""),
        acceptance_criteria=state.get("acceptance_criteria", []),
        changed_files=changed_files if changed_files is not None else state.get("changed_files", []),
        risk=risk,
        diff_base=diff_base if diff_base is not None else state.get("diff_base"),
        **host_inputs,
    )
