#!/usr/bin/env python3
"""eval-opt Overnight — Elicitation hook (canonical source).

Fires when an MCP server requests user input *during a tool call* (the `Elicitation` /
`ElicitationResult` hook events, verified against the official Claude Code hooks docs,
/en/hooks.mdx). Without handling, such a request opens a dialog and **pauses an unattended run
waiting for input**. Active ONLY when an eval-opt overnight run is detected (env EVALOPT_OVERNIGHT
truthy, or <cwd>/.evalopt/overnight/ACTIVE exists). Then:

- DECLINE the elicitation programmatically (no dialog) so the run never blocks, and
- log the blocked request to <cwd>/.evalopt/overnight/blocked_decisions.jsonl
  (+ elicitation_blocks.jsonl) so eval-opt can park the branch and continue / report it.

Verified output schema (/en/hooks.mdx "Elicitation output"):
  {"hookSpecificOutput": {"hookEventName": "Elicitation", "action": "accept|decline|cancel"}}
Exit code 2 also denies the elicitation. We emit `action: "decline"` so the MCP server gets a
definite answer (clean "user declined") rather than a hang.

When overnight is NOT active this hook is a no-op (prints nothing) so interactive sessions show the
dialog normally. This file is the canonical, unit-tested source; install it by referencing this path
from a hook entry, or copy it to ~/.claude/hooks/ next to the other example hooks.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone


def overnight_active(cwd: str) -> bool:
    if str(os.environ.get("EVALOPT_OVERNIGHT", "")).lower() in ("1", "true", "yes", "on"):
        return True
    return os.path.isfile(os.path.join(cwd or ".", ".evalopt", "overnight", "ACTIVE"))


def log_block(cwd: str, record: dict) -> None:
    try:
        odir = os.path.join(cwd or ".", ".evalopt", "overnight")
        os.makedirs(odir, exist_ok=True)
        for name in ("elicitation_blocks.jsonl", "blocked_decisions.jsonl"):
            with open(os.path.join(odir, name), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
    except Exception:
        pass


def build_output(event: dict) -> dict:
    """Return the decline decision for an Elicitation/ElicitationResult event."""
    name = event.get("hook_event_name") or event.get("hookEventName") or "Elicitation"
    return {
        "hookSpecificOutput": {
            "hookEventName": "ElicitationResult" if "Result" in str(name) else "Elicitation",
            "action": "decline",
        }
    }


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0  # no event → do nothing
    cwd = event.get("cwd") or os.getcwd()
    if not overnight_active(cwd):
        return 0  # interactive session → let the elicitation dialog proceed normally

    name = event.get("hook_event_name") or event.get("hookEventName") or "Elicitation"
    log_block(
        cwd,
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": name,
            "mcp_server": event.get("mcp_server_name", "") or event.get("mcp_server", ""),
            "message": str(event.get("message", ""))[:300],
            "behavior": "decline",
            "reason": "eval-opt overnight: MCP elicitation auto-declined (no unattended prompt)",
            "source": "elicitation_hook",
        },
    )
    print(json.dumps(build_output(event)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
