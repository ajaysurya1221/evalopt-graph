#!/usr/bin/env python3
"""Safely merge the eval-opt Overnight Permission block into ~/.claude/settings.json.

DRY-RUN BY DEFAULT — prints exactly what would change and modifies nothing. Pass --apply to write,
which first backs up the existing settings to settings.json.bak.<timestamp>, merges the block
(union allow/deny rules + append hooks), preserves all unrelated settings, validates JSON, and writes.

Usage:
    python examples/claude-code-overnight/apply_overnight_permissions.py                 # dry-run (default)
    python examples/claude-code-overnight/apply_overnight_permissions.py --apply         # write (creates backup)
    python examples/claude-code-overnight/apply_overnight_permissions.py --settings <p> --block <p> --apply
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
from evalopt_graph import permissions  # noqa: E402

DEFAULT_BLOCK = os.path.expanduser("~/.claude/evalopt-overnight-permissions.example.json")
DEFAULT_SETTINGS = os.path.expanduser("~/.claude/settings.json")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Apply the eval-opt overnight permission profile (safe merge).")
    ap.add_argument("--settings", default=DEFAULT_SETTINGS, help="settings.json to merge into")
    ap.add_argument("--block", default=DEFAULT_BLOCK, help="the overnight permission block JSON to merge")
    ap.add_argument("--apply", action="store_true", help="actually write (default is dry-run)")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.block):
        print(f"ERROR: block file not found: {args.block}", file=sys.stderr)
        return 2
    with open(args.block, encoding="utf-8") as fh:
        block = json.load(fh)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = permissions.apply_overnight_settings(args.settings, block, apply=args.apply, ts=ts)

    mode = "APPLIED" if summary["applied"] else "DRY-RUN (no changes written)"
    print(f"== eval-opt overnight permissions :: {mode} ==")
    print(f"settings: {summary['settings_path']}")
    if summary["backup_path"]:
        print(f"backup:   {summary['backup_path']}")
    print(f"+ allow rules added ({len(summary['added_allow'])}): {summary['added_allow']}")
    print(f"+ deny rules added  ({len(summary['added_deny'])}): {summary['added_deny']}")
    print(f"+ hook events:        {summary['added_hook_events']}")
    print(f"preserved top-level keys: {summary['preserved_top_level_keys']}")
    if not summary["applied"]:
        print("\nRe-run with --apply to write these changes (a timestamped backup is created first).")
    print("\nRollback: restore the printed backup, e.g.  cp <backup> " + summary["settings_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
