REVIEW 07A — Reviewer Fable high | Verdict ACCEPT

Fresh, independent, read-only review of Task 07A (Actseal README-only independence clarification). Target: worktree `/Users/ajay/Developer/.evalopt-worktrees/wt-portfolio-07a`, branch `winddown/20261013/07A`, exact HEAD `52dbc14554486e8ff9e31455d550bfc3d43f139e` whose sole parent is the base `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b`. Working tree clean before and after every command; HEAD unchanged at exit. No target edits, no Git mutation, no model or subagent calls, no network, no credentials or `.env`, no global changes. Only this file was written. The implementer REPORT (`reports/07A.md`) was read as a claim; the prior Codex review was not read and this verdict does not rely on it. Model: `claude-fable-5-1`, requested effort high.

## What was inspected

- Central `PLAN.md` Section C (lanes, frozen Portfolio contract 4, review protocol) and Section D Task 07A; `tasks/07A.md`, `tasks/07A-implementation.md`, `tasks/07A-review.md`; `reports/07A.md`; preflight `reports/07-portfolio-preflight.md`; audit `audits/portfolio-independence.md`; accepted wording in the control worktree `docs/decisions/winddown-positioning.md`, `docs/migration.md`, `docs/portfolio.md`.
- Target repository contracts: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, `NOTICE`, `pyproject.toml`, `.pre-commit-config.yaml`, `docs/decisions/0002-minimal-attributed-reuse.md`, `tests/docs/test_readme.py` (guard at lines 636–645 and the absolute-link test at 690–702).
- `git diff --stat 111afb3..52dbc14`: `README.md` only, 1 insertion, 1 deletion (line 181, the single Related projects paragraph). Commit message and `Co-Authored-By` trailer present; author is the repository owner.

## Independence wording versus package and source evidence

- `[project].dependencies = []`; the `laya` extra and `assets`/`dev` groups name no sibling project; `tool.uv.sources` names only `torch`. `uv.lock` has no `evalopt`, `dorian`, `frontier` or `arci` entry (grep over `*.toml`/`*.lock`: 0 hits beyond prose).
- Every `import`/`from` in `src/` resolves to the standard library or `actseal`; no runtime import of any sibling package. Editable install in the task `.venv` points at this worktree (`direct_url.json` → `file:///…/wt-portfolio-07a`, `pyvenv.cfg` created by uv 0.11.29, CPython 3.12). So "no dependency on, import of or shared runtime with any project named here" is supported by the manifest, lock, source and environment.
- Adapted-source attribution is untouched: `NOTICE` (last changed at `96ec16a`), `src/actseal/stats.py:5–10` and `tests/unit/test_stats.py` still record the ARCI Clopper-Pearson port at its pinned commit; `NOTICE` still states that canonical hashing and self-sealing evidence are informed by the public evalopt-graph design with no evalopt-graph source included. The new README clause "whose public design informed Actseal's canonical hashing and self-sealing evidence as the NOTICE records" restates NOTICE accurately and links it with the repository's required absolute same-repo URL form.
- STOP wording: "whose standalone feature development has ended" is the exact accepted phrase from `winddown-positioning.md` and `docs/migration.md`. The paragraph does not say archived, published, final release, adoption, superiority, security, label truth or execution safety. "Action-policy qualification" matches the accepted migration-map job name (`docs/migration.md:40`, `docs/portfolio.md:16`).
- Guard structure preserved: one paragraph, exactly three sentence-ending full stops, exact `COMPARISON` string, ending `against supplied evidence.`, all four `(<url>)` targets. Opening, examples, images, guarantee/limit bullets and disclosure untouched (verified by the passing guard suite, not by claim).

## Commands run (pinned uv first on PATH: `/Users/ajay/Developer/.evalopt-worktrees/wt-control-00/plan/artifacts/tooling/bin/uv`, reporting `uv 0.11.29 (901092ee1 2026-07-15 aarch64-apple-darwin)`; run from the task worktree)

| Command | Result |
|---|---|
| `git diff --check 111afb3cf0dbab94e7bdf7917e800ba6faaeac0b 52dbc14554486e8ff9e31455d550bfc3d43f139e` | exit 0, no output |
| `uv run --frozen pytest -p no:cacheprovider -q tests/docs/test_readme.py` | 27 passed in 0.38s, exit 0 |
| `uv run --frozen ruff check .` | "All checks passed!", exit 0 |
| `uv run --frozen ruff format --check .` | "481 files already formatted", exit 0 |
| `uv run --frozen mypy --strict src tests` | "Success: no issues found in 106 source files", exit 0 |
| `uv run --frozen pytest -p no:cacheprovider -q -rs -m "not integration and not packaging"` | 4216 passed, 1 skipped, 31 deselected in 90.00s, exit 0; skip is `tests/release/test_agg_probe.py:224: this worktree carries the approved Linux agg pin` |

`-p no:cacheprovider` was added only to avoid writing a cache into the implementer's worktree; it does not change selection. Counts match the implementer's second run exactly. Hosted CI was not run and is not claimed.

## Findings by severity

High: none. Medium: none.

Low:
1. `README.md:181` "no … import of … any project named here" is accurate in the Python sense (no runtime import) but a lay reader could take "import" as "nothing taken from", while `stats.py` does port ARCI units under NOTICE. Not a false statement and not required to change; optional tightening to "no runtime import of" if the paragraph is reopened.
2. Link text "Evalopt Graph" is the pre-existing README name; the accepted portfolio page uses the prose name "evalopt (`evalopt-graph`)". The guard checks only the URL, and the positioning ADR forbids renaming projects, so leaving the existing name is correct; noted for consistency only.
3. The third sentence carries two nested relative clauses before its main verb. It is grammatical and the three-sentence guard constrains alternatives; readability only.

Informational:
- The commit used `-c core.hooksPath=/dev/null`. `.pre-commit-config.yaml` defines only `types_or: [python, pyi]` ruff/mypy hooks, so no hook would have fired for a README-only commit; the same checks were rerun here and pass. Nothing was bypassed.
- The implementer's first run reported 4210 passed / 2 skipped versus 4216 / 1 in the second and in this review. The second run and this review ran alone; the first ran concurrently with ruff and mypy. Not caused by the README change; root may glance if hosted CI differs.

## Required changes

None.

## Follow-ups

- Root: push the branch and open the PR from the exact reviewed commit `52dbc14`; require green hosted CI on that commit before squash merge; no `--admin`, no branch deletion.
- Optional, not blocking: consider "no runtime import of" wording in a later README pass (Low 1).
- Independent Codex review remains a separate gate; this record does not stand in for it.

## Limits and spend

Scope limit: local checks only; rendered GitHub/PyPI output and hosted CI not observed. Turns used: 10 of 20. Wall clock: within the 20-minute cap by local observation; exact elapsed time and token counts are not asserted and are left to native receipts collected after exit.
