# Public development tasks

These 12 problems are **development controls**, not a sealed held-out set and not live benchmark results. They are authored for this maintainer-run study. Separate review improves task quality; it does not establish independent human authorship.

Each category has two different problems. The committed-review category includes a clean candidate, both constraint tasks are solvable without changing frozen files, and the two evidence tasks have specified blocked outcomes. A blocked response fails every other task.

## Files and the agent boundary

Each development directory contains `task.json`, `agent/`, `hidden_cases.json`, and `controls.json`. Implementation tasks also have `oracle/`; review tasks may have `candidate/` patches and Git-state operations. Only `suite.materialize_agent(task, destination)` output enters the agent image. The instruction is `suite.instruction(task)` and includes the same structured report contract for every arm.

The words “hidden cases” describe the execution boundary: these development cases are public in this repository but must not be mounted in a trial's agent or candidate execution environment. Their publication does not make them suitable held-out tasks.

Materialization creates a real repository with the fixed `benchmark-base` tag and deterministic commit timestamps. Mixed-workspace tasks preserve staged, unstaged, untracked, and deleted states. Candidate responses belong at the workspace root as `response.json`.

## Controller integration

1. Materialize an empty workspace; retain `file_manifest(workspace)` as its baseline. Keep its `.git` metadata when capturing the stopped workspace.
2. After the agent stops, freeze the workspace, response, and controller-observed visible check. Evaluate U/M/G before calling the hidden grader.
3. Call `evaluate_cases(task, invoke)`. The callback receives only `module`, `function`, and JSON `args`; expected outputs remain in the controller. Run each invocation in an isolated child environment containing only the stopped workspace and that request. Do not import candidate code into the controller, mount graders/oracles in the child, or expose controller output paths. A live callback must bound time/output and run without network or privileges. The returned object must contain exactly `result` and post-call `args`, or exactly `error` (exception class name, qualified with its module unless built-in) and post-call `args`. Missing or malformed output, including an early exit with code zero, fails.
4. Supply that boolean plus the retained manifests, parsed response, and actual controller observation to `grade_snapshot`. Only a unique observation for the exact visible command is accepted. `source: controller` is a caller-side assertion; this module does not authenticate arbitrary JSON and must never consume agent-provided observations.
5. Retain individual grade fields. A failed boundary or unsupported completion is not converted into success by a passing functional check. Review scoring uses defect location/symbol and generic behavior kinds; equivalent `./path`, module-qualified symbols, and data-loss/incorrect-result descriptions are normalized. It does not grade prose style or workflow vocabulary.

The live agent environment sets `PYTHONDONTWRITEBYTECODE=1` for every arm; checks use `-B`. No cache directory is exempt from boundary grading. File types, permission modes, all frozen files, and logical staging/commit state are included in boundary grading. Git index v2/v3 parsing is performed without executing candidate Git configuration. Stat-cache refreshes are ignored; staged object identity, modes, and index flags are preserved. Unsupported index formats fail closed. Non-index Git files are hashed. The `@git/` manifest namespace is reserved.

## Controls

Run from the repository root:

```sh
python -B -m pytest tests/test_skill_workflow_tasks.py -q
```

Controls execute only repository-authored fixtures locally. This test helper is **not** the live candidate runner. Every task has a successful oracle/response control and at least one relevant incorrect control. Additional checks cover forged and duplicate observations, missing hidden results, read-only source edits, frozen files, staging changes, removed Git objects, malformed responses, early process exit, grader isolation, and clean-review false positives.

Held-out designs, executable tasks, reference solutions and detailed controls remain
outside the public checkout until evaluation and publication. The held-out milestone
requires validated controls, separate review and an immutable freeze before any
candidate scores are observed. Public development tasks never count as held-out results.
