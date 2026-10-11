---
name: eval-opt-v2
description: "Bounded implementation, debugging, and review against explicit task contracts and candidate-specific verification. Use for iterative fixes, complete patch review, or evidence-backed completion reports."
metadata:
  version: "2.0.0"
---

# Eval-opt v2

Work against the requested outcome, preserve its boundaries, and verify the same
candidate you report. This skill supplies instructions: it does not enforce a
sandbox, authenticate observations, or install a runner. A kernel decision is a
decision about supplied evidence, not independent proof of correctness.

## Scope and budget

Read the target's operating instructions. Identify the requested outcome, allowed
paths, frozen inputs, existing changes, and required checks. Diagnosis and review
remain read-only when requested, including Git state, caches and fixtures. Write
notes or probes only in an allowed location; do not initialize repositories,
install globally, change permissions, or switch billing routes to unblock work.
Continue already authorized work without requesting the same permission again.

Honor host time, call, concurrency and iteration limits across parent and children.
Without a supplied cycle limit, use at most six implementation/check or diagnostic
cycles, or four research rounds. Record the ceiling before starting. Repeated
hypotheses and delegation consume the same budget. After the same failure recurs
three times, choose a different discriminating check or report the remaining gap.
Retry an infrastructure error only when the host permits it; agent mistakes and
exhausted task budgets are results.

## Conditional references

- For a defect or regression, read [debugging](references/debugging.md).
- For commit or workspace review, read [review coverage](references/review.md).
- When the host supplies structured observations, read the common
  [evidence record definitions](references/evidence-record.md). Use the host's
  exact response schema; this reference does not replace it.
<!-- evalopt-v2:typed-evidence-dispute:start -->
- When a check, its evidence availability, or a proposed completion claim conflicts
  with the task contract, use the
  [typed evidence and dispute procedure](references/evidence-dispute.md).
<!-- evalopt-v2:typed-evidence-dispute:end -->

## Work loop

1. State observable acceptance criteria and the checks required by the task.
   Separate facts, assumptions and unavailable information.
2. Inspect the actual candidate and choose the smallest coherent change or
   discriminating check. Preserve unrelated behavior and other workers' changes.
3. Implement only within ownership. Never delete, skip, weaken or rewrite a test
   merely to obtain a pass. Preserve the original failure and any frozen inputs.
4. Verify the same candidate. Record the command, candidate identity, actual
   outcome and evidence location. A success message is insufficient if it checked
   a different revision, file set or behavior. Retain unsuccessful observations.
5. Stop when the requested outcome is verified, or report the exact remaining
   criterion when the budget or authorized options are exhausted. A plausible
   implementation is not a verified completion.

Use available native subagents for useful independent investigation or disjoint
work. Give each worker the candidate, allowed paths, acceptance checks and shared
budget; tell editing workers they are not alone. Do not invoke another agent CLI.
Inspect returned evidence before relying on it. On resumption, recheck candidate
and evidence freshness without resetting the consumed budget.

Follow the requested final format. State completed work, checks actually run,
supported findings and remaining gaps. Do not present agreement, a model score,
or a workflow summary as an actual kernel decision. See [attribution](ATTRIBUTION.md).
