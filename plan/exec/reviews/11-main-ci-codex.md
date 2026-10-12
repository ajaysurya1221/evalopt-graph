REVIEW 11-main-ci — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT

## Exact final-main gate

At 2026-10-12 23:19:29.288288 UTC, current public main is `b52c87539932c4b0682049f88eeeb5a433523150`. PR 43 merged normally at 23:14:19 UTC and its reviewed head remains `ba5db20743e632f6295a2d9bfbda7867e6579978`. Independent GitHub Git-object reads and local pinned `git rev-parse <commit>^{tree}` checks establish exact tree equality: both are `ec2198320003800ae6f75f9b105467d2aeac2455`.

This acceptance concerns the actual final-main hosted CI endpoint. The prior exact-candidate source reviews and PR gate remain separate evidence; there is no new source review or release authorization in this record.

## Complete applicable current-run roster

| Workflow | Run | Current attempt | Jobs | Reported steps | Result |
|---|---:|---:|---:|---:|---|
| CI | 38321068543 | 1 | 10 | 87 | completed / success |
| CodeQL | 38321068674 | 1 | 1 | 8 | completed / success |

Both actual main-push runs and all 11 jobs / 95 reported steps are completed/success. There are zero skipped, failed, cancelled or pending jobs/steps. Every retained job and check-run binds the exact target head. The initial, completed and final readback inventories contain the same two run IDs at attempt 1; there was no rerun or waiver.

The CI roster includes Ubuntu Python 3.10–3.14, macOS Python 3.14, quality/demos/smoke/artifacts, Windows clean-wheel verification, full-history Gitleaks and the required aggregate. CodeQL supplies its configured Python job. I matched exact job names to the previously inspected, unchanged workflow definitions and retained the final-main workflow source files. No independent lane is accepted merely because its aggregate is green.

The final readback contains exactly 11 check runs, each successful and corresponding to one of these workflow jobs. The extra advisory CodeQL service check observed on PR 43 was not present in this main snapshot; it is not a configured independent workflow job.

## Required-context distinction

Fresh branch-rules API data still names four required contexts: `CI / required`, `CodeQL / Python`, `Dependency review`, and `Gitleaks / full history`. The three applicable main-push contexts all pass. Dependency review is configured for pull requests only and passed on the exact reviewed PR head (run 38320137497, attempt 1); its absence from a main-push run is expected, not a skipped or missing applicable lane. This report does not assert a new Dependency review execution on the squash commit.

The remaining CI jobs are individually successful and are explicit dependencies of the required aggregator. The release workflow is tag-triggered and is outside this documentation closeout push gate. No advisory status substitutes for the two independent source reviews.

## Findings, analysis correction and limits

No hosted CI finding requires a change. Required changes: none for this exact endpoint.

An initial reviewer summary assertion incorrectly expected 12 check runs by carrying forward an extra advisory service check from the prior PR snapshot. It failed after the raw API captures had succeeded. Inspection established the actual roster of 11 workflow checks, with every job and step successful; the corrected summary and explicit analysis note are retained. This was a reviewer counting assumption, not a failed workflow, changed artifact, retry or waived gate.

Complete raw run records, exact-current-attempt jobs/steps, before/after inventories, current main/ref and PR metadata, Git-object/tree checks, branch rules and all check runs are retained privately under `plan/artifacts/11-main-ci-codex/`. Per-call records include exit status, timestamp and raw-output hash. Final receipt SHA-256: `3a0cdbb8a939f16565f8b4064040eee0053c0c9cebeecdf544566d3aea7478f4`.

API job/step success does not independently recount test assertions or establish zero test-case skips. No source, package bytes, Fable review, credentials or repository settings were modified or re-reviewed here. No workflow mutation, merge, ref change or publication occurred in this review. A later head or new attempt requires a fresh check.
