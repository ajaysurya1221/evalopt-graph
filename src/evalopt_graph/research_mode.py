"""Research mode — decompose, gather evidence, verify, and synthesize a *cited* answer that never
overclaims.

Research mode never pretends to a deterministic PASS. It produces a synthesis whose confidence is
governed by the claim ledger: confirmed facts vs likely conclusions vs assumptions are kept
separate, contradictions are preserved, and an explicit "what would change the conclusion" section
states the missing evidence.
"""

from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from . import epistemic
from .claim_ledger import ClaimLedger
from .confidence import score_confidence
from .contradictions import Contradiction

_WORD_RE = re.compile(r"[a-z0-9_./@-]{3,}")
_RESEARCH_CLAIM_TYPES = (
    "research_claim",
    "api_fact",
    "architecture_decision",
    "dependency_fact",
    "performance_claim",
    "security_claim",
)

# task families
MODE_BUILD = "build"
MODE_RESEARCH = "research"
MODE_MIXED = "mixed"


def _kw(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def classify_task(task: str, mode_hint: str = "auto") -> tuple[str, str]:
    """Return ``(mode, task_class)``.

    mode ∈ {build, research, mixed}; task_class ∈ {build, research, mixed, debug, architecture,
    security, performance, product}. A ``mode_hint`` of build/research/mixed is authoritative.
    """
    t = (task or "").lower()
    research_kw = (
        "research",
        "compare",
        "comparison",
        "investigate",
        "evaluate options",
        "which is better",
        "best architecture",
        "survey",
        "pros and cons",
        "trade-off",
        "tradeoff",
        "should i use",
        "deeply compare",
        "analysis of",
    )
    build_kw = (
        "implement",
        "build",
        "fix",
        "add ",
        "refactor",
        "create",
        "write code",
        "patch",
        "migrate the code",
    )
    mixed_kw = (
        "then build",
        "verify current docs then",
        "architecture, verify",
        "design and build",
        "research then build",
    )

    hint = (mode_hint or "auto").lower()
    if hint in (MODE_BUILD, MODE_RESEARCH, MODE_MIXED):
        mode = hint
    elif any(k in t for k in mixed_kw):
        mode = MODE_MIXED
    elif any(k in t for k in research_kw) and not any(k in t for k in build_kw):
        mode = MODE_RESEARCH
    else:
        mode = MODE_BUILD

    if "security" in t or "vuln" in t or "auth" in t:
        cls = "security"
    elif "perf" in t or "latency" in t or "faster" in t or "throughput" in t:
        cls = "performance"
    elif "architecture" in t or "design the" in t:
        cls = "architecture"
    elif "debug" in t or "failing" in t or "bug" in t:
        cls = "debug"
    elif "product" in t or "feature spec" in t or "requirements" in t:
        cls = "product"
    elif mode == MODE_RESEARCH:
        cls = "research"
    elif mode == MODE_MIXED:
        cls = "mixed"
    else:
        cls = "build"
    return mode, cls


# ============================== local-only research provider ==============================
# Fixes the standalone-runner limitation: research can run with NO web/MCP by using only safe local
# sources (repo files, README/docs, package metadata). It NEVER invents web evidence; when web/MCP is
# unavailable it reports "local-only research mode" and lowers confidence (coverage is limited).

_LOCAL_DOC_NAMES = ("readme.md", "readme.rst", "readme.txt", "readme")
_META_FILES = ("package.json", "pyproject.toml", "cargo.toml", "go.mod", "composer.json", "gemfile")


def _safe_read(path: str, limit: int = 20000) -> str:
    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read(limit)
    except Exception:
        return ""


def local_research_packets(repo_path: str, questions: list[str]) -> list[dict[str, Any]]:
    """Gather evidence packets from SAFE LOCAL sources only (repo files / README / docs / metadata).

    For each question, find a local file whose text mentions the question's keywords and emit a
    proposal containing a repository-relative locator and exact quoted span. The controller-owned
    local-file adapter retrieves and attests the bytes as T1; this producer does not assign trust.
    Returns [] when nothing local matches, so missing coverage remains explicit."""
    repo = os.path.abspath(repo_path or ".")
    candidates: list[str] = []
    for name in os.listdir(repo) if os.path.isdir(repo) else []:
        low = name.lower()
        if low in _LOCAL_DOC_NAMES or low in _META_FILES or low.endswith((".md", ".rst")):
            candidates.append(os.path.join(repo, name))
    docs_dir = os.path.join(repo, "docs")
    if os.path.isdir(docs_dir):
        for name in sorted(os.listdir(docs_dir))[:30]:
            if name.lower().endswith((".md", ".rst", ".txt")):
                candidates.append(os.path.join(docs_dir, name))

    packets: list[dict[str, Any]] = []
    for q in questions or []:
        qk = {w for w in _kw(q) if len(w) >= 4}
        if not qk:
            continue
        for path in candidates:
            text = _safe_read(path)
            if not text:
                continue
            for line in text.splitlines():
                if qk & _kw(line.lower()) and len(line.strip()) > 8:
                    excerpt = line.strip()[:200]
                    packets.append(
                        {
                            "claim": {
                                "text": excerpt,
                                "type": "research_claim",
                                "subject": q,
                                "notes": "local-only research mode",
                            },
                            "evidence_requests": [
                                {
                                    "adapter_id": "local_file",
                                    "locator": os.path.relpath(path, repo),
                                    "quoted_span": excerpt,
                                }
                            ],
                        }
                    )
                    break  # one supporting line per (question, file)
    return packets


def default_local_investigation_hook(state: dict[str, Any], ctx: Any, phase: str) -> list[dict[str, Any]]:
    """A ctx.investigation_hook that uses ONLY local sources (no web/MCP). Used by the standalone CLI
    so overnight research is not blocked when web/MCP is unavailable."""
    if phase != "investigation":
        return []
    return local_research_packets(state.get("repo_path", "."), state.get("research_questions", []))


def coverage(
    ledger: ClaimLedger, questions: list[str], now: str | None = None
) -> tuple[list[str], list[str]]:
    """Split research questions into (covered, missing) by whether a *usable* claim addresses each."""
    covered, missing = [], []
    for q in questions or []:
        qk = _kw(q)
        hit = any(
            epistemic.is_usable(c, now) and (c.subject == q or (qk & _kw(f"{c.text} {c.subject}")))
            for c in ledger.claims()
        )
        (covered if hit else missing).append(q)
    return covered, missing


def passes_research_gate(
    ledger: ClaimLedger,
    contradictions: list[Contradiction],
    *,
    questions: list[str] | None = None,
    min_confirmed: int = 1,
    require_source_table: bool = True,
    now: str | None = None,
) -> tuple[bool, list[str]]:
    """Research 'gate': coverage + confirmed claims + a source table. Unresolved contradictions are
    *preserved and reported*, not treated as failures — but a missing source table or an unverified
    central claim does block a confident synthesis. A missing/failed docs fetch is NOT a failure."""
    reasons: list[str] = []
    confirmed = [c for c in ledger.usable_claims(now) if c.type in _RESEARCH_CLAIM_TYPES]
    if len(confirmed) < min_confirmed:
        reasons.append("no confirmed research claims yet")
    if require_source_table and not ledger.sources:
        reasons.append("no sources recorded (source table required)")
    if questions:
        _, missing = coverage(ledger, questions, now)
        if missing:
            reasons.append(f"uncovered questions: {missing}")
    central_unverified = [c.id for c in ledger.central_claims() if not epistemic.is_usable(c, now)]
    if central_unverified:
        reasons.append(f"central claims unverified: {central_unverified}")
    return (len(reasons) == 0, reasons)


@dataclass
class ResearchReport:
    answer: str = ""
    confirmed_claims: list[dict[str, Any]] = field(default_factory=list)
    likely_conclusions: list[dict[str, Any]] = field(default_factory=list)
    source_table: list[dict[str, Any]] = field(default_factory=list)
    contradictions: list[dict[str, Any]] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    confidence_by_section: dict[str, float] = field(default_factory=dict)
    what_would_change: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def synthesize(
    ledger: ClaimLedger,
    contradictions: list[Contradiction],
    *,
    topic: str = "",
    now: str | None = None,
) -> ResearchReport:
    """Build an evidence-grounded report. Confirmed facts, likely conclusions, assumptions and
    contradictions are kept strictly separate so nothing is overclaimed."""
    rep = ResearchReport()
    usable = ledger.usable_claims(now)
    unverified = [c for c in ledger.claims() if c.status == epistemic.STATUS_UNVERIFIED]

    # A reported "confirmed fact" must be evidence-backed and must NOT be the user's own question /
    # acceptance criterion. Excluding assumptions is not enough: user_requirement claims auto-confirm
    # with zero evidence, so without this they render as high-confidence "facts" with `evidence: —` and
    # inflate the headline confidence. (Mirrors the context_hygiene retrieval-pack exclusion.)
    rep.confirmed_claims = [
        {
            "id": c.id,
            "text": c.text,
            "type": c.type,
            "confidence": score_confidence(c, ledger.sources),
            "evidence": c.evidence_refs,
        }
        for c in usable
        if c.type not in ("assumption", "user_requirement") and c.evidence_refs
    ]
    rep.likely_conclusions = [
        {"id": c.id, "text": c.text, "confidence": score_confidence(c, ledger.sources)} for c in unverified
    ]
    rep.assumptions = [c.text for c in ledger.assumptions()]
    rep.source_table = [
        {
            "id": s.id,
            "kind": s.kind,
            "trust_tier": s.trust_tier,
            "locator": s.locator,
            "summary": s.summary[:200],
        }
        for s in ledger.sources.values()
    ]
    rep.contradictions = [(x if isinstance(x, dict) else x.to_dict()) for x in contradictions]

    # confidence by section
    def _avg(items: list[dict[str, Any]]) -> float:
        vals = [i.get("confidence", 0.0) for i in items]
        return round(sum(vals) / len(vals), 3) if vals else 0.0

    rep.confidence_by_section = {
        "confirmed_facts": _avg(rep.confirmed_claims),
        "likely_conclusions": _avg(rep.likely_conclusions),
        "overall": round(
            (sum(c["confidence"] for c in rep.confirmed_claims) + 0.0)
            / max(1, len(rep.confirmed_claims) + len(rep.likely_conclusions)),
            3,
        ),
    }

    # what would change the conclusion
    for x in rep.contradictions:
        if x.get("status") != "resolved":
            rep.what_would_change.append(
                f"resolve the contradiction on '{x.get('subject')}' with stronger evidence"
            )
    for c in ledger.central_claims():
        if not epistemic.is_usable(c, now):
            rep.what_would_change.append(f"obtain T2+ evidence to confirm central claim: {c.text[:80]}")
    for c in ledger.claims():
        if c.status == epistemic.STATUS_STALE:
            rep.what_would_change.append(f"refresh stale source for: {c.text[:80]}")

    # answer + next actions
    n_conf, n_unv, n_contra = (
        len(rep.confirmed_claims),
        len(rep.likely_conclusions),
        len([x for x in rep.contradictions if x.get("status") != "resolved"]),
    )
    rep.answer = (
        f"Synthesis for: {topic or '(topic)'}. {n_conf} confirmed fact(s), {n_unv} likely (unverified) "
        f"conclusion(s), {n_contra} unresolved contradiction(s). See sections for evidence and confidence."
    )
    if n_contra:
        rep.next_actions.append("gather decisive evidence to resolve open contradictions before committing")
    if rep.likely_conclusions:
        rep.next_actions.append("promote likely conclusions to confirmed by finding primary/official sources")
    if not rep.next_actions:
        rep.next_actions.append("conclusions are evidence-backed; proceed and re-verify if inputs change")
    return rep


def render_markdown(rep: ResearchReport, *, topic: str = "") -> str:
    def _src(refs: list[str]) -> str:
        return ", ".join(refs) if refs else "—"

    lines = [f"# Research synthesis — {topic or '(topic)'}", "", "## Answer", rep.answer, ""]
    lines.append("## Confirmed facts")
    if rep.confirmed_claims:
        for c in rep.confirmed_claims:
            lines.append(f"- ({c['confidence']:.2f}) {c['text']}  _[evidence: {_src(c['evidence'])}]_")
    else:
        lines.append("- (none confirmed)")
    lines += ["", "## Likely conclusions (unverified — treat as hypotheses)"]
    lines += [f"- ({c['confidence']:.2f}) {c['text']}" for c in rep.likely_conclusions] or ["- (none)"]
    lines += ["", "## Assumptions"]
    lines += [f"- {a}" for a in rep.assumptions] or ["- (none)"]
    lines += ["", "## Unresolved contradictions (preserved, not smoothed away)"]
    open_x = [x for x in rep.contradictions if x.get("status") != "resolved"]
    lines += [f"- [{x.get('severity', 'normal')}] {x.get('summary')}" for x in open_x] or ["- (none)"]
    lines += ["", "## Source table"]
    if rep.source_table:
        lines.append("| id | tier | kind | locator | summary |")
        lines.append("|---|---|---|---|---|")
        for s in rep.source_table:
            lines.append(f"| {s['id']} | {s['trust_tier']} | {s['kind']} | {s['locator']} | {s['summary']} |")
    else:
        lines.append("- (no sources)")
    lines += ["", "## Confidence by section"]
    lines += [f"- {k}: {v:.2f}" for k, v in rep.confidence_by_section.items()]
    lines += ["", "## What would change the conclusion"]
    lines += [f"- {w}" for w in rep.what_would_change] or ["- (nothing outstanding)"]
    lines += ["", "## Recommended next actions"]
    lines += [f"- {a}" for a in rep.next_actions]
    return "\n".join(lines) + "\n"
