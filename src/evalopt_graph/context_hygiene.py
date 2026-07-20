"""Context Hygiene — keep long autonomous runs from rotting their own context.

Raw logs live on disk; prompts get a compact **retrieval pack** rebuilt from the ledgers before
each major patch. Command output is summarized (exit code + first/last relevant error + repro +
artifact path). Repeated errors dedupe by fingerprint. Noise is detected and logged. A lightweight,
secret-free cache accelerates repeated doc/API lookups and remembers rejected hallucinations — but
the cache is retrieval acceleration only and never confirms a claim.

ReAct instrumentation emits a PUBLIC trace event per node (no private chain-of-thought).
Pure stdlib; deterministic; no network.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import epistemic
from .claim_ledger import ClaimLedger

# things that must NEVER be summarized away (kept verbatim in the retrieval pack)
PROTECTED = (
    "user requirements",
    "acceptance criteria",
    "destructive-action blocks",
    "security findings",
    "central claims + evidence",
    "exact repro commands",
    "final diff summary",
)

_DIGIT_RE = re.compile(r"\d+")
_PATH_RE = re.compile(r"(/[\w.\-/]+)+")
_HEX_RE = re.compile(r"0x[0-9a-fA-F]+")
_ERROR_LINE_RE = re.compile(
    r"(error|exception|assert|failed|fail|traceback|panic|fatal|cannot|undefined|not found)", re.I
)
_SECRET_RE = re.compile(
    r"AKIA[0-9A-Z]{12,}|sk-[A-Za-z0-9]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|(api[_-]?key|secret|token|password)\s*[:=]\s*\S{6,}",
    re.I,
)


def _redact(text: str) -> str:
    return _SECRET_RE.sub("«redacted»", text or "")


# ============================== command-output summarization ==============================


def summarize_command_output(result: dict[str, Any], *, log_path: str = "") -> dict[str, Any]:
    """Compress a gate/command result into a bounded summary; keep the full log by REFERENCE.

    Returns: exit_code, result, failing_target, first_error, last_error, repro, log_path, summary.
    """
    out = (result.get("stdout") or "") + "\n" + (result.get("stderr") or "")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    err_lines = [ln for ln in lines if _ERROR_LINE_RE.search(ln)]
    first_error = _redact(err_lines[0].strip()[:240]) if err_lines else ""
    last_error = _redact(err_lines[-1].strip()[:240]) if err_lines else ""
    failing = _extract_failing_target(out)
    return {
        "gate": result.get("gate", ""),
        "exit_code": result.get("exit_code"),
        "result": result.get("result", ""),
        "failing_target": failing,
        "first_error": first_error,
        "last_error": last_error,
        "repro": _redact(result.get("command", "")),
        "log_path": log_path,  # full log kept on disk, not in the prompt
        "summary": _redact(result.get("summary", ""))[:240],
    }


def _extract_failing_target(out: str) -> str:
    # pytest: tests/test_x.py::test_y ; file:line ; "FAILED tests/..."
    for pat in (
        r"FAILED\s+(\S+)",
        r"([\w./\-]+\.py::[\w\[\]\-]+)",
        r"([\w./\-]+:\d+:\d+)",
        r"(at\s+[\w./\-]+:\d+)",
    ):
        m = re.search(pat, out)
        if m:
            return m.group(1)[:160]
    return ""


# ============================== error fingerprinting / dedup ==============================


def error_fingerprint(text: str) -> str:
    """Stable fingerprint of an error: drop volatile digits/paths/hex, hash the residue."""
    t = (text or "").lower()
    t = _HEX_RE.sub("0xX", t)
    t = _PATH_RE.sub("/P", t)
    t = _DIGIT_RE.sub("#", t)
    t = re.sub(r"\s+", " ", t).strip()
    return hashlib.sha1(t.encode("utf-8")).hexdigest()[:16]


def dedupe_by_fingerprint(items: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    """Return (kept_unique, dropped) where dropped records the fingerprint + duplicate count."""
    seen: dict[str, int] = {}
    kept: list[str] = []
    dropped: list[dict[str, Any]] = []
    for it in items:
        fp = error_fingerprint(it)
        if fp in seen:
            seen[fp] += 1
            dropped.append({"fingerprint": fp, "reason": "duplicate_error", "sample": it[:120]})
        else:
            seen[fp] = 1
            kept.append(it)
    return kept, dropped


# ============================== noise detection ==============================


def detect_noise(observation: str, *, prior_fingerprints: set[str] | None = None) -> str | None:
    """Classify an observation as noise (or None if it carries signal)."""
    text = observation or ""
    low = text.lower()
    if (
        prior_fingerprints is not None
        and error_fingerprint(text) in prior_fingerprints
        and _ERROR_LINE_RE.search(low)
    ):
        return "repeated_identical_stack_trace"
    if low.count("\n") > 400 or ("lockfile" in low and len(text) > 4000):
        return "giant_lockfile_or_dump"
    if ("screenshot" in low or ".png" in low) and "assert" not in low and "expect" not in low:
        return "screenshot_without_assertion"
    if (
        ("summary" in low or "i think" in low or "probably" in low)
        and "evidence" not in low
        and "source" not in low
        and len(text) < 400
    ):
        return "evidenceless_summary"
    return None


# ============================== retrieval pack ==============================


def build_retrieval_pack(state: dict[str, Any], ledger: ClaimLedger, *, now: str | None = None) -> str:
    """The compact pack each node receives — confirmed claims ONLY, plus the protected essentials.

    Deliberately EXCLUDES unverified/contradicted/stale claims so noise and unproven premises do not
    propagate. Keeps user requirements + acceptance criteria + open blockers + the current failing
    gate + the last useful observation + changed files + evidence refs.
    """
    usable = ledger.usable_claims(now)
    user_reqs = [c.text for c in ledger.claims_by_type("user_requirement")]
    confirmed = [
        f"[{c.id}] {c.text}  (evidence: {', '.join(c.evidence_refs) or '—'})"
        for c in usable
        if c.type != "user_requirement"
    ]
    failing = [
        f"{r.get('gate')}: {r.get('summary', '')[:120]}"
        for r in state.get("verification_results", [])
        if str(r.get("result", "")).upper() in ("FAIL", "ERROR")
    ]
    blockers = list(state.get("risk_flags", []) or []) + [
        b.get("action", "") for b in state.get("blocked_decisions", []) or []
    ]
    changed = list(state.get("changed_files", []) or [])[:40]
    last_obs = ""
    react = state.get("react_trace", []) or []
    if react:
        last_obs = str(react[-1].get("observation", ""))[:200]

    lines = [
        "# Retrieval pack (compact — confirmed claims only)",
        f"## Goal\n{state.get('task', '')}",
        "## Acceptance criteria",
        *([f"- {a}" for a in (state.get("acceptance_criteria", []) or [])] or ["- (none yet)"]),
        "## Active constraints / user requirements",
        *([f"- {r}" for r in user_reqs] or ["- (none)"]),
        "## Confirmed claims (usable as premises)",
        *([f"- {c}" for c in confirmed] or ["- (none confirmed yet)"]),
        "## Current failing gate(s)",
        *([f"- {f}" for f in failing] or ["- (none failing)"]),
        "## Open blockers / deferred actions",
        *([f"- {b}" for b in blockers] or ["- (none)"]),
        f"## Last useful observation\n{last_obs or '(none)'}",
        "## Files changed",
        *([f"- {f}" for f in changed] or ["- (none)"]),
    ]
    return "\n".join(lines) + "\n"


def stale_or_contradicted_in_pack(pack_text: str, ledger: ClaimLedger) -> list[str]:
    """Context checker helper: claim ids in the pack whose current status is NOT usable."""
    ids = set(re.findall(r"\[(c\d+)\]", pack_text or ""))
    bad = []
    for cid in ids:
        c = ledger.get_claim(cid)
        if c is not None and c.status not in epistemic.USABLE_STATUSES:
            bad.append(cid)
    return bad


# ============================== ReAct trace ==============================

_REACT_FIELDS = (
    "timestamp",
    "iteration",
    "node",
    "goal",
    "thought_summary",
    "action",
    "action_input_summary",
    "observation",
    "evidence_refs",
    "claim_updates",
    "decision",
    "next_node",
)


def react_event(
    *,
    node: str,
    iteration: int = 0,
    goal: str = "",
    thought_summary: str = "",
    action: str = "",
    action_input_summary: str = "",
    observation: str = "",
    evidence_refs: list[str] | None = None,
    claim_updates: list[str] | None = None,
    decision: str = "continue",
    next_node: str = "",
    timestamp: str = "",
) -> dict[str, Any]:
    """Build a PUBLIC ReAct trace event (bounded; no private chain-of-thought)."""
    return {
        "timestamp": timestamp,
        "iteration": int(iteration),
        "node": node,
        "goal": goal[:200],
        "thought_summary": _redact(thought_summary)[:300],  # public rationale only
        "action": action,
        "action_input_summary": _redact(action_input_summary)[:300],
        "observation": _redact(observation)[:400],
        "evidence_refs": list(evidence_refs or []),
        "claim_updates": list(claim_updates or []),
        "decision": decision,
        "next_node": next_node,
    }


def validate_react_event(ev: dict[str, Any]) -> bool:
    if not isinstance(ev, dict) or any(k not in ev for k in _REACT_FIELDS):
        return False
    return isinstance(ev.get("evidence_refs"), list) and isinstance(ev.get("iteration"), int)


# ============================== lightweight semantic cache ==============================


def normalize_query(query: str, *, library: str = "", version: str = "", url: str = "") -> str:
    base = re.sub(r"\s+", " ", (query or "").strip().lower())
    key = f"{base}|lib={library.lower()}|ver={version}|url={url.lower()}"
    return key


@dataclass
class SemanticCache:
    """Local, secret-free retrieval cache. NEVER proof — only acceleration. Stale entries are not
    returned. Rejected (hallucinated) claims are remembered so they don't re-enter the loop."""

    queries: dict[str, dict[str, Any]] = field(default_factory=dict)
    docs: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected_claims: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put_query(
        self,
        query: str,
        value: dict[str, Any],
        *,
        library: str = "",
        version: str = "",
        url: str = "",
        trust_tier: str = epistemic.T3_SECONDARY,
        retrieved_at: str = "",
        freshness_required: bool = False,
    ) -> None:
        if _SECRET_RE.search(str(value)):
            return  # never cache secrets
        self.queries[normalize_query(query, library=library, version=version, url=url)] = {
            "value": value,
            "trust_tier": trust_tier,
            "retrieved_at": retrieved_at,
            "freshness_required": freshness_required,
        }

    def get_query(
        self,
        query: str,
        *,
        library: str = "",
        version: str = "",
        url: str = "",
        now: str = "",
        max_age_seconds: int = 60 * 60 * 24 * 30,
    ) -> dict[str, Any] | None:
        entry = self.queries.get(normalize_query(query, library=library, version=version, url=url))
        if entry is None:
            return None
        if entry.get("freshness_required") and not self._fresh(entry, now, max_age_seconds):
            return None  # stale cache entry is not used
        return entry["value"]

    def _fresh(self, entry: dict[str, Any], now: str, max_age_seconds: int) -> bool:
        r = epistemic._parse_iso(entry.get("retrieved_at"))
        cur = epistemic._parse_iso(now)
        if r is None or cur is None:
            return False
        return (cur - r).total_seconds() <= max_age_seconds

    def remember_failure(self, error_text: str, fix_summary: str = "") -> str:
        fp = error_fingerprint(error_text)
        self.failures[fp] = {"sample": error_text[:200], "fix": fix_summary[:400]}
        return fp

    def known_fix(self, error_text: str) -> str | None:
        return (self.failures.get(error_fingerprint(error_text)) or {}).get("fix") or None

    def reject_claim(self, claim_text: str, reason: str = "") -> str:
        fp = error_fingerprint(claim_text)
        self.rejected_claims[fp] = {"sample": claim_text[:200], "reason": reason[:200]}
        return fp

    def is_rejected(self, claim_text: str) -> bool:
        return error_fingerprint(claim_text) in self.rejected_claims

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
