"""Deprecated compatibility host for the pure governance kernel.

The loop remains available during migration, but hosts own orchestration and only the kernel decides
acceptance. The former LangGraph subset was removed because it never reached behavioral parity.
"""

from __future__ import annotations

import copy
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from . import (
    attestation,
    checkers,
    checks,
    claim_ledger,
    codex_bridge,
    confidence,
    epistemic,
    evaluator,
    evidence_adapters,
    kernel,
    project_detect,
    reflection,
    research_mode,
    stability,
    tool_router,
    unattended,
)
from . import (
    context_hygiene as hygiene,
)
from . import (
    contradictions as contra,
)
from . import (
    source_verification as sv,
)
from .codex_bridge import CodexConfig
from .providers import LLMProvider, MockProvider
from .state import (
    ADJUDICATOR,
    ASSUMPTION_EXTRACTION,
    CONTRADICTION_HUNTER,
    EVALUATOR,
    FAILURE_REPORT,
    FINAL_REVIEW,
    GENERATION,
    GOAL_INTAKE,
    HUMAN_GATE,
    PARALLEL_INVESTIGATION,
    PLANNING,
    PROJECT_SCAN,
    QUALITY_CONTRACT,
    REFLECTION,
    RESEARCH_PLANNER,
    SOURCE_VERIFIER,
    STABILITY_CONTROLLER,
    STOP_BLOCKED,
    STOP_CRASHED,
    STOP_DEFERRED,
    STOP_MAX_ITERS,
    STOP_MAX_RESEARCH_ROUNDS,
    STOP_PASS,
    STOP_PASS_WITH_WARNINGS,
    STOP_RESEARCH_SYNTHESIS,
    STOP_STUCK,
    STOP_UNVERIFIED,
    STOP_WALL_CLOCK,
    STUCK_ANALYSIS,
    STUCK_REPEAT_THRESHOLD,
    SYNTHESIS,
    TOOL_ROUTER,
    VERIFICATION,
)

# Codex enrichment node names
CODEX_REVIEW = "codex_review"
CODEX_ADVERSARIAL = "codex_adversarial_review"
CODEX_FINAL_REVIEW = "codex_final_review"
SECURITY_REVIEW = "security_review"

ProgressFn = Callable[[dict[str, Any]], None]
# Optional plug-in that performs REAL code edits in the standalone runner. Signature:
#   (state, ctx) -> list[str]  (returns changed file paths). Default: no-op.
GenerationHook = Callable[[dict[str, Any], "RunContext"], list[str]]
# Optional plug-in that proposes claims and evidence locators (research mode / assumptions).
# Signature: (state, ctx, phase) -> list[{"claim": {...}, "evidence_requests": [{...}]}].
# The hook is a proposal producer, not an authority: only registered adapters may retrieve content
# and issue attestations. ``sources`` remains a visibly downgraded legacy migration path.
InvestigationHook = Callable[[dict[str, Any], "InvestigationContext", str], list[dict[str, Any]]]

# Default epistemic-governor / research-mode / stability config (merged with state/ctx overrides).
DEFAULT_GOVERNOR_CONFIG: dict[str, Any] = {
    "epistemic_governor": {
        "enabled": True,
        "require_claim_evidence": True,
        "prevent_unverified_claim_propagation": True,
        "model_consensus_is_not_proof": True,
        "require_contradiction_search_before_final": True,
        "require_source_verification_for_research": True,
        "trust_tier_required_for_central_claims": epistemic.T2_OFFICIAL,
        "deterministic_evidence_overrides_model_opinion": True,
        "max_parallel_agents": 6,
        "max_research_rounds": 4,
        "max_tool_calls_per_round": 30,
    },
    "research_mode": {
        "enabled": True,
        "default_freshness_check": "auto",
        "require_source_table": True,
        "require_confidence_by_section": True,
        "require_unresolved_uncertainty_section": True,
    },
    "stability_controller": {
        "detect_patch_oscillation": True,
        "detect_repeated_failures": True,
        "repeated_failure_threshold": 3,
        "flaky_test_reruns": 3,
        "retry_transient_tool_failures_once": True,
        "stop_on_low_information_gain": True,
    },
}

# Claim kwargs an investigation packet may set (everything else is ignored). Provenance, creator,
# status and trust are deliberately absent: the trusted controller owns those fields.
# NOTE: "status" is intentionally NOT here — a model/hook packet may not preseed a claim as
# `confirmed`; status is earned only through the source verifier (or user/deterministic provenance).
_CLAIM_KW = {
    "type",
    "confidence",
    "subject",
    "stance",
    "central",
    "expires_at",
    "notes",
}


@dataclass(frozen=True)
class InvestigationContext:
    """Read-only run metadata exposed to proposal-producing investigation hooks."""

    repo_path: str
    knowledge_dir: str | None
    observed_at: str


@dataclass
class RunContext:
    provider: LLMProvider = field(default_factory=MockProvider)
    runner: checks.Runner = checks.run_command
    on_progress: ProgressFn | None = None
    generation_hook: GenerationHook | None = None
    codex: CodexConfig = field(default_factory=CodexConfig)  # library default: disabled
    run_dir: str | None = None  # where Codex logs/diffs are written (set by CLI --write)
    # tool-router: config + how optional gates execute (argv runner is injectable for hermetic tests)
    router_config: dict[str, Any] = field(default_factory=dict)
    argv_runner: Callable[[str, list[str], str], checks.CommandResult] = checks.run_command_argv
    execute_optional_gates: bool = True
    docker_enabled: str = "auto"
    # epistemic governor: config + evidence source + claim persistence + injectable clock
    epistemic_config: dict[str, Any] = field(default_factory=dict)
    investigation_hook: InvestigationHook | None = None
    # Host adapters retrieve material; the pure kernel seals their controller-owned policies.
    evidence_adapters: tuple[evidence_adapters.EvidenceAdapter, ...] = ()
    evidence_authority: evidence_adapters.EvidenceAuthority | None = None  # deprecated retrieving facade
    _sealed_evidence_authority: kernel.EvidenceAuthority | None = field(default=None, init=False, repr=False)
    _sealed_evidence_adapters: dict[str, evidence_adapters.EvidenceAdapter] = field(
        default_factory=dict, init=False, repr=False
    )
    _validated_record_sha256: frozenset[str] = field(default_factory=frozenset, init=False, repr=False)
    _issued_record_sha256: set[str] = field(default_factory=set, init=False, repr=False)
    knowledge_dir: str | None = None  # .evalopt/knowledge — append-only claim/source ledger
    now: Callable[[], str] = epistemic.now_iso

    def progress(self, state: dict[str, Any], node: str) -> None:
        if self.on_progress:
            self.on_progress({**state, "_node": node})


# ============================== ROUTING (pure) ==============================


def route(state: dict[str, Any]) -> str:
    """The single routing decision, evaluated after the evaluator node.

    Priority (maps to the architecture spec):
      1. a pending destructive/external action            -> HUMAN_GATE
      2. all required gates pass (+ rubric ok)             -> FINAL_REVIEW
      3. the same failure repeats / patch oscillates       -> STUCK_ANALYSIS (-> human gate)
      4. iteration budget exhausted                        -> FAILURE_REPORT
      5. otherwise (checks fail / score low, budget left)  -> REFLECTION
    """
    if _needs_human_gate(state):
        return HUMAN_GATE

    passed, _ = evaluator.passes_quality_gate(
        state.get("verification_results", []),
        state.get("evaluator_score"),
        _effective_required_gates(state),
        state.get("quality_threshold", 0.90),
        tests_weakened=bool(state.get("tests_weakened", False)),
    )
    if passed:
        return FINAL_REVIEW

    if _stuck_or_oscillating(state):
        return STUCK_ANALYSIS

    if int(state.get("iteration", 0)) >= int(state.get("max_iterations", 6)):
        return FAILURE_REPORT

    return REFLECTION


def _stuck_threshold(state: dict[str, Any]) -> int:
    """Consecutive-failure threshold for stuck detection, honoring a per-run config override
    (``stability_controller.repeated_failure_threshold``) so the setting is a real contract."""
    cfg = state.get("epistemic_config") or {}
    try:
        return int(
            cfg.get("stability_controller", {}).get("repeated_failure_threshold", STUCK_REPEAT_THRESHOLD)
        )
    except (TypeError, ValueError):
        return STUCK_REPEAT_THRESHOLD


def _stuck_or_oscillating(state: dict[str, Any]) -> bool:
    """STUCK when the same blocking failure repeats N consecutive iterations (N from config) OR the
    failure signatures ping-pong between two shapes (A→B→A→B) — a patch that oscillates should escalate
    to root-cause/human rather than burn the whole iteration budget. Prefers the stability controller's
    computed signals when present (so its output is actually consumed), else derives them inline so the
    decision is identical for the compatibility loop and the mid-iteration Codex re-route.
    """
    st = state.get("stability") or {}
    if st.get("repeated_failure") or st.get("patch_oscillation"):
        return True
    sigs = state.get("failure_signatures", []) or []
    return reflection.is_stuck(sigs, _stuck_threshold(state)) or stability.detect_patch_oscillation(sigs)


def _needs_human_gate(state: dict[str, Any]) -> bool:
    flags = state.get("risk_flags", []) or []
    gating = ("destructive", "external", "human-gate", "human_gate", "secret", "security:")
    return any(any(d in str(f).lower() for d in gating) for f in flags)


def _effective_required_gates(state: dict[str, Any]) -> list[str]:
    """Core required gates plus any BLOCKING optional gates the router selected (e.g. gitleaks,
    or semgrep at risk=high). Advisory optional gates are recorded but never gate the loop."""
    req = list(state.get("required_gates", []) or [])
    for g in state.get("blocking_gates", []) or []:
        if g not in req:
            req.append(g)
    return req


# ============================== EPISTEMIC GOVERNOR (config + ledger helpers) ==============================


def _deep_merge(base: dict[str, Any], over: dict[str, Any] | None) -> dict[str, Any]:
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in base.items()}
    for k, v in (over or {}).items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def _gov(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return _deep_merge(DEFAULT_GOVERNOR_CONFIG, state.get("epistemic_config") or ctx.epistemic_config or {})


def _epistemic_enabled(gov: dict[str, Any]) -> bool:
    return bool(gov.get("epistemic_governor", {}).get("enabled", True))


def _gov_val(gov: dict[str, Any], section: str, key: str, default: Any) -> Any:
    return gov.get(section, {}).get(key, default)


def _ledger(state: dict[str, Any], ctx: RunContext) -> claim_ledger.ClaimLedger:
    return claim_ledger.ClaimLedger.from_snapshot(
        state.get("knowledge"), knowledge_dir=ctx.knowledge_dir, now=ctx.now
    )


def _save_ledger(state: dict[str, Any], led: claim_ledger.ClaimLedger) -> None:
    state["knowledge"] = led.snapshot()
    state["assumptions"] = [c.to_dict() for c in led.assumptions()]


def _now(ctx: RunContext) -> str:
    return ctx.now()


def _authority(
    state: dict[str, Any], ctx: RunContext
) -> tuple[kernel.EvidenceAuthority, dict[str, evidence_adapters.EvidenceAdapter]]:
    """Seal host adapter policies before proposal code runs."""
    if ctx._sealed_evidence_authority is None:
        adapters = ctx.evidence_adapters or tuple(
            (ctx.evidence_authority._adapters if ctx.evidence_authority else {}).values()
        )
        ctx._sealed_evidence_adapters = {adapter.policy.adapter_id: adapter for adapter in adapters}
        ctx._sealed_evidence_authority = kernel.EvidenceAuthority(
            adapter.policy.to_dict() for adapter in adapters
        )
    return ctx._sealed_evidence_authority, dict(ctx._sealed_evidence_adapters)


def _investigation_proposals(
    state: dict[str, Any], ctx: RunContext, phase: str
) -> tuple[
    list[dict[str, Any]],
    kernel.EvidenceAuthority,
    dict[str, evidence_adapters.EvidenceAdapter],
]:
    """Call an untrusted proposal hook without exposing mutable controller authority or state."""
    authority, adapters = _authority(state, ctx)
    hook_context = InvestigationContext(
        repo_path=os.path.realpath(state.get("repo_path", ".")),
        knowledge_dir=ctx.knowledge_dir,
        observed_at=_now(ctx),
    )
    packets = (
        ctx.investigation_hook(copy.deepcopy(state), hook_context, phase) if ctx.investigation_hook else []
    )
    return list(packets or []), authority, adapters


def _attested_source(
    led: claim_ledger.ClaimLedger,
    result: tuple[attestation.EvidenceAttestation, attestation.SupportAssessment],
) -> epistemic.Source:
    """Persist a kernel-issued result and materialize its claim-scoped Source view."""
    evidence, support = result
    led.add_attestation(evidence)
    led.add_support_assessment(support)
    for source in led.sources.values():
        if (
            source.attestation_id == evidence.attestation_id
            and source.support_assessment_id == support.assessment_id
        ):
            return source
    return led.add_source(
        kind=evidence.source_kind,
        locator=evidence.final_locator,
        summary=evidence.selected_text,
        quoted_span_or_hash=evidence.selected_sha256,
        trust_tier=evidence.trust_tier,
        freshness_required=evidence.freshness_required,
        retrieved_at=evidence.retrieved_at,
        attestation_id=evidence.attestation_id,
        attestation_status=evidence.status,
        support_assessment_id=support.assessment_id,
        support_relation=support.relation,
    )


def _legacy_source(led: claim_ledger.ClaimLedger, packet: dict[str, Any]) -> epistemic.Source:
    """Retain legacy packet evidence for audit visibility without granting it authority."""
    return led.add_source(
        kind="legacy_model_packet",
        locator=str(packet.get("locator", "")),
        summary=str(packet.get("summary", "")),
        quoted_span_or_hash=str(packet.get("quoted_span_or_hash", "")),
        trust_tier=epistemic.T4_MODEL,
        freshness_required=False,
        attestation_status=attestation.UNVERIFIED,
        support_relation=attestation.NOT_ASSESSED,
    )


def _ingest_packets(
    led: claim_ledger.ClaimLedger,
    packets: list[dict[str, Any]] | None,
    *,
    created_by: str,
    authority: kernel.EvidenceAuthority | None = None,
    adapters: dict[str, evidence_adapters.EvidenceAdapter] | None = None,
    issued_record_sha256: set[str] | None = None,
    observed_at: str = "",
) -> list[Any]:
    """Ingest proposal-only packets into claims and controller-issued evidence records.

    ``evidence_requests`` may select content through a registered adapter. Legacy ``sources`` are
    retained as T4/UNVERIFIED audit records. Producer-authored attestations, trust, source kind,
    timestamps, creator, source type and status are ignored. Duplicate claims merge only their
    claim-scoped, controller-issued source views.
    """
    added = []
    index = {(c.text.strip().lower(), c.subject): c for c in led.claims()}
    for p in packets or []:
        cl = p.get("claim") or {}
        if not isinstance(cl, dict) or not cl.get("text"):
            continue
        claim_text = str(cl["text"])
        kwargs = {k: v for k, v in cl.items() if k in _CLAIM_KW}
        key = (claim_text.strip().lower(), str(cl.get("subject", "")))
        existing = index.get(key)
        support_text = existing.text if existing is not None else claim_text
        support_type = existing.type if existing is not None else str(kwargs.get("type", "model_inference"))
        support_subject = existing.subject if existing is not None else str(kwargs.get("subject", ""))
        support_stance = existing.stance if existing is not None else str(kwargs.get("stance", ""))
        ref_ids = []
        for raw_request in p.get("evidence_requests", []) or []:
            if not isinstance(raw_request, dict):
                continue
            request = attestation.EvidenceRequest.from_dict(raw_request)
            claim = kernel.ClaimRecord(
                id=existing.id if existing else "proposal",
                text=support_text,
                claim_type=support_type,
                subject=support_subject,
                stance=support_stance,
            )
            adapter = (adapters or {}).get(request.adapter_id)
            if authority is None or adapter is None:
                result = attestation._issue_failure(
                    request,
                    claim_text=claim.text,
                    claim_type=claim.claim_type,
                    claim_subject=claim.subject,
                    claim_stance=claim.stance,
                    status=attestation.UNSUPPORTED,
                    reason=f"evidence adapter is not registered: {request.adapter_id or '(missing)'}",
                )
            else:
                try:
                    material = adapter.retrieve(request.locator)
                except evidence_adapters._BlockedRetrieval as exc:
                    result = attestation._issue_failure(
                        request,
                        claim_text=claim.text,
                        status=attestation.BLOCKED,
                        reason=str(exc),
                        claim_type=claim.claim_type,
                        claim_subject=claim.subject,
                        claim_stance=claim.stance,
                    )
                except evidence_adapters._UnsupportedRetrieval as exc:
                    result = attestation._issue_failure(
                        request,
                        claim_text=claim.text,
                        status=attestation.UNSUPPORTED,
                        reason=str(exc),
                        claim_type=claim.claim_type,
                        claim_subject=claim.subject,
                        claim_stance=claim.stance,
                    )
                except Exception as exc:
                    result = attestation._issue_failure(
                        request,
                        claim_text=claim.text,
                        status=attestation.FAILED,
                        reason=f"host evidence retrieval failed: {type(exc).__name__}",
                        claim_type=claim.claim_type,
                        claim_subject=claim.subject,
                        claim_stance=claim.stance,
                    )
                else:
                    result = authority.issue(
                        request,
                        material,
                        observed_at=observed_at or epistemic.now_iso(),
                        claim=claim,
                    )
            if result[0].status == attestation.VERIFIED and result[1].relation in {
                attestation.SUPPORTS,
                attestation.CONTRADICTS,
            }:
                (issued_record_sha256 if issued_record_sha256 is not None else set()).update(
                    (result[0].record_sha256, result[1].record_sha256)
                )
            s = _attested_source(led, result)
            ref_ids.append(s.id)
        legacy = [sp for sp in (p.get("sources", []) or []) if isinstance(sp, dict)]
        for source_packet in legacy:
            ref_ids.append(_legacy_source(led, source_packet).id)
        if legacy:
            led.add_decision(
                {
                    "kind": "legacy_evidence_downgraded",
                    "created_by": created_by,
                    "count": len(legacy),
                    "reason": "producer-authored source metadata is not an attestation",
                }
            )
        if p.get("attestations"):
            led.add_decision(
                {
                    "kind": "untrusted_attestations_ignored",
                    "created_by": created_by,
                    "count": len(p.get("attestations") or []),
                }
            )
        if existing is not None:
            merged = list(dict.fromkeys(list(existing.evidence_refs) + ref_ids))
            led.update_claim(existing.id, evidence_refs=merged)
            continue
        c = led.add_claim(
            claim_text,
            source_type="claude_inference",
            evidence_refs=ref_ids,
            created_by=created_by,
            **kwargs,
        )
        index[key] = c
        added.append(c)
    return added


def _xs_from_state(state: dict[str, Any]) -> list[contra.Contradiction]:
    fields = set(contra.Contradiction.__dataclass_fields__)
    return [
        contra.Contradiction(**{k: v for k, v in x.items() if k in fields})
        for x in state.get("contradictions", [])
    ]


def _confirmed_count(state: dict[str, Any], ctx: RunContext) -> int:
    return len(_ledger(state, ctx).usable_claims(_now(ctx)))


# ============================== UNATTENDED AUTONOMY + CONTEXT HYGIENE ==============================


def _unatt(state: dict[str, Any]) -> dict[str, Any]:
    return unattended.unattended_config(state.get("unattended"))


def _unattended_on(state: dict[str, Any]) -> bool:
    return unattended.is_unattended(_unatt(state))


def _react(
    state: dict[str, Any],
    ctx: RunContext,
    node: str,
    *,
    action: str = "",
    action_input_summary: str = "",
    observation: str = "",
    thought_summary: str = "",
    decision: str = "continue",
    next_node: str = "",
    evidence_refs: list[str] | None = None,
    claim_updates: list[str] | None = None,
) -> None:
    """Emit a PUBLIC ReAct trace event (bounded; no private chain-of-thought). Kept in state (capped)
    and appended to the run dir's react_trace.jsonl when a run dir is set."""
    ev = hygiene.react_event(
        node=node,
        iteration=int(state.get("iteration", 0)),
        goal=state.get("task", ""),
        thought_summary=thought_summary,
        action=action,
        action_input_summary=action_input_summary,
        observation=observation,
        evidence_refs=evidence_refs,
        claim_updates=claim_updates,
        decision=decision,
        next_node=next_node,
        timestamp=_now(ctx),
    )
    trace = state.setdefault("react_trace", [])
    trace.append(ev)
    if len(trace) > 300:  # context hygiene: keep only the tail in state; full log is on disk
        del trace[:-300]
    if ctx.run_dir:
        try:
            import json as _json

            with open(os.path.join(ctx.run_dir, "react_trace.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(_json.dumps(ev, default=str) + "\n")
        except Exception:
            pass


def _record_blocked_from_flags(state: dict[str, Any], ctx: RunContext) -> int:
    """Convert gating risk flags (destructive/security/external) into recorded blocked decisions
    instead of an interactive wait. Returns the count recorded."""
    gating = ("destructive", "external", "secret", "security:", "human-gate", "human_gate")
    n = 0
    existing = {b.get("action") for b in state.get("blocked_decisions", []) or []}
    for flag in state.get("risk_flags", []) or []:
        f = str(flag)
        if any(d in f.lower() for d in gating) and f not in existing:
            deferred, acls, reason, fb = unattended.evaluate_action(f, now=_now(ctx))
            bd = unattended.BlockedDecision(
                id=f"b{len(existing) + n + 1}",
                action=f,
                action_class=acls if deferred else unattended.DESTRUCTIVE,
                reason=reason if deferred else "gating risk flag — deferred in unattended mode",
                fallback=fb or "leave as-is; surface to the human",
                created_at=_now(ctx),
            )
            state.setdefault("blocked_decisions", []).append(bd.to_dict())
            n += 1
    return n


def _build_retrieval_pack(state: dict[str, Any], ctx: RunContext) -> str:
    pack = hygiene.build_retrieval_pack(state, _ledger(state, ctx), now=_now(ctx))
    state["retrieval_pack"] = pack
    return pack


def _run_checkers(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    pack = state.get("retrieval_pack") or _build_retrieval_pack(state, ctx)
    results = checkers.run_all(state, _ledger(state, ctx), pack_text=pack)
    state["checker_results"] = results
    if ctx.run_dir:
        try:
            import json as _json

            cdir = os.path.join(ctx.run_dir, "checkers")
            os.makedirs(cdir, exist_ok=True)
            for name, res in results.items():
                with open(os.path.join(cdir, f"{name}.json"), "w", encoding="utf-8") as fh:
                    _json.dump(res, fh, indent=2, default=str)
        except Exception:
            pass
    return results


def _unattended_finish(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """End-of-run hygiene for unattended mode: run checkers, write the morning report + overnight
    ledgers. Idempotent; only writes files when a repo/run dir is available."""
    if not _unattended_on(state):
        return state
    _record_blocked_from_flags(state, ctx)
    _run_checkers(state, ctx)
    state["morning_report"] = unattended.render_morning_report(state)
    repo = state.get("repo_path", "")
    if repo:
        try:
            odir = os.path.join(repo, ".evalopt", "overnight")
            os.makedirs(odir, exist_ok=True)
            _write(odir, "MORNING_REPORT.md", state["morning_report"])
            _append_jsonl(os.path.join(odir, "blocked_decisions.jsonl"), state.get("blocked_decisions", []))
            _append_jsonl(os.path.join(odir, "decisions.jsonl"), state.get("decisions", []))
            _append_jsonl(os.path.join(odir, "parked_branches.jsonl"), state.get("parked_branches", []))
            _write_context_artifacts(state, ctx, repo)
        except Exception:
            pass
    ctx.progress(state, FINAL_REVIEW)
    return state


def _write_context_artifacts(state: dict[str, Any], ctx: RunContext, repo: str) -> None:
    """Materialize the context-hygiene + cache artifact set (the durable, on-disk view of context)."""
    import json as _json

    led = _ledger(state, ctx)
    pack = state.get("retrieval_pack") or _build_retrieval_pack(state, ctx)
    cdir = os.path.join(repo, ".evalopt", "context")
    os.makedirs(cdir, exist_ok=True)
    _write(cdir, "retrieval_pack.md", pack)
    _write(cdir, "working_context.md", pack)
    react = state.get("react_trace", []) or []
    _write(
        cdir,
        "compressed_trace.md",
        "# Compressed ReAct trace\n\n"
        + "\n".join(
            f"- [{e.get('node')}] {e.get('action')} → {e.get('observation', '')[:120]}" for e in react
        ),
    )
    _write(
        cdir,
        "decision_digest.md",
        "# Decision digest\n\n## Autonomous decisions\n"
        + "\n".join(f"- {d}" for d in state.get("decisions", []))
        + "\n\n## Blocked (deferred)\n"
        + "\n".join(f"- {b}" for b in state.get("blocked_decisions", [])),
    )
    with open(os.path.join(cdir, "evidence_index.jsonl"), "w", encoding="utf-8") as fh:
        for c in led.claims():
            fh.write(
                _json.dumps({"id": c.id, "status": c.status, "evidence_refs": c.evidence_refs}, default=str)
                + "\n"
            )
    with open(os.path.join(cdir, "durable_memory.jsonl"), "w", encoding="utf-8") as fh:
        for c in led.usable_claims(_now(ctx)):
            fh.write(_json.dumps(c.to_dict(), default=str) + "\n")
    with open(os.path.join(cdir, "branch_summaries.jsonl"), "w", encoding="utf-8") as fh:
        for p in state.get("parked_branches", []):
            fh.write(_json.dumps(p, default=str) + "\n")
    # noise_log / dropped_context are append-only; ensure they exist for the artifact set
    for fn in ("noise_log.jsonl", "dropped_context.jsonl"):
        open(os.path.join(cdir, fn), "a", encoding="utf-8").close()
    # lightweight cache dir (the SemanticCache persists here when used; ensure the set exists)
    cache_dir = os.path.join(repo, ".evalopt", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    for fn in ("query_cache.jsonl", "doc_cache.jsonl", "failure_fingerprints.jsonl", "semantic_keys.jsonl"):
        open(os.path.join(cache_dir, fn), "a", encoding="utf-8").close()


def _append_jsonl(path: str, rows: list[dict[str, Any]]) -> None:
    import json as _json

    with open(path, "a", encoding="utf-8") as fh:
        for r in rows:
            fh.write(_json.dumps(r, default=str) + "\n")


def _unattended_park(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Unattended replacement for the human gate: record the blocking risk as deferred decisions,
    PARK this branch (with the next human action), and finish cleanly with a morning report — never
    sit waiting for input. Outcome is DEFERRED (safe work done; risky bits handed to the human)."""
    n = _record_blocked_from_flags(state, ctx)
    park = unattended.ParkedBranch(
        id=f"park-{state.get('iteration', 0)}",
        reason=str(state.get("stop_reason") or "human_gate")
        + ": "
        + "; ".join(str(f) for f in state.get("risk_flags", [])[-3:]),
        last_evidence=state.get("evaluator_feedback", "")[:200],
        next_human_action="review the deferred blocked_decisions and approve or reject",
        created_at=_now(ctx),
    )
    state.setdefault("parked_branches", []).append(park.to_dict())
    # Preserve a genuine no-progress outcome (STUCK): parking it must not relabel it as a clean DEFERRED
    # (which exits 0), or a cron/launchd wrapper would read an all-night stuck run as success.
    prior = state.get("stop_reason")
    if prior == STOP_STUCK:
        state["final_summary"] = (
            f"STUCK (parked): the same failure repeated with no progress; recorded {n} blocked "
            "decision(s) for human review. See .evalopt/overnight/MORNING_REPORT.md."
        )
    else:
        state["stop_reason"] = STOP_DEFERRED
        state["final_summary"] = (
            f"DEFERRED: did the safe work and recorded {n} blocked decision(s) requiring human approval "
            "(no interactive wait). See .evalopt/overnight/MORNING_REPORT.md."
        )
    _react(
        state,
        ctx,
        HUMAN_GATE,
        action="defer",
        observation=f"{n} blocked decision(s) recorded",
        decision="defer",
    )
    return _unattended_finish(state, ctx)


def _record_gate_claims(state: dict[str, Any], results: list[checks.CommandResult], ctx: RunContext) -> None:
    """Record each deterministic gate result as a T0 ``code_fact``/``test_result`` claim (build mode
    records claims from tests/commands). De-duped per gate by subject so iterations update, not pile."""
    led = _ledger(state, ctx)
    for r in results:
        if r.result == "NOT_CONFIGURED":
            continue
        subject = f"gate:{r.gate}"
        text = f"gate '{r.gate}' = {r.result}"
        ctype = "test_result" if r.gate == "tests" else "code_fact"
        stype = "test_result" if r.gate == "tests" else "command_output"
        src = led.add_source(
            kind="controller_test_output" if r.gate == "tests" else "controller_command_output",
            locator=r.command or r.gate,
            summary=text,
            trust_tier=epistemic.T0_DETERMINISTIC,
        )
        existing = [c for c in led.claims() if c.subject == subject]
        if existing:
            led.update_claim(
                existing[0].id,
                text=text,
                stance=r.result,
                evidence_refs=[src.id],
                status=epistemic.STATUS_CONFIRMED,
                notes=r.summary[:200],
            )
        else:
            led.add_claim(
                text,
                type=ctype,
                source_type=stype,
                evidence_refs=[src.id],
                status=epistemic.STATUS_CONFIRMED,
                created_by="verification",
                subject=subject,
                stance=r.result,
                notes=r.summary[:200],
            )
    _save_ledger(state, led)


# ============================== EPISTEMIC NODES ==============================


def node_goal_intake(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Classify the task (build/research/mixed + class) and seed the ledger with user requirements
    (which are confirmed/T1 evidence). Defines epistemic success alongside acceptance criteria."""
    explicit = state.get("mode")
    mode, cls = research_mode.classify_task(state.get("task", ""), explicit or "auto")
    # honor an explicit research/mixed request; let the classifier upgrade the default "build"
    if explicit in ("research", "mixed"):
        state["mode"] = explicit
    else:
        state["mode"] = mode
    state["task_class"] = cls
    if not state.get("started_at"):
        state["started_at"] = _now(ctx)  # wall-clock budget anchor (unattended)

    gov = _gov(state, ctx)
    if _epistemic_enabled(gov):
        led = _ledger(state, ctx)
        if not any(
            claim.type == "user_requirement"
            and claim.source_type == "user"
            and claim.created_by == "goal_intake"
            for claim in led.claims()
        ):
            led.add_claim(
                (state.get("task", "") or "(task)").strip(),
                type="user_requirement",
                source_type="user",
                created_by="goal_intake",
                subject="task",
            )
            for crit in state.get("acceptance_criteria", []) or []:
                led.add_claim(crit, type="user_requirement", source_type="user", created_by="goal_intake")
        _save_ledger(state, led)
    ctx.progress(state, GOAL_INTAKE)
    return state


def node_assumption_extraction(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """List the assumptions needed to proceed as explicit (mostly unverified) claims so they can be
    verified or carried forward as labelled assumptions — never silently used as facts."""
    gov = _gov(state, ctx)
    if not _epistemic_enabled(gov):
        ctx.progress(state, ASSUMPTION_EXTRACTION)
        return state
    led = _ledger(state, ctx)
    if ctx.investigation_hook:
        cap = int(_gov_val(gov, "epistemic_governor", "max_parallel_agents", 6))
        packets, authority, adapters = _investigation_proposals(state, ctx, "assumptions")
        _ingest_packets(
            led,
            packets[:cap],
            created_by="assumption_extraction",
            authority=authority,
            adapters=adapters,
            issued_record_sha256=ctx._issued_record_sha256,
            observed_at=_now(ctx),
        )
    _save_ledger(state, led)
    ctx.progress(state, ASSUMPTION_EXTRACTION)
    return state


def node_research_planner(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Choose what must be looked up this round (bounded by max_tool_calls_per_round)."""
    gov = _gov(state, ctx)
    if not state.get("research_questions"):
        qs = [state.get("task", "")] + list(state.get("acceptance_criteria", []) or [])
        state["research_questions"] = [q for q in qs if q][:6]
    led = _ledger(state, ctx)
    led.add_decision(
        {
            "kind": "research_plan",
            "round": state.get("research_round", 0),
            "questions": state.get("research_questions", []),
            "max_tool_calls": int(_gov_val(gov, "epistemic_governor", "max_tool_calls_per_round", 30)),
        }
    )
    _save_ledger(state, led)
    ctx.progress(state, RESEARCH_PLANNER)
    return state


def node_parallel_investigation(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Gather evidence packets (capped at max_parallel_agents). Subagents return packets, never
    naked conclusions — each packet must carry its sources."""
    gov = _gov(state, ctx)
    cap = int(_gov_val(gov, "epistemic_governor", "max_parallel_agents", 6))
    led = _ledger(state, ctx)
    packets, authority, adapters = _investigation_proposals(state, ctx, "investigation")
    capped = packets[:cap]
    _ingest_packets(
        led,
        capped,
        created_by="researcher",
        authority=authority,
        adapters=adapters,
        issued_record_sha256=ctx._issued_record_sha256,
        observed_at=_now(ctx),
    )
    state["last_investigation_count"] = len(capped)
    _save_ledger(state, led)
    ctx.progress(state, PARALLEL_INVESTIGATION)
    return state


def node_source_verifier(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Revalidate content-bound attestations, then derive claim status from eligible support edges."""
    led = _ledger(state, ctx)
    authority, adapters = _authority(state, ctx)
    ctx._validated_record_sha256 = frozenset()
    validated: set[str] = set()
    claims = led.claims()
    for source in list(led.sources.values()):
        if not source.attestation_id:
            continue
        evidence = led.get_attestation(source.attestation_id)
        support = led.get_support_assessment(source.support_assessment_id)
        if evidence is None or support is None:
            led.update_source(
                source.id,
                attestation_status=attestation.FAILED,
                support_relation=attestation.NOT_ASSESSED,
            )
            continue
        if evidence.status != attestation.VERIFIED:
            continue
        adapter = adapters.get(evidence.adapter_id)
        policy = authority._policy_for(evidence.adapter_id)
        if adapter is None or policy is None:
            valid, status, reason = False, attestation.UNSUPPORTED, "adapter is not registered"
        else:
            try:
                material = adapter.retrieve(evidence.requested_locator)
            except evidence_adapters._BlockedRetrieval as exc:
                valid, status, reason = False, attestation.BLOCKED, str(exc)
            except evidence_adapters._UnsupportedRetrieval as exc:
                valid, status, reason = False, attestation.UNSUPPORTED, str(exc)
            except Exception as exc:
                valid, status, reason = (
                    False,
                    attestation.FAILED,
                    f"host retrieval failed: {type(exc).__name__}",
                )
            else:
                valid, status, reason = attestation._revalidate_material(policy, evidence, material)
                linked = next(
                    (
                        claim
                        for claim in claims
                        if source.id in claim.evidence_refs
                        and attestation.claim_digest(
                            claim.text,
                            claim_type=claim.type,
                            claim_subject=claim.subject,
                            claim_stance=claim.stance,
                        )
                        == support.claim_sha256
                    ),
                    None,
                )
                current_issue = {
                    evidence.record_sha256,
                    support.record_sha256,
                } <= ctx._issued_record_sha256
                if valid and not material.retrieved_at and not current_issue:
                    valid, status, reason = (
                        False,
                        attestation.UNVERIFIED,
                        "controller retrieval time is unavailable for a restored record",
                    )
                if valid and linked is not None:
                    request = attestation.EvidenceRequest(
                        evidence.adapter_id,
                        evidence.requested_locator,
                        quoted_span=(
                            evidence.selector_value if evidence.selector_kind == "quoted_span" else None
                        ),
                        json_pointer=(
                            evidence.selector_value if evidence.selector_kind == "json_pointer" else None
                        ),
                    )
                    expected = authority.issue(
                        request,
                        material,
                        observed_at=(evidence.retrieved_at if current_issue else _now(ctx)),
                        claim=kernel.ClaimRecord(
                            linked.id,
                            linked.text,
                            linked.type,
                            linked.subject,
                            linked.stance,
                        ),
                    )
                    if expected != (evidence, support):
                        valid, status, reason = (
                            False,
                            attestation.FAILED,
                            "support record does not replay under the current policy",
                        )
                elif valid:
                    valid, status, reason = (
                        False,
                        attestation.FAILED,
                        "attestation has no claim-bound support record",
                    )
        if valid:
            validated.update((evidence.record_sha256, support.record_sha256))
        current_status = evidence.status if valid else status
        current_relation = support.relation if valid else attestation.NOT_ASSESSED
        if source.attestation_status != current_status or source.support_relation != current_relation:
            led.update_source(
                source.id,
                attestation_status=current_status,
                support_relation=current_relation,
            )
        if not valid:
            led.add_decision(
                {
                    "kind": "attestation_revalidation_failed",
                    "attestation_id": evidence.attestation_id,
                    "status": status,
                    "reason": reason,
                }
            )
    ctx._validated_record_sha256 = frozenset(validated)
    sv.verify_ledger(led, now=_now(ctx))
    confidence.score_ledger(led)
    _save_ledger(state, led)
    ctx.progress(state, SOURCE_VERIFIER)
    return state


def node_contradiction_hunter(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Actively search for disconfirming evidence/counterexamples, then detect contradictions and
    preserve them (status unresolved) for the adjudicator."""
    gov = _gov(state, ctx)
    led = _ledger(state, ctx)
    if ctx.investigation_hook:
        cap = int(_gov_val(gov, "epistemic_governor", "max_parallel_agents", 6))
        packets, authority, adapters = _investigation_proposals(state, ctx, "contradiction")
        _ingest_packets(
            led,
            packets[:cap],
            created_by="contradiction_hunter",
            authority=authority,
            adapters=adapters,
            issued_record_sha256=ctx._issued_record_sha256,
            observed_at=_now(ctx),
        )
        sv.verify_ledger(led, now=_now(ctx))
    xs = contra.find_contradictions(led.claims())
    state["contradictions"] = [x.to_dict() for x in xs]
    _save_ledger(state, led)
    ctx.progress(state, CONTRADICTION_HUNTER)
    return state


def node_adjudicator(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Weigh evidence by trust tier, resolve decisively-won contradictions, and block PASS while any
    central claim is unverified or below the required trust tier."""
    gov = _gov(state, ctx)
    req_tier = str(
        _gov_val(gov, "epistemic_governor", "trust_tier_required_for_central_claims", epistemic.T2_OFFICIAL)
    )
    led = _ledger(state, ctx)
    xs = _xs_from_state(state)
    # Promote centrality by POLICY first, so a model self-labelling central=False cannot dodge the
    # PASS-blocking check; then adjudicate, passing the acceptance criteria as the answer's conclusions.
    criteria = list(state.get("acceptance_criteria", []) or [])
    extra = list(state.get("plan", []) or []) + [str(n) for n in state.get("reflection_notes", []) or []]
    led.promote_centrality(criteria, extra_texts=extra)
    adj = confidence.adjudicate(led, xs, required_tier=req_tier, conclusions=criteria, now=_now(ctx))
    state["adjudication"] = adj.to_dict()
    state["contradictions"] = [x.to_dict() for x in xs]  # statuses updated in place
    _save_ledger(state, led)
    ctx.progress(state, ADJUDICATOR)
    return state


def node_synthesis(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Research synthesis: an evidence-grounded report that keeps confirmed facts, likely
    conclusions, assumptions and contradictions strictly separate."""
    led = _ledger(state, ctx)
    rep = research_mode.synthesize(led, _xs_from_state(state), topic=state.get("task", ""), now=_now(ctx))
    state["research_report"] = research_mode.render_markdown(rep, topic=state.get("task", ""))
    state["research_report_obj"] = rep.to_dict()
    _save_ledger(state, led)
    ctx.progress(state, SYNTHESIS)
    return state


def node_stability_controller(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Detect repeated failures, patch oscillation, and diminishing returns; record for routing."""
    gov = _gov(state, ctx)
    thr = int(_gov_val(gov, "stability_controller", "repeated_failure_threshold", 3))
    state["stability"] = stability.analyze(state, repeated_failure_threshold=thr)
    ctx.progress(state, STABILITY_CONTROLLER)
    return state


# ============================== NODES ==============================


def node_project_scan(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    state["project_profile"] = project_detect.detect_project(state["repo_path"])
    configured = set(project_detect.configured_gates(state["project_profile"]))
    req = state.get("required_gates") or []
    if state.get("required_gates_explicit"):
        # The user demanded these gates (e.g. --threshold lint+typecheck): keep every one. Any that
        # the project does not configure will surface as NOT_CONFIGURED (a warning, not a silent PASS)
        # — never drop a demanded gate, which would let the run go green without running it.
        state["required_gates"] = list(req)
    else:
        # Default gate set: narrow to what's actually configured (don't fail a Python lib on a
        # missing 'build'), falling back to the configured set if none of the defaults apply.
        state["required_gates"] = [g for g in req if g in configured] or list(configured)
    ctx.progress(state, PROJECT_SCAN)
    return state


def node_tool_router(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Record the deprecated no-op host-planning decision."""
    cfg = tool_router.RouterConfig.from_dict(state.get("tool_router_config") or ctx.router_config or None)
    if not cfg.enabled:
        state["router_decision"] = {"enabled": False}
        ctx.progress(state, TOOL_ROUTER)
        return state
    decision = tool_router.plan_from_state(
        state,
        risk=str(state.get("risk", "low")),
    )
    state["router_decision"] = decision.to_dict()
    state["blocking_gates"] = []
    state.setdefault("router_trace", []).append(
        {
            "iteration": state.get("iteration"),
            "changed_files": list(decision.changed_files),
            "verification_mode": decision.verification_mode,
        }
    )
    ctx.progress(state, TOOL_ROUTER)
    return state


def node_quality_contract(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    if not state.get("acceptance_criteria"):
        state["acceptance_criteria"] = [f"Implement and verify: {state.get('task', '').strip()}"]
    state["quality_contract"] = render_contract(state)
    ctx.progress(state, QUALITY_CONTRACT)
    return state


def node_planning(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    from .providers import parse_json_blob

    system = "Plan the smallest coherent slice to satisfy the acceptance criteria. Respond ONLY as a JSON array of short step strings."
    raw = ctx.provider.complete(
        system, f"TASK: {state.get('task', '')}\nCRITERIA: {state.get('acceptance_criteria')}", tag="plan"
    )
    blob = parse_json_blob(raw)
    state["plan"] = (
        [str(x) for x in blob] if isinstance(blob, list) else [raw.strip() or "Implement the task."]
    )
    ctx.progress(state, PLANNING)
    return state


def node_generation(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Standalone-runner generation.

    Real file edits are performed by an injected ``generation_hook`` (e.g. a tool-enabled agent),
    or by the Claude Code skill in Layer 1. With no hook this is a recorded no-op so the loop and
    routing remain fully exercisable offline.
    """
    if ctx.generation_hook:
        changed = ctx.generation_hook(state, ctx) or []
        for f in changed:
            if f not in state["changed_files"]:
                state["changed_files"].append(f)
    else:
        ctx.provider.complete(
            "You are the generator.",
            f"PLAN: {state.get('plan')}\nREFLECTION: {state.get('reflection_notes')}",
            tag="generate",
        )
    ctx.progress(state, GENERATION)
    return state


def _retry_transient_gates(
    results: list[checks.CommandResult], state: dict[str, Any], ctx: RunContext, max_reruns: int
) -> list[checks.CommandResult]:
    """Rerun a core gate that failed for a TRANSIENT reason (timeout/rate-limit/503) up to
    ``max_reruns`` times. A genuine CODE_FAILURE (assertion/traceback) is never retried.

    Crucially, the **tests** gate is NEVER auto-passed on a fail-then-pass: a test that only passes on
    rerun is *flaky*, and flaky is a real defect — masking it as green would be a false PASS. So a flaky
    tests gate keeps its FAIL and is flagged loudly. For deterministic tool gates (lint/typecheck/build)
    a transient invocation blip that recovers on rerun IS accepted, so infra noise cannot burn the budget.
    Wires ``classify_tool_failure`` / ``is_retryable`` / ``classify_flaky``.
    """
    cmds = (state.get("project_profile") or {}).get("commands") or {}
    repo = state["repo_path"]
    out: list[checks.CommandResult] = []
    for r in results:
        kind = stability.classify_tool_failure(f"{r.summary} {r.stderr}", r.exit_code)
        command = cmds.get(checks.GATE_TO_CMD_KEY.get(r.gate, r.gate))
        if r.result not in ("FAIL", "ERROR") or not stability.is_retryable(kind) or not command:
            out.append(r)
            continue
        reruns = max_reruns if r.gate == "tests" else 1
        outcomes = [False]
        passed: checks.CommandResult | None = None
        for _ in range(max(1, reruns)):
            rr = ctx.runner(r.gate, command, repo)
            outcomes.append(rr.result == "PASS")
            if rr.result == "PASS":
                passed = rr
                break
        flaky = stability.classify_flaky(outcomes) == "flaky"
        if r.gate == "tests" and flaky:
            # a flaky test must NOT go green — keep the FAIL, surface it as a defect to fix
            flag = (
                f"flaky test gate ({kind}): failed then passed on rerun — NOT auto-passed; needs a real fix"
            )
            _append_flag(state, flag)
            out.append(r)
        elif passed is not None:
            if flaky:
                _append_flag(state, f"flaky/transient gate '{r.gate}' ({kind}) recovered on rerun — advisory")
            out.append(passed)
        else:
            out.append(r)
    return out


def _append_flag(state: dict[str, Any], flag: str) -> None:
    if flag not in (state.get("risk_flags") or []):
        state.setdefault("risk_flags", []).append(flag[:200])


def node_verification(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    results = checks.run_gates(
        state["project_profile"],
        state["repo_path"],
        required_gates=state.get("required_gates"),
        runner=ctx.runner,
    )
    # Transient (network/timeout) gate failures are reruns of a blip, not a code failure: retry once
    # (or up to flaky_test_reruns for the tests gate) so infra noise cannot consume the budget.
    gov = _gov(state, ctx)
    if _gov_val(gov, "stability_controller", "retry_transient_tool_failures_once", True):
        results = _retry_transient_gates(
            results, state, ctx, int(_gov_val(gov, "stability_controller", "flaky_test_reruns", 3))
        )
    # Optional gates selected by the tool router (argv-based, diff-scoped, safe). Unavailable
    # binaries are skipped (NOT_CONFIGURED), advisory failures recorded but non-gating.
    opt_specs = (state.get("router_decision") or {}).get("selected_gates", []) or []
    opt_results: list[checks.CommandResult] = []
    if ctx.execute_optional_gates and opt_specs:
        opt_results = checks.run_optional_gates(opt_specs, state["repo_path"], runner_argv=ctx.argv_runner)
    all_results = results + opt_results

    state["verification_results"] = [r.to_dict() for r in all_results]
    for r in all_results:
        if r.command:
            state["command_history"].append({"gate": r.gate, "command": r.command, "exit": r.exit_code})
    # Signature over BLOCKING gates only (core required + blocking optional) so advisory-gate noise
    # cannot destabilize consecutive-failure stuck detection.
    blocking = set(state.get("required_gates", []) or []) | set(state.get("blocking_gates", []) or [])
    sig_source = [r.to_dict() for r in all_results if r.gate in blocking] or [r.to_dict() for r in results]
    sig = reflection.iteration_signature(sig_source)
    if sig:
        state["failure_signatures"].append(sig)
    # deterministic anti-gaming: detect tests weakened/deleted/skipped to pass (read-only git diff)
    weakened, ev = checks.detect_test_weakening(state["repo_path"])
    state["tests_weakened"] = weakened
    if weakened:
        flag = "tests_weakened: " + "; ".join(ev)
        if flag not in state["risk_flags"]:
            state["risk_flags"].append(flag[:200])
    # epistemic: deterministic gate results become T0 confirmed claims (evidence, not vibes)
    if _epistemic_enabled(gov):
        _record_gate_claims(state, all_results, ctx)
    ctx.progress(state, VERIFICATION)
    return state


def node_evaluator(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    ev = evaluator.evaluate(state, ctx.provider)
    state["evaluator_score"] = ev["score"]
    state["evaluator_feedback"] = ev["feedback"]
    ctx.progress(state, EVALUATOR)
    return state


def node_reflection(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    state["reflection_notes"].extend(reflection.reflect(state, ctx.provider))
    state["iteration"] = int(state.get("iteration", 0)) + 1
    ctx.progress(state, REFLECTION)
    return state


def node_stuck_analysis(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    state["risk_flags"].append("stuck: same failure repeated — needs a different approach (human-gate)")
    state["stop_reason"] = STOP_STUCK
    ctx.progress(state, STUCK_ANALYSIS)
    return state


def node_human_gate(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    if state.get("stop_reason") in (None, "in progress"):
        state["stop_reason"] = STOP_BLOCKED
    state["final_summary"] = (
        "BLOCKED at human gate: a risky/destructive action or repeated failure needs human approval. "
        f"Risk flags: {state.get('risk_flags')}"
    )
    ctx.progress(state, HUMAN_GATE)
    return state


def _node_final_review(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Render an accepted result; only ``_finalize`` may call this terminal host helper."""
    weak = _has_warnings(state)
    state["stop_reason"] = STOP_PASS_WITH_WARNINGS if weak else STOP_PASS
    unconfigured = _unconfigured_required_gates(state)
    if unconfigured:
        reason = f"PASS_WITH_WARNINGS: required gate(s) {unconfigured} are NOT_CONFIGURED in this repo — demanded but not run."
    elif weak:
        reason = "PASS_WITH_WARNINGS: gates green but verification is weak (e.g. no tests configured)."
    else:
        reason = "PASS: all required quality gates satisfied."
    state["final_summary"] = (
        reason + f" Iterations used: {state.get('iteration')}/{state.get('max_iterations')}."
    )
    ctx.progress(state, FINAL_REVIEW)
    return state


def node_failure_report(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    state["stop_reason"] = STOP_MAX_ITERS
    _passed, reasons = evaluator.passes_quality_gate(
        state.get("verification_results", []),
        state.get("evaluator_score"),
        _effective_required_gates(state),
        state.get("quality_threshold", 0.90),
        tests_weakened=bool(state.get("tests_weakened", False)),
    )
    state["final_summary"] = (
        f"FAILED_MAX_ITERS after {state.get('iteration')}/{state.get('max_iterations')} iterations. "
        f"Outstanding: {reasons}"
    )
    ctx.progress(state, FAILURE_REPORT)
    return state


def _unconfigured_required_gates(state: dict[str, Any]) -> list[str]:
    """Required gates that produced a NOT_CONFIGURED result — i.e. demanded but not actually run."""
    required = set(state.get("required_gates", []) or [])
    by_gate = {r.get("gate"): r for r in state.get("verification_results", [])}
    return [g for g in required if str((by_gate.get(g) or {}).get("result", "")).upper() == "NOT_CONFIGURED"]


def _has_warnings(state: dict[str, Any]) -> bool:
    profile = state.get("project_profile", {}) or {}
    if not profile.get("has_tests", False):
        return True
    # Any required gate that did not actually run (NOT_CONFIGURED) downgrades a clean PASS to a warning.
    if _unconfigured_required_gates(state):
        return True
    for r in state.get("verification_results", []):
        if r.get("gate") == "tests" and str(r.get("result", "")).upper() == "NOT_CONFIGURED":
            return True
    return False


# ============================== CODEX ENRICHMENT NODES ==============================
# Codex is a second independent agentic worker (review/patch/adversarial). Every node here is a
# NO-OP unless ctx.codex.enabled AND `codex` is on PATH. Codex output is advisory — deterministic
# gates remain the final authority.


def _codex_ctx(state: dict[str, Any]) -> dict[str, Any]:
    failing = [
        r
        for r in state.get("verification_results", [])
        if str(r.get("result", "")).upper() in ("FAIL", "ERROR")
    ]
    return {
        "task": state.get("task", ""),
        "acceptance": "; ".join(state.get("acceptance_criteria", [])) or "(none)",
        "gates": ", ".join(state.get("required_gates", [])) or "(none)",
        "failures": str(failing or state.get("evaluator_feedback", ""))[:1500],
        "review": " ".join(state.get("codex_notes", [])[-2:]) or "(none)",
    }


def _record_codex(state: dict[str, Any], res: codex_bridge.CodexResult) -> None:
    state["codex_calls_total"] = int(state.get("codex_calls_total", 0)) + 1
    state["codex_calls_this_iter"] = int(state.get("codex_calls_this_iter", 0)) + 1
    note = f"[{res.label}] {res.summary[:400]}" if res.summary else f"[{res.label}] exit={res.exit_code}"
    state.setdefault("codex_notes", []).append(note)


def _codex_enrich(
    state: dict[str, Any], ctx: RunContext, trigger: str, kind: str, node_name: str
) -> dict[str, Any]:
    """Run a read-only Codex review/adversarial/final pass if enabled and within budget."""
    cfg = ctx.codex
    if codex_bridge.should_invoke(state, cfg, trigger):
        prompt = codex_bridge.render_prompt(kind, _codex_ctx(state))
        res = codex_bridge.run_codex(
            prompt,
            cwd=state["repo_path"],
            sandbox=codex_bridge.SANDBOX_READ_ONLY,
            config=cfg,
            run_dir=ctx.run_dir,
            label=node_name,
        )
        if not res.skipped:
            _record_codex(state, res)
    ctx.progress(state, node_name)
    return state


def node_codex_review(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return _codex_enrich(state, ctx, codex_bridge.TRIGGER_FIRST_FAILURE, "review", CODEX_REVIEW)


def node_codex_adversarial(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return _codex_enrich(state, ctx, codex_bridge.TRIGGER_REPEATED, "adversarial", CODEX_ADVERSARIAL)


def node_codex_final_review(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    return _codex_enrich(state, ctx, codex_bridge.TRIGGER_BEFORE_FINAL, "final", CODEX_FINAL_REVIEW)


def node_security_review(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Lightweight deterministic security pass over changed files (secrets/destructive patterns).

    Heavy review is the `evalopt-security-reviewer` subagent (Layer 1) or Codex adversarial mode.
    """
    import re as _re

    secret_re = _re.compile(
        r"(AKIA[0-9A-Z]{12,})|(sk-[A-Za-z0-9]{20,})|(-----BEGIN [A-Z ]*PRIVATE KEY-----)|(password\s*=\s*['\"][^'\"]{6,})",
        _re.I,
    )
    destructive_re = _re.compile(
        r"\brm\s+-rf\b|\bgit\s+reset\s+--hard\b|\bgit\s+clean\b|\bDROP\s+TABLE\b|\bgit\s+push\s+--force\b",
        _re.I,
    )
    repo = state.get("repo_path", "")
    for rel in state.get("changed_files", [])[:50]:
        path = rel if os.path.isabs(rel) else os.path.join(repo, rel)
        try:
            if not os.path.isfile(path):
                continue
            text = open(path, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        if secret_re.search(text):
            flag = f"security: possible secret in {rel}"
            if flag not in state["risk_flags"]:
                state["risk_flags"].append(flag)
        if destructive_re.search(text):
            flag = f"destructive: risky command in {rel}"
            if flag not in state["risk_flags"]:
                state["risk_flags"].append(flag)
    ctx.progress(state, SECURITY_REVIEW)
    return state


# ============================== PURE-PYTHON BACKEND ==============================


def run(state: dict[str, Any], ctx: RunContext | None = None) -> dict[str, Any]:
    """Top-level entrypoint: classify the task and dispatch to the build loop or the research loop.

    Build/mixed → :func:`run_loop`; research → :func:`run_research_loop`. ``run_loop`` itself also
    dispatches, so calling either directly is safe and back-compatible.
    """
    return run_loop(state, ctx)


def run_loop(state: dict[str, Any], ctx: RunContext | None = None) -> dict[str, Any]:
    """Execute the graph in pure Python. No LangGraph dependency. Bounded by ``max_iterations``.

    Build mode by default. ``goal_intake`` may classify the task as research (→ research loop) or
    mixed (→ a research pre-pass then the build loop)."""
    ctx = ctx or RunContext()
    ctx._issued_record_sha256.clear()
    ctx._validated_record_sha256 = frozenset()
    state = node_goal_intake(state, ctx)
    gov = _gov(state, ctx)
    if state.get("mode") == "research":
        return run_research_loop(state, ctx)
    if _epistemic_enabled(gov):
        state = node_assumption_extraction(state, ctx)
        if state.get("mode") == "mixed":
            state = _research_prepass(state, ctx)  # front-load evidence, then build
    state = node_project_scan(state, ctx)
    state = node_tool_router(state, ctx)  # initial plan (task-signal + any pre-existing diff)
    state = node_quality_contract(state, ctx)
    state = node_planning(state, ctx)

    # absolute backstop independent of routing logic (defense in depth)
    hard_cap = int(state.get("max_iterations", 6)) + 2
    unatt = _unatt(state)
    max_hours = float(unatt.get("max_wall_clock_hours", 8))
    steps = 0
    while True:
        steps += 1
        # unattended wall-clock budget: stop cleanly with a morning report (never hang overnight)
        if _unattended_on(state) and unattended.wall_clock_exceeded(
            state.get("started_at", ""), _now(ctx), max_hours
        ):
            state["stop_reason"] = STOP_WALL_CLOCK
            state["final_summary"] = (
                f"WALL_CLOCK: stopped after ~{unattended.elapsed_hours(state.get('started_at', ''), _now(ctx))}h "
                f"(budget {max_hours}h). Safe work committed to the working tree; see morning report."
            )
            _react(
                state,
                ctx,
                STABILITY_CONTROLLER,
                action="budget",
                observation="wall-clock exceeded",
                decision="stop",
            )
            return _unattended_finish(state, ctx)
        try:
            state["codex_calls_this_iter"] = 0
            state = node_generation(state, ctx)
            state = node_tool_router(state, ctx)  # refresh: re-scope gates to the latest diff
            if _unattended_on(state):
                _build_retrieval_pack(state, ctx)  # context hygiene: regenerate before verifying/patching
            state = node_verification(state, ctx)
            state = node_evaluator(state, ctx)
            state = node_stability_controller(state, ctx)  # oscillation/repeated-failure signals for route()
            _react(
                state,
                ctx,
                VERIFICATION,
                action="run_gates",
                observation=",".join(
                    f"{r.get('gate')}={r.get('result')}" for r in state.get("verification_results", [])
                ),
                decision="route",
            )
            nxt = route(state)

            if nxt == FINAL_REVIEW:
                return _finalize(state, ctx)
            if nxt == FAILURE_REPORT:
                state = node_failure_report(state, ctx)
                return _unattended_finish(state, ctx) if _unattended_on(state) else state
            if nxt == STUCK_ANALYSIS:
                state = node_codex_adversarial(state, ctx)  # red-team the repeated failure
                state = node_stuck_analysis(state, ctx)
                return _unattended_park(state, ctx) if _unattended_on(state) else node_human_gate(state, ctx)
            if nxt == HUMAN_GATE:
                return _unattended_park(state, ctx) if _unattended_on(state) else node_human_gate(state, ctx)
            if nxt == REFLECTION:
                # Model-host mutation and patch scheduling belong to the embedding runtime.
                cmode = ctx.codex.mode
                if cmode == "review":
                    state = node_codex_review(state, ctx)
                elif cmode == "adversarial":
                    state = node_codex_adversarial(state, ctx)
                state = node_reflection(state, ctx)
        except Exception as exc:  # never hang: a mid-iteration crash yields a terminal state + report
            return _handle_crash(state, ctx, exc, steps)

        if steps > hard_cap:  # should never trigger; routing already bounds the loop
            state["stop_reason"] = STOP_MAX_ITERS
            state["final_summary"] = "Hard backstop tripped — routing failed to terminate."
            return state


def _handle_crash(state: dict[str, Any], ctx: RunContext, exc: Exception, steps: int) -> dict[str, Any]:
    """Turn an unhandled mid-iteration exception into a terminal, reported outcome. Unattended runs
    finish cleanly with a morning report (never a silent hang); attended runs re-raise after recording,
    so the crash still surfaces to the caller."""
    state["stop_reason"] = STOP_CRASHED
    state["final_summary"] = f"CRASHED mid-iteration (step {steps}): {type(exc).__name__}: {exc}"[:400]
    flag = f"crash: {type(exc).__name__}"
    if flag not in (state.get("risk_flags") or []):
        state.setdefault("risk_flags", []).append(flag[:200])
    _react(state, ctx, STABILITY_CONTROLLER, action="crash", observation=str(exc)[:120], decision="stop")
    if _unattended_on(state):
        return _unattended_finish(state, ctx)
    raise exc


def _kernel_acceptance(state: dict[str, Any], ctx: RunContext) -> kernel.AcceptanceDecision:
    led = _ledger(state, ctx)
    authority, _adapters = _authority(state, ctx)
    gov = _gov(state, ctx)
    criteria = tuple(state.get("acceptance_criteria", []) or [])
    extra = list(state.get("plan", []) or []) + [
        str(note) for note in state.get("reflection_notes", []) or []
    ]
    resolved_losers = {
        claim_id
        for item in state.get("contradictions", [])
        if item.get("status") == "resolved"
        for claim_id in item.get("claim_ids", [])
        if claim_id != item.get("resolution")
    }
    disqualified_claim_ids = {
        claim.id
        for claim in led.claims()
        if claim.status
        in {
            epistemic.STATUS_SUPERSEDED,
            epistemic.STATUS_CONTRADICTED,
            epistemic.STATUS_REJECTED,
            epistemic.STATUS_STALE,
        }
    }
    claims = []
    required_claim_ids = []
    for claim in led.claims():
        # User requirements are policy input, and controller gate observations are represented by
        # gate_results below. Requiring a second evidence attestation for either would duplicate the
        # same authority decision and can turn an ordinary passing gate into UNVERIFIED.
        controller_requirement = (
            claim.type == "user_requirement"
            and claim.source_type == "user"
            and claim.created_by == "goal_intake"
        )
        controller_gate = claim.created_by == "verification" and claim.source_type in {
            "test_result",
            "command_output",
        }
        if controller_requirement or controller_gate or claim.id in resolved_losers:
            continue
        if epistemic.derive_centrality(claim, criteria, extra_texts=extra):
            required_claim_ids.append(claim.id)
        assessment_ids = tuple(
            source.support_assessment_id
            for ref in claim.evidence_refs
            if (source := led.sources.get(ref)) and source.support_assessment_id
        )
        claims.append(
            kernel.ClaimRecord(
                id=claim.id,
                text=claim.text,
                claim_type=claim.type,
                subject=claim.subject,
                stance=claim.stance,
                assessment_ids=assessment_ids,
            )
        )
    policy = kernel.GovernancePolicy(
        required_gates=tuple(_effective_required_gates(state)),
        minimum_trust=str(
            _gov_val(
                gov,
                "epistemic_governor",
                "trust_tier_required_for_central_claims",
                epistemic.T2_OFFICIAL,
            )
        ),
        quality_threshold=float(state.get("quality_threshold", 0.90)),
        # The compatibility host has always treated an unavailable model rubric as advisory. A
        # present score still has to meet the threshold; stable API consumers can require one.
        require_evaluator=False,
        required_claim_ids=tuple(required_claim_ids),
        disqualified_claim_ids=tuple(sorted(disqualified_claim_ids)),
        allowed_authority_policies=authority.policy_hashes,
        authorized_record_sha256=tuple(sorted(ctx._validated_record_sha256)),
    )
    input_ = kernel.AcceptanceInput(
        observed_at=_now(ctx),
        gate_results=tuple(
            (str(result.get("gate", "")), str(result.get("result", "")))
            for result in state.get("verification_results", [])
        ),
        criteria=criteria,
        claims=tuple(claims),
        contradictions=tuple(
            (str(item.get("id", "")), str(item.get("severity", "")), str(item.get("status", "")))
            for item in state.get("contradictions", [])
        ),
        attestations=tuple(led.attestations.values()),
        assessments=tuple(led.support_assessments.values()),
        tests_weakened=bool(state.get("tests_weakened")),
        evaluator_score=state.get("evaluator_score"),
    )
    decision = kernel.evaluate_acceptance(policy, input_)
    state["kernel_decision"] = decision.to_dict()
    return decision


def _finalize(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """Before declaring PASS: Codex final review -> security review -> epistemic adjudication
    (contradiction search + central-claim check) -> human gate or final review.

    A final PASS is BLOCKED while a central claim is unverified or below the required trust tier."""
    state = node_codex_final_review(state, ctx)
    state = node_security_review(state, ctx)
    gov = _gov(state, ctx)
    # Evidence authorization is rebuilt from current adapter material on every terminal path.
    state = node_source_verifier(state, ctx)
    if _epistemic_enabled(gov):
        # Source verification + central-claim adjudication ALWAYS run when the epistemic governor is
        # enabled — the PASS-block on an unverified central claim must not be silently bypassable by
        # turning off contradiction search. Only the (more expensive) contradiction hunt is gated behind
        # ``require_contradiction_search_before_final``.
        if _gov_val(gov, "epistemic_governor", "require_contradiction_search_before_final", True):
            state = node_contradiction_hunter(state, ctx)
        state = node_adjudicator(state, ctx)
    decision = _kernel_acceptance(state, ctx)
    if decision.status != "ACCEPTED":
        reasons = "; ".join(decision.reasons)
        state["stop_reason"] = STOP_UNVERIFIED
        flag = f"governance: {decision.status.lower()} — PASS blocked ({reasons})"
        if flag not in state["risk_flags"]:
            state["risk_flags"].append(flag[:200])
        state["final_summary"] = f"{decision.status}: canonical kernel refused PASS. {reasons}"
        _persist_knowledge(state, ctx)
        return _unattended_finish(state, ctx) if _unattended_on(state) else state
    if _needs_human_gate(state):  # security/destructive flag found at the gate
        if _unattended_on(state):
            return _unattended_park(state, ctx)
        return node_human_gate(state, ctx)
    state = _node_final_review(state, ctx)
    _persist_knowledge(state, ctx)
    return _unattended_finish(state, ctx) if _unattended_on(state) else state


def _research_prepass(state: dict[str, Any], ctx: RunContext) -> dict[str, Any]:
    """One evidence-gathering round used by mixed mode before the build loop begins."""
    state = node_research_planner(state, ctx)
    state = node_parallel_investigation(state, ctx)
    state = node_source_verifier(state, ctx)
    state = node_contradiction_hunter(state, ctx)
    state = node_adjudicator(state, ctx)
    return state


def run_research_loop(state: dict[str, Any], ctx: RunContext | None = None) -> dict[str, Any]:
    """Bounded research executor: plan -> investigate -> verify -> hunt contradictions -> adjudicate,
    repeated until coverage is met, returns diminish, or ``max_research_rounds`` is hit. Produces an
    evidence-grounded synthesis (never a deterministic PASS)."""
    ctx = ctx or RunContext()
    ctx._issued_record_sha256.clear()
    ctx._validated_record_sha256 = frozenset()
    if not state.get("task_class"):
        state = node_goal_intake(state, ctx)
    gov = _gov(state, ctx)
    if ctx.investigation_hook is None:
        state["research_backend"] = "pure_executor:no investigation adapter"
    else:
        state["research_backend"] = "pure_executor (hook-provided evidence)"
    state = node_assumption_extraction(state, ctx)

    max_rounds = int(
        _gov_val(gov, "epistemic_governor", "max_research_rounds", state.get("max_research_rounds", 4))
    )
    stop_low_gain = bool(_gov_val(gov, "stability_controller", "stop_on_low_information_gain", True))
    unatt = _unatt(state)
    max_hours = float(unatt.get("max_wall_clock_hours", 8))

    while int(state.get("research_round", 0)) < max_rounds:
        if _unattended_on(state) and unattended.wall_clock_exceeded(
            state.get("started_at", ""), _now(ctx), max_hours
        ):
            state["stop_reason"] = STOP_WALL_CLOCK
            break
        state["research_round"] = int(state.get("research_round", 0)) + 1
        before = _confirmed_count(state, ctx)
        state = node_research_planner(state, ctx)
        state = node_parallel_investigation(state, ctx)
        state = node_source_verifier(state, ctx)
        state = node_contradiction_hunter(state, ctx)
        after = _confirmed_count(state, ctx)
        state.setdefault("confirmed_gain_history", []).append(after - before)
        state = node_stability_controller(state, ctx)
        state = node_adjudicator(state, ctx)

        led = _ledger(state, ctx)
        passed, _reasons = research_mode.passes_research_gate(
            led, _xs_from_state(state), questions=state.get("research_questions"), now=_now(ctx)
        )
        blocks = bool(state.get("adjudication", {}).get("blocks_pass"))
        if passed and not blocks:
            break
        # consume the stability controller's already-computed signal (set by node_stability_controller
        # above) rather than recomputing it, so the node's output is not write-only
        if stop_low_gain and (state.get("stability") or {}).get("low_information_gain"):
            break

    state = node_adjudicator(state, ctx)  # final pass over the full ledger
    state = node_synthesis(state, ctx)

    led = _ledger(state, ctx)
    passed, reasons = research_mode.passes_research_gate(
        led, _xs_from_state(state), questions=state.get("research_questions"), now=_now(ctx)
    )
    if state.get("stop_reason") == STOP_WALL_CLOCK:
        pass  # wall-clock stop already set
    elif int(state.get("research_round", 0)) >= max_rounds and not passed:
        state["stop_reason"] = STOP_MAX_RESEARCH_ROUNDS
    else:
        state["stop_reason"] = STOP_RESEARCH_SYNTHESIS
    state["final_summary"] = (
        f"RESEARCH_SYNTHESIS after {state.get('research_round')}/{max_rounds} round(s) "
        f"[backend: {state.get('research_backend')}]. "
        + ("Open items: " + "; ".join(reasons) if reasons else "Coverage + source criteria satisfied.")
    )
    _react(state, ctx, SYNTHESIS, action="synthesize", observation=state["final_summary"], decision="stop")
    _persist_knowledge(state, ctx)
    if _unattended_on(state):
        return _unattended_finish(state, ctx)
    ctx.progress(state, SYNTHESIS)
    return state


def _persist_knowledge(state: dict[str, Any], ctx: RunContext) -> None:
    """Write compatibility evidence artifacts and materialize the append-only knowledge ledger."""
    if not ctx.run_dir:
        return
    import json as _json

    led = _ledger(state, ctx)
    # knowledge dir is append-only and already written incrementally when ctx.knowledge_dir is set;
    # here we additionally snapshot the run-scoped reports.
    try:
        os.makedirs(ctx.run_dir, exist_ok=True)
        if state.get("research_report"):
            _write(ctx.run_dir, "evidence_pack.md", state["research_report"])
        _write(
            ctx.run_dir,
            "confidence_report.md",
            "# Confidence report\n\n"
            + "\n".join(
                f"- {c.id} [{c.status}] conf={c.confidence:.2f} :: {c.text[:100]}" for c in led.claims()
            ),
        )
        _write(
            ctx.run_dir,
            "contradiction_report.md",
            "# Contradictions\n\n"
            + (
                "\n".join(
                    f"- [{x.get('status')}] {x.get('summary')}" for x in state.get("contradictions", [])
                )
                or "- none"
            ),
        )
        _write(
            ctx.run_dir,
            "claim_graph.md",
            "# Claim graph\n\n"
            + "\n".join(
                f"- {c.id} ({c.type}/{c.status}) <- evidence {c.evidence_refs} used_by {c.used_by}"
                for c in led.claims()
            ),
        )
        # also dump the knowledge snapshot for convenience
        with open(os.path.join(ctx.run_dir, "knowledge_snapshot.json"), "w", encoding="utf-8") as fh:
            _json.dump(led.snapshot(), fh, indent=2, default=str)
    except Exception:
        pass


def _write(directory: str, name: str, content: str) -> None:
    with open(os.path.join(directory, name), "w", encoding="utf-8") as fh:
        fh.write(content or "")


# ============================== REMOVED LANGGRAPH COMPATIBILITY ==============================


def build_graph(ctx: RunContext | None = None):
    """Removed: the experimental backend never reached behavioral parity."""
    del ctx
    raise RuntimeError("LangGraph backend removed; use the pure host adapter and stable kernel API")


# ============================== contract rendering ==============================


def render_contract(state: dict[str, Any]) -> str:
    p = state.get("project_profile", {}) or {}
    c = p.get("commands", {}) or {}
    crit = "\n".join(f"- [ ] {x}" for x in state.get("acceptance_criteria", [])) or "- [ ] (none yet)"
    return f"""# Quality Contract
- Task: {state.get("task", "")}
## Acceptance criteria
{crit}
## Detected project
- Type: {p.get("type")} | Package manager: {p.get("package_manager")}
- Test: {c.get("test")} | Lint: {c.get("lint")} | Typecheck: {c.get("typecheck")} | Build: {c.get("build")}
- Has tests: {p.get("has_tests")}
## Quality gates (required)
- {", ".join(state.get("required_gates", [])) or "(none configured)"}
- Evaluator score threshold: {state.get("quality_threshold")}
- No weakened/deleted/skipped tests; no faked success; no secrets; no new security risk.
## Run state
- Iteration: {state.get("iteration")} / {state.get("max_iterations")}
- Stop reason: {state.get("stop_reason")}
## Evaluator rubric
- Correctness vs criteria (0.40) · Tests genuinely pass & not weakened (0.25) ·
  Lint/typecheck/build (0.15) · Safety (0.10) · Scope discipline (0.10)
"""
