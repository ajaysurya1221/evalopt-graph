"""Evaluator node: deterministic quality-gate check + optional LLM rubric score.

``passes_quality_gate`` is pure and is the function the router trusts. The LLM rubric (``evaluate``)
is *advisory on top of* the deterministic gates — a high rubric score can never override a failing
test gate.
"""

from __future__ import annotations

from typing import Any

from .providers import LLMProvider, parse_json_blob


def _field(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def passes_quality_gate(
    verification_results: list[Any],
    evaluator_score: float | None,
    required_gates: list[str],
    quality_threshold: float = 0.90,
    *,
    use_rubric: bool = True,
    tests_weakened: bool = False,
) -> tuple[bool, list[str]]:
    """Return ``(passed, reasons)``.

    A gate fails if a *configured* required gate is FAIL/ERROR. NOT_CONFIGURED gates are tolerated.
    If ``use_rubric`` and a score is present, it must meet ``quality_threshold``. Any detected test
    weakening fails the gate outright.
    """
    reasons: list[str] = []
    by_gate = {_field(r, "gate"): r for r in verification_results}

    for gate in required_gates:
        r = by_gate.get(gate)
        if r is None:
            continue
        status = str(_field(r, "result", "")).upper()
        if status in ("FAIL", "ERROR"):
            reasons.append(f"gate '{gate}' {status}: {_field(r, 'summary', '')}")

    if tests_weakened:
        reasons.append("tests were weakened/deleted/skipped to pass — automatic fail")

    if use_rubric and evaluator_score is not None and evaluator_score < quality_threshold:
        reasons.append(f"evaluator score {evaluator_score:.2f} < threshold {quality_threshold:.2f}")

    return (len(reasons) == 0, reasons)


def evaluate(state: dict[str, Any], provider: LLMProvider) -> dict[str, Any]:
    """Ask the provider to score the result against the contract rubric. Tolerant of bad output."""
    system = (
        "You are evalopt-critic, a rigorous, skeptical reviewer. Score 0.0-1.0 against the rubric: "
        "correctness vs acceptance criteria (0.40), tests genuinely pass & not weakened (0.25), "
        "lint/typecheck/build (0.15), safety (0.10), scope discipline (0.10). Any test gaming caps "
        'the score at 0.50. Respond ONLY as JSON: {"score": float, "feedback": str}.'
    )
    prompt = (
        f"TASK:\n{state.get('task', '')}\n\n"
        f"ACCEPTANCE CRITERIA:\n{state.get('acceptance_criteria', [])}\n\n"
        f"VERIFICATION RESULTS:\n{state.get('verification_results', [])}\n\n"
        f"CHANGED FILES:\n{state.get('changed_files', [])}\n"
    )
    raw = provider.complete(system, prompt, tag="evaluate")
    blob = parse_json_blob(raw) or {}
    try:
        score = float(blob.get("score")) if blob.get("score") is not None else None
    except (TypeError, ValueError):
        score = None
    feedback = str(blob.get("feedback") or raw or "").strip()
    return {"score": score, "feedback": feedback}
