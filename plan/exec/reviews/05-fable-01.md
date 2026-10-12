REVIEW 05 — Reviewer Fable high | Verdict ACCEPT

Target: commit `7742bae5f90c371cc6f21c8309492099983f5586` on `winddown/20261013/05`, delta from `cb5f3ceae4e149843dc37c0390668faaa3dc91b6`, inspected in `wt-notice-05` (HEAD equals the target, working tree clean). Read-only review; nothing edited, staged, committed, pushed; no model, subagent, network, benchmark or credential access. Evidence read independently: `plan/exec/tasks/05.md`, `05-implementation.md`, the four accepted ADRs under `docs/decisions/`, `docs/migration.md`, `docs/migration-sources.md`, `plan/exec/audits/portfolio-independence.md`, `plan/exec/reports/04-url-check.md`, commit `624ed11` and the current `kernel.py`. The author REPORT at `plan/exec/reports/05.md` was read after the diff and is not the basis for this verdict.

## Scope and ownership

- Exactly eight files changed, all in the Task 05 allowlist: `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `.github/ISSUE_TEMPLATE/{bug,config,feature}.yml`, `docs/portfolio.md` (new), `CHANGELOG.md`. `git diff --stat cb5f3ce 7742bae` shows nothing under `src/`, `tests/`, `bench/`, `docs/assets/`, `docs/migration*.md`, `docs/architecture.md` or `pyproject.toml`.
- Version literal untouched: `pyproject.toml:7` and `__init__.py:20` are `0.1.0`; README install line still `evalopt-graph==0.1.0` (`README.md:76`).

## Checks run (all from the target worktree)

| Check | Command | Result |
|---|---|---|
| Whitespace | `git diff --check cb5f3ce 7742bae` | no output, exit 0 |
| README example and figures | `<control>/plan/artifacts/tooling/bin/uv run --frozen --extra dev python -m pytest tests/test_figures.py -q` | `...` 3 passed, exit 0 (the test execs the README's first `python` block and asserts the `text` block matches) |
| Preservation | `python3 -B plan/exec/preservation.py` | `{"baseline": "fc3045d…", "protected_files": 75, "errors": []}`, exit 0 |
| Issue-form YAML | PyYAML `safe_load` plus structural checks (top-level keys, unique body ids, allowed body types, dropdown options, labels, `contact_links` keys) | bug 8 ids, feature 5 ids, config 4 links; all well-formed. GitHub's live form schema not exercised (no network). |
| Local links and anchors | inline Python over the eight files; `blob/main`, `raw/main`, relative and `#anchor` targets resolved against the worktree with GitHub-style heading slugs | 0 missing targets, 0 bad anchors (`#alternatives`, `#the-sixteen-entries`, `#where-each-job-goes`, `#install`, `#kernel-owns--host-owns` all resolve); 35 external URLs not fetched |
| README invariants vs. `cb5f3ce` and baseline `fc3045d` | first `python` block, first `text` block, all `<picture>`/`srcset`/`<img>` lines, all Harbor lines compared byte-for-byte | identical in all four comparisons |
| Canonical notice | exact five-sentence string from `winddown-positioning.md` counted in README | exactly 1 occurrence, directly under the title, before the implementation overview; "listed below" is true because `## Alternatives` (`README.md:44`) precedes `## Install` |
| Migration map intact | row count and headings of `docs/migration.md` | 16 numbered rows, not modified by the commit |
| Stale phrases | grep for "one migration cycle", "is archived", "has been archived", "published v0.1.1", "welcome", "wedge", "successor" across the eight files | none in new text; the only "one migration cycle" hit is the historical `[0.1.0]` section of CHANGELOG (`CHANGELOG.md:75`), correctly preserved; "welcome" survives only in SECURITY's pre-existing "Security reports are welcome" |

## Source precision findings

- README matrix (`README.md:52-60`): seven rows in the exact routing-boundary order (OPA; in-toto attestation framework and Witness; GitHub rulesets and required checks; Actseal; Dorian; Frontier Scout; ARCI). Descriptions are paraphrases of `docs/migration.md:37-43`; no route added; hash/signature limit sentence matches the ADR wording; deprecated surfaces point to entry 16 instead of restating it.
- `docs/portfolio.md`: four jobs in map order; pinned commits `111afb3`, `eeb1937` (tag `v1.4.1`), `e34d4a6`, `a5adc83` and the 2026-10-12 UTC check date match `docs/migration-sources.md:31-34`; each limit sentence matches the appendix's status note; the "no package dependency, no runtime import" statement matches audit Results P and I (`portfolio-independence.md:85, 111`); ARCI hashing adaptation stays "attributed adaptation, not a dependency"; evalopt is placed under ended standalone experiments with archival "a separate human action that this page does not claim has happened" and the release "not asserted here". Preservation sentence matches the ADR's Preservation consequence.
- CHANGELOG `### Fixed` entry verified against `git show 624ed11`: old `rows()` did `tuple(tuple(row) for row in values)`, so a string of the right width was split into characters and accepted and a non-iterable raised `TypeError`; the new code raises `ValueError` with the pre-existing "entries require N string fields" message for string/bytes/non-iterable values and rows; `from_dict` now passes raw rows to the constructor. Author line is "Göktuğ Özkan, MD <232098340+goktugozkanmd@…>", subject "(#4)", trailer co-authors the maintainer. Credit is accurate. Existing Unreleased entries, the `[0.1.0]` section and the compare links are unchanged; the paragraph scopes inherited differences to `v0.1.0` tag versus baseline `fc3045d` and makes no byte-identical or published claim.
- STOP/release/archive status: README, CONTRIBUTING, SECURITY, CHANGELOG and the portfolio index all say "standalone feature development has ended" and never say archived, published or v0.1.1. `docs/migration.md` is unchanged.
- Security/intake consistency: SECURITY keeps the private advisory link, the `0.1.x` supported table, the report contents, the boundary section, and the three timing targets; new wording says patch releases "remain possible" and a final deprecation release "does not rule out a later security patch", with no support period or capacity promised. "Single maintainer" is supported by `pyproject.toml:14`. CONTRIBUTING's accepted list (bug reports with version and minimal reproduction, documentation and migration corrections, private security) matches README "Maintenance and security", `bug.yml`, `feature.yml` and `config.yml`; no file promises conversion, sibling-project support or response time. The feature form is now a documentation/migration form with a checkbox excluding capability requests; the bug form retains all original fields. No file deleted; `blank_issues_enabled: false` unchanged.
- No new feature invitation: "Integrate it anywhere" became "Historical integration examples" with an explicit "not an invitation"; "focused proposals … and integrations are welcome" removed; the benchmark protocol is framed as preserved historical material with "no new benchmark programme" in both places it is linked.
- Navigation: README uses absolute GitHub URLs only (renders on PyPI; `pyproject.toml:9` sets `readme = "README.md"`); no private worktree path appears in any of the eight files. External destinations in the matrix and portfolio are the same URLs root fetched with HTTP 200 for Task 04 (`04-url-check.md:3`); the only new external URLs are `pull/4`, the contributor profile, `discussions` (pre-existing) and `releases`.

## Findings by severity

High: none.

Medium: none.

Low:

1. `README.md:203-204` — "a host adapted observations from Codex, Claude Code, OpenHands, LangGraph, CI or its own runtime" turns the original prescriptive list into a past-tense statement. The repository contains no OpenHands adapter, and the LangGraph backend was removed (`graph.py:1870-1876`); `docs/releases/v0.1.0.md:31` phrases this as capability ("can"), not history. A reader may take it as a usage claim, which the positioning ADR forbids. Suggested wording: "The kernel was built host-independent so that a host could adapt observations from … into `AcceptanceInput` and store …". Non-blocking; one clause.
2. `README.md:54` — "A signed Statement binds a typed predicate to artifact digests". In in-toto terms the Statement binds predicate to subjects and the DSSE envelope carries the signature; the map's own row (`docs/migration.md:38`) keeps those separate. Acceptable compression for a one-line matrix; non-blocking.

Informational:

3. `CHANGELOG.md` now discloses the scalar-row fix, the interpreter selection and the helper move, but the archive ADR's release-note consequence also lists the readiness-message/docstring wording and the packaging and optional-dependency floor changes. Those belong to Task 08's release notes, not Task 05, and are not a defect here.
4. Whether GitHub Discussions is enabled for the repository was not verified (pre-existing link in `config.yml`; no network in this review).

## Required changes

None. The two Low items are optional wording tightenings that root may fold into integration or leave for a later documentation correction; neither affects the accepted contracts.

## Limits of this review

- Source review only. Root's integrated rendered README inspection on desktop and phone (long matrix rows, opening blockquote, PyPI rendering of the absolute anchor) is **pending, not passed**, and is explicitly left open here.
- No external URL was fetched; GitHub's live issue-form validation and label existence were not exercised.
- No release approval is implied; version numbering, release notes and publication remain Task 08 and root gates.

## Follow-ups

- Root: rendered desktop/phone inspection; live link/render checks; confirm the `documentation` label exists or accept GitHub's silent no-label behaviour.
- Task 08: complete the inherited-difference enumeration in release notes per `archive-standalone.md` Consequences.
- Independent Codex review (`05-codex-01.md`) remains a separate gate; this review does not depend on it.
