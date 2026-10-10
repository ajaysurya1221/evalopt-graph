# Held-out operations note — final campaign reconciliation

This note records two different interruptions in the frozen 432-trial held-out campaign. It reports operational evidence and recovered resource usage, not benchmark scores. Final reconciliation found **432 terminal unique trials and 433 retained attempts**, including the one permitted infrastructure retry. All final outcomes are available; this note does not assess their scores.

The controller stayed at commit `31231949412ea6d0101331720c0f0ed2d9f50b46`. The held-out registration's canonical JSON digest is `bd8bc5e42717a26570055db5896fb880ba92c7dc5725b3bcaca330d3abed4f8e`. The distinct scheduler-registration digest is recorded in [receipt.json](receipt.json). No task, skill, grader, policy, model condition or completed outcome was changed by these operational actions.

## Audit pause after 22 trials

Run 1 was stopped at a clean boundary on 2026-10-09 at 09:04 UTC, after 22 finalized trials and with zero active attempts. Its native end receipt records `interrupted` / `CancelledError`. This was a precautionary billing-boundary audit, not observed quota exhaustion. The audit found no evidence of a credit debit, purchase or authentication-route change; it did not establish a server-side billing guarantee within an active turn. At 09:10 UTC, the unchanged registered pre-dispatch guard reported ordinary usage allowed and the campaign resumed. No trial was discarded or retried for this pause.

## Controller interruption and one explicit retry

Run 2 later lost its controller. The exact cause is unconfirmed. At the retained historical prefix, 419 attempts were finalized, 420 unique trials had started and 12 trials remained unstarted. Run 2 has 398 allowed permission receipts, corresponding to 397 finalized original attempts plus one start-only attempt. This correspondence is externally reconstructed; the native run-end receipt and its executor-return list are unavailable. They remain unavailable rather than being recreated.

The affected original attempt, `heldout--unavailable-signing-key--r2--A` attempt 1, had performed model work but had no retained stopped snapshot, acceptance decisions or grade. It was explicitly finalized as `infra_failure` / `controller_interrupted` at 20:15 UTC. Its original records and the earlier prefix were preserved. A late workspace archive is forensic material; it is not an original stopped snapshot and was not graded.

Rescued native logs support complete accounting for two agents: **140,003 input tokens, 1,167 output tokens, 10 model calls and 8 tool calls**, with **39.644 seconds of parent wall time**. Frozen parsing and separate maintainer-agent review confirmed the registered runtime and accounting gate. Complete resource accounting does not restore a workflow grade. Count these counters once for original attempt 1; do not add the corroborating stdout totals again or sum child wall time into parent wall time.

Run 3 performed one explicitly authorized infrastructure retry as attempt 2. At its review on 2026-10-09 at 20:19 UTC, the retry was finalized with runtime status `completed`, leaving **420 finalized unique trials, 421 retained attempts and 12 scheduled trials remaining**. This note does not assess its functional grade. Both original and retry attempts remain in all-attempt resources; final-attempt totals are a separate view and must not be added to them.

Run 4 was launched at 20:22:59 UTC and its native start was recorded at 20:23:00 UTC for the remaining 12 trials, without retry, recovery or quota-resume flags. Its native end at **20:35:54.650832 UTC** records `finished`, no stop reason and 12 returned trial IDs. Final reconciliation at **20:36:01.923158 UTC** verified **432 terminal unique trials, 433 retained attempts, zero active attempts and zero pending trials**. The one interrupted original remains an infrastructure attempt; the retry supplies that trial’s final outcome. Run 2’s native end and executor-return list remain unavailable; its 398-attempt correspondence remains externally reconstructed.

## Evidence scope

[receipt.json](receipt.json) provides the sanitized chronology, final reconciliation counts and exact identities of retained source records. SHA-256 over literal file bytes is labeled `sha256_bytes`; canonical parsed-JSON digests are separately labeled. In particular, the recovered usage file's byte hash differs from its canonical object digest. Hashes identify retained content; they do not authenticate its producer. Private paths, account/container/native-session identifiers, prompts, trajectories and candidate content are excluded.

This is a maintainer-run operations record. It is not independent human replication, a comparative result, a full evidence replay, or authorization to alter the frozen study. Final private reconciliation and a separate fresh-environment public replay have passed. Public replay validates supplied-reply grades and registered analysis; it does not reconstruct private native trajectories or the missing run-end record. This operations projection itself supports file-identity checks, not full replay of the private incident.

The final private report export ID used for transfer linkage is `75049e332567275d12287036a9f9bd2a2eff1921852c06f5cd5d697b8a94c7fc`. The public report-object digest is `df1047d68be946e93daa138ba91488ab2a30289aaa4ab69d150c0edeac78a731`; its analysis adds an explicit empty declared-unavailable roster. The held-out public bundle ID is `6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa`. These identify distinct objects and must not be substituted for one another. The retained final QA, report-binding and fresh-replay byte hashes are recorded in the receipt.
