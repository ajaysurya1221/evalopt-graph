REVIEW 02 — Reviewer Fable high | Verdict REVISE | Findings by severity | Required changes | Follow-ups

Reviewed diff: a545477..93028ef (chore: add run-local supervision and preservation controls), branch winddown/20261013/02, worktree wt-control-02. Four new files under plan/exec: supervise.py, preservation.py, verify.sh, tests/test_supervise.py. No package code touched. `git diff --check a545477 93028ef` clean. Requested model/effort for this session: claude-fable-5-1[1m], high; terminal JSON does not expose effective effort. No model dispatch was performed by this review.

Context observed during review: the lane branch advanced while this review ran. HEAD moved from 93028ef to 9674f80, 4861ba4, then e6b8fe1 (all 2026-10-12T19:32Z–19:35Z). A Codex round-1 review (02-codex-round1.md) already records REVISE at 93028ef with three findings. This review was formed independently from the diff and offline probes before reading that record; it reaches the same verdict on 93028ef. Evidence on the follow-up commits is given under Follow-ups, but no ACCEPT is granted here for a commit that was not the assigned target.

## Evidence (commands and results)

- `python3 -B -m unittest discover -s plan/exec/tests -p 'test_*.py' -v` at 93028ef: Ran 5 tests, OK.
- Same command at HEAD e6b8fe1: Ran 10 tests, OK (adds test_preservation.py and five supervise cases).
- `python3 -B plan/exec/preservation.py` (both revisions): `{"baseline": "fc3045d…", "protected_files": 75, "errors": []}`, exit 0, against current version 0.1.0. PLAN.md SHA-256 matches 697f3fd7…b3c.
- `bash -n plan/exec/verify.sh`: syntax OK. All seven scripts it invokes exist in the repo. The full runbook was NOT executed here: it requires an isolated uv 0.11.29 binary and RUN_ARTIFACTS, and the baseline full package suite runs separately per assignment. Claims of a passing runbook are therefore unverified by this review.
- Offline classifier probe against the committed 93028ef `supervise.py` (extracted with `git show`, loaded by importlib): a report whose body contains the contract template line "Status DONE/PARTIAL/BLOCKED" classified DONE; "REVIEW … Verdict REVISE. A later round may Verdict ACCEPT." classified DONE. Same probe against HEAD e6b8fe1: both PARTIAL with reason missing_or_nonaccepted_report; a plain "REPORT 02 — Status DONE" header stays DONE.
- Ignore rules: `git check-ignore -v` confirms `/plan/logs/` covers `plan/logs/<id>/start.json` and `plan/logs/fable-slot-N.lock`, so raw receipts and lock files cannot be committed by accident. start.json contains the full command (prompt and CONTRACT text) and absolute cwd; no credential values are read or written. The provider-routing check reports variable names only.
- `plan/exec/reports/02.md` does not exist at review time; STATUS.md still lists 02 as PENDING. The implementer REPORT required by the task is absent.

## Findings by severity (against 93028ef)

P1 — Self-reported DONE could be granted by substring match (supervise.py classify). The acceptance regex searched the whole report for `Status DONE` or `Verdict ACCEPT`. A PARTIAL report that quotes the REPORT template, a REJECT review that mentions a future ACCEPT, or a stale "Status DONE" line from an earlier attempt all classified DONE. This contradicts the task interface contract "no self-reported DONE grants acceptance" and the id/type of the record was never checked, so a REVIEW could satisfy a REPORT slot and a Task 03 report could satisfy Task 02. Confirmed by probe above.

P1 — Timeout handling did not confirm the owned process group stopped (supervise.py execute). After SIGTERM, if the leader exited but a descendant ignored or outlived the signal, SIGKILL was never sent and the function returned as if terminated. `claude -p` spawns subprocesses, so an orphaned worker could keep consuming a Fable slot and acting on the worktree after the supervisor reported PARTIAL. Scope: only the child's own session is signalled (start_new_session=True), so unrelated processes are never terminated; that constraint is met.

P2 — preservation.py missed untracked files under src/, tests/ and bench/. New-path detection used `git ls-files` without `--others`, so an untracked new module under src/ passed the "no new protected path" check while remaining eligible for inclusion in a working-tree build.

P2 — verify.sh ran scripts/smoke_test.sh with the global uv on PATH. smoke_test.sh calls bare `uv`; only `.venv/bin` was prepended, so the smoke step would use installed uv 0.12.5 rather than the pinned 0.11.29 isolated binary required by the plan and Task01 decisions.

P3 — Attempt directory is created before slot acquisition (supervise.py main). `output_dir.mkdir()` precedes the flock loop; when both slots are busy the run exits with an empty attempt directory, and the same attempt id can never be retried because mkdir refuses to replay. Move the mkdir after slot acquisition, or write a `rejected.json` into it so the empty directory is itself evidence.

P3 — No post-run integrity check of PLAN_ROOT. Scope enforcement runs `git diff`/`ls-files` only in the task cwd. Workers receive an absolute central path in the control worktree, so a write to another task's REPORT, a task spec, or PLAN.md in the control worktree is not detected by the supervisor. PLAN.md SHA is checked only before dispatch. Re-hash PLAN.md and the tasks/ directory after the child exits and record a `git status --porcelain` snapshot of PLAN_ROOT in finish.json.

P3 — The `wrapup` admission bypass is not recorded. `cfg.get('wrapup')` lets a dispatch start after 04:37:18Z, which is legitimate for finalizing reports, but start.json does not record that the exception was used.

P3 — Unhandled decode path. `native.json` is read with `read_text()`; invalid UTF-8 would raise before finish.json is written, leaving no classified record for that attempt. Read bytes and decode with `errors='replace'`, or catch and classify as invalid_json.

Informational — The two-slot limit is enforced only for dispatches that go through supervise.py. The review dispatch that launched this session used a raw subprocess.Popen with no slot lock, no scope check and no deadline cap, so the "at most two concurrent Fable task processes" rule depends on root routing every call through the supervisor. The release-start deadline (03:37:18Z) is not enforced by the supervisor; it belongs to Astra's Task 10 path and is acceptable to leave there. Effective effort is correctly reported as not exposed in terminal JSON, consistent with Task01.

Informational — Test coverage at 93028ef: the six required mock cases (success, nonzero exit, malformed JSON, absent REPORT, timeout, out-of-scope modification) are present via classify() and a real subprocess. Untested: changed_paths (git), slot locking, deadline arithmetic, main(). The passing suite did not cover either P1.

## Required changes (for 93028ef)

1. Validate the first non-empty header line only: exact record type, exact task id, and `Status DONE` / `Verdict ACCEPT` in the correct field position; reject other types, other ids, and later-field matches. Add negative tests for template echo, stale DONE, REJECT-then-ACCEPT, wrong id and wrong type.
2. After the leader exits or SIGTERM, verify the process group is empty; escalate to SIGKILL on the group and record termination_confirmed and leftover_children in finish.json; force PARTIAL when either is bad. Add a test with a SIGTERM-ignoring grandchild.
3. Include `git ls-files --others --exclude-standard` paths in the preservation new-path check, with a test.
4. Put `dirname "$UV_BIN"` ahead of PATH in verify.sh so smoke_test.sh resolves the pinned uv.
5. Write the Task 02 REPORT to plan/exec/reports/02.md with the commands and results actually run, including that the full verify.sh runbook either ran under isolated uv 0.11.29 or was not run.

## Follow-ups

- HEAD e6b8fe1 (three commits after 93028ef) appears to implement required changes 1–4: first-header validation with id and kind, group_live/signal_group with SIGKILL escalation and lifecycle reasons, untracked protected paths in preservation.py, and the PATH fix. My independent probe and the 10-test suite confirm the P1 and P2 behaviors are fixed at HEAD. P3 items above remain open at HEAD. One smell: `classify()` defaults `expected_id="02"`; it should have no default so a missing config key fails loudly rather than silently checking the wrong task.
- `group_live` uses `ps -axo pgid=,stat=`; this is correct on macOS, where the run executes, and tolerated by procps on Linux with a warning. Acceptable for run-local use.
- Merge gate: the final commit for this lane needs its own fresh Codex and Fable ACCEPT records plus the Task 02 REPORT. This REVISE record applies to 93028ef and does not waive that gate.
