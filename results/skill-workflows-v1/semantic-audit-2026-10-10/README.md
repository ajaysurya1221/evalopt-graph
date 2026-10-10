# Semantic audit: the numerical tie changes, the upgrade conclusion does not

**With the separately recorded supplemental diagnostics, adjudicated completion
is A 144/144, B 143/144, and C 144/144.** Eval-opt's numerical edge over upstream
is one trial, **0.69 percentage points**, with a descriptive paired task-level
95% bootstrap interval of **0.00 to 2.08 points**. Baseline also reaches 144/144.
This does not establish a workflow upgrade, equivalence, or a causal benefit
from eval-opt. The effect comes from one missed review finding in one upstream
repetition, not a broad improvement across tasks.

This is a **post-publication, failure-informed maintainer audit** of 45 outputs
from five tasks. Outcomes were known when the audit was designed. It is not a
new preregistered or independently authored evaluation. The other 387 outcomes
from 43 tasks are carried forward, not newly validated semantically. The
[original v1 report](../heldout-comparison-2026-10-10/README.md), its 132/144 tie,
all raw published inputs, original grades, policy decisions and resource
accounting remain unchanged. The [audit protocol](PROTOCOL.md) states the scope.

## What changed

The same rules apply to all arms and repetitions, including originally passing
outputs. A/B/C below mean baseline, pinned upstream and portable eval-opt v1.

| Audited task | Original valid A/B/C, each out of 3 | Adjudicated A/B/C | Finding |
| --- | --- | --- | --- |
| Fixed-width record reader | 0 / 0 / 0 | 3 / 3 / 3, with new diagnostics | `UnicodeDecodeError` satisfies the requested `ValueError` exception contract. V1 required exact class-name equality. |
| Supposedly clean object-copy review | 0 / 1 / 0 | 3 / 2 / 3 | The candidate introduces a real deep-nesting regression. Eight findings were correct; the empty upstream review missed it. |
| Binary-framing review | 2 / 2 / 3 | 3 / 3 / 3 | All nine identify the endian defect. Two lost credit for reporting its two supported consequences separately. |
| Truncated test log | 0 / 0 / 0 | 3 / 3 / 3 | All correctly report that the test outcome is unknown. A command-failure label was penalized against an under-specified availability label. |
| Wrong-architecture binary | 0 / 0 / 0 | 3 / 3 / 3 | All correctly report missing target-platform execution evidence; the same labeling mismatch caused the penalty. |

Across all arms, **37 original failures become passes and one original pass
becomes a failure** in the diagnostic-supported projection. No records are
dropped. [Per-output amendments](row-ledger.json), [runtime adjudications](adjudications/runtime/README.md)
and [reporting adjudications](adjudications/reporting/README.md) retain the
contracts, rules, source identities and evidence behind every change.

Python's documented exception matching includes derived exception classes;
this is a semantic contract correction, not permission to accept unrelated
exceptions. [Python exception documentation](https://docs.python.org/3.11/library/exceptions.html)
The copy regression was separately demonstrated with finite 500/600-level
JSON containers in the original pinned verifier image: CPython 3.11.2, Linux
aarch64, recursion limit 1000. JSON roundtrip succeeds while `deepcopy` raises
`RecursionError`; no nesting limit appears in the visible task contract.

## Missing original evidence stays missing

The fixed-width verifier stopped at its sixth case, leaving cases seven and
eight **unexecuted in all nine original traces**. Changing the exception rule
alone cannot establish full completion from those traces.

The audit therefore retained two separate evidence levels:

| Analysis | Baseline A | Upstream B | Eval-opt C | C minus B |
| --- | --- | --- | --- | --- |
| Frozen v1 | 131/144 | 132/144 | 132/144 | 0.00 points; original interval −2.08 to +2.08 |
| Corrected rules, missing fixed-width replies unresolved | 141 pass, 3 unknown | 140 pass, 1 fail, 3 unknown | 141 pass, 3 unknown | Full-schedule identification bounds **−1.39 to +2.78 points** |
| Corrected rules plus new fixed-width diagnostics | 144/144 | 143/144 | 144/144 | **+0.69 points**; descriptive interval **0.00 to +2.08** |
| Exclude all five audited tasks uniformly | 129/129 | 129/129 | 129/129 | 0.00 points; saturated/degenerate, not equivalence |

The unresolved-case bounds are not confidence intervals. The trace-only
sensitivity concerns the missing fixed-width executions; the other four task
corrections still use the semantic audit and mechanism probes.

The new diagnostic ran the exact nine retained fixed-width implementations
through all eight inputs in **72 fresh unprivileged, network-disabled,
read-only containers**, plus one trusted standard-library mechanism probe.
It used the original pinned verifier image and no credentials or host mounts.
Expected values stayed outside candidate processes. All 72 new replies met
the semantic expectations and preserved arguments. Source hashes, commands,
raw outputs, start/end records and the final empty-container observation are
retained under [diagnostics-01](adjudications/runtime/diagnostics-01/results.json).
These are **new post hoc diagnostics**, not original hidden replies, agent
retries, new model trials, or replacement v1 evidence. Static source inspection
is also retained but is not promoted to another headline score.

The resampling procedure is the original category-stratified paired task/cluster
bootstrap, with 20,000 resamples and seed `20261008`. Repetitions are not
independent tasks. Applying that procedure after selecting task corrections
does not restore preregistered inference. The numerical gain is below the
registered 10-point threshold and the interval includes zero; no superiority
claim is supported. The exclusion sensitivity is itself post hoc.

## Kernel and resource implications

U/M/G decisions are unchanged. Against diagnostic-supported labels, U accepts
432 outputs including the one adjudicated invalid output. M and G each accept
378, including that same invalid output, and do not accept 54 adjudicated
valid blocker reports. G's nine abstentions overlap non-acceptance. With only
one adjudicated invalid output, these error counts cannot establish robust
false-acceptance performance. The [report](report.json) also retains cross-tabs
for original labels and unresolved-case sensitivities.

Policy acceptance of a patch and successful reporting of a specified blocker
are different outcomes. This adapter did not model that distinction adequately.
Its post-stop policy decisions cannot explain or improve earlier agent behavior.
The original 417 complete/16 partial accounting records and the separate
incomplete transfer study are unchanged. No efficiency or dollar-cost claim
follows from this audit; diagnostic/engineering work is outside trial usage.

## Reproduce and inspect

From a checkout containing both the original and audit packages, with
**CPython 3.13.12**:

```sh
python3.13 -I -B results/skill-workflows-v1/semantic-audit-2026-10-10/reproduce.py --source .
```

This standard-library replay verifies original input identities, adjudication
identities, the new diagnostic evidence, every row amendment, all four report
scenarios and the full audit file manifest. It makes no model/network calls,
starts no Docker containers and executes no candidate or original grader.
It verifies retained evidence; it does not independently authenticate its
producer or rerun the historical execution. Optional diagnostic source is
retained for inspection and is never invoked by this replay command.

[Independent arithmetic](reviews/independent-arithmetic.json) checks the 38
changed labels and the single-task contrast separately from the report code.
The [analysis review](reviews/analysis-review.md) records separate maintainer-agent
review and negative controls. [Input registration](audit-inputs.json),
[generated report](report.json), [row ledger](row-ledger.json), and
[checksums](CHECKSUMS.json) make the analysis reviewable. Hashes identify bytes,
not authenticated authors. Exact-head CI checks this audit separately from v1.

## What to implement next

The [v2 implementation plan](V2_PLAN.md) prioritizes four bounded work packages:

1. Correct semantic grading and collect all case results; use these exposed
   tasks as development regression controls, never fresh held-out evidence.
2. Add typed execution/evidence/outcome records and explicit contract-dispute
   handling to the portable skill and a separate optional host adapter.
3. Repair JSONL framing, child lifecycle and timeout capture in a new harness
   version before another live campaign.
4. Evaluate individual mechanisms on independently reviewed, newly authored
   tasks with enough difficulty to distinguish workflows.

The audit supports improving measurement and evidence handling. It does not
show that longer prompts, extra agents, relaxed gates or a new kernel policy
would improve performance. The portable v1 skill and stable kernel API were
not changed by this audit; v2 remains proposed work.
