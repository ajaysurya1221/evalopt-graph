# Prospective external validation protocol

**Protocol:** `evalopt-governance-external-v1`

**Status:** Prospective and unexecuted. This repository contains no result from this protocol.

The purpose of this protocol is to test whether evalopt reduces false acceptance relative to both no
policy and a credible minimal policy, without hiding capability, reliability, cost, or latency losses.
It is an evaluation design, not authorization to spend money or access sealed tasks.

## Research question

For independently authored tasks with hidden correctness grading, does evalopt reduce the rate at which
incorrect stopped outputs are accepted?

The primary outcome is false acceptance:

```text
policy_acceptance = 1 and hidden_task_success = 0
```

Policy acceptance and task success are always stored separately. Official task success is never used to
construct the policy input and is revealed only after the stopped output and all policy decisions are
immutable.

## Compared policies

Each task trial produces one stopped agent output. Three deterministic policy programs evaluate blinded
copies of the same controller-built visible observation in randomized order:

- **U — ungoverned:** accepts every stopped output and does not import evalopt.
- **M — minimal:** an independently implemented, reviewable policy that rejects obvious forged trust
  metadata and requires declared visible gates to pass. It does not import or copy evalopt code.
- **G — governed:** `evalopt-graph` evaluates the same visible observation under a frozen
  `GovernancePolicy`.

Only policy evaluation changes. The model, prompt, tools, budgets, stopped output, visible gates, and
hidden grader are identical across U/M/G. If M matches G with less complexity or better guardrails, the
study must report that result rather than weakening M.

The repository's `bench/harbor/conformance` task demonstrates this wiring with a deterministic public
oracle. It is not an evaluation task and must not appear in the external result set.

## Preregistration package

Before any evaluation outcome is visible, publish or escrow an immutable manifest containing:

- task-set identity, family labels, inclusion/exclusion rules, and an encrypted or access-controlled
  evaluation bundle digest;
- model and agent versions, complete prompts/configuration, tool and network policy, and sampling
  settings;
- U/M/G policy sources, the evalopt release artifact, observation builders, and their content hashes;
- environment, verifier, grader, and dependency image digests;
- task/trial counts, schedule seed, retry rules, budgets, and hard provider-side spending limits;
- metric definitions, aggregation code, statistical decision rules, and report templates; and
- named independent owners for task authorship, minimal-policy review, grading, and analysis.

Changing those fields after outcomes are visible creates a new protocol and requires a new registration.

## Tasks and independence

The primary set must be authored and sealed by people who did not implement G. It must include multiple
tasks in each declared governance family and vary repositories, operators, visible-test shapes, evidence
sources, and failure signatures—not only constants in repository-authored fixtures.

Relevant families may include false success, visible-test manipulation, weak-spec overfitting,
configuration suppression, unsupported critical claims, evidence/provenance mismatch, contradiction
handling, and missing required artifacts. Reports may claim only the families represented in the sealed
manifest.

Use a separate, established benchmark to measure underlying task capability. For coding tasks, follow
the [SWE-bench capability boundary](SWEBENCH.md). A coding resolve rate is a guardrail; by itself it does
not show that governance adds value.

## Isolation and information flow

Every trial requires a fresh agent environment and fresh host state. The agent cannot access:

- policy/verifier source, other policy decisions, or analysis output;
- hidden tests, grader implementation, gold outputs, or post-grade results;
- credentials beyond the exact provider route; or
- another trial's conversation, cache, workspace, or artifacts.

After the agent stops, a controller-owned observation builder reads only preregistered visible artifacts
and gate outputs. It emits the exact canonical policy/input records used by U/M/G. The policy verifier
has no network and cannot access the hidden grader. A separate sealed grader evaluates the immutable
stopped output afterward.

Timeout, budget exhaustion, environment failure, policy failure, missing artifact, and grader failure
are distinct recorded outcomes. None may be silently dropped after inspection.

## Metrics and analysis

Primary governance metric:

- family-macro false-acceptance rate among hidden-incorrect stopped outputs.

Required guardrails:

- hidden task success and false rejection;
- policy, environment, and artifact failure rates;
- decision replay fidelity and required-artifact completeness;
- model/tool calls, tokens, dollar cost, and end-to-end latency; and
- task-level safety outcomes declared by the independent task authors.

Aggregate task-first, then family-first, so repeated trials and large families do not dominate. Use
paired comparisons because U/M/G evaluate the same stopped output. The preregistered analysis must
publish confidence intervals and all missing-data sensitivity analyses.

A comparative claim requires the complete interval for `false_acceptance_G - false_acceptance_M` and
`false_acceptance_G - false_acceptance_U` to remain below zero, with every preregistered guardrail met.
Families without enough hidden-incorrect outputs are reported as underpowered rather than pooled into a
different estimand. No result may be promoted beyond the task families, models, and environments tested.

## Required artifacts

For every trial retain outside the source repository:

- resolved task, model, agent, environment, policy, verifier, grader, and schedule identities;
- exact instruction and visible observation-builder inputs;
- stopped output or patch, visible gates, and policy decisions for U/M/G;
- hidden grade produced after policy artifacts freeze;
- complete failure stage, timing, token/call, and cost accounting;
- canonical evalopt policy, input, decision, and replay result; and
- a manifest of artifact paths, byte sizes, hashes, and redaction state.

Never publish credentials or secret-bearing trajectories. If safe redaction prevents independent review,
mark the trial unavailable and account for it under the preregistered missing-data rule.

## Execution gates

Do not start a paid or sealed campaign until all of the following are true:

1. independent tasks and observation builders are sealed;
2. the minimal policy and analysis are independently reviewed;
3. immutable task/verifier/grader images pass public preflight controls;
4. the random schedule and registration package are frozen;
5. hard provider-side token and spending limits are demonstrated;
6. the artifact path is complete and replay-tested on public controls; and
7. the maintainer explicitly approves the final projected spend.

The current evidence remains the bounded conformance described in
[`BENCHMARK_RESULTS.md`](BENCHMARK_RESULTS.md) until this protocol is executed and independently reviewed.
