REVIEW control-packet-final — Reviewer Astra independent Codex subagent baseline_verify | Verdict ACCEPT

Exact target: `4fcce2394270cfe8c4e082de418dc9b322e9c97f`, compared with previously reviewed `2b4f00eb9c3c004af7da8b728aaedc404bfc1779`. This is a targeted operational-record re-review, not a release approval. Later working-tree changes are excluded.

## Findings by severity

None requiring changes. The sole requested clarification from `control-packet-codex-01.md` is resolved by the append-only final section of DECISIONS:

- External enforcement is correctly limited to wall-clock, owned-process and post-run scope constraints; the controller passes the requested CLI turn cap.
- Requested caps and native `num_turns` are retained separately, with the three observed differences and the Task01 probe stated accurately. They are not called proven cap violations, and no undocumented counter-equivalence or controller fix is inferred.
- Model self-reported assistant/tool counts are excluded as enforcement evidence. Final usage accounting must retain the requested/native distinction. The two superseded wording locations are identified explicitly; historical reports, reviews and native outcomes remain unchanged.

STATUS now identifies the Task02 root receipts and clarification, Task03 final-review supersession, Task06 corrected report, and Task04 as in progress with reviews pending. It does not claim the new amendment has already received both reviews, or that pending work is complete.

The research-preservation snapshot is bounded to root's dated read-only GitHub observation of PR33–36 availability/state; it explicitly disclaims fresh result reproduction or acceptance and requires final ref rechecking. All four listed head commits exist locally and none is an ancestor of baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`. Live OPEN/draft/remote-branch state was not independently queried in this review; this accepts the snapshot's bounded record, not a new live-state attestation.

The new Task05 implementation prompt preserves the approved file ownership, source/test/research exclusions and security route. It keeps version/release ownership with Task08, prohibits premature publication/archival claims, and leaves integrated rendered README inspection pending with root. CHANGELOG scalar-row disclosure is an inherited-baseline fact, not new capability. Required local checks, native accounting, no-model/no-credential boundaries and two-review requirements are explicit. The prompt does not authorize dispatch before its approved dependencies or editing any current evidence.

## Commands and results

- Resolved `4fcce23` to the exact full target above; inspected the complete seven-file record delta and prior reviews.
- `git diff --check 2b4f00e 4fcce23`: exit 0.
- PLAN SHA-256 remains `697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c`.
- No delta in PLAN, supervisor/preservation/runbook/test code, product source, tests, benchmark files or package metadata. The specified historical reports/reviews are unchanged.
- Selectively read the prior Fable review's retained finish receipt: head `2b4f00eb9c3c004af7da8b728aaedc404bfc1779`, DONE, exit 0, measured elapsed 314.828 seconds, matching the added decision note. This prior acceptance is not represented as its review of the new amendment.
- `git cat-file -e <head>^{commit}` succeeds for each PR33–36 head; `git merge-base --is-ancestor <head> fc3045d` exits 1 for all four.

## Required changes and limits

None. Fresh Fable review of this amendment remains required before the two-review merge gate is satisfied. Prior accepted control, preservation and privacy findings remain applicable because their bytes and packaging allowlists did not change. No repeat full suite, model probe, scanner, build or live GitHub refresh was performed for this record-only amendment.

Only this review file was written. No network, model call, source edit, credential or `.env` read, release action or change to historical evidence occurred. This verdict is neither package qualification nor authorization to publish a release.
