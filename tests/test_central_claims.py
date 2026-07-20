from __future__ import annotations

import subprocess

from evalopt_graph import checks, epistemic, graph
from evalopt_graph.state import new_state

# ------------------------------- B1: central_criteria -------------------------------


def test_central_criteria_selects_critical_ones():
    crits = [
        "reset the user password securely with token expiry",
        "render the results table with pagination",
        "delete the production database backup on cleanup",
    ]
    got = epistemic.central_criteria(crits)
    assert crits[0] in got  # password/token -> critical
    assert crits[2] in got  # production/delete -> critical
    assert crits[1] not in got  # cosmetic UI -> not critical


# ------------------------------- B4: wired into run_loop, block vs warn -------------------------------


def _green_runner(gate, command, cwd):
    return checks.CommandResult(gate, command, 0, "PASS", "12 passed")


def _py_repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True, capture_output=True, text=True)
    return str(tmp_path)


def test_unverified_critical_criterion_blocks_pass_even_when_gates_green(tmp_path):
    repo = _py_repo(tmp_path)
    st = new_state(
        "secure it",
        repo,
        required_gates=["tests"],
        acceptance_criteria=["reset password securely with token expiry"],
    )
    final = graph.run_loop(st, graph.RunContext(runner=_green_runner))
    assert final["stop_reason"] == "blocked_unverified_central_claim"


def test_unverified_noncritical_criterion_is_warning_not_block(tmp_path):
    repo = _py_repo(tmp_path)
    st = new_state(
        "cosmetic",
        repo,
        required_gates=["tests"],
        acceptance_criteria=["render the results table with pagination"],
    )
    final = graph.run_loop(st, graph.RunContext(runner=_green_runner))
    assert final["stop_reason"] in ("pass", "pass_with_warnings")  # cosmetic isn't critical -> not blocked


# ------------------------------- Codex-review regressions -------------------------------


def test_central_criteria_covers_mfa_oauth_rbac_access_control():
    # The critical-topic detector must catch common security wording, or the PASS-block never fires.
    for c in [
        "require MFA for admin users",
        "add OAuth login for all endpoints",
        "enforce RBAC on the dashboard",
        "add access control checks to the API",
        "add access-control checks to the API",  # hyphenated form (Codex re-verify catch)
    ]:
        assert epistemic.central_criteria([c]) == [c], c


def test_unverified_critical_criterion_blocks_even_without_contradiction_search(tmp_path):
    # Disabling contradiction search must NOT bypass the unverified-central-claim PASS-block.
    repo = _py_repo(tmp_path)
    st = new_state(
        "secure it",
        repo,
        required_gates=["tests"],
        acceptance_criteria=["reset password securely with token expiry"],
        epistemic_config={"epistemic_governor": {"require_contradiction_search_before_final": False}},
    )
    final = graph.run_loop(st, graph.RunContext(runner=_green_runner))
    assert final["stop_reason"] == "blocked_unverified_central_claim"


def test_legacy_epistemic_disable_cannot_bypass_canonical_kernel(tmp_path):
    repo = _py_repo(tmp_path)
    state = new_state(
        "secure it",
        repo,
        required_gates=["tests"],
        acceptance_criteria=["reset password securely with token expiry"],
        epistemic_config={"epistemic_governor": {"enabled": False}},
    )

    final = graph.run_loop(state, graph.RunContext(runner=_green_runner))

    assert final["stop_reason"] == "blocked_unverified_central_claim"
    assert final["kernel_decision"]["status"] == "UNVERIFIED"
    assert "critical_criterion_unverified:0" in final["kernel_decision"]["reasons"]
