# STOP wind-down: final report

**Release, closeout merge and restoration are complete; terminal packet publication is the remaining mechanical step.** v0.1.1 is published on [GitHub](https://github.com/ajaysurya1221/evalopt-graph/releases/tag/v0.1.1) and [PyPI](https://pypi.org/project/evalopt-graph/0.1.1/). Deprecation, migration guidance and final documentation are merged. Main `b52c87539932c4b0682049f88eeeb5a433523150` passes every applicable hosted lane. Four reviewed portfolio README PRs remain open for the maintainer. Repository archival is deliberately human-owned.

The independently reviewed [full release-stage report](https://github.com/ajaysurya1221/evalopt-graph/blob/b52c87539932c4b0682049f88eeeb5a433523150/plan/exec/FINAL_REPORT.md) retains the detailed task evidence, metrics, changes, deviations and limits at its earlier endpoint. This final report and [terminal receipt](TERMINAL_RECEIPT.md) supersede only its pending closeout actions and earlier usage snapshot. Historical records are not rewritten as later evidence.

## Delivered against the memo

| Item | Final disposition |
|---|---|
| S1 STOP ADR | Merged; [decision](https://github.com/ajaysurya1221/evalopt-graph/blob/b52c87539932c4b0682049f88eeeb5a433523150/docs/decisions/archive-standalone.md) |
| S2 Use-instead matrix | Merged; [README](https://github.com/ajaysurya1221/evalopt-graph/blob/b52c87539932c4b0682049f88eeeb5a433523150/README.md) |
| S3 Schema migration map | Documentation only; all 16 fixed coverage entries have a mapping or explicit non-equivalence; [migration](https://github.com/ajaysurya1221/evalopt-graph/blob/b52c87539932c4b0682049f88eeeb5a433523150/docs/migration.md), [coverage](https://github.com/ajaysurya1221/evalopt-graph/blob/b52c87539932c4b0682049f88eeeb5a433523150/docs/migration-coverage.md) |
| S4 v0.1.1 deprecation release | Published 2026-10-12 22:56:37 UTC; [actual receipt](release-receipt.json) |
| S5 Freeze deprecated surfaces | Maintenance boundaries documented; implementation retained unchanged relative to the run baseline except its version literal |
| S6 Portfolio independence | Zero declared, locked or runtime-imported evalopt dependencies in four inspected primary trees; no unnecessary removal; [audit](audits/portfolio-independence.md) |
| S7 Standardise wording | Four reviewed, pushed README-only PRs; sibling mains untouched |
| S8 Reproducibility receipt | Public GitHub/PyPI bytes, installed API/replay, provenance and archive-level SPDX independently checked |
| S9 Close migration surfaces | Contribution/issue guidance published; security reporting remains available |
| S10 Archive repository | Not performed by design; [HUMAN_INBOX](HUMAN_INBOX.md) contains the exact action |
| S11 Portfolio index | Merged; [independent portfolio](https://github.com/ajaysurya1221/evalopt-graph/blob/b52c87539932c4b0682049f88eeeb5a433523150/docs/portfolio.md) |

No new product capability, converter, adapter, policy language, shared runtime dependency, benchmark programme or model trial was added. STOP was not reopened. Existing kernel bytes, ten exports, serialization, fail-closed semantics and zero required runtime dependencies were preserved against baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`, with only the authorized source-version normalization. v0.1.0-to-baseline inherited fixes are disclosed; no byte-identity claim against v0.1.0 is made.

## Final source, checks and reviews

[PR42](https://github.com/ajaysurya1221/evalopt-graph/pull/42) merged the reviewed deprecation source to `8c8b7f4583a161947578fdd62d4c6658a1956f55`. The annotated v0.1.1 tag remains at that release source. [PR43](https://github.com/ajaysurya1221/evalopt-graph/pull/43) merged the separately reviewed closeout to `b52c87539932c4b0682049f88eeeb5a433523150` at 23:14:19 UTC; its tree exactly equals reviewed head `ba5db20743e632f6295a2d9bfbda7867e6579978`. Final main is later documentation, not replacement release bytes.

Final-main CI and CodeQL passed **11 jobs / 95 reported steps**, with no skipped, pending, failed or cancelled jobs/steps. The PR-only Dependency review passed at the exact reviewed PR head; it is not misrepresented as a new main-push execution. Independent [main review](reviews/11-main-ci-codex.md) records the complete roster. Source qualification passed 422 tests, 32 conformance cases, 75 protected-file checks and 11 run-local controls. Evalopt has no configured typing gate. These finite checks do not establish semantic truth or universal correctness.

Both merged diffs received **two accepted review records**, independent Codex and fresh Fable, before merge. PR43's records are [Codex](reviews/11-closeout-codex.md) and [Fable](reviews/11-closeout-fable.md); PR42's exact-source and actual-hosted-artifact pairs are retained under `reviews/10-*`. **Merged changes with one review: 0. Merged changes with no review: 0.** The post-merge observational terminal packet remains on the control branch: root authored it and Codex independently checks its correspondence; no fresh Fable review of those later observations is claimed. It is not another main change.

The original branch-cleanup setting is restored to `true`; main/tag rulesets and the PyPI environment match their retained original responses. Both merged branch refs remain. The finite pre-receipt inventory matches all 19 local lane refs to their remote refs; the control branch advances only to publish this packet, followed by a private final readback. Every lane has an associated REPORT, including auxiliary review/operations records. Historical partial attempts and original failures remain intact.

## Portfolio PRs and preserved research

| Repository | Reviewed, pushed PR | Recorded validation |
|---|---|---|
| Actseal | [70](https://github.com/ajaysurya1221/actseal/pull/70) | 4216 passed; 1 platform skip; 31 authorized integration/packaging exclusions; lint/format/mypy pass; 17 hosted entries successful |
| Dorian | [44](https://github.com/ajaysurya1221/dorian/pull/44) | 1119 passed; 1 optional DuckDB skip; lint pass; 5 hosted entries successful |
| Frontier Scout | [81](https://github.com/ajaysurya1221/frontier-scout/pull/81) | 254 non-live tests; lint/type pass; 7 hosted entries successful |
| ARCI | [14](https://github.com/ajaysurya1221/agent-reliability-ci/pull/14) | 881 passed; 2 pre-existing Node SDK example skips; lint/type and all 48 frozen hashes pass; 5 hosted entries successful |

All four diffs have Codex and fresh Fable acceptance and bounded desktop/phone inspection. Hosted entry counts include configured push/PR duplication; they are not independent repetitions. No sibling main was merged. Research PRs 33–36 remain open drafts at their original heads, with no new trials or regrading. Old v0.1.0 tag and compared release/asset metadata are unchanged; that last check compared retained identities/digest declarations, not fresh downloads of old assets.

## Metrics, cuts and deviations

| Metric | Target | Measured result |
|---|---|---|
| Final release | By 19 October 2026 | Published 12 October UTC; actual public bytes verified |
| Portfolio runtime coupling | 0 of 4 | 0 of 4 within inspected manifests, locks and runtime imports |
| Migration coverage | 100% of major capabilities | 16 of 16 fixed roster entries; coverage is not lossless conversion |
| Archival | By 21 October | Human-owned, not executed |
| Migration blockers | 0 known by 11 November | No new blocker identified in finite review; future/user outcomes unmeasured |
| New features | 0 through 10 January 2027 | Zero added during this run; future interval unmeasured |
| Reopening | All memo criteria | Documented and not pursued, including three independent organisations, production commitment, non-composable gap and the 80%-overlap gate |

No authorized implementation item was cut to add a feature. S7 ends at reviewed PRs and S10 at exact archival instructions under the stated authority. The memo's 26.5 working-hour estimate is not elapsed run time. Run began 19:22:18 UTC; final-main acceptance at 23:19:29 UTC was **3h57m11s** later, within the ten-hour budget. Terminal record review/push follows that observation.

The full report and `DECISIONS.md` retain the three blind-proposal ADRs and substantive deviations: exact historical scanner exceptions with negative controls; supported pinned-uv invocation correction; draft lookup and local tracking-ref corrections; original partial Dorian and semantic-review attempts; rejected mixed-model/turn-limit review; explicit tool roster that is not a security sandbox; and reviewed reversible branch cleanup preservation. Two final observational corrections are disclosed in the terminal receipt: an exact-body trailing-LF comparison and an extra advisory CI-check counting assumption. Neither changed source, waived a gate, reran a completed merge or altered frozen evidence.

## Final retained usage and limits

[Usage snapshot03](usage-final.json), independently recomputed from 140 hashed inputs, contains **50 attempted CLI invocations / 50 unique complete results**: 44 supervised (38 DONE, 6 PARTIAL) and six direct. Fable 5.1 reports 16,516 input, 1,030,219 output, 25,832,473 cache-read and 3,262,241 cache-creation tokens. Its 412,954 thinking tokens are separately observed, not added twice. The rejected auxiliary Haiku entry remains counted once: 1,670 input and 63 output; it was not accepted as a substitute.

Combined native list-price estimate is **$123.381033**, not an observed subscription charge. Actual subscription charges, effective effort and run-attributable Astra/Codex token/cost totals are unavailable. Native 885-turn and summed-duration counters are not API-call or wall-time claims. Snapshot03's conservative `incomplete_snapshot: true` flag is retained; this is complete for the explicit retained roster, not all-account billing or pre-run planning activity. No model call followed that snapshot in this run.

The signed subject roster includes an unretained hosted `.gitignore` marker whose hash matches a local one-byte marker. Both archive bindings passed native verification. SPDX inventories the two distribution archives, not every dependency/source file. No separate PyPI publisher-attestation verification is claimed. Public evidence remains evidence, not a truth oracle.

## Next three human actions

1. Decide the four independent README PRs through their normal controls.
2. Verify the final release and outstanding PR dispositions, then archive evalopt through the exact [HUMAN_INBOX](HUMAN_INBOX.md) instructions if desired.
3. Use the unsent [clarification drafts](OUTREACH_DRAFTS.md) only if useful for migration validation; future closure metrics remain future observations.
