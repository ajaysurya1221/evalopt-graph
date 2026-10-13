REVIEW portfolio-merge-closeout — Reviewer Codex | Verdict ACCEPT

## Accepted scope and exact document identity

Acceptance covers the sanitized portfolio-merge follow-up and its correspondence to the retained native evidence and independent source/main-CI reviews. The documents stay on the existing control branch; this review neither requests nor approves another main integration. It does not execute a merge, grant a native GitHub approval, authorize a new setting change, reopen source review, or certify a future endpoint.

Reviewed against control HEAD `2638f3e804b763a5e3563d880f15f801eb1e9083`, with the following exact working-file identities. The two existing files are updated; the other three are new. HEAD alone does not identify these uncommitted document bytes.

| Document | Bytes | SHA-256 |
|---|---:|---|
| `plan/exec/PORTFOLIO_MERGE_FOLLOWUP.md` | 7843 | `5057dd0873c924b31c2a1046ff5ecd24d2867786c1c212fd225d990ed213e3fa` |
| `plan/exec/reports/portfolio-merge.md` | 3407 | `1cd6db4fd455ef83d659837ee89bc4beefa067073526141503e34f942972d9cc` |
| `plan/exec/HUMAN_INBOX.md` | 2610 | `d1b2e46c621189fc79e60b9745d0e912c95dab6353cc0f7e4e99efe2dd5d6d68` |
| `plan/exec/STATUS.md` | 3528 | `7a00848a1993fef69dde9c7679b5329a4c25da4a7e01a17e0ed3ee87a505c66b` |
| `docs/decisions/portfolio-readme-merge-2026-10-13.md` | 2416 | `5a27e3a11b136998f32b8017fb3b7d933930223c81ac88d78a9a233477cc2a6d` |

## Findings

No blocking or required correction remains in the reviewed packet. The canonical report correctly remains **PARTIAL: three of four requested merges completed**, because Frontier Scout is still blocked by its native approval requirement. Successful verification of the three completed merges is not mislabeled as completion of all four requested merges.

The newer user instruction is explicitly separated from the completed STOP wind-down. It supersedes the earlier no-sibling-merge restriction only for the four unchanged README PRs; no new runtime feature, dependency, release or archival authority is inferred. The dated STATUS addendum preserves the original end-of-wind-down entries rather than rewriting their history. HUMAN_INBOX now distinguishes the completed evalopt release/closeout from the remaining portfolio action. The earlier original-source review paths explicitly identify the final Codex records for 07C/07D, preserving earlier nonfinal reviews.

## Actual evidence correspondence

I read the native merge receipts and the underlying command, commit, compare, repository-setting and retained-ref responses, rather than relying only on the narrative summaries. Recomputed stdout/stderr hashes agree with each merge's command manifest. The manifest schemas differ (`name`/`exit` for Actseal and `label`/`exit_code` for Dorian/ARCI); the corrected shape-specific reader verified them. One preliminary generic reader raised a KeyError and supplied no accepted evidence or mutation.

| Repository / PR | Actual merged UTC | Actual merged commit | Reviewed/result tree |
|---|---|---|---|
| Actseal / 70 | 2026-10-13 02:27:46 | `ad62ec8ff33f858e1759149389f6700c03de6022` | `95b5819235ad1f447301261d349fb5380a25930b` |
| Dorian / 44 | 2026-10-13 02:21:08 | `5962bbeb99ef1c22a44d5dbea8cd77c689ff9b65` | `98cbda60fa5031f0c5eedbcaf6edb312a082aeb7` |
| ARCI / 14 | 2026-10-13 02:21:19 | `06e87442772ac59b68ce5009e9ac37fa1d111c64` | `67a690c31341c0590790bed1aa768f884d96e40e` |

Each actual merged tree equals the accepted candidate tree. Each base-to-main native compare contains only `README.md`, and each merge's sole parent is the recorded prior main. Each retained source ref equals the accepted head. The recorded merge commands are ordinary `gh pr merge --squash --match-head-commit` calls; none contains `--admin`, `--auto` or `--delete-branch`.

Actseal's actual mutation sequence consists of the single cleanup-field PATCH to false, the ordinary exact-head merge, and the single cleanup-field PATCH restoring true, all exit 0. Separate repository readbacks show **true → false → true**. The complete captured ruleset roster, full ruleset 24679548, effective main rules, environment roster and PyPI environment bytes match before/while disabled/after restoration. The retained head ref still matches after restoration. Its two classic-protection reads returned the disclosed HTTP404/exit1 and remain distinct from the active ruleset; no claim that every native command succeeded is made. Dorian and ARCI's cleanup readbacks are false before and after, and their retained main-rule responses are equal. The broader final control comparisons are independently recorded in the accepted endpoint reviews.

I read [07AB source/current-CI](portfolio-merge-07AB-codex.md), [07CD source/current-CI](portfolio-merge-07CD-codex.md), [07AB actual-operation/main-CI](portfolio-merge-07AB-main-codex.md), and [07D main-CI/Frontier refresh](portfolio-merge-07D-main-codex.md). The follow-up's run IDs, source SHAs, counts and limits correspond to those records:

- Actseal actual main: runs `38336991567`, `38336991552`, `38336991586`, all attempt 1, **8 successful jobs / 85 successful reported steps**. Dependency review is an accepted PR-only gate, not an invented main-push run.
- Dorian actual main: runs `38336473165`, `38336473354`, attempt 1, **4 successful jobs / 41 successful reported steps**. Absence of configured required-status contexts is distinguished from independently checked actual CI.
- ARCI actual main: run `38336487604`, attempt 1, **4 successful jobs, 49 successful steps and four expected conditional skips**. The final review at **02:38:50.206298 UTC** separately binds all 48 frozen blobs through remote/local tree identity and actual hashing. It does not claim the new main was fetched or tested in a fresh installed checkout.

Pre-merge counts also match the accepted records: Actseal 15 jobs/159 successful steps; Dorian 4/41; Frontier Scout 5/49 with CodeQL scoped to Actions; ARCI four jobs with 49 successful steps and four conditional skips. Hosted job/step evidence is not a fresh local full-suite rerun or an independent recount of test-case skips. This correspondence review does not duplicate the source or main-CI reviewers' work.

Root's retained `worktrees-final.json`, observed at **02:37:33.968168 UTC**, identifies all four task worktrees as clean at the accepted source heads. The public packet accurately labels that as a separate retained local check. This review does not promote a source-worktree observation into proof of a later remote state.

## Frontier Scout remains bounded

The final independent refresh shows PR81 still open at `b0d2ae108e62ef7c8a890e8294104a577217b4f8`, `BLOCKED` / `REVIEW_REQUIRED`, no native approving review, administrator enforcement intact, and cleanup still true. Offline two-model ACCEPT and successful CI do not satisfy a required native GitHub approval; the authenticated PR author cannot self-approve.

The follow-up and HUMAN_INBOX expressly preserve **two separate conditions**: obtain an eligible native approval, and preserve the source branch during any later otherwise-authorized merge despite automatic cleanup currently being enabled. Neither document says approval alone permits branch deletion. This Actseal operational ADR grants no Frontier setting toggle, alternate-account workaround, synthetic approval, protection relaxation or administrative merge. The completed three merges do not erase the fourth repository's blocker. Evalopt archival remains human-owned.

## Usage, preservation and privacy

The one new operating-review call's actual native result and supervisor receipts match the disclosed figures: canonical Fable 5.1, firstParty, requested xhigh with effective effort unexposed, native success/exit0, seven native turns, **243.777 supervisor seconds**, 194 input, 16,556 output, 168,774 cache-read, 54,198 cache-creation and separately reported 6,700 thinking tokens. The native **USD 1.9558935** amount is explicitly a list-price estimate, not a subscription charge. No additional Fable closeout call is claimed. Attributable Astra usage remains unavailable; the original wind-down totals are not retroactively altered.

The approved PLAN, original FINAL_REPORT, release-receipt.json, TERMINAL_RECEIPT.md and the original usage-method report are byte-identical to the control HEAD. Tracked diffs contain only HUMAN_INBOX and the dated STATUS addendum; the intended new files are follow-up documents, the ADR, sanitized reviews and the review task. No package source, release artifact or historical research file is part of this reporting change. No tracked file exists under `plan/logs/` or `plan/artifacts/`.

A bounded credential/private-key/header-pattern scan of the ten new Markdown records returned no matches; the five reviewed public documents also contain no local user path or credential-pattern match. Manual inspection found summaries and private-evidence pointers, not native stdout/stderr dumps, model transcripts, private history, campaign data, `.env` values or credentials. This is finite inspection of the listed reporting scope, not a universal no-secrets assertion. Raw merge and model evidence remains privately retained.

`git diff --check` passes for tracked edits. The three new documents and both updated documents were also checked directly for trailing whitespace and final LF; all pass. No new product tests are needed or claimed for these retrospective records.

## Required changes and limits

None. Commit/push only the intended control-branch reporting records within the existing authorization; this ACCEPT creates no requirement for another main PR or Fable call. Any later change to the five bound document bytes needs a scoped recheck. The later Frontier approval/branch-preservation/merge endpoint is outside this acceptance.

Only this assigned review file was written. I performed no network request, model call, credential read, repository/ref/settings mutation, source edit or redundant main-CI review. The accepted actual-operation/main-CI reports remain the primary independent endpoint evidence; this review accepts their accurate and sanitized presentation.
