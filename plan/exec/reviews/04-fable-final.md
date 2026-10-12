REVIEW 04-FINAL — Reviewer Fable xhigh | Verdict ACCEPT

Target: `8f60a3a40cd0f1f1100211009f25cbf920b11dd6` on `winddown/20261013/04`, worktree `wt-semantics-04`, reviewed as the delta from `80816612c0ad9ccae4350095869e9fa77515187e`. The revision touches exactly `docs/migration.md`, `docs/migration-sources.md` and `docs/migration-coverage.md` (32 insertions, 27 deletions). Nothing under `src/`, `tests/`, `bench/`, README, `docs/architecture.md`, ADRs, PLAN, task specs or prior review records changed. The worktree was clean at the target SHA.

Fresh, read-only session. Prior records read for scope only: `reviews/04-codex-01.md` (F1–F6), `reviews/04-fable-01.md`, `reviews/04-root-observations.md`, `reports/04-url-check.md`; the author `reports/04-r1.md` was read after the independent inspection and only compared, no finding rests on it. Independent prior review findings on unchanged material are carried, not repeated. No model call, subagent, credential or `.env` access, target edit, Git mutation, install or network write. One read-only `curl` batch for the four newly added links was denied by the permission mode and not retried.

This verdict accepts the documentation diff for integration. It is not release approval, and the independent Codex final review remains required under the contract.

## Required corrections, each checked against source

1. **VSA verifier compromise (Codex F1)** — `docs/migration-sources.md:25` now ends "it does not protect against verifier compromise, and consumers must choose trusted verifiers." That is the limitation the control-lane preflight recorded for v1.2 ("explicitly excludes protection against a compromised verifier") and the one Codex read at immutable `ae7fc76` lines 316–318. v1.2 stays "Approved on the access date, status context only, not a route"; v1.0 stays Retired historical prior art. The reversed phrase "excludes a compromised verifier" no longer appears in any of the three files. Accurate.

2. **Deserialization versus integrity/authorization (Codex F2, Fable Minor 1, root observation 1)** — map row 12 (`docs/migration.md:72`) now says `from_dict` is not uniform; deserialization "may enforce constructor, type, shape and base64 checks; it does not by itself establish record-hash validity, replay or policy authorization, and no kernel check establishes authentication or truth." Coverage row 12 cites `kernel.py:230–242` and `attestation.py:147–153`. Verified at `fc3045d`: `AcceptanceInput.from_dict` (229–242) calls the validating constructor and builds nested `ClaimRecord`, `EvidenceAttestation.from_dict`, `SupportAssessment.from_dict`; `RetrievedArtifact.from_dict` (146–153) uses `b64decode(..., validate=True)` and a constructor rejecting empty locator or media type; `EvidenceAttestation.from_dict` and `SupportAssessment.from_dict` (215–216, 291–292) only filter known fields through `_known` (70–72) and never call `validate_record_hash()`; `AcceptanceDecision.from_dict` (286–290) never calls `validate()` or `replay()`. Direct stdlib run against the unchanged `src/`: bad schema → `ValueError`; bad base64 → `binascii.Error` (a `ValueError` subclass) "Only base64 data is allowed"; empty media type → `ValueError`; a bogus attestation constructs and `validate_record_hash()` is False; a status-tampered decision constructs and `validate()` and `replay()` are both False. The Fable-suggested phrase implying that `validate()`/`evaluate_acceptance` establish provenance or truth was correctly not used; row 12 states the opposite. Accurate.

3. **Witness functionaries, not attestors (Codex F3)** — map row 7 (`docs/migration.md:67`) and coverage row 7 now read "a Witness policy identifies permitted collection signers through public keys or certificate trust rules"; "attestor" occurs nowhere in the three files, so no attestor source anchor is needed. The wording is the bounded analogy Codex proposed and matches the preflight's reading of the policy document at `1eaafd5` (trusted functionaries, collection signatures and trust roots, signer-to-step authorization). The stable material-consuming authority versus deprecated retrieving facade text is unchanged. Accurate within the limit below.

4. **Finite non-equivalence claims (Codex F4, Fable Minor 2, root observation 2)** — label definition (`migration.md:56`), rows 6, 11 and 13, coverage rows 6, 11 and 13 and the appendix attribution paragraph (`migration-sources.md:78–82`) are all bounded to "the inspected sources" / "inspected route sources"; the appendix now separates source-paraphrased capabilities and limits from non-equivalence statements, which it labels "bounded interpretations of this finite source set as read on the access date; no primary source guarantees such an absence." No universal negative ("no other tool", "every tool", "no destination publishes") remains (grep). No substitute universal about every routed project was introduced. The four labels, seven routes in ADR order and the no automatic/lossless mapping rule are unchanged. Accurate.

5. **Allowlist types (Codex F5)** — map row 1 and coverage row 1 now name `allowed_authority_policies` and `authorized_record_sha256` as the SHA-256 digest allowlists and `allowed_verifiers` as id/version pairs. Verified at `kernel.py:55–57` (types), `89–90` (nonempty id and version), `95–97` (64-hex lowercase digests); stdlib run reproduces both `ValueError` messages. The coverage line citations are exact. Accurate.

6. **Missing source pins (Codex F6)** — GH-RULES now links both `about-rulesets.md` and `available-rules-for-rulesets.md` at `4b1c2131e25f98e22d54e2e3c450cf7285d469f3`; the SLSA-VSA-1.2 revision cell adds the v1.1 official page and immutable `3e02e587beb414f69b07310eb2ab9f0049b624a6/spec/verification_summary.md`, commit 2026-04-13T11:24:50Z, marked status context only; the v1.1 receipt row points to that cell. Revisions, commit timestamps, line counts (372, 418) and digests match the control-lane `04-primary-sources-preflight.md` verbatim. Every receipt now has a linked revision. The appendix keeps eight external rows and twelve keys. Accurate.

7. **v1.2 as status context only (Fable required change 3)** — `SLSA-VSA-1.2` is removed from map rows 9 and 14 and from coverage rows 9 and 14; coverage row 9 says v1.2 is "status context confined to the appendix and the map's SLSA note." The key is now used only in the map's SLSA paragraph (`migration.md:45–48`) and defined in the appendix, consistent with `migration-interface.md` and `routing-boundary.md`. Row 9 still cites the retired v1.0 as prior art only. Accurate.

8. **Durable release status (root observation 3, Fable Low 5)** — `migration.md:13–16`: the map is tied to baseline `fc3045d`, "not to a release"; whether `v0.1.1` has been published "is tracked separately on the public releases page and is not asserted here." No "prospective", "is published" or "archived" wording remains; `v0.1.1` is still called the final deprecation release, matching `winddown-positioning.md`; the releases link targets the same repository as the worktree's `origin` remote. The inherited-difference disclaimer (CHANGELOG plus archive decision) is retained. Accurate and will not go stale after an authorized release.

9. **Actseal attribution (Fable Low 6)** — `git show 111afb3cf0dbab94e7bdf7917e800ba6faaeac0b:README.md` in the local clone, line 13: "Replay checks consistency; it does not authenticate responses or prove label truth." The appendix's "in its own words at line 13 of that README" is exact. Accurate.

## Structure, preservation and leakage

- Map and coverage each have 16 numbered rows in order 1–16; entry and label pairs identical row by row; label counts 5 conceptual analogy, 4 host responsibility, 4 project-specific semantics, 3 no supported equivalence, matching the coverage header; the Keys column equals the paired External keys column on every row.
- Twelve keys defined once in the appendix, twelve used, none undefined or unused. Table column counts consistent in all three files (map 4-col and 7-col, appendix 7/2/3-col, coverage 6-col). All 16 relative links resolve.
- `__all__` has the same ten names in the same order at HEAD and `fc3045d`; rows 1–10 follow it.
- No `/Users`, `file://`, `.venv`, worktree names, private artifact file names, token/secret/key/password patterns in the three public files.
- Job table, shared limitations and checklist are textually unchanged by this revision (word diff).

## Findings by severity

No blocking or major finding. No revision round is required.

- **Low 1 — coverage row 12 citation precision.** The clause "without calling `validate()` or `replay()`" is most directly evidenced by `AcceptanceDecision.from_dict` at `kernel.py:286–290`, which is not among the cited lines; the cited `kernel.py:230–242` and `attestation.py:147–153` carry the constructor, nested `from_dict` and base64 points. The statement is true as written. Optional citation addition at integration; not a defect requiring a round.
- **Low 2 — four new links unverified here.** `https://github.com/ajaysurya1221/evalopt-graph/releases`, the GitHub `available-rules-for-rulesets.md` snapshot at `4b1c213`, `https://slsa.dev/spec/v1.1/verification_summary` and the SLSA `3e02e58` snapshot. Network was denied in this session. Three of the four were retrieved by the control lane on 2026-10-12 UTC per the preflight; the releases page is a navigation link to the origin repository. Root's read-only status check remains the gate for these four; the 32 original links are unchanged and already confirmed by root.
- **Low 3 (carried, outside Task 04)** — CHANGELOG still lacks the `624ed11` scalar-row entry, so the map's "disclosed in the CHANGELOG" clause is carried by its "enumerated in the archive decision" clause until Task 05/08 lands.

## Required changes

None.

## Follow-ups

- Root: read-only HTTP check of the four new links listed under Low 2.
- Independent Codex final review of `8f60a3a` per the contract; merge requires both acceptances.
- Task 05/08: CHANGELOG entry for `624ed11` before release.
- Optional at integration: add `kernel.py:286–290` to coverage row 12's citations.

## Commands and results

```
git rev-parse HEAD                                        → 8f60a3a40cd0f1f1100211009f25cbf920b11dd6
git status --short                                        → (clean); branch winddown/20261013/04
git diff --stat 8081661..8f60a3a                          → 3 files, 32 insertions(+), 27 deletions(-)
git diff --name-status 8081661..8f60a3a                   → M docs/migration-coverage.md, M docs/migration-sources.md, M docs/migration.md
git diff --check 8081661..8f60a3a                         → no output, exit 0
git diff --check 2b4f00e..8f60a3a                         → no output, exit 0
python3 -B plan/exec/preservation.py (read first; identical to control copy)
                                                          → {"baseline": "fc3045dbda29c1d274747329ceb6724a783b0df7", "protected_files": 75, "errors": []}, exit 0
git diff --name-only fc3045d HEAD -- src tests bench      → empty
git diff --stat fc3045d HEAD -- <9 cited baseline files>  → empty (byte-identical)
git diff --word-diff=plain 8081661..8f60a3a (per file)    → changed spans listed above; job table, shared limits, checklist untouched
git show fc3045d:src/evalopt_graph/kernel.py | awk 44–104, 140–246, 249–302
git show fc3045d:src/evalopt_graph/attestation.py | awk 56–74, 120–155, 184–310
python3 -B (sys.path=src, stdlib only)                    → from_dict presence 6 of 9 types; ValueError on bad schema, empty locator, empty media type, bad verifier pair, non-hex digest; binascii.Error on bad base64; bogus attestation validate_record_hash False; tampered decision validate False, replay False
python3 -B structure script                               → 16/16 rows, paired labels, 5/4/4/3, keys equal, 12 defined/12 used, column histograms consistent, 16 relative links OK, zero leakage hits, zero "attestor"/"prospective"/universal-negative hits
python3 -B URL set diff 8081661 vs 8f60a3a                → 4 added, 0 removed
git -C /Users/ajay/Developer/actseal show 111afb3…:README.md | sed -n 1,30p → line 13 matches verbatim
git remote -v                                             → origin https://github.com/ajaysurya1221/evalopt-graph.git
curl -sS -I/-L on the 4 new URLs                          → DENIED by permission mode; not retried
```

## Limits

- External standards facts (SLSA v1.2 verifier-compromise text, Witness functionary key/certificate rules, GitHub and SLSA snapshot revisions) were checked against the retained control-lane preflight and Codex's dated retrieval, not re-fetched; network was denied. No local Witness or in-toto clone exists for an offline read.
- The product test suite was not run; this is a prose-only change and the direct stdlib checks above read the unchanged baseline modules without installation.
- Requested and observable model: Fable 5.1 (`claude-fable-5-1`); effort level not observable from inside the session. Native elapsed time and token usage are measured externally and are not estimated here. Seven tool turns before this write.
- No source, test, benchmark, research artifact, tag, asset, contract, ADR or prior review changed. This file is the only write of the session.
