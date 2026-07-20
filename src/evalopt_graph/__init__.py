"""evalopt's stable kernel API plus lazy compatibility imports."""

from __future__ import annotations

import importlib

from .kernel import (
    AcceptanceDecision,
    AcceptanceInput,
    ClaimRecord,
    EvidenceAttestation,
    EvidenceAuthority,
    EvidenceMaterial,
    EvidenceRequest,
    GovernancePolicy,
    SupportAssessment,
    evaluate_acceptance,
)

__version__ = "0.1.0"
__all__ = [
    "GovernancePolicy",
    "ClaimRecord",
    "EvidenceRequest",
    "EvidenceMaterial",
    "EvidenceAttestation",
    "SupportAssessment",
    "EvidenceAuthority",
    "AcceptanceInput",
    "AcceptanceDecision",
    "evaluate_acceptance",
]

# One compatibility cycle: old graph/runtime names remain addressable without making a kernel import
# load orchestration, providers, CLIs, benchmark code, or optional integrations.
_LEGACY = {
    "EvalOptState": ("state", "EvalOptState"),
    "new_state": ("state", "new_state"),
    "DEFAULT_MAX_ITERATIONS": ("state", "DEFAULT_MAX_ITERATIONS"),
    "DEFAULT_QUALITY_THRESHOLD": ("state", "DEFAULT_QUALITY_THRESHOLD"),
    "RunContext": ("graph", "RunContext"),
    "build_graph": ("graph", "build_graph"),
    "node_tool_router": ("graph", "node_tool_router"),
    "render_contract": ("graph", "render_contract"),
    "route": ("graph", "route"),
    "run": ("graph", "run"),
    "run_loop": ("graph", "run_loop"),
    "run_research_loop": ("graph", "run_research_loop"),
    "ClaimLedger": ("claim_ledger", "ClaimLedger"),
    "Claim": ("epistemic", "Claim"),
    "Source": ("epistemic", "Source"),
    "is_usable": ("epistemic", "is_usable"),
    "meets_trust_requirement": ("epistemic", "meets_trust_requirement"),
    "verify_claim": ("source_verification", "verify_claim"),
    "verify_ledger": ("source_verification", "verify_ledger"),
    "Contradiction": ("contradictions", "Contradiction"),
    "find_contradictions": ("contradictions", "find_contradictions"),
    "AdjudicationResult": ("confidence", "AdjudicationResult"),
    "adjudicate": ("confidence", "adjudicate"),
    "score_confidence": ("confidence", "score_confidence"),
    "ResearchReport": ("research_mode", "ResearchReport"),
    "classify_task": ("research_mode", "classify_task"),
    "passes_research_gate": ("research_mode", "passes_research_gate"),
    "render_markdown": ("research_mode", "render_markdown"),
    "synthesize": ("research_mode", "synthesize"),
    "CommandResult": ("checks", "CommandResult"),
    "detect_test_weakening": ("checks", "detect_test_weakening"),
    "git_changed_files": ("checks", "git_changed_files"),
    "is_github_repo": ("checks", "is_github_repo"),
    "resolve_diff_base": ("checks", "resolve_diff_base"),
    "run_command": ("checks", "run_command"),
    "run_command_argv": ("checks", "run_command_argv"),
    "run_gates": ("checks", "run_gates"),
    "run_optional_gates": ("checks", "run_optional_gates"),
    "evaluate": ("evaluator", "evaluate"),
    "passes_quality_gate": ("evaluator", "passes_quality_gate"),
    "failure_signature": ("reflection", "failure_signature"),
    "is_stuck": ("reflection", "is_stuck"),
    "reflect": ("reflection", "reflect"),
    "MockProvider": ("providers", "MockProvider"),
    "get_provider": ("providers", "get_provider"),
    "CodexConfig": ("codex_bridge", "CodexConfig"),
    "build_codex_command": ("codex_bridge", "build_codex_command"),
    "codex_available": ("codex_bridge", "codex_available"),
    "run_codex": ("codex_bridge", "run_codex"),
    "configured_gates": ("project_detect", "configured_gates"),
    "detect_docker": ("project_detect", "detect_docker"),
    "detect_project": ("project_detect", "detect_project"),
    "should_use_docker": ("project_detect", "should_use_docker"),
    "RouterConfig": ("tool_router", "RouterConfig"),
    "RouterDecision": ("tool_router", "RouterDecision"),
    "classify_changes": ("tool_router", "classify_changes"),
    "detect_task_signals": ("tool_router", "detect_task_signals"),
    "plan_from_state": ("tool_router", "plan_from_state"),
    "plan_tools": ("tool_router", "plan"),
    "resolve_binary": ("tool_router", "resolve_binary"),
    "BlockedDecision": ("unattended", "BlockedDecision"),
    "Decision": ("unattended", "Decision"),
    "ParkedBranch": ("unattended", "ParkedBranch"),
    "classify_action": ("unattended", "classify_action"),
    "render_morning_report": ("unattended", "render_morning_report"),
    "SemanticCache": ("context_hygiene", "SemanticCache"),
    "build_retrieval_pack": ("context_hygiene", "build_retrieval_pack"),
    "react_event": ("context_hygiene", "react_event"),
    "summarize_command_output": ("context_hygiene", "summarize_command_output"),
}


def __getattr__(name: str):
    try:
        module_name, symbol = _LEGACY[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = importlib.import_module(f".{module_name}", __name__)
    value = module if symbol is None else getattr(module, symbol)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted({*globals(), *_LEGACY})
