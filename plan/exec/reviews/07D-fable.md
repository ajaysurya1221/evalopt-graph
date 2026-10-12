REVIEW 07D — Reviewer Fable high | Verdict ACCEPT

Target: `/Users/ajay/Developer/.evalopt-worktrees/wt-portfolio-07d`, branch `winddown/20261013/07D`, HEAD `ba179f3a188710e38ec4557d2f65b66a8953c099` vs base `a5adc834f74f5546fa3585b4ce6adfc96e2c37a3` (ARCI main). Working tree clean at HEAD. Reviewer model: Fable high requested; observable ID `claude-fable-5-1`. Read-only review: no network, no `uv`, no mutating Git, no writes to the target, no model/subagent calls, no global changes. Only this file was written. The final Codex review (`07D-codex-final.md`) and the first Codex review (`07D-codex.md`) were NOT read; the first-round REVISE findings were known only through the revision brief and the author's REPORT 07D-r1.

## What was inspected

- Actual diff `a5adc83..ba179f3`: `README.md` only, +17/−0 (one blank line plus a 16-line `**Independence.**` paragraph inserted between the "**Related work:**" line and `## Roadmap`, README lines 352–367). `git diff --name-status` shows exactly `M README.md`. Two commits by root (`4e4862a` first candidate, `ba179f3` revision), author/committer `ajaysurya1221`; no source, test, lock, metadata, NOTICE or frozen file touched.
- Byte identity outside the block: `diff <(sed '352,368d' README.md) <(git show a5adc83:README.md)` → IDENTICAL. Pre-existing README text, hero/where figures, operating-characteristic table (lines 208–233), examples and the verdict table (lines 93–102) are unchanged.
- Frozen manifest: `shasum -a 256 -c FROZEN.sha256` → 48 × OK, 0 FAILED; README.md and NOTICE are not frozen entries. `NOTICE` is byte-identical to base (not in the diff).
- Task brief `exec/tasks/07D.md`, implementation prompt `07D-implementation.md`, revision brief `07D-revision-1.md`, author REPORTs `07D.md` and `07D-r1.md`, root records `07D-root-first-validation.md` and `artifacts/07D-root-final-validation/commands.json` + logs (read, not altered).
- Repo contracts: `AGENTS.md`, `docs/STATISTICS.md` (Rule, Experiment verdict, Discipline, `prior_runs`), `docs/TRUST_MODEL.md` ("What is trusted": manifest author), `src/arci/interfaces.py`/`schema.py`/`schedule.py` (`spec_sha256`, `record_sha256` sealing), `src/arci/hashing.py` docstring, `pyproject.toml`, `uv.lock`, the Task 06 audit `exec/audits/portfolio-independence.md` and the accepted wording in control `docs/decisions/winddown-positioning.md`, `docs/migration.md` (ARCI route row), `docs/portfolio.md` (ARCI row).

## Claim-by-claim check of the new paragraph against the repository

| README sentence (lines 352–367) | Evidence | Result |
|---|---|---|
| "preregistered stochastic regression testing … manifest is a prospective contract supplied by its author: it fixes the task, fault conditions, sample size and decision rule before the trials run" | STATISTICS "Frozen before execution (the manifest)": alpha, delta, n_per_arm, K conditions, seeds, fixture hashes; TRUST_MODEL line 8 trusts "the manifest author" | Accurate; author-supplied, not independently authenticated chronology |
| "a rule changed after the fact is detected, not merely forbidden" | STATISTICS Discipline lines 116–118 (`alpha`, `delta`, `interval_method` bound into `spec_sha256`; resealed manifest → `ERROR`); README lines 131–133 say the same | Accurate, consistent with existing text |
| "does not independently authenticate when the manifest was written or that every earlier run was disclosed; that discipline stays with the author" | STATISTICS lines 123–125 (`prior_runs` author-supplied; v0.1 does not discover earlier runs or enforce a cross-run budget) | Accurate; chronology/provenance bounded |
| "A `PASS` reports relative non-inferiority against the baseline within the registered margin under those conditions, never absolute reliability or a general quality score" | STATISTICS rule 4 (`PASS` iff `L > -delta`), experiment verdict 4 (every gating condition PASS); README line 13 and table line 99 | Accurate; conditioned on PASS only, not on every verdict |
| "`BLOCK`, `INCONCLUSIVE` and `ERROR` are defined above" | README verdict table lines 93–102 precedes line 352 | Accurate |
| "alongside the earlier evalopt-graph experiment, whose standalone feature development has ended" | evalopt first commit 2026-07-20 vs ARCI 2026-09-21 ("earlier" holds); wording mandated by the implementation brief and matches the accepted STOP ADR (`winddown-positioning.md:17`); says neither "archived" nor "published" | Accurate per plan; see Follow-up F1 on public sequencing |
| "declares no package or runtime dependency on evalopt and imports nothing from it" | `pyproject.toml` dependencies = `pydantic`, `pyyaml` only; `grep -c -i evalopt uv.lock` → 0; `grep -rn -i evalopt src tests examples bench action.yml justfile` → only the attribution docstring `src/arci/hashing.py:6–7` | Accurate (class P and I both absent, matching Task 06 audit) |
| "shares no runtime layer with the maintainer's sibling projects Actseal, Dorian and Frontier Scout" | Repo-wide grep (excluding `.venv/.git`) for actseal/dorian/frontier: zero hits in `src/`, `examples/`, `tests/`, `pyproject.toml`, `uv.lock`; frontier-scout appears only as the subject of the recorded guardrail experiment (README:179, `docs/results/guardrail/**`, `docs/reports/ci-gate-2026-10-06/**`), which is recorded data, not a shared runtime layer. The three names are exactly the four-repository set the Task 06 audit inspected | Accurate and finite: bounded to the inspected siblings and to ARCI's own side; no universal, historical or "all repositories ever" claim |
| "[NOTICE](NOTICE) records two adaptations from evalopt under MIT with attribution: … `src/arci/hashing.py` and … `src/arci/schema.py`, both attributed source adaptation inside the frozen manifest, not a dependency" | NOTICE names exactly these two (from `attestation.py` and `kernel.py`); both files are FROZEN.sha256 entries; phrased as what NOTICE records, not as an exhaustive provenance inventory | Accurate; attribution preserved |
| "not a successor to, conformance target for or drop-in replacement for evalopt, and nothing here claims adoption, performance or superiority" | Matches accepted `docs/portfolio.md:7–8, 36` wording; no benchmark, adoption or comparative claim added anywhere in the diff | Accurate |

Both first-round required changes are reflected in the final text: non-inferiority is attached to `PASS` specifically, preregistration is described as an author-supplied prospective contract without authenticated chronology, independence is bounded to evalopt coupling and the three named siblings, and the NOTICE sentence no longer says "the only evalopt-derived code".

## Findings by severity

- **P0/P1/P2:** none.
- **P3 (nit, optional):** four wrapped lines of the new paragraph are 101 characters (README lines 355, 358, 363, 365) against the prose's informal 100-column wrap. The README already has 26 lines over 100 columns at base (30 at HEAD, mostly image alt text and tables) and no Markdown length guard exists, so this is cosmetic only.
- **Informational:** README line 179 and `docs/results/guardrail/` already disclose that ARCI ran frontier-scout's shipped hook as a subject under test. The new sentence that ARCI "shares no runtime layer" with Frontier Scout is accurate alongside that disclosure (no import, dependency or shared code; the results are recorded data). No change needed.
- **Informational:** `src/arci/schema.py` carries no inline attribution docstring; the attribution for the self-sealing pattern lives in NOTICE only. The README says exactly that ("NOTICE records …"), so the wording is correct as written. Not an ARCI diff issue and `schema.py` is frozen.

## Required changes

None.

## Follow-ups (not blocking this diff)

- **F1 (root sequencing):** evalopt-graph `main` is at `fc3045d` (2026-10-08) and carries no public wind-down notice yet; the STOP wording lives in the control worktree branch. The ARCI sentence "standalone feature development has ended" is mandated by the brief and uses the accepted ADR wording, but root should land the evalopt notice (Tasks 04/05) before or together with the ARCI PR so the public README sentence has public evidence behind it. No ARCI text change is required for this.
- **F2 (optional, cosmetic):** rewrap the four 101-column lines if root wants a uniform 100-column paragraph; purely stylistic.
- Pre-existing, out of scope: the two Node SDK acceptance skips (`tests/acceptance/test_decisions_node.py:35, :52`, `@typesafe-ai/sdk` absent; installing needs network).

## Commands actually run (read-only, task-local binaries, from the target worktree unless noted)

| Command | Result |
|---|---|
| `git diff --stat a5adc83 ba179f3` ; `git diff a5adc83 ba179f3` ; `git diff --name-status a5adc83 ba179f3` | `README.md | 17 +` ; 1 file, 17 insertions, 0 deletions ; `M README.md` |
| `git log --format=... a5adc83..ba179f3` | two commits, `4e4862a` and `ba179f3`, author/committer ajaysurya1221 |
| `git diff --check a5adc83 ba179f3` | no output, exit 0 |
| `git status --short` ; `git rev-parse HEAD` | clean ; `ba179f3a188710e38ec4557d2f65b66a8953c099` |
| `shasum -a 256 -c FROZEN.sha256 \| grep -c ': OK$'` ; `... \| grep -v ': OK$'` | 48 ; no FAILED lines |
| `diff <(sed '352,368d' README.md) <(git show a5adc83:README.md)` | IDENTICAL |
| `.venv/bin/ruff format --check .` | `202 files already formatted`, exit 0 |
| `.venv/bin/ruff check .` | `All checks passed!`, exit 0 |
| `.venv/bin/basedpyright` | `0 errors, 0 warnings, 0 notes`, exit 0 |
| `grep -rn -i evalopt src tests action.yml examples bench justfile` ; `grep -c -i evalopt uv.lock` | only `src/arci/hashing.py:6–7` docstring ; 0 |
| `grep -rn -i -E 'evalopt\|actseal\|dorian\|frontier[ -]?scout'` repo-wide excluding `.venv/.git/.ruff_cache` | NOTICE, README:179 and new block, `docs/results/**`, `docs/reports/**` only; nothing under `src/`, `examples/`, `tests/` |
| `awk 'NR>=352 && NR<=367 && length($0)>100' README.md` | lines 355, 358, 363, 365 at 101 |
| `git -C agent-reliability-ci log --reverse` ; `git -C evalopt-graph log --reverse` ; `git -C evalopt-graph log -3 main` | ARCI 2026-09-21 ; evalopt 2026-07-20 ; evalopt main `fc3045d` 2026-10-08 |
| Read-only `cat`/`sed`/`grep` of the task, briefs, REPORTs, audit, accepted docs, STATISTICS/TRUST_MODEL/AGENTS, `schema.py`/`schedule.py`/`hashing.py`, root validation `commands.json` and log tails | as cited above |

## Limits

- `pytest` (≈336 s) was not rerun by this reviewer; the diff is README-only and no test reads README prose (`tests/unit/planning/test_planning.py` pins the operating-characteristic cells in code; `tests/unit/docs/test_figures.py` checks generated figures). Root's retained final validation at HEAD (`artifacts/07D-root-final-validation`, started 2026-10-12T22:09:39Z, after the `ba179f3` commit at 22:08:11Z) shows all six commands exit 0 and `881 passed, 2 skipped in 336.74s`; I read those records and did not alter them. Hosted CI was not observed.
- No review of other repositories' PRs or merges; this task ends with this review. No network or remote state was checked; "public evidence" statements above are from local `main` heads only.
- Turns used: 13 of 20 at the time of writing; elapsed and token counts not self-measured.
