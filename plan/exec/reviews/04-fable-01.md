REVIEW 04 — Reviewer Fable xhigh | Verdict REVISE

Target: `80816612c0ad9ccae4350095869e9fa77515187e` on `winddown/20261013/04`, worktree `wt-semantics-04`, base `2b4f00e`. Diff adds exactly three files (`docs/migration.md` 115, `docs/migration-sources.md` 79, `docs/migration-coverage.md` 39; 233 insertions, 0 deletions). Nothing under `src/`, `tests/`, `bench/`, README, `docs/architecture.md`, PLAN, task specs or prior decisions changed. Every baseline file the map cites (`__init__.py`, `kernel.py`, `attestation.py`, `evidence_adapters.py`, `docs/architecture.md`, `README.md`, `SECURITY.md`, `tests/test_kernel.py`, `CHANGELOG.md`) is byte-identical between HEAD and `fc3045dbda29c1d274747329ceb6724a783b0df7`, so the `file:line` references resolve at both.

Fresh, read-only, independent session. The author REPORT (`reports/04.md`) and root observations were read only after the independent inspection and only for comparison; no finding below rests on them. No model call, subagent, credential, `.env`, mutation or target edit; one `curl` batch for live primary-source re-fetch was denied by the permission mode and not retried.

## Verified (no change needed)

- **Roster and order.** `__all__` at `fc3045d` and at HEAD has exactly ten names in the documented order; map rows 1–10 follow it, rows 11–16 follow the topic order fixed in `migration-interface.md`. Both tables have 16 rows; label counts are 5 conceptual analogy, 4 host responsibility, 4 project-specific semantics, 3 no supported equivalence, one label per row, matching the coverage header.
- **Seven routes.** Jobs, destinations and order match `routing-boundary.md` exactly; routes are stated as job pointers, not drop-in replacements; sibling independence, no successor/conformance/endorsement/coupling, ARCI hashing as attributed adaptation. No eighth route; SLSA is excluded from the route table.
- **Baseline semantics, all 16 rows checked line-by-line against `git show fc3045d:…`.** Row 1 defaults and 64-hex allowlists (`kernel.py:48–57, 95–97`). Row 2 claim digest excludes `id`/`assessment_ids` (`attestation.py:75–84`) while `to_dict()` in the input hash includes them (`kernel.py:221`). Row 3 selector enforced at issuance, expected checks only when truthy (`attestation.py:505–525`), no `__post_init__` on `EvidenceRequest`. Row 4 alias (`kernel.py:32`), base64 serialization, empty `retrieved_at` falls back to `observed_at` (`attestation.py:499`). Row 5 statuses and `validate_record_hash()` (`attestation.py:22–28, 218–268`), non-`VERIFIED` requires failure reason and no selection. Row 6 relations and `_support` exact-match/polarity/subject grounding (`attestation.py:29–34, 363–381`). Row 7 stable authority vs lazy same-name retrieving facade (`kernel.py:305–359`; `attestation.py:658–676`; `evidence_adapters.py:161–242`; `__init__.py:7–18`). Row 8 constructor `ValueError`s (`kernel.py:153–213`). Row 9 `create`/`validate`/`replay` and malformed branch with empty evidence (`kernel.py:263–302, 536–537`). Row 10 precedence and `_load_bearing` (`kernel.py:410–422, 536–546`). Row 11 `_DECISIONS` and every reason string (`kernel.py:33, 437–488, 493–534`), separate attestation/relation vocabularies. Row 12 canonical JSON, NFC/LF, case-fold/whitespace, 24-hex prefixes, `from_dict` present on six of nine types and absent on policy, claim and authority (confirmed by direct `hasattr` check). Row 13 replay equality (`kernel.py:301–302`). Row 14 no key or signature field in any stable record; `SECURITY.md:44` "not a … signature system". Row 15 eligibility conjunction, contradiction before age, strict `>` only with `freshness_required`, `evidence_from_future` only for `VERIFIED` (`kernel.py:373–407, 450–455`). Row 16 `_LEGACY` outside `__all__`, README 182–184, architecture 105–107 and 129.
- **Direct stdlib check against the unchanged `src/` tree** (`python3 -B`, no install): `evaluate_acceptance` on a default policy and empty input → `ACCEPTED`, `validate()` True, `replay()` True; a fabricated self-consistent `AcceptanceDecision.create(...)` → `validate()` True, `replay()` False; `observed_at="not-a-time"` → `FAILED`, reasons `('invalid_observation_time',)`, `evidence_sha256=()`. Rows 9 and 13 and the shared validate/replay limitation are correct.
- **Acceptance criteria.** Five states kept distinct and never collapsed (rows 9–11, shared limits, checklist 4); claim-support limits (row 6, shared limit 3); replay meaning (row 13); VSA retirement disclosed with a dated check, version-specific, v1.2 Approved as status context and not a route (map lines 43–46; appendix rows SLSA-VSA-1.0/1.2); every hash described as a content digest and never a signature (grep of all three files: only negations); no automatic or lossless mapping promised; no conformance certification or endorsement; `v0.1.1` prospective; inherited `v0.1.0` differences disclosed by CHANGELOG reference and archive ADR, no "byte-identical" claim.
- **Appendix consistency.** All twelve keys used in the map and coverage record are defined once in the appendix; revisions, commit timestamps, line counts and the ten raw-content SHA-256 receipts match the control-lane `04-primary-sources-preflight.md` verbatim; `__version__ == "0.1.0"` at `__init__.py:20` confirmed. Sibling paraphrases checked read-only against the local clones at the pinned commits: actseal `111afb3` = `v1.0.1-6` ("frozen policy", "the application owns execution", offline replay, one README mention of evalopt, NOTICE says design influence and no evalopt source); dorian `eeb1937` = `v1.4.1` (README lines 5–6 and 21 match the route and limit wording verbatim; zero evalopt mentions); frontier-scout `e34d4a6` = `v2.2.0-1` (lines 5–8, 23; zero mentions); ARCI `a5adc83` (lines 6–7, 13, 15 "beyond v0.7.0; no PyPI package"; `pyproject.toml` version 0.7.0; NOTICE and `src/arci/hashing.py` header attribute the helpers to `attestation.py` under MIT; zero evalopt in any sibling `pyproject.toml`).
- **Structure.** Map tables 4×7 and 7×16, coverage 6×16, appendix 7×8, 7×4, 2×9, 3×10 with no column mismatch; all 14 relative links resolve; no `/Users` path or private log in the three files.

## Findings by severity

No blocking or major finding. Three minor wording defects, each one sentence, that the review brief explicitly asked to be distinguished; three low notes.

**Minor 1 — `docs/migration.md:70` (row 12): "deserializing validates or authorizes nothing" is overbroad.** Direct check: `AcceptanceInput.from_dict({"observed_at": …, "gate_results": [["only-one"]]})` raised `ValueError("gate_results entries require 2 string fields")`; `EvidenceMaterial.from_dict(... "final_locator": "")` raised `ValueError`; `EvidenceAttestation.from_dict` built a bogus record whose `validate_record_hash()` is False. Deserialization therefore does run constructor shape checks for some types while establishing no hash consistency, authorization or truth for any. As written the sentence also contradicts row 8 ("Construction validates shape and may raise `ValueError`") and shared limitation 7.

**Minor 2 — `docs/migration.md:71` (row 13): "No other tool replays an evalopt decision."** A universal negative over all tools; the inspected evidence covers only the routed destinations and their cited documentation. The brief forbids absence claims beyond the inspected destinations.

**Minor 3 — `docs/migration.md:72` and `docs/migration-coverage.md:33` (row 14), with `docs/migration.md:67` and `docs/migration-coverage.md:28` (row 9): key `SLSA-VSA-1.2` attached without a status-context qualifier.** `migration-interface.md` and `routing-boundary.md` admit the v1.2 page only as source-status context. Row 14's text never mentions SLSA, so the key reads as a substantive source for the signatures topic. Row 9's text names v1.0 as retired prior art but says nothing about what v1.2 contributes.

**Low 4 — `docs/migration.md:14–15`: "disclosed in the CHANGELOG".** At this commit the CHANGELOG "Unreleased" section carries the interpreter and helper-move changes but no entry for the scalar-row kernel fix `624ed11`, as `archive-standalone.md` itself records; the sentence is carried by its second clause ("and enumerated in the archive decision"). Not a Task 04 defect; CHANGELOG completion is Task 05/08 work and must land before release so the clause becomes fully true.

**Low 5 — `docs/migration.md:15–16`: "v0.1.1 is prospective and is not claimed here".** Accurate now and required by `winddown-positioning.md`; it will need a maintenance edit after a verified release. Integration follow-up, not a defect.

**Low 6 — `docs/migration-sources.md:31` (ACTSEAL): "Replay there checks consistency and does not authenticate responses or prove label truth, in its own words."** The README at `111afb3` says offline replay runs with no model call and that the application owns execution; the quoted limit was not located in the README lines this review read and may live in Actseal's threat-model or results docs. Cite the exact file or drop "in its own words". Non-blocking.

## Required changes (one revision round; wording only, no structural rework, no source change)

1. Row 12: replace "`from_dict` is not uniform across the ten exports, and deserializing validates or authorizes nothing." with wording of the form "`from_dict` is not uniform across the ten exports; deserialization performs at most constructor shape checks and never establishes record-hash consistency, authorization, provenance or truth, which only `validate_record_hash()`, `validate()` and `evaluate_acceptance` address."
2. Row 13: replace "No other tool replays an evalopt decision." with a bounded statement, e.g. "None of the routed destinations replays an evalopt decision; replay is defined only as equality with evalopt's own `evaluate_acceptance` at the pinned version."
3. Row 14: remove `SLSA-VSA-1.2` from the keys in both the map and the coverage record, or add an explicit "(v1.2: status context only)" to the row text. Row 9: add the same qualifier or drop the key. Keep the appendix rows unchanged.

Everything else in the three files is accepted as checked. Re-review of the revision can be limited to those four lines in the map and two in the coverage record plus `git diff --check`.

## Follow-ups (outside Task 04)

- Task 05/08: add the `624ed11` scalar-row fix to CHANGELOG before release so the map's CHANGELOG clause is complete (Low 4).
- Integration: schedule the post-release maintenance edit of the prospective `v0.1.1` sentence (Low 5).
- Appendix ACTSEAL citation precision (Low 6) may be folded into the revision round if trivial.
- A live status-code pass over the absolute URLs in `docs/migration-sources.md` remains undone by both the author and this review (network denied); root may run it read-only.

## Commands and results

```
git rev-parse HEAD                                  → 80816612c0ad9ccae4350095869e9fa77515187e
git status --short                                  → (clean)
git diff --check 2b4f00e..HEAD                      → no output, exit 0
git diff --stat 2b4f00e..HEAD                       → 3 files, 233 insertions(+)
git diff --stat fc3045d HEAD -- <9 cited baseline files> → empty (identical)
python3 -B plan/exec/preservation.py                → {"baseline": "fc3045dbda29c1d274747329ceb6724a783b0df7", "protected_files": 75, "errors": []}, exit 0
python3 -B (regex over __init__.py)                 → __all__ has 10 names in documented order
git show fc3045d:<file> | cat -n                    → kernel.py (all), attestation.py (cited ranges), __init__.py (all), evidence_adapters.py 155–255, docs/architecture.md 25–65/98–132, README.md 120–130/178–188, SECURITY.md 38–50, tests/test_kernel.py 92–115/186–202
awk column counts; relative-link existence loop; vocabulary grep; key usage vs definition grep → all consistent (see Verified)
python3 -B stdlib check (sys.path=src)              → from_dict shape ValueErrors; bogus attestation validate_record_hash False; real decision validate/replay True; fabricated validate True/replay False; malformed FAILED with empty evidence
git -C /Users/ajay/Developer/{actseal,dorian,frontier-scout,agent-reliability-ci} cat-file -e / describe / show <pin>:README.md|NOTICE|pyproject.toml|src/arci/hashing.py → pins present; descriptions v1.0.1-6, v1.4.1, v2.2.0-1, 0.7.0; paraphrases match
curl batch (10 raw snapshots, 3 rendered SLSA pages, sibling raw files) → DENIED by permission mode; not retried
```

No tests added or run beyond the direct stdlib check; the product suite was not rerun for prose.

## Limits

- External capability, status and digest statements were checked against the control-lane primary-sources preflight (an independent, dated record) and against local sibling clones at the pinned commits, not against live pages; this review did not re-fetch any URL. The SLSA v1.0 Retired / v1.1 Retired / v1.2 Approved statuses rest on that preflight's 2026-10-12 UTC observation.
- Reading `tests/test_kernel.py:98–110, 191–197` establishes specified cases, not a fresh passing run.
- Native elapsed time and token usage for this session are unavailable until after exit and are not estimated here. Requested and observable model: Fable 5.1 (`claude-fable-5-1`); effort level is not observable from inside the session.
- No source, test, benchmark, research artifact, tag, asset, contract or prior decision was changed; this file is the only write.
