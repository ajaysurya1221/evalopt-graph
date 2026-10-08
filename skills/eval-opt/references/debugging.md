# Debugging

Use this procedure within the main skill's scope and remaining budget.

1. Record the original trigger, expected result, and observed symptom. Run a
   symptom-specific check capable of detecting the failure. Inspect whether a
   proposed command writes caches, snapshots, databases, or baselines before
   using it under a read-only request.
2. Reduce inputs or steps only while preserving the failure mechanism. Keep the
   original scenario available for final verification.
3. State a falsifiable hypothesis, its predicted observation, and the cheapest
   check that distinguishes it from plausible alternatives. Change one
   investigative variable at a time.
4. Exercise the real caller pattern. Where feasible, observe a failing regression
   check before patching. Derive expected values from the contract, a justified
   invariant, or an independent oracle, not the implementation under test.
5. After an authorized fix, rerun the regression and original scenario, then the
   required project checks. Report these results separately.

A passing new test without an observed pre-fix failure does not establish that
the reported bug was reproduced. Mark that limit. If prerequisites prevent
reproduction, distinguish the attempted command's failure from the reported
defect. Continue useful source inspection without presenting an inferred cause
or unexecuted fix as verified.

Do not manufacture a red result by changing frozen inputs or weakening an oracle.
For intermittent failures, retain every attempt; zero failures in a finite sample
does not prove absence. Use the main skill's stopping rules rather than starting
an unbounded stress loop.

Carry forward the hypothesis, command, observation, and evidence location. Redact
secrets while preserving diagnostic meaning and note material redactions. Track
remaining instrumentation and checks that could not run.

The diagnostic sequence adapts upstream work identified in
[ATTRIBUTION.md](../ATTRIBUTION.md).
