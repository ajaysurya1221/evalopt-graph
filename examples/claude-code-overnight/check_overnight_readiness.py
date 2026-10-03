#!/usr/bin/env python3
"""Pre-flight check for an eval-opt overnight run. Read-only; never changes anything.

Reports READY / READY_WITH_WARNINGS / NOT_READY plus the exact command to start an overnight run.

Usage:
    python examples/claude-code-overnight/check_overnight_readiness.py --repo .
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from evalopt_graph import permissions  # noqa: E402

SETTINGS = os.path.expanduser("~/.claude/settings.json")
SKILL = os.path.expanduser("~/.claude/skills/eval-opt")


def _run(argv: list[str]) -> tuple[int, str]:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=20)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception:
        return 1, ""


def _git(repo: str, *args: str) -> tuple[int, str]:
    return _run(["git", "-C", repo, *args])


def _read_settings() -> dict:
    try:
        with open(SETTINGS, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _hooks_installed(settings: dict) -> bool:
    hooks = json.dumps(settings.get("hooks", {}))
    return "permission_request_evalopt_overnight" in hooks and "pretool_evalopt_safety" in hooks


def _elicitation_hook_installed(settings: dict) -> bool:
    """True if an Elicitation hook is registered globally (settings.json) or skill-scoped (SKILL.md)."""
    settings_hooks = settings.get("hooks", {}) or {}
    if "Elicitation" in settings_hooks or "elicitation_evalopt_overnight" in json.dumps(settings_hooks):
        return True
    skill_md = os.path.join(SKILL, "SKILL.md")
    try:
        with open(skill_md, encoding="utf-8") as fh:
            head = fh.read(4000)  # frontmatter lives at the top
        return "Elicitation" in head or "elicitation_evalopt_overnight" in head
    except Exception:
        return False


def _docker_needed(repo: str) -> bool:
    names = ("Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
    return any(os.path.exists(os.path.join(repo, n)) for n in names)


def gather_facts(repo: str) -> dict:
    settings = _read_settings()
    code, ver = _run(["claude", "--version"])
    code_co, codex_ver = _run(["codex", "--version"])
    dirty = _git(repo, "status", "--porcelain")
    return {
        "claude_version": ver.strip() if code == 0 else "(not found)",
        "is_git_repo": _git(repo, "rev-parse", "--is-inside-work-tree")[1].strip() == "true",
        "working_tree_dirty": bool(dirty[1].strip()),
        "permission_mode": settings.get("permissions", {}).get("defaultMode")
        or settings.get("permissionMode"),
        "permission_hooks_installed": _hooks_installed(settings),
        "elicitation_hook_installed": _elicitation_hook_installed(settings),
        "eval_opt_skill": os.path.isfile(os.path.join(SKILL, "SKILL.md")),
        "config_yaml_exists": os.path.isfile(os.path.join(repo, ".evalopt", "config.yaml")),
        "docker_needed": _docker_needed(repo),
        "docker_running": _run(["docker", "info"])[0] == 0,
        "codex_present": code_co == 0,
        "codex_default_full_access": False,  # template/skill default is workspace-write, never full-access
        "sleep_prevented": _run(["pgrep", "-x", "caffeinate"])[0] == 0,
        "codex_version": codex_ver.strip() if code_co == 0 else "(not found)",
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="eval-opt overnight readiness check (read-only)")
    ap.add_argument("--repo", default=".", help="target repository (default: .)")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args(argv)
    repo = os.path.abspath(args.repo)

    facts = gather_facts(repo)
    result = permissions.assess_readiness(facts)

    if args.json:
        print(json.dumps({"facts": facts, **result}, indent=2, default=str))
        return 0 if result["status"] != "NOT_READY" else 1

    print(f"== eval-opt overnight readiness: {result['status']} ==")
    print(f"repo: {repo}")
    print(
        f"claude: {facts['claude_version']} | codex: {facts['codex_version']} | "
        f"docker: {'up' if facts['docker_running'] else 'down'}{' (needed)' if facts['docker_needed'] else ''}"
    )
    print(
        f"git repo: {facts['is_git_repo']} | tree dirty: {facts['working_tree_dirty']} | "
        f"perm mode: {facts['permission_mode']} | hooks: {facts['permission_hooks_installed']} | "
        f"elicitation hook: {facts['elicitation_hook_installed']}"
    )
    for b in result["blocking"]:
        print(f"  [BLOCK] {b}")
    for w in result["warnings"]:
        print(f"  [warn]  {w}")
    print("\nStart an overnight run with:")
    print(
        f'  caffeinate -dimsu evalopt --repo {repo} --task "<your task>" '
        f"--overnight --max-wall-clock-hours 8 --write"
    )
    print(
        f'  (in Claude Code, from {repo}:  /eval-opt "<your task>" overnight=true'
        "  — after /model opus, /effort xhigh)"
    )
    return 0 if result["status"] != "NOT_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
