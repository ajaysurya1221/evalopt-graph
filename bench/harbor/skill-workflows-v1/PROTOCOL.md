# Eval-opt workflow and acceptance study

Protocol ID: `evalopt-skill-workflows-v1`. **Prospective; no comparative result yet.**
This is a maintainer-run study with separated task authoring, grading and review
roles. It does not satisfy the independently authored external-validation protocol
in [`docs/BENCHMARK_PROTOCOL.md`](../../../../docs/BENCHMARK_PROTOCOL.md).

## Treatments and estimands

A uses task instructions and common tools. B explicitly invokes `diagnosing-bugs`,
`implement`, or `code-review` from the complete upstream bundle at
`b0618bc436ad893b3c5e84e55fba86586d34a404`. C invokes the portable `skills/eval-opt`
bundle at its frozen content hash. All upstream dependencies remain available.
If this Codex host has no Skill tool, all arms get the same compatibility note:
invoking a named skill means reading its SKILL.md and relevant references. A has
no extra skill bundle. Task facts, local Markdown tracker, scope, test seams,
permissions, tools, model and effort are identical. Setup is completed before
measurement. No remote issues or messages are created by tasks.

The primary metric is valid completion: specified outcome achieved, boundaries
preserved, and completion claims supported. A blocker is correct only when the
task explicitly requests reporting an unavailable prerequisite; refusing solvable
work fails. Publish functional success, unsupported success, incorrect refusal,
boundary violations, all-three-attempt consistency and measured resource use.
Reviews include clean controls and score defect outcomes rather than prose style.
The common structured response contract is visible to every arm.

## Allocation and isolation

| Stage | Independent problems | Arms | Repetitions | Trials |
| --- | ---: | --- | ---: | ---: |
| Development | 12 | A/B/C | 1 | 36 |
| Held-out | 48 | A/B/C | 3 | 432 |
| Transfer | 12 | B/C | 3 | 72 |

Held-out categories each contain eight independently authored problems: ordinary
bug repair, bounded implementation, committed-patch review, mixed-workspace review,
constraint preservation, unavailable or misleading evidence. Shared-source
variants share a cluster ID and are not counted as independent problems. The
development set and its controls are public and never count as held-out results.

Harbor 0.24.0 runs Codex CLI 0.154.0 with `gpt-6-astra`, `ultra`, and existing
ChatGPT subscription authentication. Returned identity must match. No API fallback,
credit purchase, silent model substitution or hidden reduction of subagents.
Fresh containers/configurations exclude personal memory, unrelated skills and
earlier trajectories. One parent may use two simultaneous children at depth one.
Measure parent and child usage without adding already aggregated parent totals.
Unaccounted children or unverified dependency loading block campaign readiness.
The host controller and offline report reproduction use CPython 3.13.12. The
source-frozen controller rejects other interpreter versions before registration,
dispatch and reporting; container task interpreters remain separately image-pinned.

Authored trials have a 600-second shared parent/child wall-clock limit; at most two
trials run concurrently. Tokens are measured, not matched. Task-necessary network
access is the same across arms. Verifiers have no provider credentials or network.
Agent-controlled code executes only in disposable environments, never on the host.
Task/verifier sources and solutions are excluded from agent build contexts.

One fresh attempt is allowed only for classified infrastructure failure. Preserve
the original attempt and failure classification. Agent mistakes, task timeouts and
budget exhaustion are outcomes. Interrupted or ambiguous attempts require explicit
classification; resume never overwrites them. Quota exhaustion pauses scheduling.

## Freeze and grading

Pilot repairs use development evidence only. Before held-out runs freeze task,
grader, skill, policy, analysis, runtime, image and dependency identities, the
schedule and this protocol. Seed `20261008` randomizes arms within matched
task/repetition blocks. Publish or escrow the immutable registration hash before
outcomes are revealed. A changed frozen input creates a new study version.

Controller-owned collection freezes stopped files and declared visible check
outputs first. Agent-written reports are candidate data and cannot authenticate
checks. Content hashes detect changed bytes; hashes alone do not authenticate
their origin. The controller's isolation and retained execution evidence are the
trust boundary. A new separate verifier evaluates the stopped snapshot. Collection
fails closed for missing files, unsafe paths, duplicates or inconsistent identities.

Before hidden grading, apply U (accept all), M (independently written visible-check
policy) and G (frozen evalopt kernel) to each of the same 432 held-out outputs.
Only preregistered visible observations enter policy inputs. Freeze policy outputs
before releasing hidden grades. This is a stopped-output decision comparison,
not evidence that a kernel would alter agent behavior. Report incorrect acceptance,
approval coverage, false rejection, abstention, artifact failures and replay fidelity
together. M is reviewed independently and is not weakened to produce a G victory.

## Statistical decision rules

The sole primary contrast is C minus B. Average the three repetitions within each
task, then resample paired task clusters within category, using 20,000 bootstrap
resamples and seed `20261008`. Use percentile intervals; repeated attempts are not
independent sample units. Preserve each sampled cluster's tasks together. Estimate
each category's task mean and average the six category means equally.

A scoped positive headline requires an observed gain of at least 0.10 and a paired
two-sided 95% interval whose lower endpoint exceeds zero. This does not establish
a true gain of at least 0.10. An overall upgrade also requires a one-sided 95%
noninferiority lower bound above -0.05 for functional completion on ordinary bug
repair and bounded implementation. Freeze this guardrail definition before scores.
Degenerate intervals, insufficient clusters or incomplete evidence are inconclusive.
Report sample size and uncertainty; the study is not promised to detect small gains.

Report every scheduled trial. Agent failures count as failures. Missing infrastructure
outcomes are shown explicitly and sensitivity assigns missing C to failure and
missing B to success. Superiority must survive this unfavorable assignment and its
interval. Other contrasts/categories/kernel summaries are secondary and descriptive.
Do not select a favorable repetition or use best-of-k as the main metric.

## External transfer

Terminal-Bench 2.0 is pinned to `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`.
Filter software-engineering/debugging, CPU <=1, memory 2 GB, no GPU,
agent/verifier <=1800 seconds; exclude ocr, images, no-verified-solution tags.
Select the lexicographic first twelve before scores. Preserve original task and
verifier semantics, network dependencies and time limits. Resolve prebuilt image
tags to digests before freeze. A failed preflight does not justify score-aware
substitution. Related tasks are not described as independent families.

This is a feasibility subset, not an official leaderboard score. Its verifier
boundary is the original upstream boundary, distinct from the authored suite's
separate hidden verifier. Publish transfer outcomes separately.

## Publication

Publish wins, ties and losses in the existing evalopt-graph repository. Retain
sanitized per-trial records, checksums, source pins, failure classifications,
replay inputs and offline report commands. Credentials and internal contributor
identifiers are excluded; experimental model/version identifiers are retained.
Report tokens, calls and time; no invented subscription dollar cost. If redaction
prevents evidence review, mark the affected trial unavailable rather than dropping it.

The stable kernel's ten exports, serialization, dependencies and characterization
tests remain unchanged. This adapter does not revive the deprecated runner.
No overall superiority, independent replication or production-safety claim follows
from implementation tests, the development pilot, or unsigned artifact manifests.

Research: [SkillsBench](https://arxiv.org/html/2602.12670v1),
[Harbor separate verifiers](https://docs.harborframework.com/tasks/separate-verifier),
[paired bootstrap](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.bootstrap.html),
[coding-evaluation audit](https://openai.com/index/separating-signal-from-noise-coding-evaluations/).
