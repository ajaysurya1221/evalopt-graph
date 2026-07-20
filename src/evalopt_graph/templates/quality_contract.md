# Quality Contract

> The explicit, project-local agreement the Evaluator-Optimizer loop is held to.
> Edit this by hand to add/lock acceptance criteria; the loop will respect it.

- **Task:** <user task>
- **Created:** <timestamp> | **Last updated:** <timestamp>

## Acceptance criteria
<!-- Concrete, checkable. The loop cannot declare PASS until these are satisfied with evidence. -->
- [ ] <criterion 1>
- [ ] <criterion 2>

## Detected project
- Type: <type> | Package manager: <pm>
- Test: `<cmd>` | Lint: `<cmd>` | Typecheck: `<cmd>` | Build: `<cmd>`
- Runtime / manual checks: <steps or "none">
- Has tests: <yes/no/partial>

## Quality gates (required)
- relevant unit/integration tests pass
- lint passes (if configured)
- typecheck passes (if configured)
- build passes (if configured)
- **no tests weakened, deleted, skipped, or rewritten merely to pass**
- no broad unrelated refactors unless required
- no hardcoded/faked success
- no secrets introduced (use `.env.example` only)
- no new obvious security risk
- acceptance criteria satisfied
- evaluator rubric score >= 0.90 (when an LLM rubric is used)

## Evaluator rubric (weights)
- Correctness vs acceptance criteria — 0.40
- Tests genuinely pass & not weakened — 0.25  (any gaming caps the score at 0.50)
- Lint / typecheck / build — 0.15
- Safety / no new risk — 0.10
- Scope discipline — 0.10

## Run state (updated by the loop)
- Current iteration: <n> / <max_iters>
- Failing checks: <list>
- Files changed: <list>
- Stop reason: <reason or "in progress">

## Stop conditions
- All required gates pass → **DONE (PASS / PASS_WITH_WARNINGS)**
- Same failure repeats ≥ 3× → **stuck → human gate**
- Risky/destructive action needed → **human gate**
- `max_iters` reached → **DONE_WITH_BLOCKERS (FAILED_MAX_ITERS)**
