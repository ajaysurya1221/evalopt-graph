REVIEW 02 — Reviewer Fable high | Verdict ACCEPT | Findings by severity | Required changes | Follow-ups

Target: exact 5d6df50e7dbc73323503be211269ed872c5f6215, branch winddown/20261013/02, worktree wt-control-02, full scope a545477..5d6df50 (six commits). Diff touches only plan/exec/preservation.py, plan/exec/supervise.py, plan/exec/verify.sh, plan/exec/tests/test_preservation.py, plan/exec/tests/test_supervise.py (336 insertions, no deletions outside those files). No src/, tests/, bench/, scripts/ or package metadata change; `__version__` is still "0.1.0". This review ran read-only: no model dispatch, no source or git mutation; the only write is this file. Session request per start.json: model claude-fable-5-1[1m], effort high; effective effort is not exposed in terminal JSON.

## Evidence (commands and results, all at 5d6df50)

- `python3 -B -m unittest discover -s plan/exec/tests -v` (CPython 3.14.6): Ran 11 tests, OK, 0.6 s. Count is 11, not the 10 stated in reports/02.md; the eleventh is test_invalid_utf8_fails added by 5d6df50. Precision only.
- `python3 -B plan/exec/preservation.py`: `{"baseline": "fc3045d…", "protected_files": 75, "errors": []}`, exit 0. `git ls-tree -r fc3045d src tests bench | wc -l` independently gives 75. PLAN.md SHA-256 in this worktree is 697f3fd7…b3c and equals the literal in both scripts.
- `git diff --check a545477 HEAD`: exit 0. `bash -n plan/exec/verify.sh`: syntax OK. `py_compile` of both modules: OK.
- `git check-ignore -v`: /plan/logs/ and /plan/artifacts/ cover attempt directories, lock files and baseline logs; receipts cannot be committed by accident.
- `claude --version` 2.1.281; `claude --help` lists every flag the supervisor passes (--model, --effort, --permission-mode, --max-turns, --output-format, --no-session-persistence, --safe-mode, --append-system-prompt). reports/01.md records that native modelUsage keys are canonical `claude-fable-5-1` with provider firstParty, so the exact single-key check in classify() matches real output rather than failing closed on every run.
- Offline classifier probe (14 headers, 5 JSON shapes): template echo "Status DONE/PARTIAL/BLOCKED", BLOCKED, DONEISH, wrong id "REPORT 2", REVIEW in a REPORT slot, REVISE, ACCEPTED, and a Verdict ACCEPT placed in a later field all classify PARTIAL with missing_or_nonaccepted_report; plain, bold, markdown-heading and "Status: DONE" headers classify DONE; empty body, `null`, a second modelUsage key, a "[1m]" key and a missing is_error each classify PARTIAL with the expected reason. Bytes are passed straight to json.loads, so 0xFF inside a valid JSON string raises UnicodeDecodeError (a ValueError) and classifies invalid_json; the committed test covers this.
- Offline process probe: a leader that exits 0 after spawning a SIGTERM-ignoring child returns exit_code 0, leftover_children True, termination_confirmed True, and `group_live(pgid)` is False afterwards, so main() forces PARTIAL with process_group_lifecycle. Re-running execute() against the same output path raises FileExistsError (exclusive create), so an attempt id cannot be replayed. Only the child's own session (start_new_session) is ever signalled; unrelated processes are not touched.
- Live supervisor state during this review (`ps -axo pid,pgid,etime,command`): two supervise.py processes, pid 32185 (02-review-r2, started 19:38:36Z against b792371) and pid 32988 (02-final-review, 19:41:03Z against 5d6df50), each leading its own process group with a single `claude -p` child; plan/logs/fable-slot-0.lock and fable-slot-1.lock mtimes match the two starts. Both start.json records carry id, started_at, cwd, base, requested_model, requested_effort, turn_cap 20, timeout 1200 s, allow [], report path, supervisor_pid, wrapup False and a central_before map hashing exec/PLAN.md, exec/CONTRACT.md and every exec/tasks/*.md (22 and 23 entries respectively; the extra entry is the new 02-final-review.md task spec). Deadline literals ADMISSION_END 04:37:18Z and RUN_END 05:22:18Z equal the CONTRACT values. Provider-routing variable check is by name only.
- Baseline runbook evidence (not rerun here; it needs the isolated uv binary and I made no network calls): plan/artifacts/baseline/ in the central root contains verify-baseline-pinned.log and verify-baseline.log whose SHA-256 values match those printed in reports/02-baseline.md (bfaf2a9c…883bd and 0f4ea6bd…ac045). The pinned result record shows head 93028ef, nested uv resolving to the isolated 0.11.29 binary, exit 0, 19:32:05–19:32:18Z. The log shows "collected 422 tests (minimum 408)", "422 passed", the conformance JSON with 8 valid, 12 adapter and 12 legacy-rejected cases, "SMOKE TEST PASSED" and the preservation line with 75 files and no errors. The single "Gates: [('tests','FAIL')]" line is smoke scenario C, the expected bounded stuck case with non-zero exit.

## Findings by severity

No P1 or P2 findings. Every earlier required change is present and tested at 5d6df50: first-header-only validation with exact type, id and field position (test_rejected_headers_and_identity, test_wrong_record_type, test_later_accept_cannot_override_reject); owned process-group termination with SIGKILL escalation and lifecycle reasons (test_child_survives_leader_term, plus my leader-exit probe); untracked protected paths in preservation.py (test_untracked_source_fails); pinned uv directory ahead of PATH in verify.sh; attempt directory created only after slot, admission, scope and report-exists checks; wrapup flag recorded; central immutable hashes taken before dispatch and re-checked after, with a git status snapshot of plan/exec; stdin DEVNULL; invalid UTF-8 classified instead of crashing.

P3 (precision, no change required): reports/02.md states 10 tests; the suite is 11. The REPORT predates 5d6df50 and the task spec anticipates this.

P3 (precision, no change required): the baseline runbook pass is recorded at 93028ef with the uv directory prepended externally; the committed verify.sh at 5d6df50 internalizes that same one-line fix and differs from the tested script only by that line. The final script bytes have therefore not themselves executed end to end. The evidence is equivalent, and later release gates (Tasks 08–10) re-run the verifiers.

P3 (informational): native success in finish.json is execution accounting only. classify() returns DONE when the process, model, provider, scope, central hashes and record header are all clean; it does not and must not read as merge approval. Root's gate remains the two accepted independent reviews.

## Required changes

None.

## Follow-ups (not blocking, outside the accepted plan's acceptance criteria)

- start.json does not record which slot index was acquired; supervisor_pid and lock-file mtimes currently serve. A one-field addition would make admitted-slot evidence self-contained.
- classify() still defaults expected_id to "02"; main() always passes cfg['report_id'], so production is unaffected. Removing the default would make a missing config key fail loudly.
- report.read_text() and the prompt read use strict UTF-8; a non-UTF-8 REPORT would raise after the child exits and leave no finish.json for that attempt. Exit would still be non-zero (PARTIAL by contract) but the classified record would be lost.
- The non-timeout leftover-children path is exercised only by my probe, not by a committed test. test_child_survives_leader_term covers the timeout path.
- Root records: STATUS.md still lists 02 as IN_PROGRESS at 93028ef and should be advanced by root at integration. The concurrently running 02-review-r2 session targets b792371, not 5d6df50; its eventual record should not be counted as a review of the final commit.
- Independent Codex ACCEPT at 5d6df50 is still required by the contract; this Fable record alone does not satisfy the merge gate.

Spend: this review made no model calls; elapsed wall clock approximately 8 minutes within the 1200 s cap and 20-turn limit.
