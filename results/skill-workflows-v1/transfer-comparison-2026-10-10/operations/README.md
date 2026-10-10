# Transfer execution history and approved stopping

The planned 72-trial transfer stage ended with **58 executed attempts and 14 unstarted rows**. Each executed row ran once. All 72 original scheduled identities remain in the report. No timeout was retried, retrospectively graded, or given a reconstructed stopped snapshot.

This is a **failure-informed, amended feasibility study**. Two explicitly approved admission amendments changed when a later original row could start. They did not change task facts, skills, model, effort, original agent/verifier limits, runtime parsing, scoring or the per-trial stop checks. The operator subsequently approved finalizing the incomplete study after a failure outside the second amendment's allowed class.

| Execution phase | Native executions | External completion acknowledgments | End state |
| --- | ---: | ---: | --- |
| Original controller, trials 1–55 | 55 | 54 | Trial 55 timed out; original STOP retained |
| Exact historical exception, trial 56 | 1 | 0 | Trial 56 timed out with a different boundary failure; second STOP retained |
| Bounded continuation, trials 57–58 | 2 | 1 | Trial 57 quarantined without a score; trial 58 failed admission classification; third STOP retained |
| Remaining original schedule, trials 59–72 | 0 | 0 | 14 rows unstarted; no execution authorized after finalization approval |

An external acknowledgment is not a native execution or successful task outcome. All 58 native end records exist. The missing external acknowledgments for trials 55, 56 and 58 remain missing. The final operator's `dispatched: 1` counts its one acknowledgment, despite two native executions. The retained mapping records both numbers.

## Four preserved timeouts

Trial 55 (`transfer--make-doom-for-mips--r1--B`) reached its original 900-second agent deadline. Its native-stop command exceeded the controller's ten-second command limit. No stopped capture or original verifier reward was retained. Separately, the frozen parser used `str.splitlines()` on LF-delimited JSON containing literal U+0085 inside a string; parsing failed. Frozen accounting stays unavailable with invalid provenance. Corrected-parser counters were not substituted. The underlying cause of the stop-command timeout is not established.

Trial 56 (`transfer--make-doom-for-mips--r1--C`) also reached its original deadline. Native stopping was confirmed, but the execution boundary remained unconfirmed because of unclassified processes. Its retained accounting is partial with valid provenance. Capture and reward are absent. This different failure stopped the first continuation.

Trial 57 (`transfer--make-doom-for-mips--r2--C`) reached its original deadline with confirmed native stopping but an unconfirmed execution boundary. Under the second approved policy, its exact matching failure was durably quarantined after its genuine native end, child exit, and fresh process/container absence checks. Quarantine permitted only the next original row. The timeout remains unscored, with partial accounting and missing capture; quarantine is not a successful completion or restored boundary.

Trial 58 (`transfer--make-doom-for-mips--r2--B`) reached its original deadline. Its retained accounting has partial, valid provenance, but delegation evidence is unverified: child concurrency could not be verified and owned turn ends were missing. This does **not** establish that the concurrency limit was exceeded. Its native-stop command also exceeded ten seconds; no confirmed native stop, stopped capture, verifier result or reward was retained. Its genuine native end records `delegation_boundary_requires_remediation`. The unchanged classifier rejected the failure as outside the approved class, and the operator stopped. No second quarantine entry or completion acknowledgment was created.

Later process/container absence establishes only current quiescence. It cannot prove a historical cutoff, repair any of these original execution boundaries, or create missing verifier results. Null rewards remain unknown rather than being silently converted to failures. Conservative full-schedule bounds make the effect of those unknown outcomes explicit.

## Amendment provenance

The [exact historical exception](exact-historical-exception/provenance.json) was approved after trial 55 and authorized only the original 17 unstarted rows, with strict stopping for every new failure. The three modules in its `source/` directory are exact copies of the accepted external adapter; its [grant projection](exact-historical-exception/grant-projection.json) is a sanitized, non-executable representation of the private authorization.

The [bounded continuation](bounded-continuation/provenance.json) was separately approved after trial 56. Its five `controller/` modules are exact copies of the accepted implementation. The [original 16-row roster](bounded-continuation/pending-rows.json) remains unchanged; only its first two rows actually ran. The implementation passed [305 offline controls](bounded-continuation/provenance.json), comprising 284 independently authored and 21 author controls. The first adapter's combined 162-control run included its 148 independent controls; those counts must not be added. Engineering controls are not benchmark trials or independent human replication.

Copied amendment provenance and validation documents are historical snapshots prepared before final endpoint QA. Their prospective labels and pending-review fields remain unchanged; they do not describe the final publication status. The separately bound finalization record below supplies the later completed checks.

Finalization approval narrowed delivery to the retained 58 executions and 14 unstarted rows. [Finalization provenance](finalization.json) binds the approvals, preserved stop records, exact stopped tree, final raw-byte checks and separate journal reconciliation. Public provenance omits private filesystem paths, process identifiers, internal conversation identifiers, credentials and trajectories. Referenced private hashes identify retained content; they do not authenticate authorship or independently demonstrate the omitted private evidence.

## Interpretation and reproduction limits

The phases differ in tasks, order and admission policy; their outcomes do not support a causal phase comparison. These post-freeze amendments, outcome-dependent stopping and incomplete schedule rule out an uninterrupted frozen-run claim. The transfer subset supports descriptive feasibility findings only—not an official Terminal-Bench leaderboard score, workflow superiority, an efficiency comparison or independent replication.

Public replay checks the supplied artifact identities, original schedule, retained reward/counter arithmetic and report consistency. It does not run original verifiers, inspect private raw logs/archives, or independently repeat private process and journal observations. The full-byte checks do not make incomplete capture complete. Partial resource totals remain lower bounds; unavailable consumption remains unknown. Setup, verification and engineering-assistant overhead are outside reported trial counters.
