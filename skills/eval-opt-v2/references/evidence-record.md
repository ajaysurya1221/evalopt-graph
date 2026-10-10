# Common evidence record definitions

Use the exact field names and value constraints supplied by the host. These are
shared definitions, not an alternative response schema or an execution tool.

| Concept | Meaning |
|---|---|
| Candidate identity | The revision or content identity to which the observation applies. |
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
owns its observation records; cite them without rewriting them. An observation
about another candidate is not evidence about the current one. Plain terminal
tools remain usable when structured host observations are unavailable; report
only facts actually observed, without inventing a controller record.

For the v2 benchmark, a command observation uses `attempt_id`, `candidate_id`,
`command` (an argv array), `execution_state`, `exit_code`,
`evidence_availability`, `artifact_refs`, and `asserted_claim`. Execution states
are `ran`, `not_run`, `timed_out`, and `interrupted`; evidence availability is
`complete`, `partial`, or `unavailable`. Only `ran` has an observed integer exit
code. These controller observations are distinct from `agent_claim` and
`task_outcome` records. Copying their shape does not change a claim's producer.
