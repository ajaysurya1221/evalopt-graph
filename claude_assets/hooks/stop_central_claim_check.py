#!/usr/bin/env python3
"""eval-opt Stop hook: refuse to finish while the claim ledger holds an unverified CENTRAL claim.

Enforces the epistemic 'no unverified central claim may PASS' rule in the interactive Claude Code path,
not only inside the Python loop. Backed by the deterministic governance library. No-op when there is no
ledger. Output schema (verified): top-level {"decision": "block", "reason": ...}."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_CANDIDATES = [
    os.environ.get("EVALOPT_SRC", ""),
    str(Path(__file__).resolve().parents[2] / "src"),
]
_gov = None
for _p in _CANDIDATES:
    if _p and os.path.isdir(_p):
        sys.path.insert(0, _p)
        try:
            from evalopt_graph import governance as _gov  # type: ignore

            break
        except Exception:
            _gov = None

if _gov is None:
    try:
        from evalopt_graph import governance as _gov  # type: ignore
    except Exception:
        _gov = None


def stop_output(cwd: str) -> dict:
    if _gov is None:
        return {}  # degraded mode: do not block (fail-open is safe for a Stop hook — it only nags)
    kdir = os.path.join(cwd or ".", ".evalopt", "knowledge")
    unverified = _gov.unverified_central_claims(kdir)
    if not unverified:
        return {}
    crit = [c for c in unverified if c.get("critical")]
    which = crit or unverified
    sample = "; ".join(c["text"][:80] for c in which[:3])
    return {
        "decision": "block",
        "reason": (
            f"{len(unverified)} central claim(s) are unverified ({len(crit)} critical). Confirm them with "
            f"evidence (a naming test or a cited source) before finishing: {sample}"
        ),
    }


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except Exception:
        return 0
    out = stop_output(event.get("cwd") or os.getcwd())
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
