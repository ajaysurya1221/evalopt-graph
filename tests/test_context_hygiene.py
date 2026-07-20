"""Context hygiene tests: retrieval pack, command summarization, fingerprint dedup, noise, ReAct
trace, lightweight cache, and the nested checkers. Pure: no network, no LangGraph, no API key."""

from __future__ import annotations

from evalopt_graph import checkers, epistemic
from evalopt_graph import context_hygiene as hygiene
from evalopt_graph.claim_ledger import ClaimLedger
from evalopt_graph.source_verification import verify_claim

NOW = "2026-06-28T00:00:00+00:00"


def _led():
    return ClaimLedger(now=lambda: NOW)


# ---------------- retrieval pack ----------------


def test_retrieval_pack_excludes_nonusable_and_keeps_essentials():
    led = _led()
    led.add_claim("must support oauth", type="user_requirement", source_type="user")  # confirmed
    src = led.add_source(
        kind="official_docs", summary="api returns json widget", trust_tier=epistemic.T2_OFFICIAL
    )
    confirmed = led.add_claim(
        "api returns json",
        type="api_fact",
        source_type="official_docs",
        subject="api widget",
        evidence_refs=[src.id],
    )
    from evalopt_graph.source_verification import verify_ledger

    verify_ledger(led, now=NOW)
    unverified = led.add_claim("api is probably restful", source_type="claude_inference", subject="guess")
    contradicted = led.add_claim("api is broken", source_type="claude_inference")
    led.set_status(contradicted.id, epistemic.STATUS_CONTRADICTED)

    state = {
        "task": "build api client",
        "acceptance_criteria": ["client calls api"],
        "verification_results": [],
    }
    pack = hygiene.build_retrieval_pack(state, led, now=NOW)
    assert "must support oauth" in pack  # user requirement kept
    assert "client calls api" in pack  # acceptance criterion kept
    assert confirmed.id in pack  # confirmed claim included
    assert unverified.id not in pack and contradicted.id not in pack  # non-usable excluded


def test_context_checker_flags_nonusable_claim_in_pack():
    led = _led()
    c = led.add_claim("shaky claim", source_type="claude_inference")  # unverified
    pack = f"premise [{c.id}] shaky claim"
    res = checkers.context_checker(pack, led)
    assert res.passed is False and any(c.id in i for i in res.issues)


# ---------------- command output summarization + dedup ----------------


def test_command_summary_keeps_log_path_and_is_compact():
    big = (
        "\n".join(f"line {i}" for i in range(5000))
        + "\nE   AssertionError: foo != bar\nFAILED tests/test_a.py::test_x"
    )
    result = {
        "gate": "tests",
        "exit_code": 1,
        "result": "FAIL",
        "command": "pytest -q",
        "stdout": big,
        "stderr": "",
        "summary": "1 failed",
    }
    s = hygiene.summarize_command_output(result, log_path="/runs/x/tests.log")
    assert s["log_path"] == "/runs/x/tests.log"
    assert s["failing_target"] in ("tests/test_a.py::test_x", "tests/test_a.py")
    assert "AssertionError" in s["first_error"]  # first relevant error surfaced
    assert "FAILED" in s["last_error"]  # last relevant error surfaced
    assert len(s["last_error"]) <= 240 and len(s["first_error"]) <= 240  # compact, not the whole log


def test_repeated_error_fingerprint_dedupes_noise():
    errs = [
        "Traceback line 12 in /a/b.py: ValueError: x",
        "Traceback line 88 in /c/d.py: ValueError: x",  # same shape, different digits/paths
        "TypeError: totally different",
    ]
    kept, dropped = hygiene.dedupe_by_fingerprint(errs)
    assert len(kept) == 2 and len(dropped) == 1
    assert dropped[0]["reason"] == "duplicate_error" and dropped[0]["fingerprint"]


def test_noise_detection():
    assert hygiene.detect_noise("screenshot saved to a.png, looks fine") == "screenshot_without_assertion"
    fp = hygiene.error_fingerprint("ValueError: boom at line 3")
    assert (
        hygiene.detect_noise("ValueError: boom at line 9", prior_fingerprints={fp})
        == "repeated_identical_stack_trace"
    )
    assert hygiene.detect_noise("assert response.status == 200  (real signal)") is None


def test_command_summary_redacts_secrets():
    result = {
        "gate": "x",
        "exit_code": 1,
        "result": "FAIL",
        "command": "run",
        "stdout": "error: api_key=sk-abcdefghij1234567890 failed",
        "stderr": "",
    }
    s = hygiene.summarize_command_output(result)
    assert "sk-abcdefghij" not in (s["first_error"] + s["last_error"])


# ---------------- ReAct trace ----------------


def test_react_event_schema_validates():
    ev = hygiene.react_event(
        node="deterministic_verification",
        iteration=3,
        goal="green tests",
        action="run_gates",
        observation="tests=PASS",
        decision="pass",
        next_node="final_review",
        timestamp=NOW,
    )
    assert hygiene.validate_react_event(ev) is True
    bad = dict(ev)
    del bad["evidence_refs"]
    assert hygiene.validate_react_event(bad) is False


def test_react_event_has_no_private_chain_of_thought_field():
    ev = hygiene.react_event(node="x", thought_summary="public rationale only")
    assert "chain_of_thought" not in ev and ev["thought_summary"] == "public rationale only"


# ---------------- lightweight cache ----------------


def test_cache_never_confirms_a_claim_by_itself():
    cache = hygiene.SemanticCache()
    cache.put_query(
        "does foo return json?", {"answer": "yes"}, library="foo", trust_tier=epistemic.T3_SECONDARY
    )
    assert cache.get_query("does foo return json?", library="foo") == {"answer": "yes"}
    # a claim backed only by the cache (no real Source) must NOT be confirmed
    led = _led()
    c = led.add_claim(
        "foo returns json", type="api_fact", source_type="claude_inference", subject="foo", notes="from cache"
    )
    status, _ = verify_claim(c, led.sources, now=NOW)
    assert status == epistemic.STATUS_UNVERIFIED  # cache is acceleration, not proof


def test_stale_cache_entry_is_not_used():
    cache = hygiene.SemanticCache()
    cache.put_query(
        "latest api",
        {"v": 1},
        url="https://x",
        trust_tier=epistemic.T2_OFFICIAL,
        retrieved_at="2020-01-01T00:00:00+00:00",
        freshness_required=True,
    )
    assert cache.get_query("latest api", url="https://x", now=NOW, max_age_seconds=60 * 60 * 24 * 30) is None


def test_cache_never_stores_secrets():
    cache = hygiene.SemanticCache()
    cache.put_query("login", {"token": "sk-abcdefghij1234567890"}, library="auth")
    assert cache.get_query("login", library="auth") is None  # refused to cache a secret


def test_cache_remembers_rejected_claims():
    cache = hygiene.SemanticCache()
    cache.reject_claim("foo() returns XML", reason="hallucinated; docs say JSON")
    assert cache.is_rejected("foo() returns XML") is True
    assert cache.is_rejected("unrelated claim") is False


# ---------------- checkers cite evidence ----------------


def test_checkers_require_evidence_refs():
    led = _led()
    src = led.add_source(
        kind="official_docs", summary="api spec for widget", trust_tier=epistemic.T2_OFFICIAL
    )
    led.add_claim(
        "widget api",
        type="api_fact",
        source_type="official_docs",
        central=True,
        subject="widget",
        evidence_refs=[src.id],
    )
    from evalopt_graph.source_verification import verify_ledger

    verify_ledger(led, now=NOW)
    res = checkers.evidence_checker(led)
    assert res.passed is True and res.citations  # cites claim<-evidence

    state = {
        "verification_results": [{"gate": "tests", "result": "PASS", "exit_code": 0}],
        "changed_files": ["src/a.py"],
    }
    gate = checkers.gate_checker(state)
    assert gate.passed is True and gate.citations  # cites gate:exit:result


def test_gate_checker_catches_misinterpreted_exit_code():
    state = {
        "verification_results": [{"gate": "tests", "result": "PASS", "exit_code": 1}],
        "changed_files": ["a.py"],
    }
    res = checkers.gate_checker(state)
    assert res.passed is False and any("misinterpreted" in i for i in res.issues)


def test_evidence_checker_flags_model_only_central_claim():
    led = _led()
    led.add_claim("central guess", type="api_fact", source_type="claude_inference", central=True, subject="g")
    res = checkers.evidence_checker(led)
    assert res.passed is False and res.issues
