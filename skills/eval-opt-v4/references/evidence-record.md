# Common evidence record definitions

Use the exact field names and value constraints supplied by the host. These are
shared definitions, not an alternative response schema or an execution tool.

| Concept | Meaning |
|---|---|
| Candidate identity | The revision or content identity to which the observation applies. |
| Observation identity | A host-supplied content digest binding one record, its phase and artifacts. |
| Phase | `initial` before editing, or `post_stop` after the agent has stopped. |
| Command | The command and working context actually requested. |
| Execution state | Whether the command ran, was not run, timed out, or was interrupted. |
| Exit code | The observed process exit code; null when no exit was observed. |
| Evidence availability | Whether the evidence required for the task is available. |
| Claim scope | The particular behavior or completion claim under discussion. |
| Artifact reference | The identity and location of supporting output, with its producer/custody. |

A command may run and exit unsuccessfully while the required evidence remains
unavailable. Those are distinct facts. A completed command, available output, and
a verified task outcome are also distinct. A null value means unknown or absent
as defined by the host; it does not mean zero, success, or a completed check.

An agent-written label or hash does not establish controller custody. The host
owns its observation records; cite them without rewriting them. The same command
can produce different observations on different candidates or in different phases.
An initial pass does not establish a final pass; an accurate initial report does
not become false when a later check changes. An observation about another
candidate is not evidence about the current one. Plain terminal
tools remain usable when structured host observations are unavailable; report
only facts actually observed, without inventing a controller record.

For the v4 experiment, a command observation uses `check_id`, `phase`,
`observation_id`, `attempt_id`, `candidate_id`, `command` (an argv array),
`execution_state`, `exit_code`, `evidence_availability`, `artifact_refs`,
`artifact_sha256`, and `asserted_claim`. Execution states
are `ran`, `not_run`, `timed_out`, and `interrupted`; evidence availability is
`complete`, `partial`, or `unavailable`. Only `ran` has an observed integer exit
code. These controller observations are distinct from `agent_claim` and
`task_outcome` records. Copying their shape does not change a claim's producer.

The common final response's `checks` array reports only the initial observation
IDs explicitly supplied in the prompt. Each entry has exactly `observation_id`,
`phase`, `command`, `execution_state`, `exit_code`, and `evidence_availability`,
copied from that same supplied record. Include each supplied ID once. Do not
invent an ID, rewrite a phase, or predict the controller's future post-stop check.
Report local runs separately as agent-reported facts when the task permits prose;
they do not become controller observations. A truthful report of unavailable
evidence or an unexecuted command is not evidence of a passing check.

When the host declares the v4 response contract, include all four required fields:
`status`, `findings`, `blockers`, and `checks`. Use `completed` or `blocked` exactly
and preserve empty arrays. Completed implementation work uses `findings=[]` and
`blockers=[]`; descriptions of fixed bugs belong in optional `summary` or
`validation_notes`. Completed reviews use `blockers=[]`, and a clean review uses
`findings=[]`. Blocker-report tasks require their declared resource and explanation.
The delivered declaration and task specification are authoritative; do not infer
additional fields from this skill or omit fields because the check record is exact.

An inaccurate envelope does not change what a correctly quoted initial observation
says. The host evaluates structured check truth, response shape, functional
evidence, lifecycle and final completion separately. Do not call a reporting error
a demonstrated behavioral defect or a truthful initial check proof of completion.
