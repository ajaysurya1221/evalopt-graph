"""Quality-gate + evaluator tests (pure; MockProvider only)."""

from __future__ import annotations

import subprocess
import sys

from evalopt_graph import MockProvider, evaluate, passes_quality_gate
from evalopt_graph.checks import (
    CommandResult,
    all_required_pass,
    detect_test_weakening,
    failing_gates,
    is_github_repo,
    run_gates,
)


def _r(gate, result):
    return {"gate": gate, "result": result, "summary": result}


def test_all_pass():
    ok, reasons = passes_quality_gate(
        [_r("tests", "PASS"), _r("lint", "PASS")], 0.95, ["tests", "lint"], 0.90
    )
    assert ok is True
    assert reasons == []


def test_failing_gate_blocks():
    ok, reasons = passes_quality_gate([_r("tests", "FAIL")], 0.99, ["tests"], 0.90)
    assert ok is False
    assert any("tests" in r for r in reasons)


def test_not_configured_is_tolerated():
    ok, _ = passes_quality_gate([_r("tests", "NOT_CONFIGURED")], 0.95, ["tests"], 0.90)
    assert ok is True


def test_low_rubric_score_blocks():
    ok, reasons = passes_quality_gate([_r("tests", "PASS")], 0.50, ["tests"], 0.90)
    assert ok is False
    assert any("0.50" in r for r in reasons)


def test_missing_score_does_not_block():
    ok, _ = passes_quality_gate([_r("tests", "PASS")], None, ["tests"], 0.90)
    assert ok is True


def test_test_weakening_is_automatic_fail():
    ok, reasons = passes_quality_gate([_r("tests", "PASS")], 0.99, ["tests"], 0.90, tests_weakened=True)
    assert ok is False
    assert any("weaken" in r.lower() for r in reasons)


def test_evaluate_with_mock_provider():
    state = {"task": "x", "acceptance_criteria": ["a"], "verification_results": [], "changed_files": []}
    out = evaluate(state, MockProvider(score=0.93))
    assert abs(out["score"] - 0.93) < 1e-9
    assert out["feedback"]


def test_run_gates_skips_unconfigured():
    profile = {"commands": {"test": "echo ok", "lint": None, "typecheck": None, "build": None}}

    def fake(gate, command, cwd):
        return CommandResult(gate, command, 0, "PASS", "ok")

    results = run_gates(profile, "/tmp", required_gates=["tests", "lint"], runner=fake)
    by_gate = {r.gate: r for r in results}
    assert by_gate["tests"].result == "PASS"
    assert by_gate["lint"].result == "NOT_CONFIGURED"
    assert failing_gates(results) == []
    assert all_required_pass(results, ["tests", "lint"]) is True


def test_run_gates_real_subprocess_pass():
    # one real subprocess to prove the runner path works end-to-end (no network, no API)
    profile = {"commands": {"test": f'{sys.executable} -c "assert 1+1==2"'}}
    results = run_gates(profile, ".", required_gates=["tests"])
    assert results[0].result == "PASS"
    assert results[0].exit_code == 0


def test_run_gates_real_subprocess_fail():
    profile = {"commands": {"test": f'{sys.executable} -c "raise SystemExit(3)"'}}
    results = run_gates(profile, ".", required_gates=["tests"])
    assert results[0].result == "FAIL"
    assert results[0].exit_code == 3


def _set_remote(tmp_path, remote_url: str):
    repo = tmp_path / "repo"
    if not repo.exists():
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", remote_url], check=True)
    else:
        subprocess.run(["git", "-C", str(repo), "remote", "set-url", "origin", remote_url], check=True)
    return repo


def test_is_github_repo_accepts_exact_github_remote_hosts(tmp_path):
    repo = _set_remote(tmp_path, "https://github.com/owner/repo.git")
    assert is_github_repo(str(repo)) is True

    _set_remote(tmp_path, "git@github.com:owner/repo.git")
    assert is_github_repo(str(repo)) is True

    _set_remote(tmp_path, "ssh://git@github.com/owner/repo.git")
    assert is_github_repo(str(repo)) is True

    _set_remote(tmp_path, "https://GitHub.com./owner/repo.git")
    assert is_github_repo(str(repo)) is True


def test_is_github_repo_rejects_github_text_outside_exact_host(tmp_path):
    repo = _set_remote(tmp_path, "https://evil.example/github.com/owner/repo.git")
    assert is_github_repo(str(repo)) is False

    _set_remote(tmp_path, "https://github.com.evil.example/owner/repo.git")
    assert is_github_repo(str(repo)) is False

    _set_remote(tmp_path, "https://github.com@evil.example/owner/repo.git")
    assert is_github_repo(str(repo)) is False

    _set_remote(tmp_path, "git@github.com.evil.example:owner/repo.git")
    assert is_github_repo(str(repo)) is False

    _set_remote(tmp_path, "https://github.com.../owner/repo.git")
    assert is_github_repo(str(repo)) is False

    _set_remote(tmp_path, "file:///tmp/github.com/owner/repo.git")
    assert is_github_repo(str(repo)) is False

    _set_remote(tmp_path, "file://github.com/owner/repo.git")
    assert is_github_repo(str(repo)) is False


def test_is_github_repo_preserves_dot_github_fallback(tmp_path):
    repo = tmp_path / "not-a-git-repo"
    repo.mkdir()
    assert is_github_repo(str(repo)) is False
    (repo / ".github").mkdir(parents=True)
    assert is_github_repo(str(repo)) is True


# ---------------- anti-gaming: test-weakening detector ----------------


def test_detect_weakening_added_skip():
    diff = "+++ b/tests/test_x.py\n+@pytest.mark.skip(reason='flaky')\n+def test_thing():\n"
    weak, ev = detect_test_weakening("/repo", get_diff=lambda _p: diff)
    assert weak is True
    assert any("skip" in e.lower() for e in ev)


def test_detect_weakening_removed_assertions():
    diff = "+++ b/tests/test_x.py\n-    assert result == expected\n-    assert other == 2\n+    pass\n"
    weak, ev = detect_test_weakening("/repo", get_diff=lambda _p: diff)
    assert weak is True
    assert any("assertion" in e.lower() for e in ev)


def test_detect_weakening_legit_change_is_clean():
    diff = "+++ b/tests/test_x.py\n+def test_new_behavior():\n+    assert add(2, 3) == 5\n"
    weak, ev = detect_test_weakening("/repo", get_diff=lambda _p: diff)
    assert weak is False
    assert ev == []


def test_detect_weakening_ignores_non_test_files():
    diff = "+++ b/src/app.py\n+    # skip this\n-    assert x\n"
    weak, _ = detect_test_weakening("/repo", get_diff=lambda _p: diff)
    assert weak is False


def test_detect_weakening_no_diff():
    weak, ev = detect_test_weakening("/repo", get_diff=lambda _p: "")
    assert weak is False
    assert ev == []
