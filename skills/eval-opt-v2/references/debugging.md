# Debugging

Record the original trigger, expected behavior and observed symptom. Choose a
check that could distinguish the suspected defect from a plausible alternative.
Minimize the input without losing the failure mechanism, and retain the original
scenario for final verification. An inferred cause is not a reproduced failure.

Derive expected behavior from the contract or an independent invariant, not the
candidate implementation. Where feasible, observe the regression before fixing it.
After an authorized patch, rerun that regression, the original scenario and the
required project checks against the same candidate. Keep their results separate.

Inspect the side effects of diagnostic commands under read-only requests. Do not
change baselines, fixtures or caches to manufacture a failure. Keep temporary
instrumentation within owned paths and remove only your own additions when
permitted. For intermittent behavior, retain every attempt; a finite passing
sample does not establish absence of a defect.
