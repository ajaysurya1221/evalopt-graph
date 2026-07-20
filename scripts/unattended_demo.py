"""Offline dry demo of unattended (overnight) mode — no network, no API key, no real risky actions.

Scenario in a temp repo:
- one SAFE ambiguity (which package manager) -> auto-decided, no prompt
- one SAFE failing test -> fixed via the reflection loop
- one SIMULATED destructive action (a script containing `rm -rf`) -> DEFERRED (blocked decision),
  never waited on

Expected: the safe work completes, the destructive action is recorded as a blocked decision, a
MORNING_REPORT.md is written, and the run exits cleanly (stop_reason = completed_with_deferred_actions).

Run:  python scripts/unattended_demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalopt_graph import MockProvider, RunContext, new_state, run_loop, unattended
from evalopt_graph.checks import CommandResult

NOW = "2026-06-28T00:00:00+00:00"


def main() -> None:
    print("=== UNATTENDED DEMO: safe fix + deferred destructive action, no waiting ===")

    # 1) safe ambiguity is auto-decided (no prompt)
    d = unattended.decide("package_manager", {"lockfile_manager": "pnpm"}, now=NOW)
    print(f"safe ambiguity      : package_manager -> {d.choice} (deferred={d.deferred})")
    assert d.deferred is False

    tmp = Path(tempfile.mkdtemp())
    (tmp / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp / "tests").mkdir()
    (tmp / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")

    # a failing test that recovers after one reflection (simulated), plus the patch introduces a
    # script with a destructive command that the security pass will catch and DEFER.
    def runner_fail_then_pass():
        counts: dict[str, int] = {}

        def runner(gate, command, cwd):
            counts[gate] = counts.get(gate, 0) + 1
            if counts[gate] <= 1:
                return CommandResult(gate, command, 1, "FAIL", "AssertionError: not yet")
            return CommandResult(gate, command, 0, "PASS", "ok")

        return runner

    def gen_hook(state, ctx):
        (tmp / "cleanup.sh").write_text("#!/usr/bin/env bash\nrm -rf /tmp/old_build\n")
        return ["cleanup.sh"]

    state = new_state(
        "fix the failing test and add a cleanup script",
        str(tmp),
        required_gates=["tests"],
        unattended={"enabled": True, "max_wall_clock_hours": 8},
    )
    final = run_loop(
        state,
        RunContext(
            provider=MockProvider(score=0.95),
            runner=runner_fail_then_pass(),
            generation_hook=gen_hook,
            now=lambda: NOW,
        ),
    )

    print(f"stop_reason         : {final['stop_reason']}  (expect completed_with_deferred_actions)")
    print(
        f"safe test fixed     : tests gate now {[r['result'] for r in final['verification_results'] if r['gate'] == 'tests']}"
    )
    blocked = final["blocked_decisions"]
    print(f"deferred (blocked)  : {[b['action_class'] for b in blocked]}")
    print(f"parked branches     : {[p['id'] for p in final['parked_branches']]}")
    report_path = tmp / ".evalopt" / "overnight" / "MORNING_REPORT.md"
    print(f"morning report      : {'written' if report_path.exists() else 'MISSING'} -> {report_path}")

    assert final["stop_reason"] == "completed_with_deferred_actions"
    assert any(b["action_class"] == "destructive" for b in blocked), "destructive action must be deferred"
    assert report_path.exists(), "MORNING_REPORT.md must be written"
    assert "git push" not in final.get("final_summary", "")  # nothing remote happened
    print("RESULT: safe work done; destructive action deferred without waiting; morning report written. OK")
    print("\nUNATTENDED DEMO PASSED")


if __name__ == "__main__":
    main()
