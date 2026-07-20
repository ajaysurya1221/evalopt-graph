"""Routing + bounded-loop tests. Pure: no LangGraph, no API key (MockProvider only)."""

from __future__ import annotations

import os

import pytest

from evalopt_graph import MockProvider, RunContext, new_state, route, run_loop
from evalopt_graph.checks import CommandResult
from evalopt_graph.state import (
    FAILURE_REPORT,
    FINAL_REVIEW,
    HUMAN_GATE,
    REFLECTION,
    STOP_PASS,
    STOP_PASS_WITH_WARNINGS,
    STOP_STUCK,
    STUCK_ANALYSIS,
)


def _state(**over):
    s = new_state("demo task", "/tmp/repo", max_iterations=6)
    s["required_gates"] = ["tests"]
    s.update(over)
    return s


def _gate(result):
    return {
        "gate": "tests",
        "command": "pytest",
        "exit_code": 0 if result == "PASS" else 1,
        "result": result,
        "summary": result,
    }


# ---------------- pure route() branches ----------------


def test_route_pass_goes_to_final_review():
    s = _state(verification_results=[_gate("PASS")], evaluator_score=0.95)
    assert route(s) == FINAL_REVIEW


def test_route_pass_with_no_rubric_score():
    s = _state(verification_results=[_gate("PASS")], evaluator_score=None)
    assert route(s) == FINAL_REVIEW  # missing score must not block a clean gate pass


def test_route_failing_gate_reflects_when_budget_remains():
    s = _state(
        verification_results=[_gate("FAIL")],
        evaluator_score=0.95,
        failure_signatures=["tests:x"],
        iteration=1,
    )
    assert route(s) == REFLECTION


def test_route_low_score_reflects_even_if_gates_pass():
    s = _state(
        verification_results=[_gate("PASS")], evaluator_score=0.40, quality_threshold=0.90, iteration=1
    )
    assert route(s) == REFLECTION


def test_route_stuck_when_signature_repeats():
    s = _state(
        verification_results=[_gate("FAIL")],
        evaluator_score=0.95,
        failure_signatures=["tests:boom", "tests:boom", "tests:boom"],
        iteration=2,
    )
    assert route(s) == STUCK_ANALYSIS


def test_route_max_iters_to_failure_report():
    # distinct signatures => not stuck; iteration at the ceiling => failure report
    s = _state(
        verification_results=[_gate("FAIL")],
        evaluator_score=0.95,
        failure_signatures=["tests:a", "tests:b"],
        iteration=6,
        max_iterations=6,
    )
    assert route(s) == FAILURE_REPORT


def test_route_human_gate_on_destructive_risk():
    s = _state(
        verification_results=[_gate("PASS")], evaluator_score=0.95, risk_flags=["destructive: rm -rf needed"]
    )
    assert route(s) == HUMAN_GATE


def test_route_blocks_when_tests_weakened_even_if_gates_green():
    # passing gates + high score must NOT pass if tests were weakened to get there
    s = _state(verification_results=[_gate("PASS")], evaluator_score=0.99, tests_weakened=True, iteration=1)
    assert route(s) != FINAL_REVIEW


# ---------------- end-to-end run_loop (bounded, offline) ----------------


@pytest.fixture
def py_repo(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    return str(tmp_path)


def _runner_pass(gate, command, cwd):
    return CommandResult(gate, command, 0, "PASS", "ok")


def _runner_fail_first(n):
    counts = {}

    def runner(gate, command, cwd):
        counts[gate] = counts.get(gate, 0) + 1
        if counts[gate] <= n:
            return CommandResult(gate, command, 1, "FAIL", "boom")
        return CommandResult(gate, command, 0, "PASS", "ok")

    return runner


def test_run_loop_pass(py_repo):
    s = new_state("demo", py_repo, max_iterations=6, required_gates=["tests"])
    ctx = RunContext(provider=MockProvider(score=0.95), runner=_runner_pass)
    final = run_loop(s, ctx)
    assert final["stop_reason"] == STOP_PASS
    assert final["iteration"] == 0  # passed on first try, no reflection needed


def test_run_loop_pass_with_warnings_when_no_tests(tmp_path):
    s = new_state("demo", str(tmp_path), max_iterations=6)
    final = run_loop(s, RunContext(provider=MockProvider(score=0.95), runner=_runner_pass))
    assert final["stop_reason"] == STOP_PASS_WITH_WARNINGS  # no tests configured => weakly verified


def test_run_loop_recovers_after_reflection(py_repo):
    s = new_state("demo", py_repo, max_iterations=6, required_gates=["tests"])
    ctx = RunContext(provider=MockProvider(score=0.95), runner=_runner_fail_first(1))
    final = run_loop(s, ctx)
    assert final["stop_reason"] == STOP_PASS
    assert final["iteration"] == 1  # one reflection cycle then green


def test_run_loop_is_bounded_and_blocks_when_stuck(py_repo):
    s = new_state("demo", py_repo, max_iterations=6, required_gates=["tests"])
    ctx = RunContext(provider=MockProvider(score=0.95), runner=_runner_fail_first(999))
    final = run_loop(s, ctx)
    assert final["stop_reason"] == STOP_STUCK  # identical failure => stuck, not infinite
    assert final["iteration"] <= s["max_iterations"]  # never exceeds the ceiling


def test_run_loop_writes_no_files(py_repo):
    # the pure loop must not create artifacts unless the CLI --write flag is used
    s = new_state("demo", py_repo, max_iterations=3, required_gates=["tests"])
    run_loop(s, RunContext(provider=MockProvider(score=0.95), runner=_runner_pass))
    assert not os.path.isdir(os.path.join(py_repo, ".evalopt"))
