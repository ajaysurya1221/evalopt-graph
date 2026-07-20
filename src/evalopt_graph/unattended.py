"""Unattended Autonomy Governor — make safe decisions instead of waiting for a human at 1 AM.

Core policy: human input is NOT the default control mechanism in unattended mode. Safe repo-local
decisions are made autonomously; ambiguous-but-reversible decisions take the safest reversible
default (logged); destructive / global / credentialed / remote-mutating actions are **deferred**
(recorded as blocked decisions with a non-destructive fallback) and the loop continues other safe
work — stopping only when every remaining useful path requires a blocked action.

Pure stdlib; deterministic; no network. The graph wires these decisions in; this module decides.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import epistemic

# --- action classes -------------------------------------------------------------------------
SAFE_REPO_LOCAL = "safe_repo_local"
REVERSIBLE = "reversible"
DESTRUCTIVE = "destructive"
CREDENTIALED = "credentialed"
REMOTE_MUTATION = "remote_mutation"
GLOBAL_STATE = "global_state"

# action classes that must be DEFERRED (never waited on) in unattended mode
DEFER_CLASSES = frozenset({DESTRUCTIVE, CREDENTIALED, REMOTE_MUTATION, GLOBAL_STATE})

# gh api is a mutation unless provably GET: -X/--method non-GET, any -f/-F/--field (implicit POST), or a
# graphql mutation body (keying only on -X — the old rule — let --method/-f/graphql slip through). This
# fragment is defined ONCE so the governor (_REMOTE_RE) and the permission classifier
# (permissions._GH_API_MUTATE_RE / _GH_API_GET_RE) can never drift out of sync.
GH_API_MUTATION_FRAGMENT = r"(?:(?:-X|--method)\s*(?:POST|PUT|PATCH|DELETE)|\s-[fF]\b|--field|--raw-field|--input\b|graphql[^\n]*mutation)"

_REMOTE_RE = re.compile(
    r"\bgit\s+push\b|\bgit\s+push\s+--force\b|--force-with-lease\b|\bgh\s+pr\s+(create|merge|close)\b"
    r"|\bgh\s+release\s+create\b|\bgh\s+workflow\s+run\b"
    r"|\bgh\s+api\b.*" + GH_API_MUTATION_FRAGMENT,
    re.I,
)
_DESTRUCTIVE_RE = re.compile(
    r"\brm\s+-rf\b|\brm\s+-fr\b|\bgit\s+reset\s+--hard\b|\bgit\s+clean\b|\bDROP\s+TABLE\b|\bTRUNCATE\b"
    r"|\bDROP\s+DATABASE\b|\bdestructive\s+migration\b|\bmass\s+deletion\b|\bdd\s+if="
    # `find` with a mutating/exec action = mass deletion or arbitrary exec (find itself is on the safe
    # read allowlist for `find -name`, so this danger check must run first).
    r"|\bfind\b[^|;&\n]*\s-(?:delete|exec|execdir|ok|okdir|fprint|fprintf|fls)\b|\bshred\b|\bmkfs\b",
    re.I,
)
_GLOBAL_RE = re.compile(
    r"\bnpm\s+i(nstall)?\s+-g\b|\bnpm\s+install\s+--global\b|\bpip\s+install\b(?!.*-r)|\bbrew\s+install\b"
    r"|\bpnpm\s+add\s+-g\b|\bcargo\s+install\b|\bgo\s+install\b|/etc/"
    # shell-init / login files are persistence vectors; match ~/, $HOME, and absolute home forms + zshenv
    r"|(?:~|\$HOME|/Users/[^/\s]+|/home/[^/\s]+)/\.(?:zshrc|zshenv|zprofile|zlogin|zlogout|bashrc|bash_profile|bash_login|bash_logout|profile|inputrc)\b"
    r"|/\.ssh/authorized_keys\b|\bcrontab\s+-|/Library/Launch(?:Agents|Daemons)/"
    r"|\bsudo\b|\bdefaults\s+write\b",
    re.I,
)
_CRED_RE = re.compile(
    r"\bAKIA[0-9A-Z]{12,}\b|\bsk-[A-Za-z0-9]{20,}\b|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b(api[_-]?key|secret|token|password|passwd|credential)\s*[:=]\s*['\"]?[^'\"\s]{6,}"
    r"|production\s+credential|prod\s+db\s+password",
    re.I,
)

# Shell command boundary: start of string, or right after a control operator / substitution opener.
# Used so a network/exfil or nested-exec binary is only matched when it is actually *invoked* as a
# command (avoids false positives on file names like ``nc.txt`` or prose that mentions ``ssh``).
_CMD_BOUNDARY = r"(?:^|[|&;`(\n]|\|\||&&|\$\()\s*"

# Network / exfiltration binaries invoked as a command (curl/wget/nc/ssh/scp/rsync/...). These are
# NOT in the safe allowlist; in an unattended run they can smuggle data out or pull code in.
NETWORK_CMD_RE = re.compile(
    _CMD_BOUNDARY + r"(?:curl|wget|nc|ncat|netcat|socat|telnet|ftp|tftp|scp|sftp|rsync|ssh)\b"
    r"|\bopenssl\s+s_client\b|/dev/(?:tcp|udp)/",  # /dev/tcp|udp = bash socket exfil via redirect
    re.I,
)
# Nested / inline shell execution: a shell run with -c, a pipe INTO a shell (``curl … | sh``), or an
# inline script evaluator (``python -c`` / ``node -e`` / ``ruby -e`` …). Opaque to static analysis →
# treated as unsafe in unattended mode. NB: ``python -m pytest`` (no -c/-e) stays safe.
NESTED_EXEC_CMD_RE = re.compile(
    _CMD_BOUNDARY + r"(?:bash|sh|zsh|dash|ksh|fish)\s+-c\b"
    r"|\|\s*(?:bash|sh|zsh|dash|ksh|fish)\b"
    r"|" + _CMD_BOUNDARY + r"(?:python[0-9.]*|node|nodejs|ruby|perl|php)\s+-(?:c|e)\b",
    re.I,
)


def classify_action(text: str) -> str:
    """Classify a proposed action's risk. Order matters: remote/destructive/global/credentialed,
    network-exfil and nested-shell exec are all deferrable; everything else is safe repo-local."""
    t = text or ""
    if _REMOTE_RE.search(t):
        return REMOTE_MUTATION
    if _DESTRUCTIVE_RE.search(t):
        return DESTRUCTIVE
    if _GLOBAL_RE.search(t):
        return GLOBAL_STATE
    if _CRED_RE.search(t):
        return CREDENTIALED
    if NETWORK_CMD_RE.search(t):
        return REMOTE_MUTATION  # network/exfiltration → treat like a remote mutation (defer)
    if NESTED_EXEC_CMD_RE.search(t):
        return GLOBAL_STATE  # nested/inline shell execution is unbounded → defer
    return SAFE_REPO_LOCAL


def is_deferrable(action_class: str) -> bool:
    return action_class in DEFER_CLASSES


# --- config ---------------------------------------------------------------------------------
DEFAULT_UNATTENDED_CONFIG: dict[str, Any] = {
    "enabled": False,
    "autonomy_level": "high",
    "max_wall_clock_hours": 8,
    "max_iters": 12,
    "max_research_rounds": 6,
    "max_codex_calls_per_run": 8,
    "max_tool_calls_per_round": 40,
    "never_wait_for_human_input": True,
    "destructive_actions": "defer_and_continue",
    "credentialed_actions": "defer_and_continue",
    "remote_mutations": "defer_and_continue",
    "global_state_changes": "defer_and_continue",
    "reversible_repo_local_actions": "auto_decide",
    "ambiguous_safe_choices": "choose_conservative_default",
    "if_all_paths_blocked": "stop_with_morning_report",
    "write_morning_report": True,
    "keep_mac_awake_hint": True,
}


def unattended_config(state_cfg: dict[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_UNATTENDED_CONFIG)
    out.update(state_cfg or {})
    return out


def is_unattended(cfg: dict[str, Any]) -> bool:
    return bool((cfg or {}).get("enabled", False))


# --- records --------------------------------------------------------------------------------
@dataclass
class Decision:
    id: str
    kind: str
    question: str
    choice: str
    rationale: str
    reversible: bool = True
    deferred: bool = False
    action_class: str = SAFE_REPO_LOCAL
    fallback: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BlockedDecision:
    id: str
    action: str
    action_class: str
    reason: str
    fallback: str = ""
    branch: str = "main"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParkedBranch:
    id: str
    reason: str
    last_evidence: str = ""
    next_human_action: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def render_morning_report(state: dict[str, Any]) -> str:
    """A wake-up-ready summary: what was done, what passed/failed, what was safely deferred, and the
    exact command to continue. Pulls everything from the final state."""
    adj = state.get("adjudication", {}) or {}
    gates = [(r.get("gate"), r.get("result")) for r in state.get("verification_results", []) or []]
    blocked = state.get("blocked_decisions", []) or []
    parked = state.get("parked_branches", []) or []
    decisions = state.get("decisions", []) or []
    changed = state.get("changed_files", []) or []
    repro = [c.get("command") for c in state.get("command_history", []) or [] if c.get("command")][:8]
    stop = str(state.get("stop_reason"))
    safe_to_commit = (
        stop in ("pass", "pass_with_warnings") and not blocked and not state.get("tests_weakened")
    )
    next_cmd = (
        f'/eval-opt "{state.get("task", "")}" mode={state.get("mode", "build")} unattended=true'
        if stop not in ("pass", "research_synthesis")
        else "review the diff and commit if it looks right"
    )
    lines = [
        "# eval-opt — Morning Report",
        "",
        f"- Started: {state.get('started_at') or '(n/a)'}",
        f"- Mode: {state.get('mode')} | class: {state.get('task_class')} | research backend: {state.get('research_backend') or 'n/a'}",
        f"- Outcome (stop_reason): **{stop}**",
        f"- Iterations: {state.get('iteration')}/{state.get('max_iterations')}"
        + (
            f" | research rounds: {state.get('research_round')}/{state.get('max_research_rounds')}"
            if state.get("mode") == "research"
            else ""
        ),
        f"- Codex calls: {state.get('codex_calls_total', 0)}",
        "",
        "## What was done / gates",
        f"- Gates: {gates or '(none)'}",
        f"- Files changed: {changed[:30] or '(none)'}",
        f"- Confirmed facts: {len(adj.get('confirmed_facts', []))} · assumptions: {len(adj.get('assumptions', []))} "
        f"· unresolved contradictions: {len(adj.get('unresolved_contradictions', []))}",
        "",
        "## Autonomous decisions",
        *(
            [f"- [{d.get('kind')}] {d.get('choice')} — {d.get('rationale')}" for d in decisions]
            or ["- (none)"]
        ),
        "",
        "## Blocked decisions (need human approval — NOT done)",
        *(
            [
                f"- [{b.get('action_class')}] {b.get('action')} — {b.get('reason')}; fallback: {b.get('fallback') or 'none'}"
                for b in blocked
            ]
            or ["- (none)"]
        ),
        "",
        "## Parked branches",
        *(
            [
                f"- {p.get('id')}: {p.get('reason')} (next: {p.get('next_human_action') or 'n/a'})"
                for p in parked
            ]
            or ["- (none)"]
        ),
        "",
        "## Reproduce / continue",
        "- Repro commands:",
        *([f"    {c}" for c in repro] or ["    (none)"]),
        f"- Next command: `{next_cmd}`",
        f"- Safe to commit: **{'yes' if safe_to_commit else 'no — review blocked items first'}**",
    ]
    return "\n".join(lines) + "\n"


# --- the decision matrix --------------------------------------------------------------------
# Each entry returns (choice, rationale, reversible, deferred, action_class, fallback).
def decide(kind: str, context: dict[str, Any] | None = None, *, now: str = "") -> Decision:
    """Make an autonomous decision for a known decision ``kind``. Deferrable kinds return a
    ``deferred`` decision carrying a non-destructive fallback instead of waiting for a human."""
    ctx = context or {}
    did = f"d-{kind}"
    table = {
        "package_manager": lambda: (
            ctx.get("pinned") or ctx.get("lockfile_manager") or "npm",
            "use the packageManager field / lockfile-pinned manager; do not ask",
            True,
            False,
            SAFE_REPO_LOCAL,
            "",
        ),
        "library_choice": lambda: (
            ctx.get("existing_dep") or "standard-library/native",
            "prefer an existing project dependency; else minimal stdlib/native; new dep only after docs verification (logged)",
            True,
            False,
            SAFE_REPO_LOCAL,
            "",
        ),
        "missing_tests": lambda: (
            "create focused tests"
            if ctx.get("has_test_framework")
            else "create smallest conventional test setup (reversible)",
            "add focused tests with the existing framework; only scaffold a framework if reversible and repo-local",
            True,
            False,
            SAFE_REPO_LOCAL,
            "",
        ),
        "env_var": lambda: (
            "add .env.example entry + test with dummy value",
            "never request a real secret; use .env.example + a dummy value",
            True,
            False,
            SAFE_REPO_LOCAL,
            "",
        ),
        "database": lambda: (
            "use a local test container or mock/fake",
            "never request production credentials; use a local/mock DB",
            True,
            False,
            SAFE_REPO_LOCAL,
            "",
        ),
        "migration": lambda: (
            "create non-destructive migration file",
            "write a non-destructive migration following framework convention; do NOT run a destructive migration",
            True,
            False,
            SAFE_REPO_LOCAL,
            "write migration file only; defer applying destructive changes",
        ),
        "remote_ci": lambda: (
            "use gh read-only",
            "read CI/PR state via gh read-only; never mutate remote state",
            True,
            False,
            SAFE_REPO_LOCAL,
            "",
        ),
        "push_or_pr": lambda: (
            "DEFER",
            "pushing/PR/merge mutates remote state — defer and record a blocked decision",
            False,
            True,
            REMOTE_MUTATION,
            "leave commits local; record the exact push/PR command for the human",
        ),
        "destructive_cleanup": lambda: (
            "quarantine instead of delete",
            "prefer git worktree / backup / rename / quarantine folder over deletion",
            True,
            False,
            SAFE_REPO_LOCAL,
            "move to .evalopt/quarantine/ instead of rm",
        ),
        "unsupported_risky": lambda: (
            "DEFER",
            "risky/unsupported operation — record blocked decision and continue a safe alternative",
            False,
            True,
            DESTRUCTIVE,
            "continue an alternative safe branch; record the blocked action",
        ),
    }
    if kind not in table:
        choice, rationale, reversible, deferred, acls, fb = (
            "choose_conservative_default",
            "unknown decision kind — take the safest reversible default and log it",
            True,
            False,
            REVERSIBLE,
            "",
        )
    else:
        choice, rationale, reversible, deferred, acls, fb = table[kind]()
    return Decision(
        id=did,
        kind=kind,
        question=str(ctx.get("question", kind)),
        choice=choice,
        rationale=rationale,
        reversible=reversible,
        deferred=deferred,
        action_class=acls,
        fallback=fb,
        created_at=now,
    )


def evaluate_action(action: str, *, now: str = "") -> tuple[bool, str, str, str]:
    """For a free-text proposed action, return (deferred, action_class, reason, fallback)."""
    acls = classify_action(action)
    if is_deferrable(acls):
        fb = {
            REMOTE_MUTATION: "keep work local; record the exact command for the human",
            DESTRUCTIVE: "use a reversible alternative (worktree/backup/quarantine) or skip",
            GLOBAL_STATE: "scope to the project (local install / .env / repo config) instead of global",
            CREDENTIALED: "use .env.example + dummy value; never embed a real secret",
        }[acls]
        return True, acls, f"{acls} action is deferred in unattended mode (never waited on)", fb
    return False, acls, "safe repo-local action — auto-decided", ""


def pop_parked(state: dict[str, Any], branch_id: str) -> dict[str, Any] | None:
    """Resume a parked branch: remove it from ``state['parked_branches']`` and return it (with the
    reason / last_evidence / next_human_action needed to continue). Returns None if not found."""
    parked = state.get("parked_branches", []) or []
    for i, p in enumerate(parked):
        if p.get("id") == branch_id:
            return parked.pop(i)
    return None


def wall_clock_exceeded(started_at: str, now: str, max_hours: float) -> bool:
    start = epistemic._parse_iso(started_at)
    cur = epistemic._parse_iso(now)
    if start is None or cur is None or not max_hours:
        return False
    return (cur - start).total_seconds() > float(max_hours) * 3600.0


def elapsed_hours(started_at: str, now: str) -> float:
    start = epistemic._parse_iso(started_at)
    cur = epistemic._parse_iso(now)
    if start is None or cur is None:
        return 0.0
    return round((cur - start).total_seconds() / 3600.0, 3)


@dataclass
class OvernightLog:
    """Accumulates the autonomous decisions / blocks / parked branches for the morning report."""

    decisions: list[dict[str, Any]] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    parked: list[dict[str, Any]] = field(default_factory=list)

    def record_decision(self, d: Decision) -> None:
        self.decisions.append(d.to_dict())

    def record_blocked(self, b: BlockedDecision) -> None:
        self.blocked.append(b.to_dict())

    def record_parked(self, p: ParkedBranch) -> None:
        self.parked.append(p.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
