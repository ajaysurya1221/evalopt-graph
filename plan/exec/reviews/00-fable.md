REVIEW 00 — Reviewer Fable high | Verdict REVISE | Findings by severity | Required changes | Follow-ups.

Scope: commit `08c87b89f8a0d0ef09b6b8716ec13a014a4fd3b5` (branch `winddown/20261013/00`) against baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`. Read-only inspection; no repository files edited other than this record. Model: claude-fable-5-1 (requested selector `claude-fable-5-1[1m]`, effort high as requested; effective effort not observable from inside the session).

## Verdict

REVISE. Every substantive acceptance criterion for Task 00 is met and verified independently (plan hash, verbatim task roster, decisions, contract, narrow ignores, no product edits, control branch only). One named "Done when" gate fails when applied to the committed diff: `git diff --check` reports a whitespace error in all 15 task files, and REPORT 00 states the check passed. The contract does not let a reviewer waive a failed gate, so this is a one-commit fix plus a REPORT correction, not a content problem. Revision round 1 of 3.

## Findings by severity

**Medium — `git diff --check` gate fails on the committed diff; REPORT claims it passed.**
`git diff --check fc3045dbda29c1d274747329ceb6724a783b0df7 08c87b8` exits 2 with `new blank line at EOF` for `plan/exec/tasks/{00,01,02,03,04,05,06,07A,07B,07C,07D,08,09,10,11}.md:15`. Each task file ends in `.\n\n` while the corresponding PLAN.md block ends in `.\n` (verified with `od -c`). A bare `git diff --check` on a clean tree after committing is vacuous, which is the likely source of the REPORT's "passed" statement. REPORT 00 therefore reports a passing result for a check that fails on the actual change.

**Low — STATUS.md records `commit INITIAL` instead of the SHA.**
`plan/exec/STATUS.md` line for task 00 says `commit INITIAL`. Later tasks must reconcile against exact commits; recording the SHA now avoids ambiguity once a revision commit lands.

**Informational — untracked files in the control worktree.**
`plan/exec/tasks/00-review.md` and `plan/exec/tasks/01-probe.md` are untracked prompt files written by root's launcher. They are not in commit 08c87b8 and are outside this review's scope. Empty untracked directories `plan/exec/{decisions,tests}` and ignored `plan/{logs,scratch,artifacts}` also exist. No action needed; noting so nobody mistakes them for omitted deliverables.

## Exact checks performed

| Check | Command | Result |
|---|---|---|
| Diff scope | `git diff --name-status fc3045d…0df7 08c87b8` | 21 files: `.gitignore` (M) and 20 files under `plan/exec/` (A). No `src/`, `tests/`, `docs/`, `scripts/`, `pyproject.toml`, `uv.lock`, or workflow changes. |
| PLAN.md hash (commit) | `git show 08c87b8:plan/exec/PLAN.md \| shasum -a 256` | `697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c` — matches the stated hash. |
| PLAN.md hash (worktree) | `shasum -a 256 plan/exec/PLAN.md` | Same hash; worktree copy equals committed copy. |
| PLAN.md encoding | Python byte inspection | 39090 bytes, LF only, no BOM, ends with single newline, final line `**Next action: accept this plan.**` retained. |
| Task roster | Regex over `**TASK <id>:` headers in PLAN.md | 15 ids: 00, 01, 02, 03, 04, 05, 06, 07A, 07B, 07C, 07D, 08, 09, 10, 11. One file per id exists under `plan/exec/tasks/`. |
| Task block fidelity | Python: extract each block from PLAN.md (header through line before next `**TASK`/`### `), compare to `git show 08c87b8:plan/exec/tasks/<id>.md` | All 15 equal byte-for-byte after stripping trailing newlines. Each file carries exactly one extra trailing `\n` versus its block. No wording, punctuation or path differences. |
| DECISIONS.md vs PLAN section I | Regex-extract both `| Decision | Rule |` tables from each; compare stripped | Both tables identical. Run-identity block adds baseline SHA, budget timestamps, plan and memo hashes; baseline SHA matches `fc3045d…0df7`, plan hash matches, memo hash matches section A. |
| Time limits consistency | Arithmetic from DECISIONS `budget begins 2026-10-12T19:22:18Z` | T+8h15 = 03:37:18Z (release cutoff), T+9h15 = 04:37:18Z (admission stop), T+10h = 05:22:18Z (hard end). All three match CONTRACT.md and PLAN section G. |
| CONTRACT.md content | Read in full | Covers ownership (task worktree, no edits to PLAN/other specs), reporting (REPORT format, PARTIAL triggers, no invented success), reviews (independent Codex + fresh Fable, 3 rounds, failed gate not waivable), scope (Fable 5.1 only, no fallback/credentials/global config/new capability, kernel bytes and ten exports frozen except version literal, ARCI no mutating git/network, preservation), time limits (three timestamps above). REPORT/REVIEW/ADR formats match PLAN section D field-for-field. |
| Ignore narrowness | `git diff … -- .gitignore`; `git check-ignore -v` | Adds exactly three anchored entries: `/plan/logs/`, `/plan/scratch/`, `/plan/artifacts/`. `plan/exec/` is not ignored (reports/reviews commit normally). No existing tracked path affected. |
| Distribution leakage | `pyproject.toml` `[tool.hatch.build.targets.sdist]` | sdist uses an explicit `include` allowlist that does not contain `/plan`; wheel packages only `src/evalopt_graph`. Committed `plan/exec/` cannot enter wheel or sdist. |
| Branch isolation | `git rev-parse main origin/main`; `git branch -a --contains 08c87b8` | `main` and `origin/main` both at `fc3045d…0df7`; 08c87b8 is on `winddown/20261013/00` (and the derived 01/02 lane branches) only. Only tag present is `v0.1.0`. |
| Whitespace gate | `git diff --check fc3045d…0df7 08c87b8; echo $?` | **exit 2**, 15 findings (see Medium). |
| Commit metadata | `git show -s --format=%H%n%P%n%an%n%ad 08c87b8` | Parent is the baseline; author ajaysurya1221; 2026-10-13 00:56:08 +0530 = 19:26:08Z, ~4 min after budget start, consistent with REPORT. |

## Required changes

1. Remove the single trailing blank line from each of the 15 `plan/exec/tasks/*.md` files so each ends `.\n`, in a follow-up commit on `winddown/20261013/00`. Do not modify PLAN.md. Re-run `git diff --check fc3045dbda29c1d274747329ceb6724a783b0df7 HEAD` and require exit 0.
2. Correct REPORT 00's Tests line to report the actual whitespace-check result and the exact command used (range form, not bare), and reference the fix commit.
3. Replace `commit INITIAL` in STATUS.md with the exact SHA(s) covered by this review.

## Follow-ups (not blocking, for later tasks)

- Task 02 scope checks should run `git diff --check <baseline> <head>` in range form so this vacuous-invocation pattern cannot recur.
- Task 09 should still confirm the built sdist excludes `plan/` empirically, even though the hatch allowlist already implies it.
- I could not compare PLAN.md to the original accepted message directly; the SHA-256 supplied by root is the only cross-check available, and it matches. If another reviewer holds the source message, a byte comparison there would close that gap.
