"""Epistemic governor tests: claim ledger, source verification, contradictions, adjudication,
research mode, stability, and loop integration. Pure: no network, no LangGraph, no API key."""

from __future__ import annotations

from evalopt_graph import (
    ClaimLedger,
    MockProvider,
    RunContext,
    adjudicate,
    classify_task,
    epistemic,
    find_contradictions,
    new_state,
    passes_research_gate,
    research_mode,
    run_loop,
    run_research_loop,
    stability,
    synthesize,
    verify_claim,
    verify_ledger,
)
from evalopt_graph.attestation import (
    AdapterPolicy,
    EvidenceAuthority,
    RecordedEvidenceAdapter,
    RetrievedArtifact,
)
from evalopt_graph.checks import CommandResult
from evalopt_graph.graph import node_parallel_investigation
from evalopt_graph.state import STOP_MAX_RESEARCH_ROUNDS, STOP_PASS, STOP_RESEARCH_SYNTHESIS, STOP_UNVERIFIED

NOW = "2026-06-27T00:00:00+00:00"


def _led(**kw):
    return ClaimLedger(now=lambda: NOW, **kw)


def _runner_pass(gate, command, cwd):
    return CommandResult(gate, command, 0, "PASS", "ok")


def _runner_fail(gate, command, cwd):
    return CommandResult(gate, command, 1, "FAIL", "boom")


def _recorded_docs(records: dict[str, str]) -> EvidenceAuthority:
    policy = AdapterPolicy(
        adapter_id="recorded-docs",
        adapter_version="1",
        source_kind="official_docs",
        trust_tier=epistemic.T2_OFFICIAL,
        retrieval_mechanism="recorded_tool_result",
        parser_identity="text/plain@1",
        freshness_required=True,
    )
    return EvidenceAuthority(
        [
            RecordedEvidenceAdapter(
                policy,
                {
                    locator: RetrievedArtifact(
                        content=text.encode(),
                        final_locator=locator,
                        retrieved_at=NOW,
                        media_type="text/plain",
                    )
                    for locator, text in records.items()
                },
            )
        ],
        now=lambda: NOW,
    )


# ---------------- reliance rules: usable vs unusable ----------------


def test_unverified_claim_is_not_usable_as_evidence():
    led = _led()
    c = led.add_claim("X is true", type="model_inference", source_type="claude_inference")
    assert c.status == epistemic.STATUS_UNVERIFIED
    assert led.usable_claims(NOW) == []  # excluded
    assert c.id not in [u.id for u in led.usable_claims(NOW)]


def test_downstream_premises_exclude_unverified_by_default():
    led = _led()
    led.add_claim("unverified guess", source_type="claude_inference")
    src = led.add_source(
        kind="official_docs", summary="documented fact about widget", trust_tier=epistemic.T2_OFFICIAL
    )
    confirmed = led.add_claim(
        "widget fact", type="api_fact", source_type="official_docs", subject="widget", evidence_refs=[src.id]
    )
    verify_ledger(led, now=NOW)
    premises = led.premises_for("generator", now=NOW)
    ids = {c.id for c in premises}
    assert confirmed.id in ids
    assert all(c.status == epistemic.STATUS_CONFIRMED for c in premises)


def test_user_provided_confirmed_but_deterministic_type_needs_real_source():
    led = _led()
    u = led.add_claim("must support refresh tokens", type="user_requirement", source_type="user")
    assert u.status == epistemic.STATUS_CONFIRMED  # the user is authoritative at creation
    # a deterministic-TYPED claim with NO real Source is NOT auto-confirmed (no self-certification)
    d0 = led.add_claim("tests pass", type="test_result", source_type="test_result", subject="suite")
    assert d0.status == epistemic.STATUS_UNVERIFIED
    status0, _ = verify_claim(d0, led.sources, now=NOW)
    assert status0 == epistemic.STATUS_UNVERIFIED
    # ... but a real, relevant T0 source verifies it to confirmed (evidence, not a self-declared type)
    ts = led.add_source(
        kind="test_output",
        locator="pytest",
        summary="suite tests pass",
        trust_tier=epistemic.T0_DETERMINISTIC,
    )
    d1 = led.add_claim(
        "suite tests pass",
        type="test_result",
        source_type="test_result",
        subject="suite",
        evidence_refs=[ts.id],
    )
    status1, _ = verify_claim(d1, led.sources, now=NOW)
    assert status1 == epistemic.STATUS_CONFIRMED


# ---------------- source verification ----------------


def test_model_only_claim_cannot_confirm():
    led = _led()
    src = led.add_source(
        kind="codex_output", summary="codex thinks the api returns json", trust_tier=epistemic.T4_MODEL
    )
    c = led.add_claim(
        "api returns json",
        type="api_fact",
        source_type="claude_inference",
        subject="api",
        evidence_refs=[src.id],
    )
    status, note = verify_claim(c, led.sources, now=NOW)
    assert status == epistemic.STATUS_UNVERIFIED  # model consensus is not proof
    assert "model" in note.lower()


def test_source_verifier_rejects_irrelevant_evidence():
    led = _led()
    irrelevant = led.add_source(
        kind="official_docs",
        summary="totally unrelated zoology of penguins",
        trust_tier=epistemic.T2_OFFICIAL,
    )
    c = led.add_claim(
        "the parser accepts utf8 input",
        type="api_fact",
        source_type="official_docs",
        subject="parser utf8 input",
        evidence_refs=[irrelevant.id],
    )
    status, note = verify_claim(c, led.sources, now=NOW)
    assert status == epistemic.STATUS_UNVERIFIED
    assert "irrelevant" in note.lower() or "no relevant" in note.lower()


def test_relevant_official_source_confirms():
    led = _led()
    src = led.add_source(
        kind="official_docs", summary="parser accepts utf8 input per spec", trust_tier=epistemic.T2_OFFICIAL
    )
    c = led.add_claim(
        "parser accepts utf8 input",
        type="api_fact",
        source_type="official_docs",
        subject="parser utf8 input",
        evidence_refs=[src.id],
    )
    status, _ = verify_claim(c, led.sources, now=NOW)
    assert status == epistemic.STATUS_CONFIRMED


def test_stale_source_fails_freshness_sensitive_claim():
    led = _led()
    old = led.add_source(
        kind="web_page",
        summary="changelog mentions feature flag api",
        trust_tier=epistemic.T2_OFFICIAL,
        freshness_required=True,
        retrieved_at="2020-01-01T00:00:00+00:00",
    )
    c = led.add_claim(
        "feature flag api exists",
        type="api_fact",
        source_type="web_primary_source",
        subject="feature flag api",
        evidence_refs=[old.id],
    )
    status, note = verify_claim(c, led.sources, now=NOW, max_age_seconds=60 * 60 * 24 * 30)
    assert status == epistemic.STATUS_STALE
    assert "stale" in note.lower()


# ---------------- contradictions + adjudication ----------------


def test_t0_deterministic_overrides_model_opinion():
    led = _led()
    ts = led.add_source(
        kind="test_output", summary="login flow test passed", trust_tier=epistemic.T0_DETERMINISTIC
    )
    det = led.add_claim(
        "login works",
        type="test_result",
        source_type="test_result",
        subject="login",
        stance="works",
        evidence_refs=[ts.id],
    )
    model = led.add_claim(
        "login is broken",
        type="model_inference",
        source_type="claude_inference",
        subject="login",
        stance="broken",
    )
    verify_ledger(led, now=NOW)
    xs = find_contradictions(led.claims())
    adjudicate(led, xs, now=NOW)
    assert xs[0].status == "resolved"
    assert xs[0].resolution == det.id  # deterministic side wins
    assert led.get_claim(model.id).status == epistemic.STATUS_SUPERSEDED


def test_equal_tier_contradiction_is_preserved():
    led = _led()
    s1 = led.add_source(
        kind="official_docs",
        summary="A is faster than B in benchmark speed",
        trust_tier=epistemic.T2_OFFICIAL,
    )
    s2 = led.add_source(
        kind="official_docs",
        summary="B is faster than A in benchmark speed",
        trust_tier=epistemic.T2_OFFICIAL,
    )
    led.add_claim(
        "A faster",
        type="research_claim",
        source_type="official_docs",
        subject="speed",
        stance="A_faster",
        evidence_refs=[s1.id],
    )
    led.add_claim(
        "B faster",
        type="research_claim",
        source_type="official_docs",
        subject="speed",
        stance="B_faster",
        evidence_refs=[s2.id],
    )
    verify_ledger(led, now=NOW)
    xs = find_contradictions(led.claims())
    adj = adjudicate(led, xs, now=NOW)
    assert xs[0].status == "unresolved"  # equal trust => preserved, not smoothed away
    assert len(adj.unresolved_contradictions) == 1


def test_subject_grouping_does_not_hide_cross_group_text_negation():
    led = _led()
    first = led.add_claim(
        "The production release is approved",
        type="research_claim",
        subject="release decision",
        stance="approved",
    )
    second = led.add_claim(
        "The production release is delayed",
        type="research_claim",
        subject="release decision",
        stance="delayed",
    )
    third = led.add_claim(
        "The production release is not approved",
        type="research_claim",
        subject="deployment",
        stance="rejected",
    )

    found = find_contradictions(led.claims())
    pairs = {frozenset(item.claim_ids) for item in found}

    assert frozenset((first.id, second.id)) in pairs
    assert frozenset((first.id, third.id)) in pairs
    assert all(item.severity == "high" for item in found)


def test_contradiction_preserved_in_research_report():
    led = _led()
    s1 = led.add_source(kind="official_docs", summary="A faster speed", trust_tier=epistemic.T2_OFFICIAL)
    s2 = led.add_source(kind="official_docs", summary="B faster speed", trust_tier=epistemic.T2_OFFICIAL)
    led.add_claim(
        "A faster",
        type="research_claim",
        source_type="official_docs",
        subject="speed",
        stance="A_faster",
        evidence_refs=[s1.id],
    )
    led.add_claim(
        "B faster",
        type="research_claim",
        source_type="official_docs",
        subject="speed",
        stance="B_faster",
        evidence_refs=[s2.id],
    )
    verify_ledger(led, now=NOW)
    xs = find_contradictions(led.claims())
    adjudicate(led, xs, now=NOW)
    rep = synthesize(led, xs, topic="A vs B", now=NOW)
    md = research_mode.render_markdown(rep, topic="A vs B")
    open_x = [x for x in rep.contradictions if x.get("status") != "resolved"]
    assert open_x and "speed" in md
    assert "Unresolved contradictions" in md


def test_central_unverified_claim_blocks_pass():
    led = _led()
    led.add_claim(
        "central api returns json",
        type="api_fact",
        source_type="claude_inference",
        central=True,
        subject="api",
    )
    verify_ledger(led, now=NOW)
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is True
    assert adj.central_unverified


def test_central_claim_confirmed_at_t2_does_not_block():
    led = _led()
    src = led.add_source(
        kind="official_docs", summary="api returns json per docs", trust_tier=epistemic.T2_OFFICIAL
    )
    led.add_claim(
        "api returns json",
        type="api_fact",
        source_type="official_docs",
        central=True,
        subject="api",
        evidence_refs=[src.id],
    )
    verify_ledger(led, now=NOW)
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is False


# ---------------- P1: epistemic provenance hardening (no self-certification) ----------------


def test_deterministic_type_without_source_is_not_confirmed():
    led = _led()
    c = led.add_claim("the code returns 200", type="code_fact", source_type="source_code", subject="endpoint")
    assert c.status == epistemic.STATUS_UNVERIFIED  # a self-declared deterministic type is not proof
    status, _ = verify_claim(c, led.sources, now=NOW)
    assert status == epistemic.STATUS_UNVERIFIED


def test_claim_creator_cannot_self_verify():
    led = _led()
    c = led.add_claim(
        "api returns json",
        type="api_fact",
        source_type="claude_inference",
        subject="api json",
        created_by="generator",
    )
    led.set_status(c.id, epistemic.STATUS_CONFIRMED, verified_by="generator")  # creator self-certifies
    assert led.get_claim(c.id).status == epistemic.STATUS_UNVERIFIED
    assert "self-certification" in led.get_claim(c.id).notes.lower()
    # an INDEPENDENT verifier backed by a real non-model source can still confirm
    src = led.add_source(
        kind="official_docs", locator="docs", summary="api returns json", trust_tier=epistemic.T2_OFFICIAL
    )
    led.update_claim(c.id, evidence_refs=[src.id])
    verify_ledger(led, now=NOW, verifier="source_verifier")
    assert led.get_claim(c.id).status == epistemic.STATUS_CONFIRMED


def test_trust_tier_cannot_be_self_raised():
    led = _led()
    c = led.add_claim(
        "lib X supports plugins", type="api_fact", source_type="official_docs", subject="plugins"
    )
    assert epistemic.best_supporting_trust(c, led.sources) == epistemic.T4_MODEL  # no real source => T4
    assert epistemic.meets_trust_requirement(c, led.sources, epistemic.T2_OFFICIAL) is False


def test_model_only_support_cannot_confirm_central_claim():
    led = _led()
    src = led.add_source(
        kind="codex_output",
        locator="codex",
        summary="codex thinks api returns json",
        trust_tier=epistemic.T4_MODEL,
    )
    led.add_claim(
        "api returns json",
        type="api_fact",
        source_type="claude_inference",
        subject="api json",
        central=True,
        evidence_refs=[src.id],
    )
    verify_ledger(led, now=NOW)
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is True and adj.central_unverified


# ---------------- P1: centrality is derived by POLICY, not self-declared ----------------


def test_centrality_policy_from_acceptance_criteria():
    led = _led()
    c = led.add_claim(
        "checkout total is computed with tax",
        type="model_inference",
        source_type="claude_inference",
        subject="checkout total tax",
    )
    assert c.central is False
    led.promote_centrality(["The checkout total must include tax"])
    assert led.get_claim(c.id).central is True and led.get_claim(c.id).centrality_policy_reasons


def test_centrality_policy_from_patch_rationale():
    led = _led()
    c = led.add_claim(
        "retry uses exponential backoff",
        type="model_inference",
        source_type="claude_inference",
        subject="retry exponential backoff",
    )
    led.promote_centrality([], extra_texts=["patch rationale: switch retry to exponential backoff"])
    assert led.get_claim(c.id).central is True


def test_centrality_policy_from_security_topic():
    led = _led()
    c = led.add_claim(
        "passwords are hashed with bcrypt",
        type="model_inference",
        source_type="claude_inference",
        subject="password hashing",
    )
    assert epistemic.derive_centrality(c)  # security-sensitive => central even with no criterion
    assert epistemic.is_critical(c) is True


def test_mislabeled_noncentral_still_blocks_pass():
    led = _led()
    # a model tags central=False to dodge the gate, but it's an api_fact with no real evidence
    led.add_claim(
        "the /users API returns an array",
        type="api_fact",
        source_type="claude_inference",
        subject="users api array",
        central=False,
    )
    verify_ledger(led, now=NOW)
    led.promote_centrality(["expose GET /users returning an array"])
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is True and adj.central_unverified


def test_critical_central_claim_hard_blocks():
    led = _led()
    led.add_claim(
        "auth tokens are validated server-side",
        type="security_claim",
        source_type="claude_inference",
        subject="auth token validation",
    )
    verify_ledger(led, now=NOW)
    led.promote_centrality([])
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is True and adj.hard_block is True and adj.critical_unverified


def test_stale_docs_cannot_confirm_central_claim():
    led = _led()
    old = led.add_source(
        kind="web_page",
        locator="changelog",
        summary="feature flag api added",
        trust_tier=epistemic.T2_OFFICIAL,
        freshness_required=True,
        retrieved_at="2020-01-01T00:00:00+00:00",
    )
    led.add_claim(
        "feature flag api exists",
        type="api_fact",
        source_type="web_primary_source",
        subject="feature flag api",
        central=True,
        evidence_refs=[old.id],
    )
    verify_ledger(led, now=NOW)
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is True


def test_irrelevant_source_cannot_confirm_central_claim():
    led = _led()
    irrel = led.add_source(
        kind="official_docs",
        locator="docs",
        summary="unrelated zoology of penguins",
        trust_tier=epistemic.T2_OFFICIAL,
    )
    led.add_claim(
        "the parser accepts utf8",
        type="api_fact",
        source_type="official_docs",
        subject="parser utf8",
        central=True,
        evidence_refs=[irrel.id],
    )
    verify_ledger(led, now=NOW)
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is True


def test_final_checker_catches_unledgered_critical_conclusion():
    led = _led()  # ledger has NO claim about payments
    adj = adjudicate(led, [], conclusions=["the payment charge is idempotent per order"], now=NOW)
    assert adj.missing_central and adj.blocks_pass is True and adj.hard_block is True


def test_ledgered_critical_conclusion_does_not_block():
    led = _led()
    src = led.add_source(
        kind="official_docs",
        locator="stripe",
        summary="payment charge idempotent per order key",
        trust_tier=epistemic.T2_OFFICIAL,
    )
    led.add_claim(
        "payment charge is idempotent per order",
        type="api_fact",
        source_type="official_docs",
        subject="payment charge idempotent order",
        evidence_refs=[src.id],
    )
    verify_ledger(led, now=NOW)
    adj = adjudicate(led, [], conclusions=["the payment charge is idempotent per order"], now=NOW)
    assert not adj.missing_central and adj.blocks_pass is False


def test_noncritical_assumption_does_not_block_pass():
    led = _led()
    led.add_claim(
        "the cache TTL is probably 60s",
        type="assumption",
        source_type="claude_inference",
        subject="cache ttl",
        central=True,
    )
    verify_ledger(led, now=NOW)
    led.promote_centrality([])
    adj = adjudicate(led, [], now=NOW)
    assert adj.blocks_pass is False and adj.hard_block is False  # explicit assumption is surfaced


def test_t0_overrides_model_but_preserves_unrelated_contradiction():
    led = _led()
    ts = led.add_source(
        kind="test_output",
        locator="pytest",
        summary="login flow test passed",
        trust_tier=epistemic.T0_DETERMINISTIC,
    )
    led.add_claim(
        "login works",
        type="test_result",
        source_type="test_result",
        subject="login",
        stance="works",
        evidence_refs=[ts.id],
    )
    led.add_claim(
        "login is broken",
        type="model_inference",
        source_type="claude_inference",
        subject="login",
        stance="broken",
    )
    a = led.add_source(
        kind="official_docs", locator="da", summary="A faster than B speed", trust_tier=epistemic.T2_OFFICIAL
    )
    b = led.add_source(
        kind="official_docs", locator="db", summary="B faster than A speed", trust_tier=epistemic.T2_OFFICIAL
    )
    led.add_claim(
        "A faster",
        type="research_claim",
        source_type="official_docs",
        subject="speed",
        stance="A",
        evidence_refs=[a.id],
    )
    led.add_claim(
        "B faster",
        type="research_claim",
        source_type="official_docs",
        subject="speed",
        stance="B",
        evidence_refs=[b.id],
    )
    verify_ledger(led, now=NOW)
    xs = find_contradictions(led.claims())
    adjudicate(led, xs, now=NOW)
    assert any(x.subject == "login" and x.status == "resolved" for x in xs)  # T0 resolves
    assert any(x.subject == "speed" and x.status != "resolved" for x in xs)  # unrelated preserved


# ---------------- research mode ----------------


def test_research_report_has_source_table_and_confidence():
    led = _led()
    src = led.add_source(
        kind="official_docs", summary="library A supports plugins", trust_tier=epistemic.T2_OFFICIAL
    )
    led.add_claim(
        "A supports plugins",
        type="research_claim",
        source_type="official_docs",
        subject="plugins",
        evidence_refs=[src.id],
    )
    verify_ledger(led, now=NOW)
    rep = synthesize(led, [], topic="plugins", now=NOW)
    assert rep.source_table and rep.confidence_by_section
    md = research_mode.render_markdown(rep, topic="plugins")
    assert "## Source table" in md and "## Confidence by section" in md and "## What would change" in md


def test_passes_research_gate_requires_sources_and_coverage():
    led = _led()
    # no sources, no confirmed claims => gate fails (but never raises)
    passed, reasons = passes_research_gate(led, [], questions=["speed"], now=NOW)
    assert passed is False and reasons


def test_classify_task_modes():
    assert classify_task("Compare A vs B")[0] == "research"
    assert classify_task("Fix the failing checkout tests")[0] == "build"
    assert classify_task("Design the architecture, verify current docs, then build it")[0] == "mixed"
    assert classify_task("anything", mode_hint="research")[0] == "research"


# ---------------- stability controller ----------------


def test_repeated_failure_detected():
    st = stability.analyze({"failure_signatures": ["tests:boom"] * 3}, repeated_failure_threshold=3)
    assert st["repeated_failure"] is True


def test_patch_oscillation_detected():
    assert stability.detect_patch_oscillation(["A", "B", "A", "B"]) is True
    assert stability.detect_patch_oscillation(["A", "A", "A"]) is False


def test_flaky_classification():
    assert stability.classify_flaky([True, False, True]) == "flaky"
    assert stability.classify_flaky([True, True, True]) == "pass"
    assert stability.classify_flaky([False, False]) == "consistent_failure"


def test_tool_failure_classification_and_retry():
    assert stability.classify_tool_failure("Connection reset by peer") == stability.NETWORK
    assert (
        stability.classify_tool_failure("ModuleNotFoundError: no module named x")
        == stability.MISSING_DEPENDENCY
    )
    assert stability.classify_tool_failure("temporarily unavailable, try again") == stability.TRANSIENT
    assert stability.is_retryable(stability.TRANSIENT) is True
    assert stability.is_retryable(stability.NETWORK) is False  # surfaced, not blind-retried


def test_low_information_gain():
    assert stability.low_information_gain([0, 0]) is True
    assert stability.low_information_gain([3, 2]) is False


# ---------------- loop integration ----------------


def test_build_mode_records_claims_from_tests(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    s = new_state("demo", str(tmp_path), required_gates=["tests"])
    final = run_loop(s, RunContext(provider=MockProvider(score=0.95), runner=_runner_pass, now=lambda: NOW))
    assert final["stop_reason"] == STOP_PASS
    claims = final["knowledge"]["claims"]
    gate_claims = [c for c in claims if c["subject"] == "gate:tests"]
    assert gate_claims and gate_claims[0]["status"] == epistemic.STATUS_CONFIRMED
    assert gate_claims[0]["type"] == "test_result"


def test_build_final_pass_blocked_when_central_claim_unverified(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")

    def hook(state, ctx, phase):
        if phase == "assumptions":
            return [
                {
                    "claim": {
                        "text": "foo() returns JSON",
                        "type": "api_fact",
                        "source_type": "claude_inference",
                        "central": True,
                        "subject": "foo",
                    }
                }
            ]
        return []

    s = new_state("implement foo", str(tmp_path), required_gates=["tests"])
    final = run_loop(
        s,
        RunContext(
            provider=MockProvider(score=0.95), runner=_runner_pass, investigation_hook=hook, now=lambda: NOW
        ),
    )
    assert final["stop_reason"] == STOP_UNVERIFIED
    assert final["adjudication"]["blocks_pass"] is True


def test_build_repeated_failure_triggers_stuck(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")
    s = new_state("demo", str(tmp_path), required_gates=["tests"], max_iterations=6)
    final = run_loop(s, RunContext(provider=MockProvider(score=0.95), runner=_runner_fail, now=lambda: NOW))
    assert final["stop_reason"] == "stuck_repeated_failure"
    assert final["iteration"] <= s["max_iterations"]


def test_research_mode_runs_and_synthesizes(tmp_path):
    authority = _recorded_docs({"docA": "Library A supports plugins."})

    def hook(state, ctx, phase):
        if phase == "investigation":
            return [
                {
                    "claim": {
                        "text": "Library A supports plugins.",
                        "type": "research_claim",
                        "subject": "plugins",
                    },
                    "evidence_requests": [
                        {
                            "adapter_id": "recorded-docs",
                            "locator": "docA",
                            "quoted_span": "Library A supports plugins.",
                        }
                    ],
                }
            ]
        return []

    s = new_state("Compare A vs B", str(tmp_path), mode="research", research_questions=["plugins"])
    final = run_research_loop(
        s,
        RunContext(
            provider=MockProvider(),
            investigation_hook=hook,
            evidence_authority=authority,
            now=lambda: NOW,
        ),
    )
    assert final["stop_reason"] == STOP_RESEARCH_SYNTHESIS
    assert "## Source table" in final["research_report"]
    assert "## Confidence by section" in final["research_report"]


def test_research_docs_fetch_failure_is_not_a_gate_failure(tmp_path):
    # investigation hook returns nothing (simulated failed fetch). The loop must still SYNTHESIZE,
    # not fail, and must not record a FAIL gate.
    s = new_state(
        "Compare A vs B", str(tmp_path), mode="research", max_research_rounds=2, research_questions=["x"]
    )
    final = run_research_loop(
        s, RunContext(provider=MockProvider(), investigation_hook=None, now=lambda: NOW)
    )
    assert final["stop_reason"] in (STOP_RESEARCH_SYNTHESIS, STOP_MAX_RESEARCH_ROUNDS)
    assert final["research_backend"] == "pure_executor:no investigation adapter"
    assert not final.get("verification_results")  # no deterministic FAIL gate from a missing fetch


def test_max_research_rounds_stops_the_loop(tmp_path):
    counter = {"n": 0}
    authority = _recorded_docs({"d1": "unrelated fact 1", "d2": "unrelated fact 2"})

    def hook(state, ctx, phase):
        # add a NEW confirmed (T2) claim each round so info-gain stays high, but it never covers the
        # target question -> coverage never met -> loop must run to the round ceiling.
        if phase == "investigation":
            counter["n"] += 1
            return [
                {
                    "claim": {
                        "text": f"unrelated fact {counter['n']}",
                        "type": "research_claim",
                        "subject": f"filler{counter['n']}",
                    },
                    "evidence_requests": [
                        {
                            "adapter_id": "recorded-docs",
                            "locator": f"d{counter['n']}",
                            "quoted_span": f"unrelated fact {counter['n']}",
                        }
                    ],
                }
            ]
        return []

    s = new_state(
        "research topic",
        str(tmp_path),
        mode="research",
        max_research_rounds=2,
        research_questions=["totally_uncovered_topic"],
    )
    final = run_research_loop(
        s,
        RunContext(
            provider=MockProvider(),
            investigation_hook=hook,
            evidence_authority=authority,
            now=lambda: NOW,
        ),
    )
    assert final["research_round"] == 2
    assert final["stop_reason"] == STOP_MAX_RESEARCH_ROUNDS


def test_max_parallel_agents_enforced():
    s = new_state("demo", "/tmp/repo", epistemic_config={"epistemic_governor": {"max_parallel_agents": 3}})

    def hook(state, ctx, phase):
        return [
            {
                "claim": {
                    "text": f"c{i}",
                    "type": "research_claim",
                    "source_type": "official_docs",
                    "subject": f"s{i}",
                },
                "sources": [{"kind": "official_docs", "summary": f"c{i}", "trust_tier": "T2_official_docs"}],
            }
            for i in range(10)
        ]

    ctx = RunContext(provider=MockProvider(), investigation_hook=hook, now=lambda: NOW)
    s = node_parallel_investigation(s, ctx)
    assert s["last_investigation_count"] == 3  # capped at max_parallel_agents


# ---------------- ledger persistence ----------------


def test_ledger_append_only_roundtrip(tmp_path):
    kdir = str(tmp_path / "knowledge")
    led = ClaimLedger(knowledge_dir=kdir, now=lambda: NOW)
    src = led.add_source(kind="official_docs", summary="doc", trust_tier=epistemic.T2_OFFICIAL)
    c = led.add_claim(
        "fact", type="api_fact", source_type="official_docs", subject="f", evidence_refs=[src.id]
    )
    led.set_status(c.id, epistemic.STATUS_CONFIRMED, verified_by="source_verifier")
    reloaded = ClaimLedger.load(kdir)
    rc = reloaded.get_claim(c.id)
    assert rc is not None and rc.status == epistemic.STATUS_UNVERIFIED
    restored_source = reloaded.get_source(src.id)
    assert restored_source is not None
    assert restored_source.kind == "legacy_unattested_snapshot"
    assert restored_source.trust_tier == epistemic.T4_MODEL


def test_research_report_excludes_user_requirement_and_evidenceless_confirmed():
    # A research report's "confirmed facts" must exclude the user's own question/criteria (which
    # auto-confirm with no evidence) and any evidence-less confirmed claim — else the deliverable
    # renders the user's question as a high-confidence fact and inflates overall confidence.
    led = ClaimLedger()
    led.add_claim("Is X faster than Y for auth?", type="user_requirement", source_type="user")
    src = led.add_source(
        kind="official_docs",
        summary="X sustains ten thousand rps",
        trust_tier=epistemic.T2_OFFICIAL,
        retrieved_at=NOW,
    )
    led.add_claim(
        "X sustains 10k rps",
        type="research_claim",
        source_type="official_docs",
        evidence_refs=[src.id],
        status=epistemic.STATUS_CONFIRMED,
        created_by="researcher",
    )
    rep = synthesize(led, [], topic="X vs Y", now=NOW)
    texts = [c["text"] for c in rep.confirmed_claims]
    assert "Is X faster than Y for auth?" not in texts  # the user's own question is not a "confirmed fact"
    assert "X sustains 10k rps" in texts  # a real evidence-backed claim is
