REVIEW CONTROL-02 — Reviewer Fable high | Verdict ACCEPT | Findings by severity | Required changes | Follow-ups

## Target and bounds

- Exact target: `4fcce2394270cfe8c4e082de418dc9b322e9c97f` (`chore: clarify requested turn caps and preserve review evidence`), reviewed as `git diff 2b4f00e..HEAD` in dedicated worktree `wt-control-review-01`, working tree clean before and after. Central `wt-control-00` HEAD was the same commit when this record was written.
- Diff: 7 files, 129 insertions, 4 deletions. `DECISIONS.md` +6/−0 (append-only), `STATUS.md` 4 roster lines reworded, five new files (`reports/research-preservation-01.md`, `reviews/control-packet-codex-01.md`, `reviews/control-packet-fable-01.md`, `tasks/05-implementation.md`, `tasks/control-packet-review-01.md`). No pre-existing report, review, ADR, proposal, task spec or PLAN line was modified or deleted.
- Scope: the amendment only, per brief. The accepted base `2b4f00e` (reviewed in `control-packet-fable-01.md`), Task02 controls, Task03 ADRs, Task06 audit and product/standards mappings were not re-reviewed.
- Read-only: no file in the reviewed worktree was modified, staged or committed. Only this record was written in `wt-control-00`, left unstaged. No model, subagent or network call. No `.env`, credential or authentication store was read. Central ignored supervisor receipts were consulted by known filename for counter/elapsed corroboration only; no raw content is reproduced here. Later untracked central records (`control-packet-codex-final.md`, Task07/review-02 briefs) are outside this verdict and were not read.

## Commands and results

| Check | Command | Result |
|---|---|---|
| Target | `git rev-parse HEAD`; `git status --porcelain` | `4fcce239…9c7c`; clean |
| Whitespace | `git diff --check 2b4f00e..HEAD` | no output, exit 0 |
| Shape | `git diff --stat`, `--numstat -- plan/exec/DECISIONS.md`, `--name-only` | as listed above; DECISIONS 6 added, 0 removed |
| PLAN immutability | `git log -- plan/exec/PLAN.md`; `shasum -a 256` | single commit `08c87b8`; `697f3fd7…2b3c` matches run identity |
| Offline controls | `python3 -B -m unittest discover -s plan/exec/tests` | `Ran 11 tests … OK`, exit 0 |
| Preservation | `python3 -B plan/exec/preservation.py` | `{"baseline": "fc3045db…", "protected_files": 75, "errors": []}`, exit 0 |
| Quoted sources | `sed -n 9p reports/02.md`; `sed -n 40p reviews/02-final-review.md` | line 9 contains "task wallclock/turn caps"; line 40 contains "within the 1200 s cap and 20-turn limit"; both unchanged in this diff |
| Task01 counter | `git grep num_turns -- plan/exec` | `reviews/00-01-review-r2.md:46` records `--max-turns 1` → `error_max_turns`, `num_turns 2` (committed evidence) |
| Native counters | config/finish receipts in central ignored logs, filenames only | 02-final-review requested 20 / native 24; 03-proposals 30 / 33; 03-implementation 30 / 40; control-packet-review-01 elapsed 314.828 s. All four DECISIONS figures corroborated |
| STATUS pointers | `test -e` on each named record | `reports/02.md`, `02-baseline.md`, `reviews/03-codex-final.md`, `03-fable-final.md`, `reports/06-r1.md` all exist |
| Task04 status | `git worktree list` | `wt-semantics-04` exists on `winddown/20261013/04` at `2b4f00e`; consistent with IN_PROGRESS |
| Snapshot heads | `git cat-file -t`; `git merge-base --is-ancestor <sha> main` | all four PR heads are local commits on `feat/skill-workflows-v1-public`, `feat/skill-workflows-v2`, `feat/evidence-phase-difficulty`, `feat/response-contract-difficulty-v4`; none is an ancestor of `main` (`fc3045d`) |
| Task05 brief vs PLAN | `cat tasks/05.md`; `grep PLAN.md` | owned files, 35-turn/50-minute cap, dependency on 03 and 04, REPORT path all match PLAN Task05 |
| Task05 brief facts | `git log -1 624ed11`; `grep version pyproject.toml`; `test -x …/tooling/bin/uv`; `test -e tests/test_figures.py` | `624ed11 Reject scalar acceptance input rows (#4)` by an external contributor; version `0.1.0`; pinned uv present; figure test present |
| Task05 inputs | `test -e docs/migration.md docs/portfolio.md` | both absent at HEAD: `migration.md` is Task04 output (not yet integrated); `portfolio.md` is Task05's own deliverable |
| "16-entry map" | `git grep -i sixteen` | `docs/decisions/migration-interface.md:11,13` fixes exactly sixteen rows; wording consistent |

## Findings by severity

P1: none.

P2: none.

P3 (record-keeping only, none blocks acceptance):

1. **Codex's request is satisfied without overreach.** The 20:43 UTC DECISIONS entry states what the supervisor enforces (wall-clock, owned process, post-run path scope) and what it merely passes through (`--max-turns`); keeps requested cap and native `num_turns` as separately retained observations; says equivalence is unestablished and no violation is proven; says self-reported assistant/tool counts do not establish enforcement; carries the distinction into final accounting; and names the two superseded sentences by file and line without editing them. Every number in the entry is corroborated by committed evidence (Task01) or native receipts (the other three pairs and 314.828 s). No controller change is proposed.
2. **The enumeration is illustrative, not exhaustive.** Native receipts also show 06-audit at native 30 against requested 25 and 06-review-r1 at 25 against 20 (the former already visible in committed `reviews/06-fable-r1.md:28`). The entry's general rule covers them and it does not claim completeness, but final usage accounting should list every requested/native pair rather than these three.
3. **Task05 brief presupposes an integrated Task04.** It instructs the worker to read `docs/migration.md` and its appendix, which do not exist at HEAD; PLAN Task05 depends on 03 and 04, and STATUS keeps 05 PENDING, so this is consistent only if the brief is dispatched after Task04 integration. The brief does not say so explicitly.
4. **Research snapshot GitHub state is not verifiable in-session.** OPEN/draft states for PRs 33–36 require network access, which this review did not use. The local facts that matter for preservation are verified: all four heads exist locally on their named branches and none is in the wind-down base. The snapshot correctly disclaims reproduction or acceptance of results.
5. **Prior follow-ups.** CONTROL-01 P3-1 and P3-5 (STATUS superseding pointers, root-receipt labels) are applied. P3-3 (cite `reviews/03-fable-final.md:74` beside the twelve-minute reference) was optional and is not applied. The CONTROL-01 record's own "Eleven tool turns" self-count sits beside native 14, which is exactly the discrepancy the new entry declines to treat as enforcement evidence.

## Required changes

None. The amendment at `4fcce239` is accepted as an operational record. It satisfies the Codex REVISE finding, leaves all historical evidence byte-unchanged, and claims no cap equivalence or violation.

## Follow-ups

- Final usage accounting: tabulate every task's requested cap, native `num_turns` and native elapsed time from receipts (including 06-audit and 06-review-r1), per the new DECISIONS rule (P3-2).
- Root: dispatch `tasks/05-implementation.md` only after Task04 is integrated and both its reviews ACCEPT, or add that gate sentence to the brief (P3-3).
- Final closeout: recheck PRs 33–36 refs and states with an actual read-only GitHub query at that time; retain, never merge or close (P3-4).
- Optional: apply CONTROL-01 P3-3 citation at a later integration commit.

## Spend

Requested model `claude-fable-5-1`, requested effort high; effective effort is not observable in-session. Zero model, subagent or network calls; zero file changes in the reviewed worktree. Elapsed wall clock and token usage are unavailable in-session and are not estimated; the native supervisor measures them after exit.
