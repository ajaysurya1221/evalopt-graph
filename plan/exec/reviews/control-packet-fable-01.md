REVIEW CONTROL-01 — Reviewer Fable high | Verdict ACCEPT | Findings by severity | Required changes | Follow-ups

## Target and bounds

- Exact target: `2b4f00eb9c3c004af7da8b728aaedc404bfc1779` (`chore: record accepted STOP contracts and isolated portfolio preparation`), read in dedicated worktree `wt-control-review-01`, working tree clean. Central `wt-control-00` HEAD was the same commit when this record was written.
- Scope reviewed: `fc3045dbda29c1d274747329ceb6724a783b0df7..HEAD` = 87 files, 3515 insertions, 0 deletions: `.gitignore` (+5 lines), `docs/decisions/*.md` (4 files), everything under `plan/exec/`.
- This is an operational-record review. It is not a release, benchmark, ADR-semantics or control-design approval. Task02 controls, Task03 ADRs and Task06 audit were byte-checked against their accepted lane heads, not re-reviewed.
- Read-only: no file in this worktree was modified, staged or committed. Only this record was written in `wt-control-00`, left unstaged. No model, subagent or network call. No `.env`, credential or authentication store was read. No central ignored log was read.

## Commands and results

| Check | Command | Result |
|---|---|---|
| Target | `git rev-parse HEAD`; `git status --porcelain` | `2b4f00eb…1779`; clean |
| Whitespace | `git diff --check fc3045d..HEAD` | no output, exit 0 |
| Offline controls | `python3 -B -m unittest discover -s plan/exec/tests` | `Ran 11 tests … OK`, exit 0 |
| Preservation | `python3 -B plan/exec/preservation.py` | `{"baseline": "fc3045db…", "protected_files": 75, "errors": []}`, exit 0 |
| PLAN hash | `shasum -a 256 plan/exec/PLAN.md` | `697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c`, matches DECISIONS run identity |
| PLAN immutability | `git log -- plan/exec/PLAN.md` | single commit `08c87b8` |
| Task trim commit | `git diff --numstat a545477~1 a545477 -- plan/exec/tasks` | 15 task files whitespace-only deletions; only `00-review.md` and `01-probe.md` are new one-line files; `--ignore-all-space` shows 2 changed lines total |
| Task02 bytes | `git diff --stat 5d6df50 HEAD -- supervise.py preservation.py verify.sh tests/ CONTRACT.md tasks/02.md` | empty: identical. Only root-added `baseline.json`, `reports/02.md`, `reports/02-baseline.md` differ (additions) |
| Task03 bytes | `git diff --stat 9d30613 HEAD -- docs/decisions plan/exec/decisions` | empty: four ADRs and six blind proposals identical |
| Task06 bytes | `git diff --stat f030ccd HEAD -- plan/exec/audits` | empty: audit identical |
| Reference commits | `git merge-base --is-ancestor` | `5d6df50`, `9d30613`, `f030ccd` are lane commits, not ancestors of HEAD; integration was by content, verified above |
| Ignores | `git check-ignore -v plan/logs/x plan/scratch/x plan/artifacts/x`; `git ls-files -o --exclude-standard plan docs` | all three matched by new `.gitignore` lines 38-40; no untracked non-ignored packet files |
| Packaging | `pyproject.toml` `[tool.hatch.build.targets.sdist] include`; `scripts/verify_artifacts.py` `ALLOWED_SDIST_ROOTS` | `plan` absent from both; `docs` is shipped, and `docs/decisions` contains no local path, email or key |
| Privacy grep | `git grep` for `/Users/`, emails, `sk-`, `ghp_`, API-key env names, `Bearer`, `password` over `plan docs/decisions` | local paths in 23 `plan/exec` files (authorized, see P3-4); only email is `fixture@example.invalid` in a test; `supervise.py:122` names env keys only to reject them; no secret values |
| Reproduced values | `plan/exec/reports/08-scan-preflight.md` §"Independent source proof" | three 64-hex SHA-256 digests only; synthetic token deliberately not expanded |
| Overclaim grep | `published|archived|charged|billed|effort observed|approved for release` over reports, STATUS, DECISIONS, CONTRACT | no matches; `08-release-preflight.md` explicitly disclaims acceptance, deployment eligibility and publication |
| Verdict roster | first lines of all 18 review files | REVISE records retained for 00 (Codex, Fable), 02 (Codex r1, Fable r1), 03 (Codex, Fable), 06 (Codex, Fable); each followed by a retained ACCEPT record |

## Findings by severity

P1: none.

P2: none.

P3 (record-keeping only, no change required for acceptance):

1. **STATUS.md is a bare roster.** Supersession of the REVISE/original records is stated in `DECISIONS.md` (Task06 entry, 20:27 and 20:34 UTC entries) and in `reviews/06-fable-final.md`, not in STATUS. The prior records are preserved and visibly superseded, which satisfies the requirement; STATUS could name the superseding record per task for faster audit.
2. **Model-authored timing remains in retained reports.** `reports/02-baseline.md:36` ("approximately 29 seconds"), `reviews/02-final-review.md:40` ("approximately 8 minutes"), `reports/06.md:11` (wall clock and "15 tool turns"), and the "Observed UTC clock" lines in `reports/03.md:19` and `reports/03-r1.md:56` are worker observations. `DECISIONS.md` 20:34 UTC entry states these are not measurements and are superseded by native receipts; `reviews/06-fable-final.md:28` supersedes `reports/06.md` specifically. `reports/01.md:9` labels its 13 seconds as native. Acceptable as retained history; final usage accounting must cite native receipts only.
3. **The superseded Task03 estimate is located.** The 20:34 UTC DECISIONS entry refers to a "final review estimate of twelve minutes"; it sits in the Spend sentence of `reviews/03-fable-final.md:74`, a long line that an initial context-bounded grep in this review missed and a plain grep then found. The estimate is model-authored, retained, and superseded by the native 272.611-second receipt recorded in DECISIONS. Cosmetic: DECISIONS opens with two consecutive `Decision | Rule` tables.
4. **Absolute local paths in the operational packet.** `DECISIONS.md:46`, `PLAN.md:5` (memo path), `audits/portfolio-independence.md:187`, `reports/06.md:5`, `reports/07-portfolio-preflight.md:20`, two reviews and sixteen task specs contain `/Users/ajay/...`. The brief authorizes retained local paths and the packet is excluded from distributions (packaging check above). Nothing under the shipped `docs/decisions` carries one.
5. **Root-added Task02 receipts sit outside the two accepted Task02 review diffs.** `baseline.json`, `reports/02.md` and `reports/02-baseline.md` were committed after lane head `5d6df50`. `reviews/02-final-review.md:15` and `:23` acknowledge the baseline evidence and the external PATH prepend, and `verify.sh:9` already contains the PATH fix at the accepted bytes, so the retained deviation in `02-baseline.md` is consistent with the committed runbook. Root receipts, not reviewed worker output; STATUS could label them as such.

## Required changes

None. The packet at `2b4f00eb` is accepted as an operational record.

## Follow-ups

- Root: add per-task superseding-record pointers to STATUS.md at the next integration commit (P3-1, P3-5).
- Root: optionally cite `reviews/03-fable-final.md:74` beside the twelve-minute reference in DECISIONS so the superseded estimate is traceable without a search (P3-3).
- Final usage accounting: use native supervisor receipts only; do not sum the approximate figures listed in P3-2.
- Before any distribution build, rerun `scripts/verify_artifacts.py` so the `plan` exclusion is proven on the actual sdist rather than inferred from configuration.

## Spend

Requested model `claude-fable-5-1`, requested effort high; effective effort is not observable in-session. Eleven tool turns, zero model, subagent or network calls, zero file changes in the reviewed worktree. Elapsed wall clock and token usage are unavailable in-session; the native supervisor measures them after exit.
