REVIEW 07C — Reviewer Fable high | Verdict ACCEPT

Exact reviewed head: `b0d2ae108e62ef7c8a890e8294104a577217b4f8` on `winddown/20261013/07C` in
`/Users/ajay/Developer/.evalopt-worktrees/wt-portfolio-07c` (working tree clean at review start and end).
Base: `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c` (`main`). Observable model: `claude-fable-5-1`, requested
effort high. Fresh review: I read Task 07C, the implementation and revision-1 packets, `reports/07C.md`,
`reports/07C-r1.md`, the Task 06 independence audit, the accepted `docs/portfolio.md` / `docs/migration.md` /
positioning ADR wording, the target's `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, the full README, the
exact diff and the source. The prior Codex verdicts were read for awareness only; nothing below relies on them.

## Diff inspected

`git diff --numstat e34d4a6 b0d2ae1` → `20 0 README.md`: one hunk (`@@ -320,6 +320,26 @@`), one new
`## Related projects` section between `## What we don't build` and `## Roadmap`, 177 words, one paragraph,
no deletions. Removing lines 323–342 from the head README reproduces the base README byte-for-byte
(`diff` → identical). No source, test, policy, lock, hook, generated settings, workflow, figure, CHANGELOG,
contract file or tag changed. Four links, all absolute GitHub URLs, bracket/paren balanced; the README has no
table of contents or anchor list that the new heading would leave stale.

## Findings by severity

No P0/P1/P2 findings.

- **Independence statement (current, finite).** "does not depend on or import it: its `pyproject.toml`,
  `requirements.txt` and Python sources name no evalopt package or module" is a present-tree claim naming
  exactly the artifacts audited. Independently re-verified at the head: `[project].dependencies =
  ['pydantic>=2.0']`, `dev` extra is tooling only, no dependency groups or `tool.uv`; `requirements.txt` is
  `pydantic>=2.0` only; no `uv.lock`/`poetry.lock`/`setup.py`/`setup.cfg`/`Pipfile`/`package.json`; 58 tracked
  `.py` files with 0 hits for `evalopt|actseal|dorian|\barci\b|agent[-_]reliability` and 0 `import`/`from
  evalopt` lines; `git grep` outside README has 0 hits. The historical "never" wording from the first head is
  gone. No history, remote, PyPI or built-artifact claim is made.
- **Sibling sentence.** "each governed by its own README, contracts and limits; this paragraph adds no
  package, import, shared runtime or signing layer between them" mirrors the accepted `docs/portfolio.md`
  sentence and makes no claim about coupling among Actseal, Dorian and ARCI (which the Task 06 audit did not
  measure, and where ARCI carries attributed evalopt-adapted code). The three one-line job descriptions match
  the positioning ADR line 17 verbatim in substance and are consistent with each sibling's own README opener.
- **Native-control compilation and PR scope.** "compile a typed repository policy into Claude Code's native
  permissions and hooks, and verify a PR's diff against the scope declared by the base commit's policy"
  matches README lines 5–6, 220, 275–276, `AGENTS.md:5–6`, `CLAUDE.md:12–13`, `CONTRIBUTING.md:7–9`, and the
  CLI help in `frontier_scout/cli.py:117,124`. Omitting "and lock" is consistent with the README's own
  headline.
- **External signing rails.** "signing stays on GitHub artifact attestations and Sigstore" matches README
  lines 127–129, 162 and 318 and the "What we don't build" list; no new signing infrastructure or shared
  evalopt layer is introduced or implied.
- **Receipts without approval authority.** "local receipts remain unsigned observations with no approval
  authority" matches README 23, 108, 164 and the contracts' "never approval" rule; `cli.py:130` and the
  UNVERIFIED semantics agree.
- **Research-preview / emit-only limits.** "stays emit-only and a research preview" matches README line 8,
  the "Emit, don't enforce" principle (README 293, AGENTS 89, CLAUDE 83, CONTRIBUTING 16) and the status
  note at README 169. No adoption, performance, superiority, security, successor, conformance or drop-in
  claim is added; the "none is a successor, conformance target or drop-in for another" sentence tracks
  `docs/portfolio.md` and `docs/migration.md:31–32`.
- **evalopt status wording.** "has ended standalone feature development" is the ADR's accepted present-tense
  status; the paragraph does not say archived or that a final release is published. "earlier
  acceptance-kernel experiment" is consistent with the portfolio index's "Ended standalone experiments".
- **P3 observation, no change required.** "inherits none of evalopt's records, states or decisions" is a
  semantic statement rather than a manifest fact; it follows from the absence of any dependency or import
  and matches `docs/portfolio.md`, so it is acceptable as written.
- **Reports.** `reports/07C.md` and `reports/07C-r1.md` follow the REPORT format, name the exact commits,
  record the "PR pushed" deviation correctly (executor may not push), and claim no elapsed time or token
  counts. Their command results agree with mine. The repo's legacy admin-merge/protection-relaxation
  instructions in `CONTRIBUTING.md:120–122` and `AGENTS.md:142` are superseded by this run's plan and were
  not acted on by the author or by me.

## Required changes

None.

## Actual tests (task worktree, `PATH="$PWD/.venv/bin:$PATH"`; `python`/`ruff`/`mypy` resolved to `.venv/bin/*`, Python 3.14.6; all foreground to exit)

| Command | Result |
| --- | --- |
| `git diff --check` (working tree) | no output, exit 0 |
| `git diff --check e34d4a6…c b0d2ae1…8` | no output, exit 0 |
| `make lint` (`ruff check frontier_scout tests`) | "All checks passed!", exit 0 |
| `make type` (`mypy`) | "Success: no issues found in 13 source files", exit 0 |
| `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -m "not live" -q` | 254 passed in 17.61s, exit 0 |
| tomllib dump of `pyproject.toml`; `cat requirements.txt`; lockfile `ls`; `git ls-files '*.py' \| wc -l`; grep of Python sources and whole tree | as stated in Findings; 0 evalopt/sibling hits |
| byte comparison: base README vs head README with lines 323–342 removed | identical |

## Follow-ups and limits

- This is a read-only source review, not a merge, hosted-CI, push or publication approval. Root still owns
  push, PR, hosted CI (full non-live suite, detect-secrets, CodeQL, advisory verify workflow) and the
  rendered-README check.
- The STOP sentence should be re-checked against the final public evalopt README before publication, as both
  author reports already note.
- Not done here: no network fetch of the four sibling URLs (they match the accepted portfolio index), no
  model or subagent calls, no live audit, no credential or `.env` read, no target edits, no Git mutation in
  any worktree, no settings or protection change. Only this file was written. Elapsed time and token counts
  are not asserted; native receipts follow.
