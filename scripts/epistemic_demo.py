"""Two offline dry demos of the epistemic governor (no network, no API key, MockProvider).

1. Research demo — compare two fictional libraries from supplied local fake docs that *contradict*
   each other at equal trust. The synthesis must PRESERVE the contradiction and not overclaim.
2. Build demo — a tiny repo with one failing test (recovered) and one unverified central API
   assumption. The loop must refuse a final PASS until the assumption is confirmed.

Run:  python scripts/epistemic_demo.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from evalopt_graph import MockProvider, RunContext, epistemic, new_state, run_loop, run_research_loop
from evalopt_graph.attestation import (
    AdapterPolicy,
    EvidenceAuthority,
    RecordedEvidenceAdapter,
    RetrievedArtifact,
)
from evalopt_graph.checks import CommandResult
from evalopt_graph.evidence_adapters import LocalFileAdapter

NOW = "2026-06-28T00:00:00+00:00"


def research_demo() -> None:
    print("\n=== RESEARCH DEMO: compare LibA vs LibB from local fake docs (with a contradiction) ===")
    tmp = Path(tempfile.mkdtemp())
    docs = tmp / "docs"
    docs.mkdir()
    # two EQUAL-tier local docs that disagree on speed -> contradiction must be preserved
    (docs / "libA.md").write_text("LibA benchmark report: LibA is faster than LibB on the speed suite.\n")
    (docs / "libB.md").write_text("LibB benchmark report: LibB is faster than LibA on the speed suite.\n")
    (docs / "common.md").write_text("Both LibA and LibB support a plugin system for plugins.\n")

    def hook(state, ctx, phase):
        if phase != "investigation":
            return []
        return [
            {
                "claim": {
                    "text": "LibA benchmark report: LibA is faster than LibB on the speed suite.",
                    "type": "research_claim",
                    "subject": "speed",
                    "stance": "A_faster",
                },
                "evidence_requests": [
                    {
                        "adapter_id": "local_file",
                        "locator": "docs/libA.md",
                        "quoted_span": "LibA benchmark report: LibA is faster than LibB on the speed suite.",
                    }
                ],
            },
            {
                "claim": {
                    "text": "LibB benchmark report: LibB is faster than LibA on the speed suite.",
                    "type": "research_claim",
                    "subject": "speed",
                    "stance": "B_faster",
                },
                "evidence_requests": [
                    {
                        "adapter_id": "local_file",
                        "locator": "docs/libB.md",
                        "quoted_span": "LibB benchmark report: LibB is faster than LibA on the speed suite.",
                    }
                ],
            },
            {
                "claim": {
                    "text": "Both LibA and LibB support a plugin system for plugins.",
                    "type": "research_claim",
                    "subject": "plugins",
                },
                "evidence_requests": [
                    {
                        "adapter_id": "local_file",
                        "locator": "docs/common.md",
                        "quoted_span": "Both LibA and LibB support a plugin system for plugins.",
                    }
                ],
            },
        ]

    state = new_state(
        "Compare LibA vs LibB", str(tmp), mode="research", research_questions=["speed", "plugins"]
    )
    ctx = RunContext(
        provider=MockProvider(),
        investigation_hook=hook,
        evidence_adapters=(LocalFileAdapter(tmp),),
        now=lambda: NOW,
    )
    final = run_research_loop(state, ctx)

    open_x = [x for x in final["contradictions"] if x.get("status") != "resolved"]
    print(f"stop_reason         : {final['stop_reason']}")
    print(f"rounds              : {final['research_round']}/{final['max_research_rounds']}")
    print(f"contradictions      : {[(x['subject'], x['status']) for x in final['contradictions']]}")
    print(f"PRESERVED open count: {len(open_x)}  (expect >=1 — the speed contradiction)")
    report = final["research_report"]
    print(f"report keeps it     : {'speed' in report and 'Unresolved contradictions' in report}")
    assert open_x, "contradiction was smoothed away — demo FAILED"
    assert "## Source table" in report and "## Confidence by section" in report
    print("RESULT: contradiction preserved; report cites sources & confidence; no overclaim. OK")


def build_demo() -> None:
    print("\n=== BUILD DEMO: failing test (recovered) + unverified central API assumption ===")
    tmp = Path(tempfile.mkdtemp())
    (tmp / "pyproject.toml").write_text("[project]\nname='demo'\n")
    (tmp / "tests").mkdir()
    (tmp / "tests" / "test_x.py").write_text("def test_x():\n    assert True\n")

    # one failing test on the first run, then green (simulated reflection recovery)
    def runner_fail_then_pass():
        counts: dict[str, int] = {}

        def runner(gate, command, cwd):
            counts[gate] = counts.get(gate, 0) + 1
            if counts[gate] <= 1:
                return CommandResult(gate, command, 1, "FAIL", "AssertionError: foo() shape")
            return CommandResult(gate, command, 0, "PASS", "ok")

        return runner

    def unverified_hook(state, ctx, phase):
        if phase == "assumptions":
            return [
                {
                    "claim": {
                        "text": "foo() returns a JSON object",
                        "type": "api_fact",
                        "source_type": "claude_inference",
                        "central": True,
                        "subject": "foo_return",
                    }
                }
            ]
        return []

    s1 = new_state("implement foo() endpoint", str(tmp), required_gates=["tests"])
    f1 = run_loop(
        s1,
        RunContext(
            provider=MockProvider(score=0.95),
            runner=runner_fail_then_pass(),
            investigation_hook=unverified_hook,
            now=lambda: NOW,
        ),
    )
    print(f"[unverified] stop_reason : {f1['stop_reason']}  (expect blocked_unverified_central_claim)")
    print(
        f"[unverified] blocks_pass : {f1['adjudication']['blocks_pass']} "
        f"central_unverified={f1['adjudication']['central_unverified']}"
    )
    assert f1["stop_reason"] == "blocked_unverified_central_claim", "should refuse PASS"

    # Same task, but now a controller-registered retrieval result binds the exact official-doc span.
    docs_locator = "docs://api.example/foo"
    docs_text = b"foo() returns a JSON object"
    docs_policy = AdapterPolicy(
        adapter_id="recorded-official-docs",
        adapter_version="1",
        source_kind="official_docs",
        trust_tier=epistemic.T2_OFFICIAL,
        retrieval_mechanism="recorded_tool_result",
        parser_identity="text/plain@1",
        freshness_required=True,
    )
    docs_authority = EvidenceAuthority(
        [
            RecordedEvidenceAdapter(
                docs_policy,
                {
                    docs_locator: RetrievedArtifact(
                        content=docs_text,
                        final_locator=docs_locator,
                        retrieved_at=NOW,
                        media_type="text/plain",
                    )
                },
            )
        ],
        now=lambda: NOW,
    )

    def confirmed_hook(state, ctx, phase):
        if phase == "assumptions":
            return [
                {
                    "claim": {
                        "text": "foo() returns a JSON object",
                        "type": "api_fact",
                        "central": True,
                        "subject": "foo_return",
                    },
                    "evidence_requests": [
                        {
                            "adapter_id": "recorded-official-docs",
                            "locator": docs_locator,
                            "quoted_span": "foo() returns a JSON object",
                        }
                    ],
                }
            ]
        return []

    s2 = new_state("implement foo() endpoint", str(tmp), required_gates=["tests"])
    f2 = run_loop(
        s2,
        RunContext(
            provider=MockProvider(score=0.95),
            runner=runner_fail_then_pass(),
            investigation_hook=confirmed_hook,
            evidence_authority=docs_authority,
            now=lambda: NOW,
        ),
    )
    print(f"[confirmed]  stop_reason : {f2['stop_reason']}  (expect pass)")
    print(f"[confirmed]  blocks_pass : {f2['adjudication']['blocks_pass']}")
    assert f2["stop_reason"] == "pass", "should PASS once the central claim is confirmed at T2"
    print("RESULT: PASS refused while central API claim unverified; PASS only after T2 confirmation. OK")


if __name__ == "__main__":
    research_demo()
    build_demo()
    print("\nBOTH DEMOS PASSED")
