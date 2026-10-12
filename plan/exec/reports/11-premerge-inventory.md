# Pre-merge preservation inventory

REPORT 11-PREMERGE-INVENTORY — Status DONE | Finite read-only preparation, not final closeout acceptance

Snapshot window: **2026-10-12 23:06:19.022540–23:06:22.497006 UTC**. Central control was `29ae21eef3e21c905df810dbbd6f6f4344c0ce03`; the clean closeout source was `ba5db20743e632f6295a2d9bfbda7867e6579978`. [PR43](https://github.com/ajaysurya1221/evalopt-graph/pull/43) was **open, draft and unmerged**, with that exact head. Final-source review and CI acceptance are not established by this inventory. Root must capture a genuinely fresh final state after the last authorized merge.

## Result and collection boundaries

All **19** local `winddown/20261013/*` branches across evalopt and the four sibling repositories had exactly matching live remote refs. Every one had an associated worktree. No additional remote branch with that prefix was returned. Before/after local branch and worktree inventories were identical during collection. The four sibling primary heads and remote mains matched their audit baselines; their README PRs remained open and unmerged. Research PRs 33–36 retained their original heads, draft/open state and live head refs. The v0.1.0 annotated-tag object and the compared release/asset metadata matched the initial retained baseline.

Raw stdout, stderr, command arguments, exit status and UTC intervals are privately retained under ignored `plan/artifacts/11-premerge-inventory/`, a newly created mode-0700 directory. The capture ran **86 recorded read-only commands**, all exit 0, plus local report-presence object probes whose outcomes are retained in `report-presence.json`. `capture.py` and `validate.py` preserve the collection and assertion methods. `validation.json` records PASS. The final evidence-manifest SHA-256 is `92e2c9e4050050dce8b2dd98df9401cee4c6164d96020384ed030e0d2432f1c0`.

Live remote evidence came from `git ls-remote` and explicit `gh api --method GET` calls. No fetch, ref update, push, merge, cleanup, setting change, model call, automation action, credential read or ignored campaign-content read occurred. Worktree metadata was enumerated, but historical campaign worktrees were not entered or inspected. This report is the only new public record written; raw API payloads remain private.

## Complete lane inventory

Every branch below has prefix **`winddown/20261013/`**; the suffix is shown to keep the table readable. **All rows have exact live remote equality.** Report references identify the central or closeout record, not a claim that early executor branches contain later reports.

| Repository | Branch suffix | Worktree | Local and live remote SHA | Associated record |
|---|---|---|---|---|
| evalopt-graph | `00` | `wt-control-00` | `29ae21eef3e21c905df810dbbd6f6f4344c0ce03` | `reports/00.md`; central operational records |
| evalopt-graph | `01` | `wt-control-01` | `08c87b89f8a0d0ef09b6b8716ec13a014a4fd3b5` | `reports/01.md` |
| evalopt-graph | `02` | `wt-control-02` | `5d6df50e7dbc73323503be211269ed872c5f6215` | `reports/02.md` |
| evalopt-graph | `03` | `wt-semantics-03` | `9d306137ab78b473ff3419c4375735819a803cce` | `reports/03.md`, `03-r1.md` |
| evalopt-graph | `04` | `wt-semantics-04` | `8f60a3a40cd0f1f1100211009f25cbf920b11dd6` | `reports/04.md`, `04-r1.md` |
| evalopt-graph | `05` | `wt-notice-05` | `c8f2b1dee5f3f0a705e87ab0f4e520695275b3d4` | `reports/05.md`, `05-r1.md` |
| evalopt-graph | `06` | `wt-portfolio-06` | `f030ccdb5361ef393b2c8ec41181a773da29c706` | `reports/06.md`, `06-r1.md` |
| evalopt-graph | `08` | `wt-release-08` | `1d8148644984ab7a8548960439b3a9d0adf7f729` | `reports/08.md` |
| evalopt-graph | `09` | `wt-verification-09` | `95b61a3ff9cbe6dc62acde75cf475958546aafc9` | `reports/09.md` |
| evalopt-graph | `10` | `wt-release-10` | `d76d6587ecd51747db6c8094613473bdf3ab896b` | `reports/10.md`; retained initial integration review |
| evalopt-graph | `10-r1` | `wt-release-10-r1` | `7043a0879a8a5491c110bd7d8a9f466700f920b7` | `reports/10.md`; integration-correction/final-review records |
| evalopt-graph | `10-ops` | `wt-operations-10` | `7ebd12580d155b7aa14cc065c26354ccd51c01ac` | `reports/10-tool-roster-probe.md`; operational reviews |
| evalopt-graph | `10-publication` | `wt-publication-10` | `8c8b7f4583a161947578fdd62d4c6658a1956f55` | `reports/10.md`; publication evidence |
| evalopt-graph | `11` | `wt-closeout-11` | `ba5db20743e632f6295a2d9bfbda7867e6579978` | `reports/11.md`, PARTIAL at this endpoint; PR43 |
| evalopt-graph | `control-review-01` | `wt-control-review-01` | `4fcce2394270cfe8c4e082de418dc9b322e9c97f` | Control-packet final reviews; auxiliary preservation branch |
| actseal | `07A` | `wt-portfolio-07a` | `52dbc14554486e8ff9e31455d550bfc3d43f139e` | `reports/07A.md`; PR70 |
| dorian | `07B` | `wt-portfolio-07b` | `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | `reports/07B.md`; PR44 |
| frontier-scout | `07C` | `wt-portfolio-07c` | `b0d2ae108e62ef7c8a890e8294104a577217b4f8` | `reports/07C.md`, `07C-r1.md`; PR81 |
| agent-reliability-ci | `07D` | `wt-portfolio-07d` | `ba179f3a188710e38ec4557d2f65b66a8953c099` | `reports/07D.md`, `07D-r1.md`; PR14 |

Canonical reports **00–06, 07A–07D, 08–11** all exist in the closeout worktree **and its committed HEAD**: 15 report files. The first 14 report headers say DONE; Task 11 says **PARTIAL — Closeout package prepared for its own review and merge**. This inventory verifies presence and header state, not acceptance merely because an executor wrote DONE. Central control contains the first 14 canonical reports in HEAD but does not yet contain `reports/11.md`; that is present on the pushed closeout branch. Auxiliary `10-*` and control-review branches have the associated preserved execution/review records and do not invent new canonical task IDs.

## Worktree cleanliness and primary heads

All **18 non-control lane worktrees** were clean. All **five primary worktrees** were also clean. The central control worktree had no tracked modification and exactly these four untracked operational records at both status reads:

- `plan/exec/reports/11-semantic-preparation.md`
- `plan/exec/reviews/11-pr-body-fable.md`
- `plan/exec/tasks/11-closeout-fable-review.md`
- `plan/exec/tasks/11-pr-body-review.md`

These expected central records are not modifications to a reviewed source worktree. This newly written inventory will itself be an additional untracked central record after the capture. Ongoing reviewers may add later records; the list is time-bounded.

| Repository | Primary local HEAD | Live remote main | Baseline interpretation |
|---|---|---|---|
| evalopt-graph | `fc3045dbda29c1d274747329ceb6724a783b0df7` | `8c8b7f4583a161947578fdd62d4c6658a1956f55` | Original primary checkout remains at the approved baseline; the separate publication worktree and remote main contain the merged release source. No local main update was attempted. |
| actseal | `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b` | same | Unchanged from Task 06 audit baseline |
| dorian | `eeb193792fac8a66b18f5222287a8fcf336dda08` | same | Unchanged from Task 06 audit baseline |
| frontier-scout | `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c` | same | Unchanged from Task 06 audit baseline |
| agent-reliability-ci | `a5adc834f74f5546fa3585b4ce6adfc96e2c37a3` | same | Unchanged from Task 06 audit baseline |

The four sibling PR GETs independently show PR70/44/81/14 open, not draft, unmerged and at the exact respective lane heads above. This inventory did not refresh their CI rosters and does not grant sibling-main merge authority.

## Preserved research PRs and refs

Compared with [research-preservation-01](research-preservation-01.md), each PR remains **open, draft, unmerged**, with `merged_at=null`. Each live remote head ref equals the PR head and baseline SHA:

| PR | Preserved head ref | Preserved SHA |
|---|---|---|
| [33](https://github.com/ajaysurya1221/evalopt-graph/pull/33) | `feat/skill-workflows-v1-public` | `2deb53feb2bf20061a754b80ff93fccafeac5af7` |
| [34](https://github.com/ajaysurya1221/evalopt-graph/pull/34) | `feat/skill-workflows-v2` | `eb181fa47a2b44c3363034038c288ba821f64d7d` |
| [35](https://github.com/ajaysurya1221/evalopt-graph/pull/35) | `feat/evidence-phase-difficulty` | `d8e6903df1aa12d35e1f7356200609617060baed` |
| [36](https://github.com/ajaysurya1221/evalopt-graph/pull/36) | `feat/response-contract-difficulty-v4` | `9e0527c23042723da93a752e6992e8682a9b3998` |

This establishes retained public heads and PR states at the captured time. It is not a new reproduction, grading or acceptance of historical experiments. No campaign content was opened and no old PR was closed or merged.

## v0.1.0 preservation

The fresh GitHub tag-ref GET and live remote ref both return annotated tag object **`50d20b15974da3a4a39967dd4977527708ed0def`**, identical to the initial `01-tags.json` and recorded baseline local ref. The fresh tag-object GET and remote peeled ref agree on commit **`42a65237303d77d8a38c2ff7d4110cb8b51a7375`**. This is content-addressed tag identity, not a claim that the annotated tag is cryptographically signed.

The current release GET returns release ID **356715018**, tag `v0.1.0`, not draft, not prerelease, published and last updated **2026-07-20T13:46:51Z**. Against the initial `01-releases.json`, these preservation fields are identical: release ID/node ID, tag, name, body, draft/prerelease flags, created/published/updated timestamps, target commitish and public/archive URLs; and each asset's ID/node ID, name, label, state, content type, size, digest, created/updated timestamps and download URL. Download counts were excluded from the identity comparison because legitimate downloads can change them; incidentally each remained 5 at both endpoints.

| Preserved asset | Asset ID | Bytes | API-reported SHA-256, equal to baseline |
|---|---:|---:|---|
| `evalopt-graph-0.1.0.spdx.json` | 483451472 | 4232 | `c619780d23b391f738c0ac68de3b0fb5c9565a7863db5e873382f230cea21c3f` |
| `evalopt_graph-0.1.0-py3-none-any.whl` | 483451471 | 134257 | `582140ec2b04c412ec7f56483b9e476c5b38ce309afb4f086b9a830e14d53156` |
| `evalopt_graph-0.1.0.tar.gz` | 483451469 | 349842 | `65845e9da30aad0ee22195076d8fcd525a282caac6809a4ea2c9cbd604547910` |
| `SHA256SUMS.txt` | 483451470 | 196 | `722b515fa680af697ab9ac808fc2938d32ef3d97c326a71a2543b3a6bfe896e1` |

All four asset IDs and metadata are retained; none was replaced in the observed records. No old release asset was downloaded or rehashed by this inventory, so the digest column is explicitly API metadata equality, not a fresh byte-verification claim. The release's `target_commitish=main` is not used to establish tag identity; the immutable annotated object and its peeled commit do that.

## Remaining limits and final refresh

The private assertion pass verified exact local/remote lane equality, one worktree for every lane, stable before/after local inventories, sibling baseline equality, all four research PR/ref equalities, v0.1.0 preservation fields and all canonical closeout report files in HEAD. A preliminary read-only baseline-inspection snippet first assumed every baseline-ref element was an object and failed on a string; the corrected shape-specific reader and retained validation passed. That inspection failure did not mutate or fetch anything.

No source or archive test suite was rerun, no release-completion or CI judgment was made, and no current setting/restoration claim is inferred. PR43 was still unmerged; its later review/CI, merge outcome, branch-retention and restored cleanup-setting readbacks remain separate obligations. Root's final post-merge snapshot must refresh actual state and retain this earlier snapshot rather than overwrite it.
