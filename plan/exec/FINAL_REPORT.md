# STOP wind-down report

**v0.1.1 is published.** Standalone feature development has ended. The kernel and historical research remain preserved; migration guidance is on main. Four reviewed README-only portfolio PRs are open for the maintainer. Repository archival remains human-owned.

This report records the release-complete endpoint of 2026-10-12 22:57:43 UTC. Its own closeout documentation is still subject to independent review and exact-head CI before merge. The terminal follow-through record on the retained control branch will record that final merge, main checks, restored cleanup preference, final usage and remote-ref reconciliation; none is assumed here.

## Shipped against the memo

| Memo item | Disposition | Evidence |
|---|---|---|
| S1 STOP ADR | Merged in PR42 | [STOP decision](../../docs/decisions/archive-standalone.md); Task03 final reviews |
| S2 Use-instead matrix | Merged | [README](../../README.md) and [migration guide](../../docs/migration.md) |
| S3 Schema migration map | Documentation only; 16/16 fixed entries covered | [Coverage roster](../../docs/migration-coverage.md); Task04 final reviews |
| S4 Final v0.1.1 | Published, not merely prepared | [GitHub release](https://github.com/ajaysurya1221/evalopt-graph/releases/tag/v0.1.1), [PyPI version](https://pypi.org/project/evalopt-graph/0.1.1/), [receipt](release-receipt.json) |
| S5 Freeze deprecated surfaces | Maintenance boundaries documented; implementation retained | README, CONTRIBUTING, STOP ADR |
| S6 Remove coupling temptation | Audit found 0/4 declared, locked or imported evalopt dependencies in inspected primary trees; no removal needed | [Bounded audit](audits/portfolio-independence.md); Task06 revised report |
| S7 Standardise portfolio wording | Four independently reviewed, pushed README-only PRs; no sibling main merge | PR table below |
| S8 Final reproducibility receipt | Actual hosted/public byte and attestation evidence retained | [Task10](reports/10.md), receipt and actual-byte reviews |
| S9 Close migration surfaces | Contribution/issue guidance directs corrections and declines new capabilities; security reporting retained | CONTRIBUTING, SECURITY, issue templates |
| S10 Archive repository | Deliberately not executed | [HUMAN_INBOX](HUMAN_INBOX.md) |
| S11 Portfolio index | Merged | [Independent portfolio](../../docs/portfolio.md) |

No converter, adapter, new predicate, policy language, integration, runtime dependency, benchmark programme or model trial was added. The 30-day plan is closure/migration validation; [announcement and clarification drafts](OUTREACH_DRAFTS.md) were not posted.

## Exact release and preservation

Verified baseline main was `fc3045dbda29c1d274747329ceb6724a783b0df7`. PR42 reviewed head `7043a0879a8a5491c110bd7d8a9f466700f920b7` merged to `8c8b7f4583a161947578fdd62d4c6658a1956f55` with identical trees. Annotated tag `v0.1.1` is object `b5b96001bb2fcc0059183bcc0a2a2151129f1404` and points to that source. Required PR CI and resulting-main CI passed; release run `38317836286`, attempt 1, passed all 15 jobs and 123 reported steps.

| Published artifact | Bytes | SHA-256 |
|---|---:|---|
| Wheel | 137354 | `d6cffc1a0f1b56b087805ee18662d11863d6063b231b2d8e97d64a3430c8e739` |
| Sdist | 382132 | `2c49351a7c6343b31faf3b9ff2c7359cc51a41f6249559c31f388be600facf10` |
| SHA256SUMS.txt | 196 | `7d7661547846d824f0709288d4730a73352903a4e58e9e63e6a68bfd7ca52e22` |
| Archive-level SPDX | 4232 | `9dee6be448e411d3190ea8ae25eb4fef2801feaa8dcdbd9065628c04ea95ff29` |

All four published GitHub assets equal the accepted hosted bundle. Both PyPI files equal their GitHub/bundle counterparts and PyPI metadata. A fresh no-deps installation from public PyPI passes the existing installed API/replay smoke. GitHub Sigstore provenance and SPDX v2.3 statements bind both distribution hashes to the exact workflow/source/tag/run. Native deployment approval used the existing eligible endpoint after independent actual-byte acceptance; no environment protection was changed.

Independent [published-byte review](reviews/10-published-codex.md) and [publication-workflow review](reviews/10-publication-workflow-codex.md) separately accepted the actual endpoints. The 75-file preservation control passes against baseline after only the authorized version-literal normalization. Ten exports, serialization/replay, five-state fail-closed semantics and zero required runtime dependencies are retained. The full source suite passed 422 tests; the existing conformance fixture has 32 cases, and the run-local supervisor has 11 offline controls. Evalopt has no configured type gate; none was invented. These finite checks do not establish universal correctness.

Main already contained ten commits beyond v0.1.0. Release notes disclose the inherited scalar-input fail-closed fix, interpreter selection, readiness wording/docstrings and packaging/optional-development dependency changes. This wind-down is unchanged relative to its verified baseline except the version literal under src; it is not claimed byte-identical to v0.1.0. Göktuğ's contribution attribution remains intact.

Study PRs 33–36 remain draft and open at their previous heads; no research branch was merged, regraded, retried or republished. The v0.1.0 tag and release metadata/assets' recorded identities remain unchanged. The final preservation refresh compared metadata/digest declarations, not newly downloaded old-release bytes. Raw campaigns and evidence stay outside public operational reports. All 48 entries in ARCI's current frozen manifest passed unchanged.

## Portfolio PRs

| Repository | PR / exact head | Root checks and hosted snapshot |
|---|---|---|
| Actseal | [70](https://github.com/ajaysurya1221/actseal/pull/70), `52dbc14554486e8ff9e31455d550bfc3d43f139e` | 4216 passed, 1 platform skip, 31 intentionally excluded integration/packaging tests; lint/format/mypy pass; 17 hosted entries success |
| Dorian | [44](https://github.com/ajaysurya1221/dorian/pull/44), `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | 1119 passed, 1 optional DuckDB skip; lint pass; 5 hosted entries success |
| Frontier Scout | [81](https://github.com/ajaysurya1221/frontier-scout/pull/81), `b0d2ae108e62ef7c8a890e8294104a577217b4f8` | 254 non-live tests passed; lint/type pass; 7 hosted entries success |
| ARCI | [14](https://github.com/ajaysurya1221/agent-reliability-ci/pull/14), `ba179f3a188710e38ec4557d2f65b66a8953c099` | 881 passed, 2 pre-existing Node SDK example skips; Ruff/basedpyright/48 frozen hashes pass; 5 hosted entries success |

Each has Codex and fresh Fable acceptance and bounded desktop/phone rendering inspection. Hosted entry counts can include push/PR duplication; they are not independent replications. All four remain unmerged by this run. No sibling dependency, source, package version, attribution or frozen test changed.

## Review coverage and deviations

Every source change merged through PR42 has accepted independent Codex and fresh Fable reviews. The implementer's REPORT never grants acceptance. Final integration reviews bind exact 7043; actual hosted artifact reviews bind exact 8c8b7f4 bytes. There are **zero merged changes with only one review and zero merged changes with no review** at this endpoint. The new closeout diff is unmerged until it satisfies the same gate.

| Scope | Accepted review records |
|---|---|
| Bootstrap, probe and supervisor | 00/01 combined final reviews; 02 final reviews |
| STOP decisions, migration, notice and audit | 03/04/05/06 final Codex and Fable records; earlier REVISE records retained |
| Four portfolio README diffs | 07A/07B/07C/07D Codex and fresh Fable ACCEPT records |
| Release metadata/scanner, local artifacts | 08 pair; 09 pair; rebuilt 10-candidate pair |
| Final source and hosted release artifacts | 10-integration-*-final and 10-hosted artifact pair; separately scoped CI/operational records |

The three blind-proposal decisions are retained in the migration-interface, positioning and routing ADRs. STOP, no integration and no API change took precedence; substantive differences used the prescribed fresh Fable opinion and reversible choice.

Other deviations were recorded rather than hidden: the exact historical scanner exemptions were narrowed to rule+commit+path+captured-value intersections and negatively tested; no whole-file or genuine-secret suppression was accepted. The CLI did not support `uv x`, so the same pinned tool's supported `uv tool run` performed Twine checks. A draft REST lookup returned 404 while native GraphQL resolved the existing draft. A no-prune fetch recovered a local tracking-ref race without remote deletion. These command corrections did not change frozen evidence or gates.

One combined Fable review attempt returned auxiliary Haiku usage and a native turn-limit failure; it remains PARTIAL and was never accepted. Its cause is not established. Subsequent reviewed explicit tool-roster calls passed the canonical Fable identity gate; that tool roster is not a security sandbox. The partial Dorian executor and first semantic/review revisions are preserved, not relabelled success. Raw requested CLI turn caps and native turn counters have different semantics; numeric differences alone are not labelled cap bypasses.

The repository's existing auto-delete preference conflicted with branch preservation. The separately reviewed [operational ADR](../../docs/decisions/preserve-winddown-branches.md) permits a reversible one-field change to false, leaving protections byte-identical. PR42's branch was retained. Restoration to the captured original true follows the final own-repository merge and must be recorded, not presumed.

## Metrics and bounded conclusions

| Metric | Target | Observed endpoint |
|---|---|---|
| Final release | v0.1.1 by 19 October 2026 | Published 12 October UTC; exact public bytes verified |
| Runtime coupling | 0/4 portfolio repositories | 0/4 in inspected declarations, locks and imports; audit scope is explicit |
| Migration coverage | 100% major capabilities | 16/16 fixed roster entries mapped or explicitly non-equivalent/unmapped |
| Archival | By 21 October | Human-owned pending; repository not claimed archived |
| Migration blockers | 0 known by 11 November | No new blocker identified in this finite review; semantic non-equivalences documented; future/user outcomes unmeasured |
| New features | 0 through 10 January 2027 | Zero added during this run; later period unmeasured |
| Reopening | All memo gates | Documented, not pursued: three independent organisations, real unmet non-composable gap, one production commitment and 80%-overlap gate clearance |

SLSA VSA 1.0 is identified as retired historical prior art; it is not offered as a current migration destination. No hashes-as-signatures, attestation-as-semantic-truth, automatic preservation of evalopt states, standards certification, endorsement or adoption claim is made.

## Usage and time

Run began 2026-10-12 19:22:18 UTC under a ten-hour cap. Release publication occurred after 3h34m19s. The memo's 26.5 working-hour estimate was not represented as elapsed run time. At the 22:58:23 UTC inventory, 48 attempted Fable CLI invocations had 48 unique complete native results, no unknown/open usage receipts and no duplicate identity conflicts. Fable fields total 16,064 input, 990,829 output, 24,965,286 cache-read and 3,121,467 cache-creation tokens; 398,191 thinking tokens are separately reported and not added twice. Rejected auxiliary Haiku usage is retained: 1,670 input and 63 output. Combined native list-price estimate is $118.374736, **not an observed subscription charge**. Effective effort and Astra/Codex run-attributable token/cost totals are unavailable. Final review calls after this snapshot belong in the terminal usage receipt.

See [usage method](reports/11-usage-method.md). Complete terminal modelUsage records are counted once; copied finish summaries and overlapping counters are not added. Pre-run consultations and sessions outside the retained roster are excluded. No billing or model substitution was authorized as a recovery path.

## Known limits, cuts and next three steps

The signed subject roster includes an unretained `.gitignore` marker alongside both archives; its digest matches a local one-byte marker, not an independently recovered hosted file. Both distribution bindings passed native verification. SPDX is an archive inventory, not a full dependency/source SBOM. No separate PyPI publisher-attestation verification is claimed. No workflow repair or new release was started for this cosmetic observation.

No sprint capability was cut in favour of another feature. S10 is intentionally human-owned; S7 ends at reviewed PRs by authorization. Thirty-day outcomes and repository archival are not compressed into this run. The remaining machine work at this report endpoint is the closeout diff's own review/CI/merge and settings/ref reconciliation.

1. Complete the bounded closeout gates and retain their terminal receipt; do not start new product work.
2. Maintainer decides the four README PRs through their normal controls.
3. Maintainer verifies release/PR dispositions and archives evalopt if still desired, following HUMAN_INBOX.
