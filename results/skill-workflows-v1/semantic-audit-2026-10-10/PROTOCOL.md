# Post-publication semantic audit, revision 1

This is a failure-informed, post hoc audit, not a preregistered replacement for
the workflow study. The user authorized this audit on 2026-10-10 after the
published v1 results and preliminary failure inspection were known. Auditors
are maintainer agents with separate authoring and review roles, not blinded
independent human adjudicators. No corrected result can establish a new
confirmatory superiority claim.

## Immutable inputs and scope

The source publication is commit
`fdf81a55f58df6cbd2a99550dd1637f9f53142f7`, and its held-out bundle is
`6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa`.
All v1 task assets, source, model outputs, grades, policy inputs/decisions,
accounting, registered analysis and transfer artifacts remain unchanged.
Only this new audit directory, repository navigation/claim qualifications,
and an additive CI replay step may change. No models, campaign restart,
agent retry, skill tuning, original-verifier repair or transfer regrading is
part of this audit. No merge, tag or release is authorized.

The audit covers all 45 retained outputs, including v1 passes, from exactly
five tasks: `fixed-width-record-reader`, `review-object-copy-clean`,
`review-binary-framing`, `truncated-test-log`, and
`wrong-architecture-binary`. Each has three arms and three repetitions.
The other 387 outcomes are carried through, not semantically revalidated.
Finding these issues does not establish that the other 43 tasks are flawless.

## Adjudication rules

1. Derive behavior from the visible contract; do not add exact exception-type,
   nesting-depth, finding-count, or exit-code labeling requirements after the
   trial. Apply each rule to every arm/repetition, including demoting v1 passes
   that missed a real defect.
2. Exception subclass compatibility is distinct from concrete class-name
   equality. Check the entire retained case trace. A short-circuited verifier
   does not supply results for cases it never executed.
3. Review findings require an introduced, contract-relevant behavior change.
   Equivalent descriptions or multiple supported consequences of one cause
   are not missing or invented defects. An empty review that misses a
   demonstrated introduced defect is unsuccessful.
4. Distinguish a failed command from unavailable task evidence. A truthful
   blocker report is not a false success merely because an under-specified
   check label differs. Unsupported success, refusal and boundary metrics
   retain distinct meanings.
5. Every row records original and adjudicated metrics, the rule and supporting
   evidence identities. Missing original executions remain missing. Any new
   isolated diagnostic is labeled supplemental evidence with its own source,
   runtime, command, output and limitations; it never becomes an original
   hidden reply or enters an original policy input.

## Evidence and execution boundary

Retained evidence inspection and trusted standard-library mechanism probes
are permitted. If full semantic adjudication needs new diagnostic execution,
use a fresh network-disabled, resource-bounded, unprivileged container,
read-only source and no credentials; do not import retained candidate code on
the host. Bind exact source bytes and distinguish new execution from original
trial evidence. Public reproduction checks retained audit inputs and arithmetic
without executing candidates, contacting models or starting Docker.

Separate retained-trace-only results from any source-assisted or supplemental
diagnostic conclusions. Unresolved labels must be null, with conservative
assignment bounds; do not silently drop them or convert them to failures.
The trace-only sensitivity concerns missing fixed-width case executions;
other task corrections still use the semantic audit, including new trusted
mechanism probes. It is not a claim that the entire audit uses only old traces.

## Analysis and review

Show original v1 and post hoc adjudicated counts side by side. Preserve the
432-trial denominator and each task/repetition pairing. The descriptive C-minus-B
calculation uses task averages and the original category-stratified paired
bootstrap method, 20,000 resamples and seed `20261008`. Mark degenerate
intervals and insufficient evidence; zero observed differences do not prove
equivalence. Report conservative bounds when trace-only labels are unresolved.
As a separate sensitivity, exclude all five audited tasks uniformly from all
arms; state the resulting 43-task/129-trial-per-arm population.

Policy decisions never change. Any cross-tabulation against new correctness
labels is secondary and explicitly post hoc; it cannot show what a policy
would have changed during execution. Resource observations remain v1 lower
bounds and support no efficiency or dollar-cost claim.

Before publication, separately review semantic rules and arithmetic, run
positive/negative and integrity controls, verify v1 preservation, and reproduce
the package from a fresh public checkout. Recommendations for eval-opt v2 are
development hypotheses, not measured improvements. The exposed v1 tasks may
be regression controls but cannot serve as fresh held-out evidence for v2.
