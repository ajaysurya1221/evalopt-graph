# Task11 closeout inventory — read-only preparation

Snapshot: **2026-10-12 22:31:39–22:32:56 UTC**. Central control HEAD was `7ebd12580d155b7aa14cc065c26354ccd51c01ac`. This is evidence collection for Task11, not its final REPORT, final review, merge authority or a release-complete claim. Later changes require refreshed records.

Read the approved PLAN, task/status records, current report/review roster and relevant release/portfolio records. Queried local run branches/worktrees, public remote refs using read-only `git ls-remote`, five PRs using `gh api` GET, and their current check rosters. All network queries completed successfully. No ref was fetched into the repository, pushed, changed or deleted; no source, credential store, `.env`, raw model log or private campaign was read. Only this inventory was written. Counts below describe this finite snapshot.

## S1–S11 disposition

“Prepared” below means reviewed content exists on a pushed release branch/PR; it does not mean merged to main or released. Evalopt [PR42](https://github.com/ajaysurya1221/evalopt-graph/pull/42) was OPEN, draft, unmerged at `7043a0879a8a5491c110bd7d8a9f466700f920b7`, with base/main `fc3045dbda29c1d274747329ceb6724a783b0df7`. Its fourteen returned check entries were SUCCESS. No `refs/tags/v0.1.1` was returned by the fresh public ref query.

| Item | Current disposition | Evidence and remaining boundary |
|---|---|---|
| S1 — STOP ADR | Prepared; reviewed and in PR42 | `docs/decisions/archive-standalone.md`, Task03 final Codex/Fable ACCEPT. Main merge pending. |
| S2 — Use-instead matrix | Prepared; reviewed and in PR42 | README alternatives and `docs/portfolio.md`, Task05 final reviews and rendered-check record. Not yet the main README. |
| S3 — Migration map | Prepared; 16/16 entries reviewed and in PR42 | `docs/migration.md`, source appendix and coverage roster, Task04 final Codex/Fable ACCEPT. Documentation only; no converter or interoperability certification. |
| S4 — v0.1.1 deprecation release | Prepared; publication pending | Task08 patch accepted; original Task09 local artifacts accepted; final source at 7043 accepted by both reviewers; latest local candidate has Codex artifact ACCEPT, fresh candidate Fable report absent at this snapshot. PR42 remains unmerged; exact main/tag/hosted-bundle/deployment/public-byte gates remain. |
| S5 — Freeze deprecated surfaces | Prepared; documented freeze | Task05 notice/intake and Task08 notes preserve implementation, with no feature work. The only source change is the version literal; preservation evidence covers 75 files. No source deletion or archival. |
| S6 — Portfolio independence | Delivered bounded audit; retained in packet | `audits/portfolio-independence.md`, `reports/06-r1.md`, Task06 final reviews. Observed 0/4 coupling; attributed adaptation retained, 48 ARCI frozen hashes verified in the audit. No unnecessary dependency removal. |
| S7 — External wording | Delivered as four reviewed, pushed README PRs | Actseal70, Dorian44, Frontier Scout81 and ARCI14 are OPEN/unmerged at their reviewed heads. All have both review records and root verification/render records. ARCI still has two running check entries; no sibling main merge is authorized. |
| S8 — Final reproducibility receipt | Partial/prepared evidence; final receipt pending | Local qualification, source/artifact reviews, hosted PR-CI review and private evidence exist. No final main/tag/run/hosted-bundle/PyPI/GitHub byte-and-attestation receipt exists yet. Old and rebuilt local candidates have different identities; retain both separately. |
| S9 — Close migration intake | Prepared; reviewed and in PR42 | CONTRIBUTING, SECURITY and issue templates retain bug/docs/private-security routes while declining new features/integrations. Main merge pending. |
| S10 — Repository archival | Human-owned pending action | Never execute during this run. HUMAN_INBOX must say to verify final release and unresolved PR dispositions before the owner's GitHub archive action. No archive-complete claim. |
| S11 — Portfolio index | Prepared; reviewed and in PR42 | `docs/portfolio.md` is accepted Task05 content. Publication on main remains pending. |

## PR and main-ref snapshot

| Repository / PR | Reviewed public head | Live PR/check snapshot | Public main |
|---|---|---|---|
| evalopt-graph / [42](https://github.com/ajaysurya1221/evalopt-graph/pull/42) | `7043a0879a8a5491c110bd7d8a9f466700f920b7` | OPEN, draft, unmerged; 14 SUCCESS | `fc3045dbda29c1d274747329ceb6724a783b0df7` |
| actseal / [70](https://github.com/ajaysurya1221/actseal/pull/70) | `52dbc14554486e8ff9e31455d550bfc3d43f139e` | OPEN, not draft, unmerged; 17 SUCCESS | `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b` |
| dorian / [44](https://github.com/ajaysurya1221/dorian/pull/44) | `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | OPEN, not draft, unmerged; 5 SUCCESS | `eeb193792fac8a66b18f5222287a8fcf336dda08` |
| frontier-scout / [81](https://github.com/ajaysurya1221/frontier-scout/pull/81) | `b0d2ae108e62ef7c8a890e8294104a577217b4f8` | OPEN, not draft, unmerged; 7 SUCCESS | `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c` |
| agent-reliability-ci / [14](https://github.com/ajaysurya1221/agent-reliability-ci/pull/14) | `ba179f3a188710e38ec4557d2f65b66a8953c099` | OPEN, not draft, unmerged; 3 SUCCESS, 2 IN_PROGRESS | `a5adc834f74f5546fa3585b4ce6adfc96e2c37a3` |

Check-entry counts can include separate push/PR runs; they are not counts of independently reproduced tests. The current PR42 check result is consistent with the more detailed `reviews/10-ci-codex.md`, which accepts exact PR CI evidence, not future-main or release CI. Release and PyPI state were not independently re-queried by this inventory; the absence of a tag ref and the open PR are not a substitute for final publication verification.

## Every run lane branch and push state

All branch names in this table have the full prefix **`winddown/20261013/`** followed by the listed suffix. “Exact remote” means the live public remote tip equals the full local SHA below; it does not rely on possibly stale tracking refs. “Absent” means that exact branch name was not returned by the successful remote query. All seventeen branches have their corresponding local worktree retained. Pre-existing research/private worktrees are outside this lane inventory and were neither changed nor published.

| Repository | Branch suffix | Local worktree | Local head | Live remote state |
|---|---|---|---|---|
| evalopt-graph | `00` | `wt-control-00` | `7ebd12580d155b7aa14cc065c26354ccd51c01ac` | Absent |
| evalopt-graph | `01` | `wt-control-01` | `08c87b89f8a0d0ef09b6b8716ec13a014a4fd3b5` | Absent |
| evalopt-graph | `02` | `wt-control-02` | `5d6df50e7dbc73323503be211269ed872c5f6215` | Absent |
| evalopt-graph | `03` | `wt-semantics-03` | `9d306137ab78b473ff3419c4375735819a803cce` | Absent |
| evalopt-graph | `04` | `wt-semantics-04` | `8f60a3a40cd0f1f1100211009f25cbf920b11dd6` | Absent |
| evalopt-graph | `05` | `wt-notice-05` | `c8f2b1dee5f3f0a705e87ab0f4e520695275b3d4` | Exact remote |
| evalopt-graph | `06` | `wt-portfolio-06` | `f030ccdb5361ef393b2c8ec41181a773da29c706` | Absent |
| evalopt-graph | `08` | `wt-release-08` | `1d8148644984ab7a8548960439b3a9d0adf7f729` | Absent |
| evalopt-graph | `09` | `wt-verification-09` | `95b61a3ff9cbe6dc62acde75cf475958546aafc9` | Exact remote |
| evalopt-graph | `10` | `wt-release-10` | `d76d6587ecd51747db6c8094613473bdf3ab896b` | Exact remote |
| evalopt-graph | `10-r1` | `wt-release-10-r1` | `7043a0879a8a5491c110bd7d8a9f466700f920b7` | Exact remote; PR42 |
| evalopt-graph | `10-ops` | `wt-operations-10` | `7ebd12580d155b7aa14cc065c26354ccd51c01ac` | Absent |
| evalopt-graph | `control-review-01` | `wt-control-review-01` | `4fcce2394270cfe8c4e082de418dc9b322e9c97f` | Absent |
| actseal | `07A` | `wt-portfolio-07a` | `52dbc14554486e8ff9e31455d550bfc3d43f139e` | Exact remote; PR70 |
| dorian | `07B` | `wt-portfolio-07b` | `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | Exact remote; PR44 |
| frontier-scout | `07C` | `wt-portfolio-07c` | `b0d2ae108e62ef7c8a890e8294104a577217b4f8` | Exact remote; PR81 |
| agent-reliability-ci | `07D` | `wt-portfolio-07d` | `ba179f3a188710e38ec4557d2f65b66a8953c099` | Exact remote; PR14 |

Eight of seventeen named branch refs are pushed at their exact local tips; nine evalopt refs are absent remotely. Accepted content can be present by integration/cherry-pick on another pushed branch without the original lane ref itself being pushed. Do not silently equate those facts. The PLAN end-state rule requires every lane to be merged or have a pushed branch and REPORT; root must reconcile the nine absent refs, including review/helper lanes, or retain exact unavailable-push actions in HUMAN_INBOX. This inventory performs no push and makes no deletion/cleanup recommendation.

## Reports and review coverage

- Canonical task REPORTs exist for 00, 01, 02, 03, 04, 05, 06, 07A, 07B, 07C, 07D, 08 and 09. Their current file headers say DONE, but those author/root reports are not substitutes for reviews, and earlier incomplete/revised evidence remains historical. Relevant revision records include 03-r1, 04-r1, 05-r1, 06-r1, 07C-r1 and 07D-r1; the Task07B partial diagnosis and completion evidence are both retained.
- Both accepted reviewer records exist for 00/01, 02, 03, 04, 05, 06, all four 07 lanes, 08 and the original 09 artifact candidate. Use the final revision review where one exists, not an earlier REVISE. In particular `reviews/07C-fable.md` and `reviews/07D-fable.md` both now say ACCEPT despite stale STATUS entries.
- Final source/integration has both `reviews/10-integration-codex-final.md` and `reviews/10-integration-fable-final.md`, ACCEPT for exact 7043. Latest rebuilt local artifacts have `reviews/10-candidate-codex.md`, ACCEPT for exact d76 source/bytes; the 7043 correction changes excluded plan records only. **`reviews/10-candidate-fable.md` was absent at this snapshot**; do not infer its acceptance from the source review or original 09 artifact reviews.
- Operational tool-roster changes have accepted `10-operations-codex.md` and `10-operations-fable.md`; branch-preservation action has a decision and `10-branch-preservation-codex.md`; hosted PR CI has `10-ci-codex.md`. Those scopes remain distinct from source/artifact/publication approval.
- **Canonical `reports/10.md` and `reports/11.md` are missing**, appropriately pending actual completion or a bounded partial closeout. No `FINAL_REPORT.md`, `HUMAN_INBOX.md` or final sanitized release receipt was found. No final closeout review/PR is established by this inventory. Launch/standards-clarification drafts have not been identified in the current record roster; the 30-day closure deliverable still needs an explicit prepared/pending disposition, with no outreach sent.
- Before this new inventory, nineteen current review/report/task files were untracked in the central worktree, including final source reviews, latest candidate/CI/operational reviews, ARCI final review and root verification, render/gate/probe/preservation records and follow-up task briefs. They exist locally but are not yet in central HEAD. Preserve and deliberately integrate their reviewed records for closeout; do not call them already committed or published.

## Claims and state requiring final updates

1. **Refresh STATUS and complete Task10/11 reporting.** STATUS still lists 07C/07D under review, 09 with Fable active and 10/11 pending. Replace these snapshots only with actual later outcomes, retaining prior commits and all failed/partial records. Final source ACCEPT, PR CI success, local artifact acceptance and actual publication must remain separate.
2. **Reconcile the two control/release histories.** Central `7ebd125` contains the accepted run-local tool-roster amendment and newer operational work; PR42 remains exact 7043. Central does not yet incorporate the release branch's immutable ADR-link and report/PR-description corrections. A final-report branch must preserve both sets deliberately; blindly copying central's older report/docs would regress accepted corrections. Any new integrated head needs its own required checks/reviews.
3. **Finish the actual publication receipt or name its exact blocked stage.** Record exact merged main, main CI, annotated tag object/commit, workflow run/attempt, hosted bundle review, eligible native deployment approval, GitHub/PyPI states and actual matching bytes/attestations only after they exist. Keep original 95b and rebuilt d76 local artifacts distinct; do not reuse the original SPDX inventory for newer hashes. No current observation establishes v0.1.1 publication.
4. **Restore the temporary branch-cleanup preference.** `reports/10-branch-preservation-decision.md` records a reviewed native change from `delete_branch_on_merge=true` to false, with protections unchanged, and requires restoration to true after the final authorized own-repository merge. Its current remote value was not re-queried here. Final closeout must verify restoration and retained branch refs or put an exact restore action in HUMAN_INBOX. No sibling setting or merge is authorized.
5. **Account for failures and usage from actual receipts.** Preserve the initial mixed-model/cap-classified Task10 attempt as PARTIAL with no REVIEW; the stricter tool-roster probe and accepted operational amendment do not retroactively approve it. Likewise retain Task07B PARTIAL, first REVISE rounds, original scanner failures and the unsupported `uv x` attempt. Final usage must distinguish requested caps from native counters, actual calls/elapsed/cache/token fields from self-reports, and list-price estimates from subscription charges. Attributable Astra totals may be unavailable; do not invent them.
6. **Keep metrics finite.** The records support the fixed 16-entry coverage roster, observed 0/4 coupling, 75-file implementation preservation, 48 ARCI frozen hashes, 422-test/local conformance results and finite scanner controls. They do not establish zero undiscovered user blockers, future no-feature compliance through January 2027, adoption, semantic truth or universal secret absence. Keep 99 reachable/78 native scanned and separate later scan scopes distinct.
7. **Refresh sibling and research preservation snapshots at closeout.** Four sibling PRs are already pushed and must remain unmerged here; ARCI CI is not yet complete in this snapshot. Preserve old benchmark PRs/branches/tags/assets, never close or merge them as cleanup. S10 archival belongs only in the human inbox after final release/disposition checks.

No existing file was edited, no model or network mutation was performed, and no remaining release/review gate is waived by this inventory.
