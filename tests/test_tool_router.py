"""Characterize the deprecated host-planning shim without restoring tool policy."""

from __future__ import annotations

from evalopt_graph import MockProvider, RunContext, new_state, node_tool_router, run_loop
from evalopt_graph.checks import CommandResult
from evalopt_graph.state import STOP_PASS
from evalopt_graph.tool_router import classify_changes, detect_task_signals, plan, resolve_binary


def test_compatibility_plan_never_selects_or_executes_host_tools() -> None:
    decision = plan(
        task="refactor the browser client for lower latency",
        acceptance_criteria=["the page renders"],
        changed_files=["web/App.tsx", "scripts/check.sh"],
        risk="high",
    )

    assert decision.selected_gates == []
    assert decision.research_tools == []
    assert decision.browser_checks == []
    assert decision.blocking_gates == []
    assert decision.verification_mode == "host"
    assert decision.selected_gate_names() == []


def test_compatibility_classification_is_serializable_and_non_authoritative() -> None:
    categories = classify_changes(["Dockerfile", ".github/workflows/ci.yml", "src/App.tsx"])
    signals = detect_task_signals("refactor against the current API", [], risk="high")

    assert categories["dockerfile_changed"]
    assert categories["github_actions_changed"]
    assert categories["ui_or_web_surface_changed"]
    assert signals["risk_high"] and signals["structural_refactor"]


def test_resolve_binary_remains_a_host_compatibility_helper() -> None:
    path, found = resolve_binary("python3")
    assert found and path and path.endswith("python3")


def test_graph_records_noop_router_decision(tmp_path) -> None:
    state = new_state("host owns tool selection", str(tmp_path))
    state["changed_files"] = ["src/app.py"]

    result = node_tool_router(state, RunContext())

    assert result["router_decision"]["selected_gates"] == []
    assert result["blocking_gates"] == []
    assert result["router_trace"]


def test_compatibility_loop_still_passes_with_host_gate_results(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    state = new_state("demo", str(tmp_path), required_gates=["tests"])

    def runner(gate: str, command: str, cwd: str) -> CommandResult:
        return CommandResult(gate, command, 0, "PASS", "ok")

    final = run_loop(state, RunContext(provider=MockProvider(score=0.95), runner=runner))

    assert final["stop_reason"] == STOP_PASS
    assert final["router_decision"]["selected_gates"] == []
