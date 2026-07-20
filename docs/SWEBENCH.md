# SWE-bench capability boundary

SWE-bench measures coding capability. It does not, by itself, measure whether evalopt governance adds
value. Any external evalopt campaign must report official task success separately from policy
acceptance.

The repository intentionally contains no local SWE-bench loader, repository preparer, or grader. Those
surfaces can diverge from the official evaluator and create results that look comparable when they are
not.

## Required responsibility split

- The host or evaluation harness owns the isolated agent trial, model metadata, trajectory, stopped
  workspace, and prediction patch.
- The agent, observation builder, and evalopt policy never receive hidden tests, `test_patch`, gold
  patches, grader source, or post-grade output.
- A trusted controller exports the immutable prediction only after the agent stops.
- A pinned official SWE-bench Docker evaluator grades that prediction.
- Compared governance policies use the same task, model, prompt, tools, budget, stopped output, and
  official grade.

## Campaign prerequisites

Before execution, freeze in the external campaign manifest:

1. the exact official SWE-bench release and evaluator image digests;
2. the dataset split, revision, instance list, and data digest;
3. the prediction schema and immutable stopped-patch digest;
4. host architecture, Docker configuration, worker count, timeouts, and failure policy; and
5. the full agent, policy, budget, schedule, and analysis identities required by
   [`BENCHMARK_PROTOCOL.md`](BENCHMARK_PROTOCOL.md).

Use the evaluator command documented by the pinned official release. Preserve its build logs, run logs,
result files, prediction file, dataset identity, image digests, host metadata, and exact command with the
campaign artifacts.

## Reporting rules

- Never describe a virtual-environment test, synthetic fixture, or Harbor reward as an official
  SWE-bench result.
- Account for checkout, image-build, timeout, infrastructure, and grader failures before inspecting
  outcomes.
- Report every preregistered trial, not only the best run.
- Keep resolve rate and policy acceptance as separate columns.
- A policy-accepted output that the official grader rejects is a false acceptance.
- An officially resolved output that policy rejects is a false-rejection candidate and requires blinded
  review.
- Do not compare results unless model, task, budget, harness, and failure handling are aligned.

No official SWE-bench execution is included in `v0.1.0`.
