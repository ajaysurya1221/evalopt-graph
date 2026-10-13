REVIEW portfolio-merge-07CD — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT for unchanged source and current CI

Native merge decisions at 2026-10-13 02:18:44 UTC: **Frontier Scout PR 81 BLOCKED by native review approval; ARCI PR 14 READY for a normal merge at the exact observed head/base.** Neither decision is a merge execution. No native requirement is waived by prior offline review acceptance.

## Exact source and current base correspondence

| Repository / PR | Accepted and current head | Accepted and current base | Actual scope |
|---|---|---|---|
| Frontier Scout / 81 | `b0d2ae108e62ef7c8a890e8294104a577217b4f8` | `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c` | README.md only, +20/-0 |
| ARCI / 14 | `ba179f3a188710e38ec4557d2f65b66a8953c099` | `a5adc834f74f5546fa3585b4ce6adfc96e2c37a3` | README.md only, +17/-0 |

I read the repository operating contracts, actual current diffs, public PR file records and decoded public README contents. Public README bytes exactly match the locally retained accepted commits and their Git blob IDs. Current source/base identities match the earlier final Codex and fresh Fable ACCEPT records (`07C-codex-final.md`, `07C-fable.md`, `07D-codex-final.md`, `07D-fable.md`). No later source or base drift exists in the captured endpoint.

The additions preserve independent repository ownership and evidence limits. Frontier Scout remains a native-control compiler and PR scope verifier with unsigned local receipts that cannot approve changes. ARCI conditions non-inferiority on PASS within registered margins and conditions, preserves author-supplied chronology limits and NOTICE attribution, and does not gain an evalopt package/runtime dependency. Nothing adds a product capability or changes another repository's semantics.

Both `git diff --check <base> <head>` commands pass. Both retained task worktrees remain clean at exact heads. Fresh `shasum -a 256 -c FROZEN.sha256` passes all 48 ARCI entries. Independently hashing every frozen blob from the exact head verifies all 48 against the manifest and byte-compares each to the original base; all match. No frozen file, NOTICE, source, test, environment or Git ref was changed.

Public README SHA-256 values:

- Frontier Scout: `d0e7673c2310e1ae87f2fe1715ed0c944062a3914b549112853251fe325600e9`.
- ARCI: `10471b789e55f49cd13f93659e9bb903bf4b0aee3bdcd7d860cca4a0edff081a`.

## Complete actual CI current-attempt review

| Repository | Workflow / run | Attempt | Jobs | Reported steps | Result |
|---|---|---:|---:|---:|---|
| Frontier Scout | CI / 38315457758 | 1 | 2 | 25 | success |
| Frontier Scout | Frontier Scout verify / 38315457787 | 1 | 2 | 14 | success |
| Frontier Scout | Native CodeQL default setup / 38315454988 | 1 | 1 | 10 | success |
| ARCI | CI / 38316271264 | 1 | 4 | 53 | success |

All nine jobs are completed/success at their exact respective heads. The complete before/after current-run inventories and retained exact-attempt jobs agree; no rerun, cancellation, pending job or failed job is present.

Frontier Scout has 49 successful reported steps, zero skipped. Its CI jobs are `test` and `action-source-install`; its two PR verification jobs are `verify` and `verify-action`. The verification workflow deliberately uses advisory mode and candidate source: successful execution is not trusted approval or enforcement evidence. The third dynamic run supplies `Analyze (actions)`; fresh native CodeQL default-setup data explicitly configures only `actions`, with default queries. Do not describe this as a new Python CodeQL scan. The additional CodeQL service check and CodeRabbit status are successful but are not additional independent workflow jobs or required human reviews.

ARCI has 53 reported steps: 49 success and four expected conditional skips. The two `Upload failed pytest stores` steps are skipped because their condition is `failure()`. Python 3.11 also skips Node setup and JavaScript SDK installation, explicitly restricted in the frozen workflow to Python 3.14; those steps succeed on 3.14. Both Linux check jobs and both macOS statistics re-derivation jobs succeed. No required execution lane is skipped. This does not infer individual test-case skip counts from job/step metadata.

## Native merge gates and blockers

**Frontier Scout PR 81:** GitHub reports OPEN, non-draft, MERGEABLE but `mergeStateStatus=BLOCKED` and `reviewDecision=REVIEW_REQUIRED`. Fresh reviews and latestReviews are empty; there are no review threads. Classic protection requires one approving review, dismisses stale approvals, enforces administrators, requires conversation resolution and strict passing `test` from GitHub Actions. The required `test` check passes. The authenticated viewer and PR author are both `ajaysurya1221`; a locally retained Codex/Fable review is not a native eligible approving review. Therefore do not attempt an admin merge or lower the review requirement. The old repository instructions describing protection relaxation/admin merges are superseded by this task's explicit no-bypass boundary.

Frontier Scout additionally has `delete_branch_on_merge=true`. That is separate from its native review blocker and conflicts with this run's branch-retention requirement. Root must preserve the source ref through an authorized native path before an eventual merge; this reviewer did not change the preference or restore/create/delete any branch.

**ARCI PR 14:** GitHub reports OPEN, non-draft, MERGEABLE and `mergeStateStatus=CLEAN`; reviewDecision is null, with zero review threads and zero native reviews. The branch-rules API returns an empty list; classic protection returns the native 404 `Branch not protected`, and `gh pr checks --required` exits 1 saying no required checks are reported. Those expected absence responses are retained and are not claimed as successful required-check runs. All configured CI lanes were nevertheless independently verified above, and the two accepted source-review records remain required by this run. `delete_branch_on_merge=false`; squash merging is enabled. No native approval or branch-deletion blocker was observed for the exact ARCI head/base.

## Required changes, evidence and bounds

No README or CI change is required by this review. Frontier Scout needs a genuine eligible native approval and source-branch preservation before merge; ARCI is ready for root's normal exact-head merge under the new user authorization. If either head, base, current run attempt or native readiness changes, refresh the affected gate. The subsequent merged-main CI is a separate check.

Private raw API/GraphQL responses, commands, pinned workflow sources, complete jobs/steps, actual diff/public-byte comparisons and frozen-file checks are retained under `plan/artifacts/portfolio-merge-20261013-review-b/`. Endpoint receipt SHA-256: `f5c038789b4e0d23a4b1912b929da2d158321059100c1e7961f9271aefa3810c`.

No full local test suite was redundantly rerun: this review verifies unchanged previously accepted source and fresh hosted evidence. No network mutation, model invocation, credential or .env read, package install, target edit, ref mutation, protection change or merge occurred. Only the assigned central review and private evidence were written. Repository-specific Python environments and all frozen boundaries remain separate.
