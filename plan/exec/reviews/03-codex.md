REVIEW 03 — Reviewer Astra | Verdict REVISE

Exact inspected head: `2d5c307830185c7f31d8d7810a1a5304dc88cf4f`, implementation baseline `0a7d3744968f935a48a78bcae870af80e78b881a`. The implementation diff adds only four owned ADRs; `git diff --check` passes. No implementation file was edited during this review.

## Findings and required changes

1. **P2 — The asserted post-tag source history is incomplete.** `docs/decisions/archive-standalone.md:34` says the other nine post-v0.1.0 commits are documentation/build/CI/dependency changes after singling out the scalar-row fix. Actual source diff includes `fc377329385261445295c4e6d13168c0c85b6dec`: `project_detect.py` changes Python test-gate command generation from a PATH-selected `python` to shell-quoted `sys.executable`; `permissions.py` changes readiness messages; `epistemic.py` changes module prose. Correct the checked-fact paragraph and ensure the release-disclosure instruction covers these inherited source differences, particularly the project-detection behavior. The total ten commits and 2026-07-20 tag date are correct. In line39, make clear that the version literal is the only change **under `src/`**, while approved release metadata/plumbing and documentation changes remain allowed; “only ... plus documentation” should not imply those approved files cannot change.

2. **P2 — No identity concept is stronger than the source supports.** `docs/decisions/archive-standalone.md:32` states the stable kernel has no signing, key or identity concept. `AdapterPolicy` in `attestation.py:88–107` explicitly contains adapter/parser identity fields and validates them; `EvidenceAuthority` in `kernel.py:306–331` indexes and serializes these policies by adapter ID. The correct limitation is no cryptographic producer authentication, signature verification or signing-key management, not absence of identity fields. Replace that clause accordingly; preserve the distinction between supplied identifiers and authenticated producer identity.

3. **P2 — The standalone STOP ADR omits the required VSA retirement qualification.** `docs/decisions/archive-standalone.md:25` links SLSA verification summaries as existing overlap without saying that the cited VSA is retired historical prior art. The accepted plan requires that qualification, and the other three ADRs already preserve it. Add the same bounded qualifier here; do not frame VSA as a current migration destination.

## Correspondence and evidence checked

- The memo digest reproduces as `e307514fc800c2ff37c8d1a6d9a454bbf4d4addf53acd38611cbbc50b5695e81`. STOP, no new capability/integration/benchmark, final gated release, human-only archival and all reopening conditions correspond to the accepted plan. Memo demand/overlap findings are clearly attributed rather than asserted as independent measurements.
- The fixed sixteen-entry roster matches the actual ten-export `__all__` order followed by the six approved topics. Shared limitations, source appendix, finite coverage record, no conversion artifact and the seven job routes correspond to the accepted tie-break.
- Blind-proposal chronology is retained: Fable `0663549` at 2026-10-12T19:58:47Z; Astra `aa28b4c` at20:00:27Z; fresh tie-break `0a7d374` at20:04:38Z; implementation `2d5c307` at20:18:39Z. These commits and their contents support the documented comparison sequence; chronology alone is not proof of unobserved reading behavior. All three ADRs retain both positions and the deciding rule.
- `AcceptanceDecision.validate()` checks schema version, allowed status and record hash; `replay()` compares against fresh deterministic evaluation of retained policy/input. The ADR correctly avoids claiming either reruns checks or establishes input truth.
- Source history was checked with `git rev-list --count v0.1.0..fc3045d`, `git log` and `git diff v0.1.0 fc3045d -- src`. The annotated v0.1.0 tag timestamp is 2026-07-20T12:40:17Z; its target is `42a65237303d77d8a38c2ff7d4110cb8b51a7375`.
- Publication and archival remain prospective, old studies remain preserved, counterpart-repository work remains README-only PRs, and no new dependency or authority claim is introduced by the ADR decisions.

## Limits

This is an independent source/plan correspondence and factual review, not a rerun of the memo's market research or a release approval. No model call, credential/environment-file read, network request, package mutation or frozen-study change occurred. Only this central review record was written. Correct the three bounded public-fact issues and submit the new immutable head for targeted re-review.
