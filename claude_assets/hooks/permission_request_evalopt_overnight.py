#!/usr/bin/env python3
"""eval-opt Overnight — PermissionRequest hook.

Fires when Claude Code is about to show a permission dialog. Active ONLY when an eval-opt overnight
run is detected (env EVALOPT_OVERNIGHT truthy, or <cwd>/.evalopt/overnight/ACTIVE exists). Then:
- ALLOW iff the tool call is safe + repo-local (deterministic classifier)
- DENY everything else (destructive/global/remote/credentialed/outside-repo/unknown) — never ask
- log every decision to <cwd>/.evalopt/overnight/permission_blocks.jsonl (+ blocked_decisions.jsonl)

Output schema (verified vs official docs): hookSpecificOutput.decision.behavior = allow|deny.
When overnight is NOT active this hook is a no-op (prints nothing) so interactive sessions are
unaffected. Deny rules in settings always take precedence regardless of this hook.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- locate the canonical classifier; fall back to a conservative embedded one ---------------
_CANDIDATES = [
    os.environ.get("EVALOPT_SRC", ""),
    str(Path(__file__).resolve().parents[2] / "src"),
]
_perm = None
for _p in _CANDIDATES:
    if _p and os.path.isdir(_p):
        sys.path.insert(0, _p)
        try:
            from evalopt_graph import permissions as _perm  # type: ignore

            break
        except Exception:
            _perm = None

if _perm is None:
    try:
        from evalopt_graph import permissions as _perm  # type: ignore
    except Exception:
        _perm = None


def _overnight_active(cwd: str) -> bool:
    if str(os.environ.get("EVALOPT_OVERNIGHT", "")).lower() in ("1", "true", "yes", "on"):
        return True
    return os.path.isfile(os.path.join(cwd or ".", ".evalopt", "overnight", "ACTIVE"))


# conservative fallback: deny by default; allow only a tiny safe set; always deny obvious danger
_SAFE_FALLBACK = (
    "npm test", "npm run test", "npm run lint", "npm run typecheck", "npm run build", "npm ci",
    "pytest", "python -m pytest", "ruff check", "ruff format", "mypy", "go test", "cargo test",
    "git status", "git diff", "git log", "git rev-parse", "git branch", "git merge-base",
    "gitleaks", "semgrep", "trivy", "shellcheck", "shfmt -d", "actionlint", "hadolint",
    "gh pr checks", "gh pr view", "gh run view", "gh run list", "ls", "cat", "head", "tail",
)
_DANGER_FALLBACK = (
    "rm -rf", "git push", "git reset --hard", "git clean", "gh pr create", "gh pr merge",
    "npm i -g", "npm install -g", "brew install", "sudo", "danger-full-access", "--privileged",
    "bypassPermissions", "--dangerously-skip-permissions", "curl", "drop table", "truncate",
)


def _fallback_behavior(tool_name: str, tool_input: dict) -> tuple[str, str]:
    if tool_name in ("Read", "Glob", "Grep", "LS"):
        path = str(tool_input.get("file_path") or tool_input.get("path") or "")
        if any(s in path.lower() for s in (".env", ".ssh", ".aws", "id_rsa", "credential", "secret", ".pem")):
            return "deny", "reads a secret/credential path (fallback)"
        return "allow", "read-only tool (fallback)"
    if tool_name in ("Bash", "WorkspaceBash"):
        cmd = str(tool_input.get("command", "")).strip().lower()
        if any(d in cmd for d in _DANGER_FALLBACK):
            return "deny", "dangerous command (fallback)"
        if any(cmd.startswith(s) for s in _SAFE_FALLBACK):
            return "allow", "safe repo-local command (fallback)"
        return "deny", "unrecognized command — denied overnight (fallback)"
    if tool_name in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        return "allow", "edit (fallback; deny rules still apply)"
    if tool_name.startswith(("mcp__playwright", "mcp__context7", "mcp__claude-code-docs")):
        return "allow", "safe local/docs MCP (fallback)"
    return "deny", "not on the overnight allowlist (fallback)"


def _log(cwd: str, record: dict, denied: bool) -> None:
    try:
        odir = os.path.join(cwd or ".", ".evalopt", "overnight")
        os.makedirs(odir, exist_ok=True)
        with open(os.path.join(odir, "permission_blocks.jsonl" if denied else "permission_allows.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
        if denied:
            with open(os.path.join(odir, "blocked_decisions.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({**record, "source": "permission_request_hook"}, default=str) + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0  # no event → do nothing
    cwd = event.get("cwd") or os.getcwd()
    if not _overnight_active(cwd):
        return 0  # not an overnight run → no-op (normal interactive prompt proceeds)

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}
    repo = cwd

    if _perm is not None:
        out = _perm.permission_request_output(tool_name, tool_input, repo_path=repo, cwd=cwd)
        decision = out["hookSpecificOutput"]["decision"]
        behavior = decision["behavior"]
        reason = decision.get("message", "allowed")
    else:
        behavior, reason = _fallback_behavior(tool_name, tool_input)
        out = {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": (
            {"behavior": "allow"} if behavior == "allow"
            else {"behavior": "deny", "message": f"eval-opt overnight: {reason}"}
        )}}

    _log(
        cwd,
        {"ts": datetime.now(timezone.utc).isoformat(), "tool": tool_name,
         "command": tool_input.get("command", "") or tool_input.get("file_path", ""),
         "behavior": behavior, "reason": reason},
        denied=(behavior != "allow"),
    )
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
