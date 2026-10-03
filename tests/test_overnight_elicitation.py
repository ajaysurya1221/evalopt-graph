"""Tests for the overnight MCP-elicitation handling (hook decline + readiness verification).

Pure/offline: loads the canonical hook by path; no Claude Code, no MCP, no network.
"""

from __future__ import annotations

import importlib.util
import os

import pytest

from evalopt_graph import permissions

_EXAMPLES = os.path.join(os.path.dirname(__file__), "..", "examples", "claude-code-overnight")
_HOOK = os.path.join(_EXAMPLES, "hooks", "elicitation_evalopt_overnight.py")


def _load_hook():
    if not os.path.isdir(_EXAMPLES):  # the examples tree is not shipped in the sdist
        pytest.skip("example Claude Code hooks are not present")
    spec = importlib.util.spec_from_file_location("elicitation_hook", os.path.abspath(_HOOK))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_hook_declines_elicitation():
    hook = _load_hook()
    out = hook.build_output({"hook_event_name": "Elicitation", "mcp_server_name": "context7"})
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "Elicitation"
    assert hso["action"] == "decline"  # never accept unattended


def test_hook_handles_elicitation_result():
    hook = _load_hook()
    out = hook.build_output({"hook_event_name": "ElicitationResult"})
    assert out["hookSpecificOutput"]["hookEventName"] == "ElicitationResult"
    assert out["hookSpecificOutput"]["action"] == "decline"


def test_hook_overnight_detection(tmp_path, monkeypatch):
    hook = _load_hook()
    monkeypatch.delenv("EVALOPT_OVERNIGHT", raising=False)
    assert hook.overnight_active(str(tmp_path)) is False  # interactive → no-op
    monkeypatch.setenv("EVALOPT_OVERNIGHT", "1")
    assert hook.overnight_active(str(tmp_path)) is True
    monkeypatch.delenv("EVALOPT_OVERNIGHT", raising=False)
    odir = tmp_path / ".evalopt" / "overnight"
    odir.mkdir(parents=True)
    (odir / "ACTIVE").write_text("")
    assert hook.overnight_active(str(tmp_path)) is True  # ACTIVE marker file


def test_hook_logs_block(tmp_path):
    hook = _load_hook()
    hook.log_block(str(tmp_path), {"event": "Elicitation", "behavior": "decline"})
    blocked = tmp_path / ".evalopt" / "overnight" / "blocked_decisions.jsonl"
    elicit = tmp_path / ".evalopt" / "overnight" / "elicitation_blocks.jsonl"
    assert blocked.is_file() and elicit.is_file()
    assert "decline" in blocked.read_text()


def _base_facts(**over):
    facts = {"is_git_repo": True, "permission_hooks_installed": True, "elicitation_hook_installed": True}
    facts.update(over)
    return facts


def test_readiness_warns_when_elicitation_hook_missing():
    res = permissions.assess_readiness(_base_facts(elicitation_hook_installed=False))
    assert any("elicitation" in w.lower() for w in res["warnings"])


def test_readiness_no_elicitation_warning_when_present():
    res = permissions.assess_readiness(_base_facts(elicitation_hook_installed=True))
    assert not any("elicitation" in w.lower() for w in res["warnings"])
