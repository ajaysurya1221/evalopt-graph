# Eval-opt v2 prospective workflow study

This protocol tests a fresh instructional mechanism after the v1 semantic audit
found a near-saturated authored suite. It preserves v1 artifacts and makes no
claim that v2 is an upgrade before evaluation. This is a maintainer-run study
with separate authoring, implementation and review roles, not independent human
task authorship or independent replication. No external transfer is included in
this iteration.

## Treatment and common access

| Arm | Instructions |
|---|---|
| A | Task instructions and common tools, without either workflow bundle. |
| B | Complete Matt Pocock bundle at `b0618bc436ad893b3c5e84e55fba86586d34a404`, explicitly invoking the appropriate upstream entrypoint and making its dependencies available. |
| C | Portable `eval-opt-v2`, version `2.0.0`, including its conditional typed-evidence/dispute procedure. |
| D | Mechanically derived C with only that named routing instruction and its procedure-only reference removed. |

All arms receive identical task facts, typed controller observations, response
contract, permissions, tools, native subagent availability and runtime limits.
C and D use the same `$eval-opt-v2` invocation, metadata and common schema
reference. The ablation manifest must prove exact byte equality for every other
file and an exact permitted deletion in `SKILL.md`; no ablation label or extra
instruction enters D's context. This comparison estimates the effect of the
instructional procedure, not the effect of access to typed observations.

The common prompt publishes the final-response transport bounds: 262,144 UTF-8
bytes, 640 nested containers, 16,384 JSON nodes including object keys, and the
task's finding-count limit. Capture retains the raw response hash when an
oversized or malformed response cannot be decoded into the evidence envelope.
These limits and the response schema are identical across all four arms.

The procedure distinguishes execution, evidence availability and the requested
outcome; when these conflict, it requests a bounded contract-based witness and
an explicit dispute rather than changing a frozen check. The common response
schema permits the same actions in every arm. Scoring rewards achieved outcomes
and supported findings, never workflow vocabulary or agreement with a check.

## Allocation and sequence

| Stage | Allocation | Agent trials |
|---|---|---:|
| Development | 12 fresh tasks × 4 arms × 1 attempt | 48 |
| Optional development revision | One complete rerun of the 12-task development stage after documented repairs | 48 maximum |
| Held-out comparison | 24 fresh tasks × 4 arms × 3 attempts | 288 |

The initial total is 336 trials, or 384 if the single development revision is
needed. Infrastructure retries are separate, retained and reported. At 600
seconds per agent trial these are 56 or 64 agent-hours before setup, verification,
retries and subscription pauses. Run one trial at a time for reliability; this
deliverable does not promise parallel wall time. The first reviewable milestone
is the portable skill, ablation, protocol, offline controls and CI, before any
live evaluation.

Each split covers `ordinary-bug-repair`, `bounded-implementation`,
`committed-patch-review`, `mixed-workspace-review`, `constraint-preservation`, and
`unavailable-or-misleading-evidence`: two development and four held-out problems
per category. Exactly 12 held-out tasks offer a predeclared evidence/dispute
opportunity; 12 are ordinary controls. Problems must have distinct logic and
source identities, not parameter substitutions. The five audited v1 families
may inform development regression controls but cannot become held-out tasks.

Every requirement tested by an oracle is stated in the visible contract. Include
clean review controls, solvable constraint cases and blocker tasks where a
specified blocker report is the correct outcome. A refusal fails a solvable task.
Each task needs a correct oracle, relevant incorrect controls, boundary controls
and a separately reviewed deterministic grader. Review witnesses compare the
same input against baseline, candidate and the declared finite-domain oracle;
extra unsupported findings fail. A dispute with a correct check is a negative
control, not a privileged path to success.

Before live development, pass task/oracle/mutant controls, exact ablation checks,
controller custody, replay, interrupted-capture, parser framing, child ownership,
missing telemetry and immutable recovery controls. Review skill/dependency
exposure in a clean configuration. The development gate requires all 48 outcomes
resolved, all offline controls passed, and B completing 4–10 of the 12 tasks,
with both a success and a failure among ordinary repair/implementation tasks.
This checks difficulty headroom; it establishes neither statistical power nor
representativeness. If the gate fails, permit one documented development revision
and full 48-trial rerun. Preserve the first run. A second failure ends this study
as `development_not_ready`, without consuming the held-out suite.

Freeze held-out task, grader, skill C/D, upstream, analysis, controller, parser,
continuation policy, image and schedule identities after development. The seed is
`20261008`: randomize task/repetition blocks and arm order within each matched
block. Authors and reviewers do not tune held-out tasks using candidate scores.
Operational health may be inspected during execution; do not peek at comparative
performance to change tasks, stop early or revise the candidate.

## Runtime, custody and continuation

Use CPython 3.13.12, Harbor 0.24.0, Codex CLI 0.154.0, `gpt-6-astra`, reasoning
effort `ultra`, and existing ChatGPT subscription authentication. Verify versions,
returned model identity, image digests and authentication in preflight. No silent
model substitution, API billing fallback, purchased credits or global skill
installation is allowed. Use fresh containers/configuration without personal
memory, unrelated skills or previous trajectories for each attempt.

The registered resource limits are one CPU, 2 GiB memory, 600 seconds including
children, 120 verifier seconds, five seconds per verifier case, one parent and at
most two concurrent native children with delegation depth one. Controller-owned
capture and separate grading occur after a confirmed execution cutoff. Candidate
code and agent-written success files cannot authenticate observations. Hidden
grades cannot enter workflow instructions or post-stop acceptance inputs.

Telemetry framing uses literal LF boundaries; count owned responses and tool
calls across parent and children without copied-history double counting. Publish
complete counters, partial observed lower bounds, unavailable counters, provenance
and historical delegation status separately. Null is unknown, not zero. Partial
usage never establishes efficiency, known cap compliance or task success.

Prospectively allow continuation after complete capture and confirmed execution
termination when model/workflow identity is correct, usage provenance is valid,
and usage is complete or partial. Historical delegation may remain unverified
because an end event is absent after a proven cutoff; retain that uncertainty.
Observed delegation violations, invalid provenance, unconfirmed termination,
incomplete capture, quota exhaustion or contradictory identity stop admission.
The missing historical event is never synthesized from a later absence check.
Lifecycle uncertainty affects outcome grading independently of accounting.

The controller writes immutable start, closure and retained-evidence records.
Resume only the same recorded schedule and verified artifacts. Recovery may
complete a previously recorded closure intent; it may not invent a historical
cutoff or grade. Permit at most one clean retry of an explicitly classified
infrastructure failure, preserving all attempt evidence and consumption. Agent
mistakes, timeouts, budget exhaustion and partial telemetry are not retry reasons.
Pause on subscription exhaustion. No post-freeze failure waiver is automatic.

The initial retryable class is a controller-observed Docker inspection transport
failure before any container creation or agent dispatch. Its retained visible
bundle must contain no identified candidate or executed check, and its verifier
must be unrun. Contradictory execution evidence, a created runtime directory,
timeouts and all other failures cannot receive this retry. A fresh quota
permission may resume a recorded subscription-only pause; it never waives a
second stopping reason or reruns a finished task.

Before each admission, require at least 2 GiB of free controller storage and no
running container bearing the v2 ownership label. Preserve original stopped
archives. Unsupported filesystem nodes or owner-unreadable modes are not
materialized on the host; missing required snapshots stop admission. Executable
frozen source must contain no bytecode caches, and policy imports must resolve
to the frozen preserved kernel. These are controller conditions common to all
arms, not additional candidate instructions.

## Outcomes, missingness and claims

The primary metric is valid completion: requested outcome achieved, boundaries
preserved and claims supported. Report functional success, unsupported-success
claims, incorrect refusals, boundary violations and all-three-attempt consistency
separately, along with resource coverage and known consumption from every attempt.

`contract_dispute` means an unresolved measurement-contract defect requiring
study-level adjudication, not an agent's supported disagreement with a deliberately
faulty visible check. Such a designed task remains gradable against its frozen
oracle. An unresolved measurement-contract defect makes the entire matched task
unknown across all arms; keep the evidence and publish sensitivity analyses
without silently repairing confirmatory scores.

Average repetitions within tasks. Use paired task-level resampling stratified by
the six categories, with 20,000 resamples and seed `20261008`. Shared-source
variants, if any, form one cluster; repeated attempts are not additional
independent tasks. The sole primary contrast is C minus D. A scoped mechanism
benefit requires an observed gain of at least five percentage points and a paired
two-sided 95% interval entirely above zero. It also requires the ordinary
repair/implementation functional-success noninferiority guard: its one-sided
95% lower bound must exceed −5 percentage points.

Only if the primary gate passes may the gatekept C-minus-B comparison support a
scoped workflow-improvement claim: observed gain at least ten percentage points,
paired two-sided 95% interval entirely above zero, and the same ordinary
functional-success guard. These thresholds concern observed effects; they do not
prove the true gain exceeds five or ten points. A provides descriptive context.
All inference gates require nondegenerate evidence. Saturation, degenerate
intervals or insufficient evidence are inconclusive, not equivalence or proof of
noninferiority. This includes a saturated ordinary-control guard or a constant
maximal observed benefit. Any missing C/comparator outcome blocks the observed
contrast in this implementation, even if a sensitivity bound alone would pass;
this is stricter than using the unfavorable bound by itself. This small staged
allocation carries no proof-of-power claim.

Publish every scheduled row, missingness reason, per-arm/category coverage and
full-denominator conservative bounds. Every positive claim must survive the
unfavorable missing assignment: missing C outcomes fail and missing comparator
outcomes succeed. Do not treat unknown as observed failure, assume missing at
random, or silently use complete cases. Explain finite-task and maintainer-suite
limits even when a numerical gate passes. No efficiency or general superiority
claim follows from partial counters or this authored suite.

Any U/M/G post-stop kernel comparison is secondary, with frozen visible evidence
and unchanged stopped outputs. Report incorrect acceptance, acceptance coverage,
false rejection, abstention and artifact failures together. It evaluates decisions
on supplied evidence and cannot establish that a kernel changed prior agent
behavior. Keep kernel APIs and v1 serialization/results unchanged.

## Publication acceptance

Retain protocol and identities, attribution, all scheduled outcomes and attempts,
sanitized controller evidence, complete task/control assets after evaluation,
ablation manifest, deterministic analysis and offline reproduction commands.
Report positive, neutral or negative results using the registered gates. Separate
authored controls, live workflow evidence and independent replication. Public
receipts name public experimental model/version conditions but exclude
credentials, personal paths and internal contributor identities. Consumption is
tokens, calls and time, never invented dollar costs. All live execution is a later
stage behind these gates; successful offline controls do not claim agent trials.
