# Fresh v2 development tasks

These twelve development problems were authored before any v2 agent scores. They
are fixtures from a maintainer-run study with separate AI authoring and review
roles, not independently human-authored benchmark evidence. They exercise CSV grammar, weighted routes,
apportionment, versioned state, percent-decoding, bit selection, literal template
bindings, padded pairing, bounded expansion, exact rational accumulation, a known
faulty visible check, and genuinely missing execution-order evidence. They do not
reuse the five audited v1 problems.

`catalog.json` contains metadata only. Each `development/<id>/task.json` is a
controller-side grader contract; its `instruction` is the visible task. Only
`agent/` belongs in the initial agent workspace. `oracle/`, `controls.json`, cases,
and `oracle_cases.json` are verifier/QA assets and must remain outside the agent
container build context. The runtime replaces `attempt_id` with the actual
immutable attempt identity. The same response contract is included in every
visible instruction and supplied unchanged to all four arms.

Reviews have a complete `baseline/` tree. Their finite witness domain is explicit
in the visible instructions; `oracle_cases.json` maps exactly those data requests
to expected behavior. A candidate's witness is executed separately against the
baseline and candidate, never accepted from its prose or success file. The two
mixed-workspace tasks additionally supply complete `committed/` and `index/`
trees: `workspace_layers` maps baseline, committed, index and workspace to these
directories. A materializer must create actual Git layers matching these trees,
including untracked helper modules, rather than treating the task as one commit.
The two other reviews compare one committed candidate against the baseline.

The schema's `allowed_changes` is an exact list of editable existing regular
files. Every other node and every mode is frozen, and adding/removing files or
directories is forbidden. Review and blocker tasks allow no workspace changes.
New temporary probes must therefore run without creating workspace files.
Task cases require preserved call arguments. Domain statements are normative;
case lists are finite tests, not permission to violate other stated inputs.

Run offline authored controls from the repository root:

```sh
.venv/bin/python -I -B bench/harbor/skill-workflows-v2/tasks/qa.py
.venv/bin/python -I -B bench/harbor/skill-workflows-v2/tests/test_tasks.py
```

These commands execute only the repository-authored fixtures in disposable fresh
processes. They are not a security sandbox and must never receive live candidate
outputs. Each positive oracle and relevant wrong solution is executed. Review
baselines are checked against their full declared finite domains; clean candidate
reviews are also exercised against every domain input. Visible checks are run and
their exit codes retained in QA observations. Every task rejects a false command
claim, an incorrect response and a concrete forbidden-file addition. Expected
failed visible checks do not make correct contract outcomes fail. No agent or
model trial, Docker run, subscription charge or held-out readiness is claimed.

No held-out task assets are published here at this development milestone. The
24 distinct held-out problems must be authored and reviewed separately, with
identities frozen before evaluation and their full assets released afterward.
