# Portfolio README merge follow-up — 13 October 2026

This is a separately authorized follow-up to the completed STOP wind-down. The user said: “Go ahead and merge the four portfolio README PRs after verifying their reviews and CI. Keep the repos independent; I’ll handle archiving evalopt.” That authorizes normal merges of these four existing PRs; it does not authorize protection bypasses, source changes, branch deletion or archival. The original PLAN, FINAL_REPORT, release receipts and usage totals remain historical records.

## Actual dispositions

| Repository / PR | Accepted source head | Result | Squash commit |
|---|---|---|---|
| [Actseal #70](https://github.com/ajaysurya1221/actseal/pull/70) | `52dbc14554486e8ff9e31455d550bfc3d43f139e` | Merged at 02:27:46 UTC | `ad62ec8ff33f858e1759149389f6700c03de6022` |
| [Dorian #44](https://github.com/ajaysurya1221/dorian/pull/44) | `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | Merged at 02:21:08 UTC | `5962bbeb99ef1c22a44d5dbea8cd77c689ff9b65` |
| [ARCI #14](https://github.com/ajaysurya1221/agent-reliability-ci/pull/14) | `ba179f3a188710e38ec4557d2f65b66a8953c099` | Merged at 02:21:19 UTC | `06e87442772ac59b68ce5009e9ac37fa1d111c64` |
| [Frontier Scout #81](https://github.com/ajaysurya1221/frontier-scout/pull/81) | `b0d2ae108e62ef7c8a890e8294104a577217b4f8` | Open; required native approval absent | None |

Every merged tree equals its accepted source tree and differs from its previous main only in README.md. Every source branch remains at its accepted commit. No source, dependency, lockfile, schema, frozen entry, package version or release changed. These separate repositories acquired no shared runtime layer. Evalopt main and preserved research remain untouched by this follow-up.

## Reviews and pre-merge checks

Original independent Codex and fresh Fable ACCEPT records for each unchanged source head are `reviews/07A-codex.md` / `07A-fable.md`, `07B-codex.md` / `07B-fable.md`, `07C-codex-final.md` / `07C-fable.md`, and `07D-codex-final.md` / `07D-fable.md`. Earlier nonfinal reviews remain preserved. The renewed independent Codex reviews are [07AB](reviews/portfolio-merge-07AB-codex.md) and [07CD](reviews/portfolio-merge-07CD-codex.md). These are offline reviews, not GitHub approving reviews.

Fresh native readbacks verified the exact candidate, current base, README-only file roster, public README bytes, full current workflow/job/step roster, mergeability, native requirements and retained source refs. No source changed after those reviews. Full source tests were not repeated unnecessarily on unchanged commits; current hosted CI was independently examined:

| Repository | Accepted original-head workflow runs | Job / step evidence |
|---|---|---|
| Actseal | 38312773157, 38312827368, 38312827325, 38312827338, 38312827339; attempt 1 each | 15 jobs, 159 successful steps; four required contexts passing |
| Dorian | 38315042449, 38315042552; attempt 1 each | 4 jobs, 41 successful steps |
| ARCI | 38316271264 attempt 1 | 4 successful jobs, 49 successful steps and 4 expected conditional skips |
| Frontier Scout | 38315457758, 38315457787, 38315454988; attempt 1 each | 5 jobs, 49 successful steps; CodeQL scope is Actions |

Dorian and ARCI have no required-status-check rule. Their full current CI was still checked; “no required checks reported” was not presented as a test pass. ARCI's four skipped conditional steps are two failure-only uploads and two Node setup/install steps restricted to Python 3.14. They do not represent skipped required jobs. ARCI's 48 frozen entries were independently rehashed and compared with the accepted/base blobs.

## Native operation and preservation

Dorian and ARCI already had `delete_branch_on_merge=false`; it stayed unchanged. Actseal had it set to true. The accepted [Codex](reviews/portfolio-merge-operations-codex.md) and [fresh Fable](reviews/portfolio-merge-operations-fable.md) operating reviews authorized a bounded general-preference change solely to retain its source branch. Root set only this field to false, read it back, performed one normal exact-head squash merge, restored true in a finally block, and read it back again. Complete ruleset and environment records matched before, while disabled, and after restoration. Legacy-protection absence and the actual active main ruleset remained distinct observations. No protection, bypass actor or deployment approval changed. See [decision record](../../docs/decisions/portfolio-readme-merge-2026-10-13.md).

All merges used `gh pr merge --squash --match-head-commit` with the accepted commit. No `--admin`, `--auto` or `--delete-branch` was used. Native commit/parent/tree/compare/ref records establish the actual merged bytes and branch retention; a successful CLI exit alone was not the acceptance evidence.

## Resulting-main verification

Independent actual-operation and resulting-main reviews: [Actseal/Dorian](reviews/portfolio-merge-07AB-main-codex.md) and [ARCI with Frontier blocker refresh](reviews/portfolio-merge-07D-main-codex.md). All observed current attempts below are attempt 1; no automatic rerun or waiver occurred.

| Exact resulting main | Current workflow runs | Result |
|---|---|---|
| Actseal `ad62ec8ff33f858e1759149389f6700c03de6022` | CI 38336991567, CodeQL 38336991552, Gitleaks 38336991586 | All 8 jobs and 85 steps success |
| Dorian `5962bbeb99ef1c22a44d5dbea8cd77c689ff9b65` | CI 38336473165, security 38336473354 | All 4 jobs and 41 steps success |
| ARCI `06e87442772ac59b68ce5009e9ac37fa1d111c64` | CI 38336487604 | All 4 jobs success; 49 successful steps and the same 4 expected conditional skips |

The final before/after inventories, current-attempt jobs and required controls are retained separately from the pre-merge observations. Final ARCI/Frontier review observed the unchanged endpoint at 02:38:50 UTC. All four retained task worktrees are clean at their accepted heads; root retained that local check separately. These are hosted execution observations, not fabricated local reruns. All required local/source reviews preceded each merge; main CI is the independent post-merge confirmation.

## Remaining native blocker

Frontier Scout requires one approving GitHub review, enforces that requirement for administrators, and reports `REVIEW_REQUIRED` / `BLOCKED`. Its native review list is empty. The authenticated account is also the PR author and cannot provide the required approval. Successful CI and local two-model reviews do not replace a native approval. Root left its PR, branch, protection and cleanup preference untouched. No alternate account, synthetic approval or protection relaxation was attempted. The user must have an eligible reviewer approve this PR; later merge must preserve its branch because automatic branch cleanup is still enabled.

## Additional model usage

One new headless operating-review call used canonical `claude-fable-5-1` through firstParty, requested xhigh, seven reported turns, exit 0, valid JSON and retained review. Effective effort is not exposed by the native output. Elapsed supervisor time: 243.777 seconds. Native usage: 194 input, 16,556 output, 168,774 cache-read and 54,198 cache-creation tokens; separately exposed thinking tokens: 6,700, not added again. CLI list-price estimate: USD 1.9558935; this is not a subscription charge. Astra usage attributable to this follow-up is unavailable. Original wind-down totals remain unchanged.

Private native stdout/stderr, command timestamps, hashes and operation receipts are retained under ignored `plan/artifacts/portfolio-merge-20261013-*` and `plan/logs/portfolio-merge-operations-review/`. Only sanitized records are committed. No raw credentials or model transcripts are published. No further release, repository archival, feature work or external outreach is part of this follow-up.
