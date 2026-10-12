# Task07B partial diagnosis and independent root-lane validation

Status: original Fable execution remains **PARTIAL**; independent required local validation subsequently passed with one explicit optional-dependency skip. This report is not the missing executor REPORT, a commit, or a two-review acceptance of the candidate.

## Original retained outcome

Source worktree `wt-portfolio-07b` remains at `eeb193792fac8a66b18f5222287a8fcf336dda08`, with only an uncommitted README addition. Original receipts remain in ignored `plan/logs/07B-implementation/`:

- Started 2026-10-12T21:29:17.507706Z; finished 21:31:59.292696Z; measured elapsed 161.722 seconds.
- Native process exited 0 with subtype success and 27 native turns against requested CLI cap 25. Counter equivalence is not assumed.
- Native final text states: “The suite is still running in the background; its completion notification is the next signal I need, so nothing else to request yet.” This is not a test-completion receipt.
- Supervisor correctly classified PARTIAL with `missing_or_nonaccepted_report`; no timeout, no leftover process-group observation, termination confirmed. There is no Task07B commit or original `reports/07B.md` at this inspection.
- A fresh process snapshot before validation showed no pytest or make test process; the expired original native completion text does not establish that a suite remained active. No original test exit status, test count or lint result is invented here. Processes belonging to other lanes were not stopped.

## Contracts and isolation

Read `CONTRIBUTING.md`, `docs/VALIDATION_HONESTY.md`, Makefile, pyproject and the actual README diff. No project AGENTS.md or CLAUDE.md was present in this worktree inventory. The contract requires full `make lint` and `make test`, including slow tests; documentation guards and examples must remain unchanged for this README-only task. No source, test, dependency or documentation guard was edited.

Validation used the worktree's own `.venv/bin/python` (Python 3.12.13), importing `src/dorian/__init__.py` from this exact worktree; installed distribution `dorian-vwp` is 1.4.1. The pinned private uv binary is 0.11.29, first on PATH, followed by this worktree's `.venv/bin`; `UV_FROZEN=1` and `UV_PROJECT_ENVIRONMENT` names this worktree's `.venv`. Inherited PYTHONPATH/PYTHONHOME were removed from the child environment. No shared environment, global tooling or lock resolution was changed.

An initial read-only metadata diagnostic mistakenly queried `dorian-warrant` and raised PackageNotFoundError. It was corrected to the distribution name in pyproject, `dorian-vwp`; the corrected identity output is retained in `environment.log`. This diagnostic typo was not a required command failure and made no environment change.

## Fresh commands and actual results

All stdout/stderr and command/result receipts are retained separately under ignored `plan/artifacts/07B-root-validation/`.

| Command | Actual result | Measured interval / elapsed | Retained output |
|---|---|---|---|
| `make lint` | Exit 0; ruff check passed; 148 files already formatted | 21:38:08.871231–21:38:08.946042Z; 0.075 s | `lint.log` |
| `make test` | Exit 0; **1119 passed, 1 skipped**, no deselection; pytest reported 102.74 s | 21:38:08.946291–21:39:51.829500Z; 102.883 s | `test.log` |
| Pinned uv `run pytest tests/test_datachecks.py::test_parquet_suggestions_pass -q -rs` | Exit 0; one skip: duckdb is not installed, `tests/test_datachecks.py:280` | 21:40:09.346634–21:40:12.201697Z; 2.855 s | `skip-detail.log` |
| `git diff --check` | Exit 0 | Post-validation | `ending.json` |

All times above are 2026-10-12 UTC. The targeted skip check clarifies the full suite's single skip; it is not another full-suite pass. Optional parquet/duckdb behavior was not exercised, and no optional package was installed to hide that limitation. No required command timed out. Full commands were supervised with a 1800-second timeout and owned process groups; original process evidence is preserved separately.

Log SHA-256 values:

- lint: `6a2a55f7a063156a058afd02652a4f59d4a6752dfe65270bdb30c3700332b82f`
- full test: `af60d5c7cd6d105532d595e151fded7c7e0f5c95efea13243ce12de96b9c2832`
- skip detail: `2953b88539dc0ec76d05815d96e3de1dc2b6131cfcd57681da2ae821b56de146`

README SHA-256 before and after the validation sequence is unchanged: `7a62147b21927909b67a8f131696058d33967a7a72e77e0aea45941f5c830ca0`. Final Git status remains exactly ` M README.md`; HEAD is unchanged. No README edit or commit was made by this verifier.

## Candidate diff and next bounded action

The candidate adds one Related projects section after the maintainer text. Existing tested examples, earlier evidence qualifications, warrant/exit-code descriptions and all source/tests remain untouched. It states the independent code-claim-warrant role, no model calls during verification, zero runtime dependencies and no evalopt runtime layer; the latter matches the already accepted Task06 audit at this same Dorian head. The STOP notice does not claim evalopt is archived or released, and the paragraph disclaims successor/drop-in/conformance status. No new blocking scope or wording concern was found in this limited inspection. Existing checker-quality limitations in README and VALIDATION_HONESTY still govern determinism and truth claims; this is not a semantic correctness endorsement.

Fresh Fable completion must inspect the current unchanged diff, cite these results as **independent root-lane validation**, write its own REPORT and commit only the README on its assigned branch. It must not claim it finished or observed the original background suite. Independent Codex and fresh Fable diff reviews still follow; the original PARTIAL record is not overwritten. Any later README change invalidates this exact candidate hash and requires proportionate rechecking.

Only private validation logs/receipts and this report were written. No live model, network mutation, source change, global change, push, PR or merge was performed.
