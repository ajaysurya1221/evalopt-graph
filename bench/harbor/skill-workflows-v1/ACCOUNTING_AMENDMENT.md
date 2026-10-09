# Partial resource accounting amendment

Amendment policy: `evalopt-partial-accounting-v1`.
The operator authorized **partial accounting** on 2026-10-09, after the development
pilot stopped at nine of 36 recorded outcomes. This is a maintainer-recorded
authorization, not independent authentication or an external preregistration.

## What changes

A source-bound amendment may admit a terminal task outcome with incomplete resource
telemetry. Retained, attributable completed-response counters provide **observed
lower bounds**, not exact billable totals. Missing responses have an unknown
remainder and no inferred upper bound. An empty observed counter is not evidence
that an interrupted request consumed no resources.

Each attempt is labeled complete, partial or unavailable. Complete means the
required native telemetry is present; it is not a reconciliation of provider billing.
Ownership, response
deduplication, the spawned-agent roster, delegation depth, and concurrency are
validated separately from resource completeness. Runtime identity must be positively
verified. Invalid or unverifiable structural evidence still prevents continuation;
the amendment does not convert every accounting-parser error into permission to run.

Reports show scheduled and attempted counts, complete/partial/unavailable coverage,
complete totals, and partial observed lower bounds separately. Final-attempt usage
and all-attempt usage remain distinct. Incomplete evidence is never inserted into
an exact total or represented as zero consumption. Resource-efficiency or cost
advantage claims are disabled for comparisons with incomplete accounting.

## Preserved experimental conditions

The existing nine pilot outcomes, finish records, grades, policy decisions, raw logs,
registration, source lock and immutable report exports remain unchanged. A separate
amendment binds their identities, the original pause, the pending schedule, and the
new accounting/controller sources. Derived accounting receipts are additional
artifacts; they do not overwrite original evidence or mark an incomplete attempt
as having complete usage.

The remaining pilot trials use the original frozen agent runtime, skills, task
facts, tools, images, model/effort, wall-clock limits, grader, policies and schedule.
The accounting rule applies identically to all arms. Task grades and their
denominators are unchanged. The ninth completed task is not retried. Infrastructure,
quota, runtime-identity and interruption gates remain in force; subscription
exhaustion pauses execution without changing billing routes.

## Later stages and publication

Before held-out or transfer execution, the new stage must explicitly freeze its
accounting-policy identity and compatibility evidence. A partial-usage receipt
cannot satisfy an old assertion that accounting was complete. Separate skill
exposure, execution-boundary, hidden-grading and native-stop requirements remain
mandatory.

Publication includes the amendment, coverage and lower-bound labels alongside
the original outcome provenance. Sanitized reproduction checks arithmetic and
retained controller evidence; it does not recover unreported usage, independently
authenticate the controller, or establish a workflow advantage. The first executable
milestone remains completion and QA of the 36-trial development pilot.
