"""Unattended Autonomy Governor tests: decision matrix, deferral of risky actions, branch parking,
wall-clock budget, and morning report. Pure: no network, no LangGraph, no API key."""

from __future__ import annotations

from evalopt_graph import MockProvider, RunContext, new_state, run_loop, unattended
from evalopt_graph.checks import CommandResult
from evalopt_graph.state import STOP_DEFERRED, STOP_WALL_CLOCK

NOW = "2026-06-28T00:00:00+00:00"


def _runner_pass(gate, command, cwd):
    return CommandResult(gate, command, 0, "PASS", "ok")


# ---------------- decision matrix (auto-decide vs defer) ----------------


def test_auto_decides_safe_repo_local_ambiguity():
    d = unattended.decide("package_manager", {"lockfile_manager": "pnpm"}, now=NOW)
    assert d.choice == "pnpm" and d.deferred is False and d.reversible is True


def test_library_choice_prefers_existing_dependency():
    d = unattended.decide("library_choice", {"existing_dep": "httpx"}, now=NOW)
    assert d.choice == "httpx" and d.deferred is False


def test_credential_request_creates_env_example_not_prompt():
    d = unattended.decide("env_var", now=NOW)
    assert ".env.example" in d.choice and "dummy" in d.choice and d.deferred is False


def test_database_uses_local_or_mock_not_prod():
    d = unattended.decide("database", now=NOW)
    assert ("mock" in d.choice or "local" in d.choice) and d.deferred is False


def test_remote_mutation_is_deferred():
    d = unattended.decide("push_or_pr", now=NOW)
    assert d.deferred is True and d.action_class == unattended.REMOTE_MUTATION
    assert d.fallback  # carries a non-destructive fallback


def test_safe_fallback_chosen_for_deletion():
    d = unattended.decide("destructive_cleanup", now=NOW)
    assert d.deferred is False and "quarantine" in d.fallback.lower()
    assert "quarantine" in d.choice.lower() and "rm " not in d.choice.lower()  # never an actual delete


def test_unknown_kind_takes_conservative_reversible_default():
    d = unattended.decide("something_unmapped", now=NOW)
    assert d.reversible is True and d.deferred is False


# ---------------- action classification (never wait on risky actions) ----------------


def test_does_not_wait_on_destructive_action():
    deferred, acls, reason, fb = unattended.evaluate_action("rm -rf build/", now=NOW)
    assert deferred is True and acls == unattended.DESTRUCTIVE and fb


def test_remote_and_global_and_cred_actions_deferred():
    assert unattended.classify_action("git push --force origin main") == unattended.REMOTE_MUTATION
    assert unattended.classify_action("npm install -g typescript") == unattended.GLOBAL_STATE
    assert unattended.classify_action("API_KEY=sk-abcdefghij1234567890") == unattended.CREDENTIALED
    assert unattended.classify_action("edit src/app.py to add a function") == unattended.SAFE_REPO_LOCAL


# ---------------- wall clock + parking ----------------


def test_wall_clock_exceeded():
    assert unattended.wall_clock_exceeded("2026-06-28T00:00:00+00:00", "2026-06-28T09:00:00+00:00", 8) is True
    assert (
        unattended.wall_clock_exceeded("2026-06-28T00:00:00+00:00", "2026-06-28T01:00:00+00:00", 8) is False
    )


def test_parked_branch_can_be_resumed():
    state = {"parked_branches": []}
    p = unattended.ParkedBranch(
        id="park-1", reason="blocked on X", next_human_action="approve push", created_at=NOW
    )
    state["parked_branches"].append(p.to_dict())
    # a parked branch does not stop other decisions
    other = unattended.decide("missing_tests", {"has_test_framework": True}, now=NOW)
    assert other.deferred is False
    resumed = unattended.pop_parked(state, "park-1")
    assert resumed is not None and resumed["next_human_action"] == "approve push"
    assert state["parked_branches"] == []  # removed on resume


def test_morning_report_includes_blocked_and_next_command():
    state = {
        "task": "implement X",
        "mode": "build",
        "stop_reason": STOP_DEFERRED,
        "started_at": NOW,
        "iteration": 2,
        "max_iterations": 12,
        "blocked_decisions": [
            {
                "action": "git push",
                "action_class": "remote_mutation",
                "reason": "remote",
                "fallback": "keep local",
            }
        ],
        "parked_branches": [{"id": "park-2", "reason": "needs push", "next_human_action": "approve"}],
        "adjudication": {"confirmed_facts": ["a"], "assumptions": [], "unresolved_contradictions": []},
        "verification_results": [{"gate": "tests", "result": "PASS"}],
        "command_history": [{"command": "pytest -q"}],
    }
    md = unattended.render_morning_report(state)
    assert "Blocked decisions" in md and "git push" in md
    assert "Next command" in md and "Safe to commit" in md


# ---------------- loop integration ----------------


def test_unattended_defers_destructive_flag_without_waiting(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")

    def gen_hook(state, ctx):
        # the patch introduces a script containing a destructive command (caught by security_review)
        p = tmp_path / "danger.sh"
        p.write_text("#!/usr/bin/env bash\nrm -rf /tmp/whatever\n")
        return ["danger.sh"]

    s = new_state(
        "add a cleanup script",
        str(tmp_path),
        required_gates=["tests"],
        unattended={"enabled": True, "max_wall_clock_hours": 8},
    )
    final = run_loop(
        s,
        RunContext(
            provider=MockProvider(score=0.95), runner=_runner_pass, generation_hook=gen_hook, now=lambda: NOW
        ),
    )
    # never waited; recorded the destructive action as a blocked decision; parked the branch
    assert final["stop_reason"] == STOP_DEFERRED
    blocked = final["blocked_decisions"]
    assert blocked and any(
        "destructive" in b["action"].lower() or b["action_class"] == "destructive" for b in blocked
    )
    assert final["parked_branches"]
    assert final["morning_report"] and "Morning Report" in final["morning_report"]


def test_unattended_wall_clock_stops_cleanly(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")

    calls = {"n": 0}

    def clock():
        # first call (goal_intake) = t0; subsequent calls jump far past the budget
        calls["n"] += 1
        return "2026-06-28T00:00:00+00:00" if calls["n"] == 1 else "2026-06-28T20:00:00+00:00"

    s = new_state(
        "do work",
        str(tmp_path),
        required_gates=["tests"],
        unattended={"enabled": True, "max_wall_clock_hours": 0.001},
    )
    final = run_loop(s, RunContext(provider=MockProvider(score=0.95), runner=_runner_pass, now=clock))
    assert final["stop_reason"] == STOP_WALL_CLOCK
    assert "morning_report" in final and final["morning_report"]


def test_normal_run_is_unaffected_when_unattended_off(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    s = new_state("demo", str(tmp_path), required_gates=["tests"])  # unattended off
    final = run_loop(s, RunContext(provider=MockProvider(score=0.95), runner=_runner_pass, now=lambda: NOW))
    assert final["stop_reason"] == "pass"
    assert final["blocked_decisions"] == [] and final["morning_report"] == ""


# ---------------- LangGraph unattended: honest guard (Option B) ----------------


def test_cli_rejects_langgraph_unattended(capsys):
    from evalopt_graph.cli import main

    rc = main(["--task", "x", "--repo", "/tmp", "--backend", "langgraph", "--unattended", "--quiet"])
    assert rc == 2  # nonzero, refused
    cap = capsys.readouterr()
    assert "langgraph" in cap.err.lower() and "removed" in cap.err.lower()
    assert "morning report" not in cap.out.lower()  # must NOT claim a report was written


def test_cli_rejects_langgraph_overnight(capsys):
    from evalopt_graph.cli import main

    rc = main(["--task", "x", "--repo", "/tmp", "--backend", "langgraph", "--overnight", "--quiet"])
    assert rc == 2


def test_cli_pure_unattended_runs_and_reports(tmp_path, capsys):
    from evalopt_graph.cli import main

    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    rc = main(
        [
            "--task",
            "make the suite green",
            "--repo",
            str(tmp_path),
            "--backend",
            "pure",
            "--unattended",
            "--simulate",
            "--quiet",
        ]
    )
    assert rc in (0, 1)  # the supported combo runs to completion (guard did not reject it)
    assert "Morning report:" in capsys.readouterr().out  # pure unattended DOES write + report
