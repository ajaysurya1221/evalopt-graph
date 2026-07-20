"""Governance library: the enforceable epistemic checks, as pure functions the Claude Code hooks and
the Layer-1 skill can call — so the 'no unverified central claim may PASS' rule is enforced in the
interactive path too, not only inside the Python loop."""

from __future__ import annotations

import os
from typing import Any

from . import epistemic
from .claim_ledger import ClaimLedger


def unverified_central_claims(knowledge_dir: str, *, now: str | None = None) -> list[dict[str, Any]]:
    """Central claims in the ledger that are NOT usable (unverified/contradicted/stale). Returns
    ``[{id, text, critical}]``. Empty when the knowledge dir is absent/empty."""
    if not knowledge_dir or not os.path.isdir(knowledge_dir):
        return []
    led = ClaimLedger.load(knowledge_dir)
    out: list[dict[str, Any]] = []
    for c in led.central_claims():
        if not epistemic.is_usable(c, now):
            out.append({"id": c.id, "text": c.text, "critical": epistemic.is_critical(c)})
    return out
