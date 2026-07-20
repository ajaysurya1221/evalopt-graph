from __future__ import annotations

import subprocess

import pytest

from evalopt_graph.cli import build_arg_parser
from evalopt_graph.generation import (
    apply_unified_diff,
    extract_unified_diff,
    make_diff_generation_hook,
)
from evalopt_graph.graph import RunContext, run_loop
from evalopt_graph.state import new_state


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _init_repo(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    return str(tmp_path)


class _DiffProvider:
    """A provider whose completion always returns a fixed fenced diff."""

    def __init__(self, diff_body):
        self._diff = diff_body

    def complete(self, system, prompt, *, tag=None, **kw):
        return f"```diff\n{self._diff}```"


# ------------------------------- apply_unified_diff -------------------------------


def test_apply_unified_diff_edits_a_file(tmp_path):
    repo = _init_repo(tmp_path)
    diff = (
        "--- a/calc.py\n"
        "+++ b/calc.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def add(a, b):\n"
        "-    return a - b\n"
        "+    return a + b\n"
    )
    ok, changed = apply_unified_diff(repo, diff)
    assert ok is True
    assert changed == ["calc.py"]
    assert (tmp_path / "calc.py").read_text() == "def add(a, b):\n    return a + b\n"


def test_apply_unified_diff_rejects_garbage(tmp_path):
    repo = _init_repo(tmp_path)
    ok, changed = apply_unified_diff(repo, "not a diff at all")
    assert ok is False
    assert changed == []


# ------------------------------- extract_unified_diff -------------------------------


def test_extract_unified_diff_from_fenced_block():
    resp = "Here is the fix:\n```diff\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-a\n+b\n```\nDone."
    got = extract_unified_diff(resp)
    assert got.startswith("--- a/x.py")
    assert "+b" in got


def test_extract_unified_diff_none_returns_empty():
    assert extract_unified_diff("no diff here, just prose") == ""


# ------------------------------- make_diff_generation_hook -------------------------------


def test_generation_hook_applies_provider_diff(tmp_path):
    repo = _init_repo(tmp_path)
    diff_body = "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
    hook = make_diff_generation_hook()
    ctx = RunContext(provider=_DiffProvider(diff_body))
    state = {
        "task": "fix add",
        "repo_path": repo,
        "changed_files": [],
        "verification_results": [],
        "reflection_notes": [],
    }
    changed = hook(state, ctx)
    assert changed == ["calc.py"]
    assert "return a + b" in (tmp_path / "calc.py").read_text()


def test_generation_hook_no_diff_records_note(tmp_path):
    repo = _init_repo(tmp_path)

    class _Prose:
        def complete(self, system, prompt, *, tag=None, **kw):
            return "I think you should refactor, but here is no diff."

    hook = make_diff_generation_hook()
    state = {
        "task": "x",
        "repo_path": repo,
        "changed_files": [],
        "verification_results": [],
        "reflection_notes": [],
    }
    changed = hook(state, RunContext(provider=_Prose()))
    assert changed == []
    assert any("no diff" in n.lower() for n in state["reflection_notes"])


# ------------------------------- end-to-end + CLI -------------------------------


def test_loop_edits_code_and_reaches_pass(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\n")
    _init_repo(tmp_path)

    diff_body = "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
    ctx = RunContext(provider=_DiffProvider(diff_body), generation_hook=make_diff_generation_hook())
    state = new_state("make add() correct", str(tmp_path), required_gates=["tests"])
    final = run_loop(state, ctx)
    assert final["stop_reason"] in ("pass", "pass_with_warnings")
    assert "return a + b" in (tmp_path / "calc.py").read_text()


def test_cli_has_edit_worker_flag_defaulting_off():
    args = build_arg_parser().parse_args(["--task", "x"])
    assert args.edit_worker == "off"
    args2 = build_arg_parser().parse_args(["--task", "x", "--edit-worker", "diff"])
    assert args2.edit_worker == "diff"


@pytest.mark.parametrize("removed_mode", ["patch", "auto"])
def test_cli_rejects_removed_codex_patch_scheduling(removed_mode):
    with pytest.raises(SystemExit):
        build_arg_parser().parse_args(["--task", "x", "--codex", removed_mode])


def test_generation_hook_includes_repo_file_contents_in_prompt(tmp_path):
    # A real model must see the code to fix it: the hook prompt includes the repo's source files.
    repo = _init_repo(tmp_path)

    class _Spy:
        def __init__(self):
            self.prompt = ""

        def complete(self, system, prompt, *, tag=None, **kw):
            self.prompt = prompt
            return "no diff"

    spy = _Spy()
    state = {
        "task": "fix add",
        "repo_path": repo,
        "changed_files": [],
        "verification_results": [],
        "reflection_notes": [],
    }
    make_diff_generation_hook()(state, RunContext(provider=spy))
    assert "calc.py" in spy.prompt
    assert "return a - b" in spy.prompt  # the actual buggy source is in the prompt
