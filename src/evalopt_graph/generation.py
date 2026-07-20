"""Standalone-runner code editing: turn a provider's textual unified diff into applied file changes.

Pure stdlib + git. The loop calls this via an injected ``generation_hook`` so ``node_generation`` stops
being a no-op. Nothing here decides PASS — the deterministic gates still do; this only makes edits.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .graph import RunContext

_FENCE_RE = re.compile(r"```(?:diff|patch)?\s*\n(.*?)```", re.DOTALL)
_DIFF_START_RE = re.compile(r"(?m)^(diff --git |--- )")
_SOURCE_EXT = (".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".rb", ".c", ".h", ".cpp")
_SKIP_DIRS = frozenset({".git", ".evalopt", "__pycache__", ".venv", "venv", "node_modules", ".ruff_cache"})

_SYSTEM = (
    "You are the generator in an evaluator-optimizer loop. You are shown the task, the current repo "
    "files, and the failing gates. Output ONLY a unified diff (```diff fenced, git-apply-able with "
    "a/ and b/ prefixes) that makes the failing gates pass. Do not weaken, delete, or skip tests. "
    "If you cannot produce a diff, say so plainly."
)


def _repo_context(repo_path: str, *, max_bytes: int = 12000) -> str:
    """A bounded snapshot of the repo's source files so a real model can localize and edit. Naive
    (no smart localization) — fine for small repos/benchmarks; large repos need a real ACI (documented
    limitation). Skips VCS/build dirs and non-source files; stops at ``max_bytes``."""
    parts: list[str] = []
    total = 0
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
        for fn in sorted(files):
            if not fn.endswith(_SOURCE_EXT):
                continue
            rel = os.path.relpath(os.path.join(root, fn), repo_path)
            try:
                content = open(os.path.join(root, fn), encoding="utf-8").read()
            except Exception:
                continue
            block = f"\n=== FILE: {rel} ===\n{content}"
            if total + len(block) > max_bytes:
                parts.append(f"\n=== FILE: {rel} === (omitted — context size budget reached)")
                return "".join(parts)
            parts.append(block)
            total += len(block)
    return "".join(parts)


def apply_unified_diff(repo_path: str, diff_text: str) -> tuple[bool, list[str]]:
    """Apply a unified diff to a git repo. Returns ``(applied_ok, changed_files)``; never raises.

    Uses ``git apply`` (tolerant flags) so context/whitespace drift does not hard-fail a good patch.
    Changed files are read back from ``git diff --name-only`` after applying.
    """
    if not diff_text or not diff_text.strip():
        return False, []
    try:
        proc = subprocess.run(
            ["git", "-C", repo_path, "apply", "--recount", "--whitespace=nowarn", "-"],
            input=diff_text,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except Exception:
        return False, []
    if proc.returncode != 0:
        return False, []
    try:
        names = subprocess.run(
            ["git", "-C", repo_path, "diff", "--name-only"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return True, []
    changed = [ln.strip() for ln in (names.stdout or "").splitlines() if ln.strip()]
    return True, changed


def extract_unified_diff(text: str) -> str:
    """Extract a unified diff body from a model response: prefer a fenced ```diff block, else the
    first region starting at ``diff --git``/``--- ``. Returns '' when no diff is present."""
    if not text:
        return ""
    for m in _FENCE_RE.finditer(text):
        body = m.group(1)
        if _DIFF_START_RE.search(body):
            return body.strip("\n") + "\n"
    m = _DIFF_START_RE.search(text)
    if m:
        return text[m.start() :].strip("\n") + "\n"
    return ""


def _failing(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        r
        for r in state.get("verification_results", [])
        if str(r.get("result", "")).upper() in ("FAIL", "ERROR")
    ]


def make_diff_generation_hook() -> Callable[[dict[str, Any], RunContext], list[str]]:
    """Build a ``generation_hook`` that asks ``ctx.provider`` for a unified diff and applies it.

    The real code-editing worker for the standalone runner. Deterministic gates still decide PASS;
    this only proposes+applies edits. Never raises; returns the list of changed repo-relative files.
    """

    def hook(state: dict[str, Any], ctx: RunContext) -> list[str]:
        prompt = (
            f"TASK:\n{state.get('task', '')}\n\n"
            f"REPO FILES:{_repo_context(state['repo_path'])}\n\n"
            f"FAILING GATES:\n{_failing(state)}\n\n"
            f"PRIOR REFLECTIONS:\n{state.get('reflection_notes', [])}\n"
        )
        raw = ctx.provider.complete(_SYSTEM, prompt, tag="generate")
        diff = extract_unified_diff(raw or "")
        if not diff:
            state.setdefault("reflection_notes", []).append("generation: no diff produced by provider")
            return []
        ok, changed = apply_unified_diff(state["repo_path"], diff)
        if not ok:
            state.setdefault("reflection_notes", []).append("generation: diff did not apply")
            return []
        return changed

    return hook
