"""Codex bridge tests — pure: NO real Codex invocation, no network, no API key.

Verifies the safe argv command builder, mode/budget decision logic, prompt rendering, and that
the bridge no-ops safely when Codex is disabled or unavailable.
"""

from __future__ import annotations

import pytest

from evalopt_graph import codex_bridge as cb
from evalopt_graph.codex_bridge import CodexConfig

# ---------------- command builder (safe argv) ----------------


def test_build_review_command_is_argv_array():
    cmd = cb.build_codex_command(
        "do a review",
        cwd="/repo",
        sandbox=cb.SANDBOX_READ_ONLY,
        approval="never",
        output_last_message="/tmp/out.txt",
    )
    assert isinstance(cmd, list)
    assert cmd[:2] == ["codex", "exec"]
    assert "--cd" in cmd and "/repo" in cmd
    assert "--sandbox" in cmd and "read-only" in cmd
    # `codex exec` 0.142.3 has NO --ask-for-approval flag (non-interactive); it must not be emitted
    assert "--ask-for-approval" not in cmd
    assert "--output-last-message" in cmd and "/tmp/out.txt" in cmd
    assert cmd[-1] == "do a review"  # prompt is the final positional arg


def test_build_patch_command_workspace_write():
    cmd = cb.build_codex_command("patch it", cwd="/wt", sandbox=cb.SANDBOX_WORKSPACE)
    assert "workspace-write" in cmd
    assert cmd[-1] == "patch it"


def test_build_command_blocks_danger_without_optin():
    with pytest.raises(ValueError):
        cb.build_codex_command("x", cwd="/r", sandbox=cb.SANDBOX_DANGER)


def test_build_command_allows_danger_with_optin():
    cmd = cb.build_codex_command("x", cwd="/r", sandbox=cb.SANDBOX_DANGER, full_access_allowed=True)
    assert "danger-full-access" in cmd


def test_build_command_rejects_invalid_sandbox_and_approval():
    with pytest.raises(ValueError):
        cb.build_codex_command("x", cwd="/r", sandbox="nope")
    with pytest.raises(ValueError):
        cb.build_codex_command("x", cwd="/r", sandbox=cb.SANDBOX_READ_ONLY, approval="sometimes")


def test_prompt_contains_no_shell_interpolation_risk():
    # a prompt with shell metacharacters stays a single argv element (never expanded)
    danger = "fix; rm -rf / && echo $(whoami)"
    cmd = cb.build_codex_command(danger, cwd="/r", sandbox=cb.SANDBOX_READ_ONLY)
    assert cmd[-1] == danger  # passed verbatim as one arg; shell=False at call site


# ---------------- prompt rendering ----------------


def test_render_prompt_fills_tokens_and_forbids_weakening():
    text = cb.render_prompt(
        "patch",
        {"task": "Add X", "acceptance": "X works", "gates": "tests", "failures": "boom", "review": "-"},
    )
    assert "Add X" in text
    assert "tests" in text
    assert "weaken" in text.lower()  # must forbid test weakening


def test_render_prompt_all_kinds_exist():
    for kind in ("review", "patch", "adversarial", "final"):
        text = cb.render_prompt(
            kind, {"task": "t", "acceptance": "a", "gates": "g", "failures": "f", "review": "r"}
        )
        assert "t" in text and len(text) > 50


# ---------------- decision logic ----------------


def _state(total=0, per_iter=0):
    return {"codex_calls_total": total, "codex_calls_this_iter": per_iter}


def test_should_invoke_false_when_disabled():
    cfg = CodexConfig(enabled=False)
    assert cb.should_invoke(_state(), cfg, cb.TRIGGER_FIRST_FAILURE) is False


def test_should_invoke_false_when_mode_off():
    cfg = CodexConfig(enabled=True, mode="off")
    assert cb.should_invoke(_state(), cfg, cb.TRIGGER_FIRST_FAILURE) is False


def test_should_invoke_respects_invoke_on(monkeypatch):
    monkeypatch.setattr(cb, "codex_available", lambda: True)
    cfg = CodexConfig(enabled=True, mode="auto", invoke_on=[cb.TRIGGER_BEFORE_FINAL])
    assert cb.should_invoke(_state(), cfg, cb.TRIGGER_FIRST_FAILURE) is False
    assert cb.should_invoke(_state(), cfg, cb.TRIGGER_BEFORE_FINAL) is True


def test_should_invoke_budget(monkeypatch):
    monkeypatch.setattr(cb, "codex_available", lambda: True)
    cfg = CodexConfig(enabled=True, mode="auto", max_codex_calls_per_run=2, max_codex_calls_per_iteration=1)
    assert cb.should_invoke(_state(total=2), cfg, cb.TRIGGER_FIRST_FAILURE) is False  # run budget hit
    assert cb.should_invoke(_state(per_iter=1), cfg, cb.TRIGGER_FIRST_FAILURE) is False  # iter budget hit
    assert cb.should_invoke(_state(), cfg, cb.TRIGGER_FIRST_FAILURE) is True


def test_should_invoke_false_when_codex_missing(monkeypatch):
    monkeypatch.setattr(cb, "codex_available", lambda: False)
    cfg = CodexConfig(enabled=True, mode="auto")
    assert cb.should_invoke(_state(), cfg, cb.TRIGGER_FIRST_FAILURE) is False


def test_resolve_action_auto_and_pinned():
    auto = CodexConfig(mode="auto")
    assert cb.resolve_action(cb.TRIGGER_REPEATED, auto) == "adversarial"
    assert cb.resolve_action(cb.TRIGGER_BEFORE_FINAL, auto) == "final"
    assert cb.resolve_action(cb.TRIGGER_FIRST_FAILURE, auto) == "review"
    pinned = CodexConfig(mode="review")
    assert cb.resolve_action(cb.TRIGGER_REPEATED, pinned) == "review"


# ---------------- run_codex no-ops safely ----------------


def test_run_codex_skipped_when_disabled():
    res = cb.run_codex("x", cwd="/r", sandbox=cb.SANDBOX_READ_ONLY, config=CodexConfig(enabled=False))
    assert res.skipped is True
    assert "disabled" in res.reason


def test_run_codex_skipped_when_unavailable(monkeypatch):
    monkeypatch.setattr(cb, "codex_available", lambda: False)
    res = cb.run_codex("x", cwd="/r", sandbox=cb.SANDBOX_READ_ONLY, config=CodexConfig(enabled=True))
    assert res.skipped is True
    assert "PATH" in res.reason


def test_run_codex_blocks_danger_without_optin(monkeypatch):
    monkeypatch.setattr(cb, "codex_available", lambda: True)
    res = cb.run_codex(
        "x", cwd="/r", sandbox=cb.SANDBOX_DANGER, config=CodexConfig(enabled=True, full_access_allowed=False)
    )
    assert res.skipped is True
    assert "full_access" in res.reason or "danger" in res.reason.lower()


def test_codexconfig_from_dict_filters_unknown():
    cfg = CodexConfig.from_dict({"enabled": True, "mode": "patch", "bogus": 1})
    assert cfg.enabled is True and cfg.mode == "patch"
    assert not hasattr(cfg, "bogus")
