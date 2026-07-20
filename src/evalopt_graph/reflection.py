"""Reflection node + stuck detection.

Reflection runs ONLY after concrete tool feedback (failing gates / low rubric score). Stuck
detection breaks the loop when the same failure signature recurs, routing to a human gate.
"""

from __future__ import annotations

import re
from typing import Any

from .providers import LLMProvider, parse_json_blob
from .state import STUCK_REPEAT_THRESHOLD

# Failing/error *counts* in a gate summary (e.g. "5 failed", "3 errors"). Kept in the signature so a
# converging run is not mistaken for the same failure repeating.
_FAIL_COUNT_RE = re.compile(r"(\d+)\s+(?:failed|failures?|errors?)\b")


def failure_signature(result: Any) -> str:
    """A stable key for a failed gate, used to detect 'same failure repeating'.

    Volatile digits (line numbers, timings) are collapsed so re-runs of the *same* error match, but
    the failing/error COUNT is preserved: a run going 5→2→1 failing tests is genuine progress, not a
    stuck loop, and must not collapse to one identical signature (which would park a converging run).
    """
    gate = result.get("gate") if isinstance(result, dict) else getattr(result, "gate", "?")
    summary = result.get("summary") if isinstance(result, dict) else getattr(result, "summary", "")
    key = (summary or "").strip().lower()
    counts = _FAIL_COUNT_RE.findall(key)
    cleaned = "".join("#" if c.isdigit() else c for c in key)[:120]
    tag = (":n=" + ",".join(counts)) if counts else ""
    return f"{gate}:{cleaned}{tag}"


def collect_signatures(verification_results: list[Any]) -> list[str]:
    """Per-gate failure signatures for one verification result set (FAIL/ERROR gates only)."""
    sigs = []
    for r in verification_results:
        status = (r.get("result") if isinstance(r, dict) else getattr(r, "result", "")) or ""
        if str(status).upper() in ("FAIL", "ERROR"):
            sigs.append(failure_signature(r))
    return sigs


def iteration_signature(verification_results: list[Any]) -> str:
    """One composite fingerprint for an iteration's failing gates (empty if nothing failed).

    Appended once per iteration so that stuck detection counts *iterations* with the identical
    failure shape, not raw per-gate occurrences.
    """
    return "|".join(sorted(collect_signatures(verification_results)))


def is_stuck(failure_signatures: list[str], threshold: int = STUCK_REPEAT_THRESHOLD) -> bool:
    """True only when the SAME non-empty failure recurs in ``threshold`` *consecutive* iterations.

    Consecutive (tail run-length) rather than cumulative, so a loop still making progress on
    different failures is not prematurely sent to the human gate, and the ``max_iterations``
    terminal stays reachable when failures genuinely vary.
    """
    tail = [s for s in failure_signatures[-threshold:]]
    if len(tail) < threshold:
        return False
    return bool(tail[-1]) and all(s == tail[-1] for s in tail)


def reflect(state: dict[str, Any], provider: LLMProvider) -> list[str]:
    """Produce 1-3 targeted hypotheses + the next concrete change, from real failure signals."""
    failing = [
        r
        for r in state.get("verification_results", [])
        if str(r.get("result") if isinstance(r, dict) else getattr(r, "result", "")).upper()
        in ("FAIL", "ERROR")
    ]
    system = (
        "You are the reflection node of an evaluator-optimizer loop. Given concrete failures, output "
        "1-3 targeted hypotheses and the single next concrete change. Respond ONLY as a JSON array "
        "of short strings. Do not propose weakening tests."
    )
    prompt = (
        f"TASK:\n{state.get('task', '')}\n\n"
        f"FAILING GATES:\n{failing}\n\n"
        f"EVALUATOR FEEDBACK:\n{state.get('evaluator_feedback', '')}\n\n"
        f"PRIOR REFLECTIONS:\n{state.get('reflection_notes', [])}\n"
    )
    raw = provider.complete(system, prompt, tag="reflect")
    blob = parse_json_blob(raw)
    if isinstance(blob, list):
        return [str(x) for x in blob][:3]
    return [raw.strip()] if raw.strip() else ["No reflection produced."]
