# REPORT 07 portfolio preflight — Status DONE

Read-only preparation for README-only Tasks 07A–07D. This is not implementation review, test acceptance or hosted-state verification. Trusts the accepted Task 06 dependency audit; no dependency search or suite was repeated. No repository file was changed, no dependencies were installed, and no network, model subprocess, credential or `.env` read occurred. Only this report was written.

## Current local bases and environment prerequisites

All four primary working trees were clean when inspected. These are local main heads, not refreshed remote observations.

| Repository | Current local HEAD | Existing environment observation |
|---|---|---|
| Actseal | `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b` | Primary `.venv` has Python 3.12.13, pytest, Ruff and mypy; actseal 1.0.1 is editable to the primary `src/`. |
| Dorian | `eeb193792fac8a66b18f5222287a8fcf336dda08` | Primary `.venv` is absent. Existing presence worktree has Python 3.12.13, pytest and Ruff, but dorian-vwp 1.4.1 is editable to that older worktree. |
| Frontier Scout | `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c` | Primary `.venv` has Python 3.14.6, pytest, Ruff, mypy and CLI; the setuptools editable finder maps both `frontier_scout` and `outputs` to primary paths. No `uv.lock` exists. |
| ARCI | `a5adc834f74f5546fa3585b4ce6adfc96e2c37a3` | Primary `.venv` has Python 3.13.12, pytest, Ruff and basedpyright; editable source points at primary `src/`. Installed distribution metadata still says 0.6.0 while current `pyproject.toml:3` says 0.7.0. |

Dorian and ARCI advanced since the original planning snapshot. Root should branch from the freshly accepted base for each PR and retain its exact SHA.

**Before candidate tests:** root should provision an isolated environment for each task worktree using that repository's unchanged requirements. Do not symlink or copy a primary `.venv`: installed entry-point shebangs and editable `.pth`/finder mappings retain the old location. Do not combine repo import paths. Check each task environment's package origin and metadata before accepting tests as candidate evidence. Worktree tests may read their own README while accidentally importing primary code if this is ignored.

Available interpreter/tool roots are `/Users/ajay/Developer/actseal/.venv/bin`, `/Users/ajay/Developer/.dorian-worktrees/presence-2026-10-12/.venv/bin`, `/Users/ajay/Developer/frontier-scout/.venv/bin` and `/Users/ajay/Developer/agent-reliability-ci/.venv/bin`; they are inventory evidence, not approved candidate environments. The pinned run-local uv 0.11.29 is available for root-managed provisioning where permitted. Never update the primary environments or locks to prepare a README PR.

## 07A — Actseal

**Contracts:** `AGENTS.md` assigns product/documentation authorship to Fable high and acceptance/integration to Codex; read `plan/v1/STATE.md`, `plan/v1/CHANGE_LOG.md`, `plan/CONTRACTS.md` and `docs/stability.md` before edits. `CLAUDE.md` says use dedicated Read/Edit/Write tools and separate literal check commands. Its pointer to old `plan/STATE.md` is historical under the explicit AGENTS active-state rule; the current central Task 07A packet is the exact scope. No frozen interface changes are required.

**Hard README guard:** `tests/docs/test_readme.py:636–645` requires the entire Related projects section (`README.md:179–181`) to be one paragraph with exactly **three sentences**. Sentence counting uses a period followed by whitespace/end. The paragraph must end with `against supplied evidence.`, retain the exact ARCI comparison string at `:136–139`, and include all four exact repository URLs from `:187–191`. Integrate the STOP/independence wording inside these three sentences; do not append a fourth sentence or edit the guard. Opening, examples, images, guarantee/limit bullets and disclosure are also pinned; keep the change in the related-project paragraph.

**Prescribed checks, from the task worktree after local environment preparation:**

```bash
git diff --check
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen mypy --strict src tests
uv run --frozen pytest -m "not integration and not packaging"
```

The targeted README guard is included in that ordinary test set. `pyproject.toml:202–204` defines integration as live/external and packaging as build/install work; the authorized command deliberately excludes both. Do not weaken warning/strict marker settings or rewrite tests. Docs fixtures write ignored temporary output within the task checkout (`tests/docs/conftest.py:22–24`).

## 07B — Dorian

**Contracts:** no repository AGENTS.md or CLAUDE.md was found. `CONTRIBUTING.md` and `docs/VALIDATION_HONESTY.md` require scoped evidence wording, no broad validation claims, and separate trigger/selection evidence from checker-verdict evidence. Current source uses Python >=3.11 (`pyproject.toml:10`).

**README guards:** `tests/test_readme_example.py` runs the Try it recipe through subprocesses and checks its commands/commit identity; retain that recipe. `tests/test_docs_polish.py:36–73` restricts new “proof” uses and requires existing trigger-versus-truth caveats. Avoid introducing the word “proof” into the new portfolio paragraph. `tests/test_pypi_readme.py:42–105` validates the dynamic README substitution contract, a single transformed hero, version-pinned Dorian links and unchanged fenced code. Absolute cross-repository URLs in a new prose paragraph avoid relative-link ambiguity. The build plugin is pinned to hatch-fancy-pypi-readme 25.1.0 at `pyproject.toml:2`; do not alter it.

**Prescribed checks:**

```bash
git diff --check
make lint
make test
```

`Makefile:7–15` expands these to uv-run Ruff over src/tests/bench and the **full** pytest suite, including slow tests. `make test-fast` is not a substitute. Root may set `UV_FROZEN=1` in the process environment to keep the locked resolution fixed without modifying the Makefile. Full tests include subprocess and wheel-build cases; environment/build prerequisites must be available before dispatch. No suite was run here.

## 07C — Frontier Scout

**Contracts:** read `AGENTS.md`, `CLAUDE.md` and `CONTRIBUTING.md`. Preserve emit-only compiler/native-control boundaries, unsigned-observation status of receipts and research-preview scope. README-only work needs no policy, hook, lock or generated-config modification. The historical release instructions recommending admin merge/protection relaxation do **not** apply: the approved wind-down task permits only a README branch/PR, no cross-repo main merge or bypass.

**README guards:** `tests/test_figures.py:39–46` checks generated figures against their generator. No dedicated whole-README prose fixture was located in the inspected tests; this is not permission to alter examples or claims beyond the task. Preserve all existing figures and policy/signing examples. GitNexus is explicitly optional in AGENTS; no `gitnexus` executable or local `.claude/skills/gitnexus` directory was found. No symbol changes are planned. Do not install it for this task.

**Prescribed checks, with the task-local `.venv/bin` first on PATH:**

```bash
git diff --check
make lint
make type
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -m "not live" -q
```

`Makefile` uses bare Ruff/mypy/Python, so PATH is part of the evidence. `make type` executes the strict mypy configuration for `frontier_scout/agent_firewall` and `frontier_scout/exporters`. Preserve the no-live marker. Additional existing offline syntax/demo checks may be run if needed by the final review; do not run the network audit or opt-in decision model as an implicit README prerequisite.

## 07D — ARCI

**Contracts:** `AGENTS.md:3` requires reading `src/arci/interfaces.py`, `src/arci/schema.py` and `docs/STATISTICS.md`; they and every entry in `FROZEN.sha256` remain untouched. The current manifest has 48 entries; Task 06 already established its preservation. **Fable must run no state-changing Git command, no network and no uv.** Root owns branch/commit/PR creation and any prior environment preparation. The README is the sole edit surface; preserve NOTICE and adapted hashing attribution.

**README guards:** `tests/unit/docs/test_figures.py` verifies four generated SVGs and their generator; `tests/unit/planning/test_planning.py:203–260` defines/checks the operating-characteristic table reflected in the README. Preserve the table, statistical interpretation, figures and executable examples. A portfolio paragraph must not claim absolute reliability or a shared evalopt runtime.

**Prescribed worker checks, using the task worktree's actual environment binaries directly:**

```bash
git diff --check
shasum -a 256 -c FROZEN.sha256
.venv/bin/ruff format --check .
.venv/bin/ruff check .
.venv/bin/basedpyright
.venv/bin/pytest -p no:cacheprovider
```

These match `justfile:4–19` and the frozen pyproject's strict typing/test configuration. The current primary editable environment's stale 0.6.0 metadata is a preflight finding, not a reason to edit frozen metadata or accept tests against the wrong installation.

## Admission and remaining work

All four README scopes remain feasible without source, guard, dependency or frozen-file changes. The concrete prerequisites are isolated task environments, the current base SHAs, and task prompts carrying the existing wording guards. Each worker may write only README plus its expressly owned central REPORT; all tests, source, generated assets, local settings and historical plans remain outside edit scope. This report did not verify actual candidate imports, run tests, inspect hosted CI or approve any PR.

Read-only discovery limitations retained: no ARCI top-level `tests/conftest.py` exists; a Frontier shell glob for nonexistent test_docs/test_readme files produced a no-match error and was replaced by direct Python/rg file inspection. No failed lookup was treated as a passed guard or suite. No new billing/model usage was initiated; Codex analysis usage is not separately attributable.
