REVIEW 05-FINAL — Reviewer Fable high | Verdict ACCEPT

Target: commit `c8f2b1dee5f3f0a705e87ab0f4e520695275b3d4` on `winddown/20261013/05`, delta from `7742bae5f90c371cc6f21c8309492099983f5586`, inspected in `wt-notice-05` (HEAD equals the target; `git status --short` empty before and after checks). Read-only review: no target edits, no Git mutation, no credentials or `.env`, no model or subagent calls, no network, no benchmarks, no installs. Only this file was written.

Evidence read before the author material: the full delta diff, `plan/exec/reviews/05-codex-01.md`, `05-fable-01.md`, `05-root-observations.md`, the four accepted ADRs under `docs/decisions/`, `docs/migration.md` (route table, entry 16, shared limitations), `docs/migration-sources.md:31-34`, `docs/releases/v0.1.0.md:31`. The author REPORT `plan/exec/reports/05-r1.md` was read afterwards and is not the basis for this verdict.

## Scope of the delta

`git diff --stat 7742bae c8f2b1d`: `README.md` 10 insertions / 8 deletions, `docs/portfolio.md` 2 insertions / 2 deletions; no other path. Cumulative from `cb5f3ce`: the same eight Task 05 owned files as round 1, nothing under `src/`, `tests/`, `bench/`, `docs/assets/`, `docs/migration*.md`, `docs/architecture.md`, `pyproject.toml`. Version literal unchanged (`pyproject.toml:7`, `__init__.py:20` and the README install pin all `0.1.0`).

## Required round-1 changes, verified against the accepted documents

1. **Bounded independence and non-equivalence (Codex P2, root item 2).** `README.md:48-50` now reads "The four sibling projects are independent of evalopt and of each other. This guide and the sources it inspected supply no automatic or lossless mapping of evalopt's five decision states, reason codes or decision records into any destination." The subject matches `docs/migration.md:30-31` and `archive-standalone.md:11` (Actseal, Dorian, Frontier Scout and ARCI); the mapping sentence matches the shared-limitations bullet at `docs/migration.md:82-83`. The blanket "none carries ... across" absence claim over OPA, in-toto, Witness and GitHub is gone. Fixed.
2. **Hypothetical host, not integration history (Codex P2, root item 1, Fable-01 Low 1).** `README.md:203-207` now says the kernel "was designed to accept host-supplied observations through `AcceptanceInput`, so that a host could adapt observations from Codex, Claude Code, OpenHands, LangGraph, CI or its own runtime into that input and store the returned decision ... The host remains responsible for both steps." This is the conditional contract form both reviews asked for and agrees with `docs/releases/v0.1.0.md:31` ("can"). The "not an invitation" sentence, the alternatives link and the four Harbor lines are unchanged. Fixed.
3. **No-destination qualification (root item 2).** Both occurrences (`README.md:68` and `README.md:218`) now read "have no supported compatible migration target in this map", which tracks entry 16's label "No supported equivalence" and its text "No destination is a drop-in for any of them" (`docs/migration.md:76`). No claim that no other host or CLI tool exists remains. Fixed.
4. **Stale no-mention claims removed (root item 3).** `docs/portfolio.md:17-18` no longer says Dorian or Frontier Scout "does not mention evalopt"; the Limits cells keep only the durable semantic limits ("A claim is only as strong as its checker"; "A research preview; unsigned receipts cannot authenticate approval"), matching the map's route table. The dated snapshot observation still lives in `docs/migration-sources.md:32-33`, which Task 05 does not own and did not change. Fixed.
5. **Statement versus DSSE (Fable-01 Low 2).** `README.md:57` now reads "A Statement binds a typed predicate to artifact digests; a DSSE envelope carries signatures; Witness verifies signed attestation collections against a signed policy", the same separation as `docs/migration.md:38`. Fixed.

## Focused checks rerun on the target

| Check | Command | Result |
|---|---|---|
| Whitespace | `git diff --check 7742bae c8f2b1d` | no output, exit 0 |
| README example and figures | `<control>/plan/artifacts/tooling/bin/uv run --frozen --extra dev python -B -m pytest -p no:cacheprovider tests/test_figures.py -q` | `...` 3 passed, exit 0 |
| Preservation | `python3 -B plan/exec/preservation.py` | baseline `fc3045d…`, 75 protected files, `errors: []`, exit 0 |
| Local links and anchors in the two changed files | inline Python resolving `blob/main`, relative and `#anchor` targets with GitHub-style slugs | 0 missing, 0 bad anchors; 27 external URLs not fetched (root already confirmed the three newly referenced public links return HTTP 200 and Discussions is enabled; not repeated here) |
| README invariants vs. baseline `fc3045d` | first `python` block, first `text` block, all `<picture>`/`srcset`/`<img>` lines, all four Harbor lines | byte-identical |
| Canonical notice | exact five-sentence string from `winddown-positioning.md` | present in the ADR, exactly 1 occurrence in README, directly under the title |
| Matrix | rows and order | 7 rows, routing-boundary order unchanged (OPA; in-toto and Witness; GitHub rulesets; Actseal; Dorian; Frontier Scout; ARCI); no route added |
| Stale phrases across the eight files | grep for "does not mention", "have no destination", "no migration destination", "host adapted", "of evalopt and of each other" | none remain except `docs/portfolio.md:7`, where the subject is already the four projects; "one migration cycle", "is archived", "published v0.1.1" absent from new text as in round 1 |

## Carried from round 1 (unchanged material, independently accepted in `05-fable-01.md`)

CONTRIBUTING, SECURITY, the three issue forms and CHANGELOG are byte-identical to `7742bae`; the round-1 findings on their contracts (bounded intake, no capacity promise, private advisory retained, `624ed11` scalar-row disclosure and contributor credit, no archived/published/v0.1.1 claim) stand without re-derivation. Codex's round-1 verification of the same files (YAML structure, 49 link targets, Dorian tag resolution) is consistent with this reading.

## Findings by severity

High: none. Medium: none. Low: none.

Informational:

1. `README.md:48` uses "the four sibling projects" two sentences before the portfolio-index sentence at `README.md:66` names them as a group; the matrix in between makes the referent inferable. No change required.
2. `docs/migration-sources.md:32-33` still carries the dated "does not mention evalopt" snapshot. That is Task 04's accepted appendix, correctly bound to pinned commits and dates; Task 07 paragraphs do not invalidate a dated observation. Not a Task 05 defect.

## Required changes

None.

## Limits of this review

- Source review only. Root's integrated desktop/phone rendering inspection (long matrix rows, opening blockquote, PyPI rendering of the absolute `#alternatives` anchor) remains a root gate after this source acceptance and is not represented as passed.
- No external URL fetched and no live GitHub issue-form validation; root's live checks are relied on only for the items root stated.
- No release approval implied; version numbering, release notes and publication remain Task 08 and root gates. Independent Codex review of `c8f2b1d` is a separate gate; this verdict does not depend on it.

## Follow-ups

- Root: rendered inspection; integration of `c8f2b1d` on acceptance of both independent reviews.
- Task 08: complete the inherited-difference enumeration per `archive-standalone.md` Consequences (carried from round 1, informational).
