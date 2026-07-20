#!/usr/bin/env python3
"""Require immutable 40-character commit pins for external GitHub Actions."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USE = re.compile(r"^\s*-?\s*uses:\s*([^\s#]+)", re.MULTILINE)
PINNED = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?@[0-9a-f]{40}$")


def main() -> int:
    failures: list[str] = []
    workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        raise SystemExit("no GitHub Actions workflows found")
    for workflow in workflows:
        for action in USE.findall(workflow.read_text(encoding="utf-8")):
            if action.startswith("./"):
                continue
            if not PINNED.fullmatch(action):
                failures.append(f"{workflow.relative_to(ROOT)}: {action}")
    if failures:
        raise SystemExit("unpinned GitHub Actions:\n" + "\n".join(failures))
    print(f"verified immutable action pins in {len(workflows)} workflows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
