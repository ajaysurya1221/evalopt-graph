---
name: eval-opt
description: Bounded implementation, debugging, review, and research against explicit acceptance criteria. Use when a task needs iterative verification, complete candidate review, or evidence-backed conclusions.
metadata:
  version: "1.0.0"
---

# Eval-opt

Turn a request into a small acceptance contract, gather evidence against it, and
stop within an explicit budget. This bundle guides the agent using it. It does
not install hooks, execute a runner, enforce a sandbox, or authenticate evidence.
The separate evalopt-graph kernel evaluates supplied inputs; its replay does not
establish that those inputs describe the world correctly.

## Establish scope and budget

Read the target's operating instructions. Record the requested outcome, allowed
paths, frozen inputs, existing changes, and required checks. Respect the requested
mode: implementation may edit owned paths; diagnosis and review remain read-only.
A read-only request includes state, logs, caches, fixtures, and Git metadata.
Use conversation records or an explicitly permitted external artifact location.
Do not create `.evalopt/`, change ignore files, or initialize Git automatically.

Use the host's tools and existing project environment. Prefer the project's own
check commands to guesses. Missing tools are evidence limits, not permission to
install globally, switch billing routes, loosen permissions, or change scope.
Continue authorized reversible work without asking for approval again. Obtain a
missing decision only when it changes acceptance, scope, or authority.

Honor the user's or harness's time, call, concurrency, and iteration limits.
When unspecified, use at most six implementation/verification cycles or four
research rounds. An initial implementation and check consumes one cycle; every
subsequent patch and check consumes another. Diagnosis consumes a cycle when a
hypothesis is tested. Delegation and changing hypotheses do not reset the budget.
An explicit smaller limit wins. Record the chosen ceiling before starting.

## Load only relevant guidance

| Situation | Read |
|---|---|
| Defect, regression, or repeated failure | [Debugging](references/debugging.md) |
| Multiple behaviors or concurrent workers | [Work packages](references/work-packages.md) |
| Patch discovery or review | [Review coverage](references/review-coverage.md) |
| Research, disputed facts, or missing verification | [Evidence](references/evidence.md) |

## Work loop

1. **Contract.** Make each acceptance criterion observable. Record how it will be
   checked, whether the check is required, and what would remain unverified if it
   cannot run. User requirements define the target; they do not prove a reported
   implementation or diagnosis correct. Keep assumptions separate from facts.
2. **Investigate and plan.** Inspect the actual candidate and relevant contracts.
   Choose the smallest coherent change or discriminating check. For a review,
   inspect only; for research, gather sources and counterevidence. Do not replace
   the requested outcome with a larger refactor or an easier task.
3. **Act within ownership.** Implement the current slice only when authorized.
   Preserve frozen inputs and others' changes. Never delete, skip, weaken, or
   rewrite a test merely to make it pass. Preserve unrelated behavior. Track any
   temporary instrumentation and remove only your own additions when permitted.
4. **Verify the same candidate.** Execute required checks and inspect their real
   output. Record command, working directory, candidate identity, exit status,
   salient observation, and available evidence location. Distinguish failed,
   not run, and passed. A success message alone is insufficient when the command
   checks the wrong files, revision, or behavior. Review contract compliance and
   implementation correctness before declaring completion.
5. **Decide and report.** If criteria and required checks are satisfied, stop.
   Otherwise use observed failures to choose the next bounded action. Stop with
   the exact unresolved criterion when the budget expires or no authorized path
   remains. Describe partial implementation without claiming verified completion.

After the same failure signature appears three times, stop repeating that action.
Diagnose the shared assumption and select a materially different check within
the remaining budget, or report the blocker. A failure signature includes the
failing check and observed cause, not only its exit code. Retry a transient
infrastructure error at most once when the host allows it; retain both results.
Agent mistakes and exhausted task budgets are not infrastructure failures.

New evidence can change the plan; it cannot silently relax acceptance. A model
score, reviewer agreement, or repeated confident answer cannot override a failed
required check. A suspicious intermittent check may be investigated within the
same budget; keep all observations and do not select only a passing rerun.

## Delegation and continuity

Use available native host subagents when independent investigation or disjoint
work can help. Do not launch a second agent CLI, require named custom agents, or
invent unavailable tools. Honor host concurrency and depth limits; parent and
children share the task's budget. When delegation is unavailable, work inline
and disclose the absence of an independent review if that review was required.

Give a worker its goal, allowed paths, exclusions, acceptance checks, current
candidate, and relevant evidence. Tell editing workers they are not alone and
must preserve others' changes. Review workers stay read-only. Verify a worker's
evidence before relying on it; its conclusion is not proof.

Keep compact progress records: contract, current candidate, consumed budget,
last observation, next action, blockers, and evidence references. Write records
only to an allowed location. On resumption, recheck candidate and evidence
freshness; retain consumed budget unless the user grants a new one. Do not reuse
a prior pass for a changed candidate.

## Final response

Follow the user's requested format. State what was completed, which checks ran
against which candidate, their outcomes, and any remaining gap. Separate observed
facts from inferences and assumptions. For a review, report supported findings
with locations and a verdict; absence of findings is not proof of correctness.

Do not label a workflow result as the kernel's `ACCEPTED`, `BLOCKED`, `FAILED`,
`UNSUPPORTED`, or `UNVERIFIED` decision unless the kernel actually produced that
decision from a retained input. Even then, state what the decision establishes.

See [attribution](ATTRIBUTION.md) for adapted upstream ideas and licensing.
