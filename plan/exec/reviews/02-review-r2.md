REVIEW 02 — Reviewer Fable high | Verdict ACCEPT | Findings by severity | Required changes | Follow-ups

Fresh independent review of a545477..b792371 on branch winddown/20261013/02, worktree wt-control-02. Five commits, five files, 331 insertions, all under plan/exec: supervise.py, preservation.py, verify.sh, tests/test_supervise.py, tests/test_preservation.py. No package code, no frozen file, no `__version__` change (src still 0.1.0). Prior records read after forming findings: 02-review-r1.md (Fable, REVISE at 93028ef), 02-codex-round1.md (Codex, REVISE at 93028ef), reports/02.md, reports/02-baseline.md. No model dispatch, no source edit and no git mutation were performed by this review. Requested model/effort for this session: claude-fable-5-1, high; effective effort is not exposed.

Context: the lane advanced during review. HEAD moved from b792371 to 5d6df50 ("fix: classify invalid native UTF-8 as partial", 2026-10-12T19:39Z). The verdict below is given for b792371 as assigned; the b792371..5d6df50 delta was inspected separately and is covered under Follow-ups.

## Evidence (commands and results)

- `python3 -B -m unittest discover -s plan/exec/tests -p 'test_*.py' -v` at b792371: Ran 10 tests, OK. At 5d6df50: Ran 11 tests, OK.
- `python3 -B plan/exec/preservation.py`: `{"baseline": "fc3045d…", "protected_files": 75, "errors": []}`, exit 0.
- `git diff --check a545477 b792371`: clean. `bash -n plan/exec/verify.sh`: OK. All seven scripts invoked by the runbook exist.
- PLAN.md SHA-256 in this worktree and in the control worktree both equal 697f3fd7…b3c, matching the literal in supervise.py and preservation.py.
- `git check-ignore -v`: `/plan/logs/` covers attempt directories and slot locks; `/plan/artifacts/` and `.venv/` are ignored. No credential values are read or written; the provider-routing check reports variable names only.
- Full runbook run independently: `UV_BIN=<control-worktree>/plan/artifacts/tooling/bin/uv RUN_ARTIFACTS=<tmp> bash plan/exec/verify.sh` with Homebrew uv 0.12.5 first on PATH and no external PATH prepend. Exit 0 in 13 s. 422 collected (minimum 408), 422 passed, zero skipped, ruff check and format clean, three demos passed, generated conformance 8 valid / 12 adapter / 12 legacy rejections all passed, smoke test passed (the single "Gates: tests FAIL" line is the designed bounded stuck-case scenario with expected nonzero exit), preservation 75 files / no errors. verify.sh and preservation.py are byte-identical between b792371 and 5d6df50, so this run covers both. Working tree clean afterwards. This is the first evidence that the corrected runbook itself resolves bare `uv` to 0.11.29; the retained baseline runs (02-baseline.md) were at 93028ef with an external PATH prepend. A replica of verify.sh line 9 confirmed `command -v uv` changes from /opt/homebrew/bin/uv 0.12.5 to the pinned 0.11.29 after the export; the dev extra contains no `uv` package, so `.venv/bin` cannot shadow it.
- Classifier probe (importlib against committed supervise.py). Rejected as PARTIAL: contract template echo "Status DONE/PARTIAL/BLOCKED", the 02-baseline header presented as task 02, id prefix "REPORT 020", "REPORT 03", REVIEW record offered as REPORT, REJECT followed by a later "Verdict ACCEPT", "Status DONEX", lowercase header, a code fence as first line, non-object JSON (`null`, `"x"`, `[]`), a second model in modelUsage, non-dict provider entry, `is_error: 0`. Accepted as DONE: the actual reports/02.md first line, `#`-prefixed and `**`-bolded headers, ASCII hyphen, `Status:` with colon, CRLF, leading blank lines.
- Lifecycle probe: leader exits 0 immediately after spawning a SIGTERM-ignoring grandchild → `leftover_children: True`, `termination_confirmed: True`, group dead afterwards, 0.06 s wall. Clean leader → both flags correct. Timeout with SIGTERM-ignoring grandchild (the committed test) → terminated and confirmed. Only the child's own session (start_new_session) is ever signalled; unrelated processes are never touched. `group_live` via `ps -axo pgid=,stat=` is correct on macOS where the run executes.
- scope_errors with fnmatchcase: a sibling report path and `.venv/bin/python` are flagged; allowed globs pass. Untracked files are now included through `git ls-files --others --exclude-standard` in both changed_paths and preservation.py (test_preservation.py builds a real repo fixture and confirms a new untracked src file fails).

## Disposition of round-1 required changes

1. First-header validation with exact type, id and field-positioned verdict: done, with negative tests (template echo, stale DONE, REJECT-then-ACCEPT, wrong id, wrong type). Verified by probe.
2. Owned-group confirmation with SIGKILL escalation, `termination_confirmed` / `leftover_children` recorded, PARTIAL forced with reason process_group_lifecycle: done. Verified by probe for both the timeout and the leader-exit paths.
3. Untracked protected paths in preservation.py: done, tested.
4. Pinned nested uv in verify.sh: done, verified by a full run.
5. REPORT at reports/02.md: present, first line parses as DONE under the new classifier. Its figures (10 tests, 75 files, 422/32, 14 stages) match what I observed.
Round-1 P3 items: attempt mkdir now follows slot acquisition, admission, scope and report-existence checks; PLAN.md, CONTRACT.md and tasks/*.md are hashed before and after dispatch with mismatches added to scope errors; `git status --porcelain -- plan/exec` of the control root is recorded in finish.json; `wrapup` is recorded in start.json; stdin is DEVNULL; native.json is read as bytes and decoded with replacement at b792371 (see P3 below).

## Findings by severity (against b792371)

No P1. No P2.

P3 — Trailing free text after the verdict token is accepted (supervise.py classify, lines 43–44). The regex allows anything after `DONE` or `ACCEPT` as long as the next character is a space or pipe. "REVIEW 02 — Reviewer Fable high | Verdict ACCEPT or REVISE or REJECT", which is the literal first-line instruction given to reviewers, classifies DONE; "REPORT 02 — Status DONE but tests failed" classifies DONE. The slash form "ACCEPT/REVISE/REJECT" is correctly rejected. Not blocking because the token must be in the correct field of the first header and root reads every review, but tighten to require that only a pipe-delimited field may follow: `DONE(?:\s*\|.*)?$` and `ACCEPT(?:\s*\|.*)?$`. Add the "ACCEPT or REVISE or REJECT" echo as a negative test.

P3 — Invalid UTF-8 inside an otherwise valid native.json classified DONE at b792371 (supervise.py main, line 166). `decode('utf-8', errors='replace')` turns a corrupted byte inside a string value into U+FFFD, leaving valid JSON. Probe: a success record with `"result":"\xff"` → DONE at b792371, PARTIAL (invalid_json) at 5d6df50, which passes bytes to json.loads so UnicodeDecodeError is caught as ValueError. Fixed by the follow-up commit; no action needed if 5d6df50 is the merged head.

P3 — Central integrity check does not cover other tasks' reports, reviews or decisions. Only PLAN.md, CONTRACT.md and tasks/*.md are hashed. In the control worktree those report and review files are currently untracked, so the recorded `git status --porcelain` snapshot shows them as `??` before and after and cannot reveal an overwrite. A worker that rewrote another task's REPORT in the central root would go undetected by the supervisor. Extend `immutable` to every pre-existing file under exec/ except the assigned report path, or at least reports/, reviews/ and decisions/.

P3 — `classify()` still defaults `expected_id="02"`. main() passes `cfg['report_id']` explicitly so production is safe, but a direct caller omitting the id silently checks task 02. Remove the default (the tests pass the id implicitly today and would need `expected_id='02'` added).

P3 — Test coverage of the leader-exit path. `test_child_survives_leader_term` lets the leader sleep until timeout, so it exercises the timeout branch only; the `leftover_children=True` branch (leader exits, descendant lingers) has no committed test. My probe confirms the branch works. The REPORT phrase "leader-exit descendant cleanup" overstates what the suite covers; add a leader-exits-0 case.

Informational — `timeout` is computed from `now` captured before slot acquisition and the scope check; a long wait for a slot cannot happen (LOCK_NB fails fast), so the drift is negligible. `report.exists()` replay refusal applies to the review path too when `record_type` is REVIEW. The two-slot limit, deadline cap and scope checks still apply only to dispatches routed through supervise.py; the REPORT states this limit honestly for reviews launched before the helper existed. The release-start deadline is not enforced here and belongs to the Task 10 path.

## Required changes

None for ACCEPT. The P3 items above are recommended follow-ups, not merge blockers.

## Follow-ups

- b792371..5d6df50 (2 files, +6/−1): passes native.json bytes directly to classify and adds `test_invalid_utf8_fails`. I inspected the diff, reran the suite (11 OK) and confirmed by probe that it resolves the UTF-8 P3 above with no behavioral change elsewhere. No findings on that delta. Root may treat this record as covering 5d6df50; the Codex record for the lane must still name the exact head it reviewed.
- STATUS.md still lists 02 as IN_PROGRESS at 93028ef; root should update it with the final head and both review records.
- The classifier regex tightening (first P3) is a one-line change with one negative test; it is worth taking before supervise.py is used to admit review records, since the reviewer prompt literally contains the echo string.
- Merge gate: this ACCEPT plus an accepted independent Codex review of the same head are both needed. An implementer REPORT and this record do not by themselves authorize merge.
