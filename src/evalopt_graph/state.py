"""Typed state and shared constants for the Evaluator-Optimizer Graph.

The state is a plain ``TypedDict`` (a ``dict`` at runtime) so that routing, detection and
quality-gate logic can be exercised in unit tests with **no LangGraph and no API key**.
"""

from __future__ import annotations

from typing import Any, TypedDict

# --- Node names (the graph vertices) --------------------------------------------------------
GOAL_INTAKE = "goal_intake"
ASSUMPTION_EXTRACTION = "assumption_extraction"
PROJECT_SCAN = "project_scan"
TOOL_ROUTER = "tool_router"
RESEARCH_PLANNER = "research_planner"
PARALLEL_INVESTIGATION = "parallel_investigation"
SOURCE_VERIFIER = "source_verifier"
CONTRADICTION_HUNTER = "contradiction_hunter"
ADJUDICATOR = "adjudicator"
QUALITY_CONTRACT = "quality_contract"
PLANNING = "planning"
GENERATION = "generation_or_patch"
SYNTHESIS = "synthesis_or_patch"
VERIFICATION = "deterministic_verification"
EVALUATOR = "evaluator"
REFLECTION = "reflection"
STABILITY_CONTROLLER = "stability_controller"
STUCK_ANALYSIS = "stuck_analysis"
HUMAN_GATE = "human_gate"
FINAL_REVIEW = "final_review"
FAILURE_REPORT = "failure_report"
DONE = "__end__"

# --- Stop reasons ---------------------------------------------------------------------------
STOP_PASS = "pass"
STOP_PASS_WITH_WARNINGS = "pass_with_warnings"
STOP_BLOCKED = "blocked_human_gate"
STOP_STUCK = "stuck_repeated_failure"
STOP_MAX_ITERS = "failed_max_iters"
STOP_IN_PROGRESS = "in progress"
STOP_RESEARCH_SYNTHESIS = "research_synthesis"
STOP_UNVERIFIED = "blocked_unverified_central_claim"
STOP_MAX_RESEARCH_ROUNDS = "research_rounds_exhausted"
STOP_WALL_CLOCK = "wall_clock_exhausted"
STOP_DEFERRED = "completed_with_deferred_actions"  # unattended: did safe work, deferred the risky bits
STOP_CRASHED = "crashed_mid_iteration"  # an unhandled exception broke an iteration (never a silent hang)

# Default required gates when a project configures them. Gates that a project does not
# configure are skipped (not counted as failing) unless explicitly required.
DEFAULT_REQUIRED_GATES = ["tests", "lint", "typecheck", "build"]
DEFAULT_QUALITY_THRESHOLD = 0.90
DEFAULT_MAX_ITERATIONS = 6
STUCK_REPEAT_THRESHOLD = 3
# epistemic governor / stability defaults
DEFAULT_MAX_RESEARCH_ROUNDS = 4
DEFAULT_MAX_PARALLEL_AGENTS = 6
DEFAULT_MAX_TOOL_CALLS_PER_ROUND = 30


class EvalOptState(TypedDict, total=False):
    """Explicit, serializable state threaded through every node."""

    task: str
    repo_path: str
    project_profile: dict[str, Any]
    acceptance_criteria: list[str]
    quality_contract: str
    plan: list[str]
    iteration: int
    max_iterations: int
    changed_files: list[str]
    command_history: list[dict[str, Any]]
    verification_results: list[dict[str, Any]]
    evaluator_score: float | None
    evaluator_feedback: str
    reflection_notes: list[str]
    risk_flags: list[str]
    failure_signatures: list[str]
    tests_weakened: bool
    codex_calls_total: int
    codex_calls_this_iter: int
    codex_notes: list[str]
    stop_reason: str | None
    final_summary: str
    # configuration carried in state so routing is self-contained
    required_gates: list[str]
    required_gates_explicit: bool  # user demanded these gates → never silently drop unconfigured ones
    quality_threshold: float
    # tool-router: deterministic plan of optional gates / research / browser / codex / docker
    risk: str
    diff_base: str | None
    tool_router_config: dict[str, Any]
    router_decision: dict[str, Any]
    router_trace: list[dict[str, Any]]
    blocking_gates: list[str]
    # epistemic governor: claim ledger + research mode + stability
    mode: str  # build | research | mixed
    task_class: str  # build | research | debug | architecture | security | performance | product
    epistemic_config: dict[str, Any]
    knowledge: dict[str, Any]  # claim/source ledger snapshot (claims, sources, contradictions, decisions)
    assumptions: list[dict[str, Any]]
    contradictions: list[dict[str, Any]]
    adjudication: dict[str, Any]
    research_questions: list[str]
    research_round: int
    max_research_rounds: int
    confirmed_gain_history: list[int]
    stability: dict[str, Any]
    research_report: str
    # unattended autonomy + context hygiene
    unattended: dict[str, Any]
    started_at: str
    research_backend: str
    blocked_decisions: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    parked_branches: list[dict[str, Any]]
    react_trace: list[dict[str, Any]]
    retrieval_pack: str
    checker_results: dict[str, Any]
    morning_report: str


def new_state(
    task: str,
    repo_path: str,
    *,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
    required_gates: list[str] | None = None,
    quality_threshold: float = DEFAULT_QUALITY_THRESHOLD,
    acceptance_criteria: list[str] | None = None,
    risk: str = "low",
    tool_router_config: dict[str, Any] | None = None,
    mode: str = "build",
    epistemic_config: dict[str, Any] | None = None,
    max_research_rounds: int = DEFAULT_MAX_RESEARCH_ROUNDS,
    research_questions: list[str] | None = None,
    unattended: dict[str, Any] | None = None,
) -> EvalOptState:
    """Construct a fresh state with safe defaults for every field."""
    # Fold the max_research_rounds param into the governor config so there is one source of truth
    # (an explicit epistemic_config value still wins).
    epistemic_config = dict(epistemic_config or {})
    _eg = dict(epistemic_config.get("epistemic_governor", {}))
    _eg.setdefault("max_research_rounds", int(max_research_rounds))
    epistemic_config["epistemic_governor"] = _eg
    return EvalOptState(
        task=task,
        repo_path=repo_path,
        project_profile={},
        acceptance_criteria=list(acceptance_criteria or []),
        quality_contract="",
        plan=[],
        iteration=0,
        max_iterations=int(max_iterations),
        changed_files=[],
        command_history=[],
        verification_results=[],
        evaluator_score=None,
        evaluator_feedback="",
        reflection_notes=[],
        risk_flags=[],
        failure_signatures=[],
        tests_weakened=False,
        codex_calls_total=0,
        codex_calls_this_iter=0,
        codex_notes=[],
        stop_reason=STOP_IN_PROGRESS,
        final_summary="",
        required_gates=list(required_gates if required_gates is not None else DEFAULT_REQUIRED_GATES),
        required_gates_explicit=required_gates is not None,
        quality_threshold=float(quality_threshold),
        risk=str(risk),
        diff_base=None,
        tool_router_config=dict(tool_router_config or {}),
        router_decision={},
        router_trace=[],
        blocking_gates=[],
        mode=str(mode),
        task_class="",
        epistemic_config=dict(epistemic_config or {}),
        knowledge={},
        assumptions=[],
        contradictions=[],
        adjudication={},
        research_questions=list(research_questions or []),
        research_round=0,
        max_research_rounds=int(max_research_rounds),
        confirmed_gain_history=[],
        stability={},
        research_report="",
        unattended=dict(unattended or {}),
        started_at="",
        research_backend="",
        blocked_decisions=[],
        decisions=[],
        parked_branches=[],
        react_trace=[],
        retrieval_pack="",
        checker_results={},
        morning_report="",
    )
