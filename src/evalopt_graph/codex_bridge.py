"""Codex CLI bridge — Codex as a controlled, autonomous second agentic worker.

Posture (matches the user's policy and verified Codex docs, see CURRENT_DOCS_AUDIT.md):
* repo/worktree-bounded autonomy, no machine-wide access
* sandbox ``workspace-write`` for patches, ``read-only`` for review; **never** danger-full-access
  by default (``--dangerously-bypass-approvals-and-sandbox`` / yolo is gated behind an explicit
  ``full_access_allowed`` escalation)
* non-interactive ``codex exec`` (no ``--ask-for-approval`` flag in 0.142.3): the sandbox is the
  boundary; out-of-workspace writes & network simply **fail** (returned to the model)
* every invocation is logged (prompt, command, sandbox, approval, exit, summary, diff) under
  ``.evalopt/runs/<ts>/codex/``

Safety design:
* commands are built as **argv arrays** and run with ``shell=False`` — no string interpolation
* importing this module never invokes Codex; ``run_codex`` no-ops unless enabled AND on PATH
* Codex output is a **hypothesis**: deterministic gates remain the final authority
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any

# Verified against installed codex-cli 0.142.3 (codex exec --help)
SANDBOX_READ_ONLY = "read-only"
SANDBOX_WORKSPACE = "workspace-write"
SANDBOX_DANGER = "danger-full-access"
VALID_SANDBOXES = {SANDBOX_READ_ONLY, SANDBOX_WORKSPACE, SANDBOX_DANGER}
VALID_APPROVALS = {"untrusted", "on-request", "never"}  # 'on-failure' is deprecated upstream

MODES = {"off", "review", "patch", "adversarial", "auto"}

# Triggers that may invoke Codex (matched against config.invoke_on)
TRIGGER_FIRST_FAILURE = "after_first_failed_verification"
TRIGGER_BEFORE_FINAL = "before_final_pass"
TRIGGER_REPEATED = "repeated_failure"
TRIGGER_SECURITY = "security_sensitive_change"
TRIGGER_ARCH = "architecture_uncertainty"

_TEMPLATES = os.path.join(os.path.dirname(__file__), "templates")
_PROMPT_FILES = {
    "review": "codex_review_prompt.md",
    "patch": "codex_patch_prompt.md",
    "adversarial": "codex_adversarial_prompt.md",
    "final": "codex_final_review_prompt.md",
}


@dataclass
class CodexConfig:
    enabled: bool = False  # library default OFF for hermetic tests; config.yaml template enables it
    mode: str = "auto"
    invoke_on: list[str] = field(
        default_factory=lambda: [
            TRIGGER_FIRST_FAILURE,
            TRIGGER_BEFORE_FINAL,
            TRIGGER_REPEATED,
            TRIGGER_SECURITY,
            TRIGGER_ARCH,
        ]
    )
    sandbox: str = SANDBOX_WORKSPACE
    approval_policy: str = "never_for_repo_local_else_fail"
    prefer_worktree: bool = True
    max_codex_calls_per_run: int = 4
    max_codex_calls_per_iteration: int = 1
    full_access_allowed: bool = False
    log_prompts: bool = True
    log_outputs: bool = True
    require_diff_review_before_merge: bool = True
    model: str | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> CodexConfig:
        d = d or {}
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})

    def approval_flag(self) -> str:
        """Logical approval posture. `codex exec` is non-interactive (no prompts) so this is
        'never' in effect; we do not pass it as a CLI flag (exec rejects it). Recorded for logs."""
        return "never"


@dataclass
class CodexResult:
    label: str
    skipped: bool = False
    reason: str = ""
    cwd: str = ""
    sandbox: str = ""
    approval: str = ""
    exit_code: int | None = None
    summary: str = ""
    stdout_tail: str = ""
    stderr_tail: str = ""
    changed_files: list[str] = field(default_factory=list)
    diff_path: str = ""
    prompt_path: str = ""
    log_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def codex_available() -> bool:
    """True iff the `codex` CLI is on PATH. Never raises."""
    return shutil.which("codex") is not None


def codex_version() -> str:
    if not codex_available():
        return ""
    try:
        p = subprocess.run(["codex", "--version"], capture_output=True, text=True, timeout=20)
        return (p.stdout or p.stderr or "").strip()
    except Exception:
        return ""


# ------------------------------- command building (safe argv) -------------------------------


def build_codex_command(
    prompt: str,
    *,
    cwd: str,
    sandbox: str,
    approval: str = "never",
    output_last_message: str | None = None,
    json_events: bool = False,
    model: str | None = None,
    skip_git_check: bool = False,
    full_access_allowed: bool = False,
) -> list[str]:
    """Build a `codex exec` argv array. No shell, no interpolation.

    Raises ValueError on an invalid/unsafe combination (e.g. danger-full-access without explicit
    opt-in). The prompt is passed as the final positional argument.
    """
    if sandbox not in VALID_SANDBOXES:
        raise ValueError(f"invalid sandbox {sandbox!r}; use one of {sorted(VALID_SANDBOXES)}")
    if sandbox == SANDBOX_DANGER and not full_access_allowed:
        raise ValueError(
            "danger-full-access requires explicit full_access_allowed=True (high-risk escalation)"
        )
    if approval not in VALID_APPROVALS:
        raise ValueError(f"invalid approval {approval!r}; use one of {sorted(VALID_APPROVALS)}")

    # NOTE: `codex exec` (verified on codex-cli 0.142.3) is non-interactive and does NOT accept
    # `--ask-for-approval` (that flag belongs to the interactive `codex`). The sandbox flag IS the
    # boundary; failures (network / out-of-workspace) return to the model. We keep `approval` only
    # for validation/record-keeping and deliberately do not emit it. (See CURRENT_DOCS_AUDIT.md.)
    cmd = ["codex", "exec", "--cd", cwd, "--sandbox", sandbox]
    if output_last_message:
        cmd += ["--output-last-message", output_last_message]
    if json_events:
        cmd += ["--json"]
    if model:
        cmd += ["--model", model]
    if skip_git_check:
        cmd += ["--skip-git-repo-check"]
    cmd.append(prompt)  # positional PROMPT; argv array => safe
    return cmd


# ------------------------------- prompt rendering -------------------------------


def render_prompt(kind: str, context: dict[str, Any]) -> str:
    """Fill a Codex prompt template (``{{TOKEN}}`` placeholders). Falls back to a minimal prompt."""
    path = os.path.join(_TEMPLATES, _PROMPT_FILES.get(kind, ""))
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        text = (
            "# Codex {{KIND}} task\nTask: {{TASK}}\nQuality gates: {{GATES}}\n"
            "Current failures: {{FAILURES}}\nOperate ONLY inside this repo/worktree. Be concise. "
            "Do NOT weaken, skip, or delete tests."
        )
    for key, val in {"KIND": kind, **{k.upper(): v for k, v in context.items()}}.items():
        text = text.replace("{{" + key + "}}", str(val))
    return text


# ------------------------------- worktree isolation -------------------------------


def is_git_repo(path: str) -> bool:
    try:
        p = subprocess.run(
            ["git", "-C", path, "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        return p.returncode == 0 and p.stdout.strip() == "true"
    except Exception:
        return False


def is_clean_git(repo: str) -> bool:
    try:
        p = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"], capture_output=True, text=True, timeout=30
        )
        return p.returncode == 0 and not p.stdout.strip()
    except Exception:
        return False


def create_worktree(repo: str, run_id: str) -> str | None:
    """Create an isolated worktree at .evalopt/worktrees/codex-<run_id>/ (detached at HEAD)."""
    wt = os.path.join(repo, ".evalopt", "worktrees", f"codex-{run_id}")
    try:
        os.makedirs(os.path.dirname(wt), exist_ok=True)
        p = subprocess.run(
            ["git", "-C", repo, "worktree", "add", "--detach", wt, "HEAD"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return wt if p.returncode == 0 else None
    except Exception:
        return None


def worktree_diff(path: str) -> str:
    try:
        p = subprocess.run(["git", "-C", path, "diff"], capture_output=True, text=True, timeout=60)
        return p.stdout if p.returncode == 0 else ""
    except Exception:
        return ""


def changed_files(path: str) -> list[str]:
    try:
        p = subprocess.run(
            ["git", "-C", path, "status", "--porcelain"], capture_output=True, text=True, timeout=30
        )
        return [ln[3:].strip() for ln in p.stdout.splitlines() if ln.strip()] if p.returncode == 0 else []
    except Exception:
        return []


def cleanup_worktree(repo: str, path: str) -> bool:
    """Remove a Codex worktree. NOT called automatically unless the caller opts in."""
    try:
        p = subprocess.run(
            ["git", "-C", repo, "worktree", "remove", "--force", path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return p.returncode == 0
    except Exception:
        return False


# ------------------------------- decision logic -------------------------------


def budget_ok(state: dict[str, Any], config: CodexConfig) -> bool:
    total = int(state.get("codex_calls_total", 0))
    per_iter = int(state.get("codex_calls_this_iter", 0))
    return total < config.max_codex_calls_per_run and per_iter < config.max_codex_calls_per_iteration


def should_invoke(state: dict[str, Any], config: CodexConfig, trigger: str) -> bool:
    """Gate every Codex call: enabled + on PATH + trigger allowed + within budget."""
    if not config.enabled or config.mode == "off":
        return False
    if not codex_available():
        return False
    if trigger not in config.invoke_on:
        return False
    return budget_ok(state, config)


def resolve_action(trigger: str, config: CodexConfig) -> str:
    """Map a trigger to a Codex action (review|adversarial|patch|final). Honors a pinned mode."""
    if config.mode in ("review", "patch", "adversarial"):
        return config.mode
    # auto:
    return {
        TRIGGER_FIRST_FAILURE: "review",
        TRIGGER_REPEATED: "adversarial",
        TRIGGER_SECURITY: "adversarial",
        TRIGGER_ARCH: "review",
        TRIGGER_BEFORE_FINAL: "final",
    }.get(trigger, "review")


# ------------------------------- invocation -------------------------------


def run_codex(
    prompt: str,
    *,
    cwd: str,
    sandbox: str,
    config: CodexConfig,
    run_dir: str | None = None,
    label: str = "codex",
    timeout: int = 900,
    skip_git_check: bool = False,
) -> CodexResult:
    """Invoke Codex non-interactively. No-ops (skipped) unless enabled AND on PATH.

    Logs prompt/command/output/diff under ``<run_dir>/codex/``. Returns a structured CodexResult.
    Never raises on Codex failure — failures are captured and returned (Codex output is advisory).
    """
    res = CodexResult(label=label, cwd=cwd, sandbox=sandbox, approval=config.approval_flag())
    if not config.enabled or config.mode == "off":
        res.skipped, res.reason = True, "codex disabled"
        return res
    if not codex_available():
        res.skipped, res.reason = True, "codex not on PATH"
        return res
    if sandbox == SANDBOX_DANGER and not config.full_access_allowed:
        res.skipped, res.reason = True, "danger-full-access blocked (no full_access_allowed)"
        return res

    log_dir = os.path.join(run_dir, "codex") if run_dir else None
    last_msg = None
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        if config.log_prompts:
            res.prompt_path = os.path.join(log_dir, f"{label}.prompt.md")
            with open(res.prompt_path, "w", encoding="utf-8") as fh:
                fh.write(prompt)
        last_msg = os.path.join(log_dir, f"{label}.last.txt")

    try:
        cmd = build_codex_command(
            prompt,
            cwd=cwd,
            sandbox=sandbox,
            approval=config.approval_flag(),
            output_last_message=last_msg,
            model=config.model,
            skip_git_check=skip_git_check or not is_git_repo(cwd),  # exec needs a git repo otherwise
            full_access_allowed=config.full_access_allowed,
        )
    except ValueError as exc:
        res.skipped, res.reason = True, f"unsafe command blocked: {exc}"
        return res

    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        res.exit_code = proc.returncode
        res.stdout_tail = (proc.stdout or "")[-4000:]
        res.stderr_tail = (proc.stderr or "")[-2000:]
    except subprocess.TimeoutExpired:
        res.exit_code, res.reason = None, f"timeout after {timeout}s"
        return res
    except Exception as exc:  # pragma: no cover - defensive
        res.exit_code, res.reason = None, f"invocation error: {exc}"
        return res

    if last_msg and os.path.isfile(last_msg):
        try:
            res.summary = open(last_msg, encoding="utf-8").read().strip()[:4000]
        except Exception:
            pass
    if not res.summary:
        res.summary = res.stdout_tail[-1000:]

    res.changed_files = changed_files(cwd)
    if log_dir:
        diff = worktree_diff(cwd)
        if diff:
            res.diff_path = os.path.join(log_dir, f"{label}.diff")
            with open(res.diff_path, "w", encoding="utf-8") as fh:
                fh.write(diff)
        if config.log_outputs:
            import json

            res.log_path = os.path.join(log_dir, f"{label}.json")
            with open(res.log_path, "w", encoding="utf-8") as fh:
                json.dump({"command": cmd, **res.to_dict()}, fh, indent=2, default=str)
    return res
