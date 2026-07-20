"""Deterministic verification: run gate commands and capture exact results.

``run_gates`` accepts an injectable ``runner`` so tests (and offline smoke runs) can simulate
command outcomes without spawning real subprocesses.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any

# gate name -> key in profile["commands"]
GATE_TO_CMD_KEY = {"tests": "test", "lint": "lint", "typecheck": "typecheck", "build": "build"}

# --- anti-gaming: deterministic test-weakening detection -----------------------------------
_TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(_test\.|\.test\.|(^|/)test_)", re.I)
_SKIP_RE = re.compile(
    r"@?\b(pytest\.mark\.skip|pytest\.mark\.xfail|unittest\.skip|skipif|xfail)\b"
    r"|\.(skip|todo)\s*\("  # it.skip( / describe.skip( / test.skip(
    r"|\bpytest\.skip\s*\("
    r"|\bt\.Skip\s*\("  # Go
    r"|#\s*(disabled|skip)\b",
    re.I,
)
_ASSERT_RE = re.compile(
    r"\b(assert|assertEqual|assertTrue|assertFalse|assertRaises|expect\(|\.should\b"
    r"|require\.|t\.Error|t\.Fatal)\b"
)
_TESTDEF_RE = re.compile(r"\b(def test_|func Test|it\s*\(|describe\s*\(|test\s*\()")


@dataclass
class CommandResult:
    gate: str
    command: str
    exit_code: int | None
    result: str  # PASS | FAIL | NOT_CONFIGURED | ERROR
    summary: str
    stdout: str = ""
    stderr: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Runner = Callable[[str, str, str], CommandResult]


def run_command(gate: str, command: str, cwd: str, timeout: int = 1800) -> CommandResult:
    """Execute one gate command, capturing stdout/stderr/exit code. Never raises on failure."""
    try:
        proc = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return CommandResult(gate, command, None, "ERROR", f"timeout after {timeout}s")
    except Exception as exc:  # pragma: no cover - defensive
        return CommandResult(gate, command, None, "ERROR", f"could not run: {exc}")

    out, err = proc.stdout or "", proc.stderr or ""
    ok = proc.returncode == 0
    summary = _summarize(out, err, ok)
    return CommandResult(
        gate=gate,
        command=command,
        exit_code=proc.returncode,
        result="PASS" if ok else "FAIL",
        summary=summary,
        stdout=out[-8000:],
        stderr=err[-8000:],
    )


def _summarize(out: str, err: str, ok: bool) -> str:
    tail = (err or out or "").strip().splitlines()
    if ok:
        return tail[-1][:200] if tail else "passed"
    for line in reversed(tail):  # surface the most decisive-looking line
        low = line.lower()
        if any(k in low for k in ("error", "failed", "assert", "exception", "fail")):
            return line.strip()[:200]
    return tail[-1][:200] if tail else "failed"


def run_gates(
    profile: dict[str, Any],
    cwd: str,
    *,
    required_gates: list[str] | None = None,
    runner: Runner = run_command,
) -> list[CommandResult]:
    """Run each required gate that has a configured command. Skip unconfigured gates."""
    cmds = profile.get("commands") or {}
    gates = required_gates or ["tests", "lint", "typecheck", "build"]
    results: list[CommandResult] = []
    for gate in gates:
        command = cmds.get(GATE_TO_CMD_KEY.get(gate, gate))
        if not command:
            results.append(CommandResult(gate, "", None, "NOT_CONFIGURED", "no command configured"))
            continue
        results.append(runner(gate, command, cwd))
    return results


def failing_gates(results: list[CommandResult]) -> list[str]:
    return [r.gate for r in results if r.result in ("FAIL", "ERROR")]


def all_required_pass(results: list[CommandResult], required_gates: list[str]) -> bool:
    """True iff every required gate that is configured passed (NOT_CONFIGURED is tolerated)."""
    by_gate = {r.gate: r for r in results}
    for gate in required_gates:
        r = by_gate.get(gate)
        if r is None:
            continue
        if r.result in ("FAIL", "ERROR"):
            return False
    return True


def safe_quote(command: str) -> str:  # convenience for logging
    try:
        return " ".join(shlex.quote(p) for p in shlex.split(command))
    except Exception:
        return command


# --- diff scoping (read-only git) -----------------------------------------------------------


def _git(repo_path: str, *args: str, timeout: int = 30) -> tuple[int, str]:
    try:
        p = subprocess.run(["git", "-C", repo_path, *args], capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except Exception:
        return 1, ""


def is_git_repo(repo_path: str) -> bool:
    code, out = _git(repo_path, "rev-parse", "--is-inside-work-tree")
    return code == 0 and out.strip() == "true"


def is_github_repo(repo_path: str) -> bool:
    """True if the repo has a github.com remote or a .github directory (best-effort, read-only)."""
    code, out = _git(repo_path, "remote", "-v")
    if code == 0 and "github.com" in out.lower():
        return True
    return os.path.isdir(os.path.join(repo_path, ".github"))


def resolve_diff_base(repo_path: str, configured: str | None = "auto") -> str | None:
    """Resolve the base to diff against. Returns a commit-ish (merge-base SHA / ref) or ``None``.

    ``configured`` other than 'auto'/None is returned verbatim (e.g. 'origin/main'). 'auto' probes
    common upstream refs and returns the merge-base with the first that exists; ``None`` if the repo
    is not git or no upstream is found (caller then falls back to the working-tree diff).
    """
    if not is_git_repo(repo_path):
        return None
    if configured and str(configured).lower() != "auto":
        return str(configured)
    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        code, _ = _git(repo_path, "rev-parse", "--verify", "--quiet", ref)
        if code == 0:
            mb_code, mb = _git(repo_path, "merge-base", "HEAD", ref)
            if mb_code == 0 and mb.strip():
                return mb.strip()
    return None


def git_changed_files(repo_path: str, base: str | None = None) -> list[str]:
    """Read-only list of repo-relative changed files (ACMR). Empty when not a git repo.

    Includes committed changes since ``base`` (three-dot, vs the merge-base) plus uncommitted
    working-tree and staged changes, so the router sees what the loop has changed so far.
    """
    if not is_git_repo(repo_path):
        return []
    files: set[str] = set()
    ranges = [
        ["diff", "--name-only", "--diff-filter=ACMR"],
        ["diff", "--name-only", "--diff-filter=ACMR", "--cached"],
    ]
    if base:
        ranges.append(["diff", "--name-only", "--diff-filter=ACMR", f"{base}...HEAD"])
    for args in ranges:
        code, out = _git(repo_path, *args)
        if code == 0:
            files.update(ln.strip() for ln in out.splitlines() if ln.strip())
    return sorted(files)


# --- optional-gate execution (safe argv, shell=False) ---------------------------------------


def run_command_argv(gate: str, argv: list[str], cwd: str, timeout: int = 600) -> CommandResult:
    """Execute one optional gate as an argv array (``shell=False`` — no string interpolation).

    Mirrors :func:`run_command` semantics (PASS on exit 0, FAIL otherwise, ERROR on failure to run)
    but is safe to feed untrusted file paths because nothing is passed through a shell.
    """
    printable = safe_quote_argv(argv)
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return CommandResult(gate, printable, None, "ERROR", f"binary not found: {argv[0] if argv else '?'}")
    except subprocess.TimeoutExpired:
        return CommandResult(gate, printable, None, "ERROR", f"timeout after {timeout}s")
    except Exception as exc:  # pragma: no cover - defensive
        return CommandResult(gate, printable, None, "ERROR", f"could not run: {exc}")
    out, err = proc.stdout or "", proc.stderr or ""
    ok = proc.returncode == 0
    return CommandResult(
        gate=gate,
        command=printable,
        exit_code=proc.returncode,
        result="PASS" if ok else "FAIL",
        summary=_summarize(out, err, ok),
        stdout=out[-8000:],
        stderr=err[-8000:],
    )


def safe_quote_argv(argv: Iterable[str]) -> str:
    return " ".join(shlex.quote(str(p)) for p in argv)


def _spec_attr(spec: Any, name: str, default: Any = None) -> Any:
    if isinstance(spec, dict):
        return spec.get(name, default)
    return getattr(spec, name, default)


def run_optional_gates(
    gate_specs: Iterable[Any],
    cwd: str,
    *,
    runner_argv: Callable[[str, list[str], str], CommandResult] = run_command_argv,
) -> list[CommandResult]:
    """Run each selected, available optional gate (argv-based). Unavailable binaries are skipped
    (recorded as NOT_CONFIGURED, never failing the loop). Accepts GateSpec objects or plain dicts."""
    results: list[CommandResult] = []
    for spec in gate_specs:
        name = _spec_attr(spec, "name", "optional")
        argv = list(_spec_attr(spec, "argv", []) or [])
        available = bool(_spec_attr(spec, "available", True))
        if not argv or not available:
            results.append(
                CommandResult(name, "", None, "NOT_CONFIGURED", "binary not on PATH; gate skipped")
            )
            continue
        results.append(runner_argv(name, argv, cwd))
    return results


def _git_diff(repo_path: str) -> str:
    """Read-only unified diff (worktree + staged) of the repo, or '' if not a git repo."""
    chunks: list[str] = []
    for extra in (["--unified=0"], ["--cached", "--unified=0"]):
        try:
            p = subprocess.run(
                ["git", "-C", repo_path, "diff", *extra],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if p.returncode == 0:
                chunks.append(p.stdout)
        except Exception:
            return ""
    return "\n".join(chunks)


def detect_test_weakening(
    repo_path: str, *, get_diff: Callable[[str], str] | None = None
) -> tuple[bool, list[str]]:
    """Deterministically detect tests being weakened to pass (anti-gaming).

    Inspects the diff of files that look like tests for: newly-added skip/xfail markers, deleted
    test definitions, or a net removal of assertions. Read-only; returns ``(weakened, evidence)``.
    ``get_diff`` is injectable for testing; the default uses ``git diff``. Returns ``(False, [])``
    when there is no diff or no git.
    """
    diff = (get_diff or _git_diff)(repo_path)
    if not diff.strip():
        return False, []

    evidence: list[str] = []
    cur_file: str | None = None
    in_test = False
    added_assert = removed_assert = skip_added = deleted_tests = 0

    for line in diff.splitlines():
        if line.startswith("+++ "):
            cur_file = re.sub(r"^[abciwo]/", "", line[4:].strip())  # a/ b/ + git mnemonic i/w/c/o
            in_test = bool(_TEST_PATH_RE.search(cur_file or ""))
            continue
        if not in_test or line.startswith(("+++", "---")):
            continue
        if line.startswith("+"):
            body = line[1:]
            if _SKIP_RE.search(body):
                skip_added += 1
                evidence.append(f"added skip/xfail in {cur_file}: {body.strip()[:80]}")
            if _ASSERT_RE.search(body):
                added_assert += 1
        elif line.startswith("-"):
            body = line[1:]
            if _ASSERT_RE.search(body):
                removed_assert += 1
            if _TESTDEF_RE.search(body):
                deleted_tests += 1

    net_removed = removed_assert - added_assert
    if deleted_tests:
        evidence.append(f"removed {deleted_tests} test definition(s)")
    if net_removed > 0:
        evidence.append(f"net removed {net_removed} assertion(s) from tests")
    weakened = skip_added > 0 or deleted_tests > 0 or net_removed > 0
    return weakened, evidence
