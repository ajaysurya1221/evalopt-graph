# Proposal 03-fable-positioning — Naming and positioning contract

- Decision: Naming and positioning (PLAN.md Section F, row 2).
- Author: Fable xhigh (requested model `claude-fable-5-1`, requested effort xhigh).
- Stage: blind proposal for comparison. Not an ADR. Not public documentation.
- Lane: `winddown/20261013/03`, worktree `wt-semantics-03`, branch base `4383cd6`.
- Source semantics: baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`.
- Written: 2026-10-12, about 19:55Z.
- Inputs used: the Task 03-P brief; PLAN.md Sections B, C, F, G; CONTRACT.md; `README.md`; `CHANGELOG.md`; `CONTRIBUTING.md`; `SECURITY.md`; `docs/releases/v0.1.0.md`; `docs/architecture.md`; `pyproject.toml`; `src/evalopt_graph/__init__.py`; `.github/ISSUE_TEMPLATE/config.yml`.
- Deliberately not read: the memo, Astra proposals, other model proposals, the four portfolio repositories.

## 1. What this proposal decides and what it cannot change

Decides: the STOP notice and where it appears; the status vocabulary and the evidence each status word requires; final-release wording for `v0.1.1`; the shape of the four portfolio descriptions and the portfolio index; wording changes needed to make existing public text true under STOP.

Cannot change (PLAN.md Section F): project names, archival status, evidence limits. No renaming. No claim of archival or of `v0.1.1` publication before actual evidence. No new positive claims about the kernel and no comparative claims in either direction.

## 2. Independently checked facts (repository at `fc3045d`)

- P1. Names in use. Distribution and repository: `evalopt-graph` (`pyproject.toml` `name`; README title). Import package: `evalopt_graph`. Short prose name: "evalopt" / "Evalopt" (README, docs). Console script: `evalopt` (`pyproject.toml` `[project.scripts]`). GitHub: `ajaysurya1221/evalopt-graph`. PyPI: `evalopt-graph`. Author and maintainer: Ajay Surya Senthilrajan.
- P2. Version at baseline is `0.1.0` in `pyproject.toml` and `__init__.py`; README's install line pins `evalopt-graph==0.1.0`.
- P3. README is the PyPI long description (`pyproject.toml` `readme = "README.md"`). The one-line `description` field is separate package metadata. Task 08's file list names only version fields in `pyproject.toml`.
- P4. `SECURITY.md:11-14` lists `0.1.x` as supported and says only the latest patch release receives security fixes; `SECURITY.md:44` says the kernel is not a sandbox, retrieval engine, secret store, signature system, model monitor or semantic truth oracle.
- P5. `CONTRIBUTING.md` opens by welcoming contributions "across the kernel, adapters, tests, documentation, and independently authored conformance cases"; `README.md:195-199` welcomes "Bug reports, focused proposals, documentation improvements, and integrations". `.github/ISSUE_TEMPLATE/config.yml` offers a "Questions and integration help" link that invites integration ideas. All three invite work STOP ends.
- P6. `README.md:183` and `docs/architecture.md:106` describe the deprecated surfaces as retained "for one migration cycle", which implies a later removal release.
- P7. `CHANGELOG.md` has an `[Unreleased]` section with inherited changes since `v0.1.0` (README opening and figures, metadata pin, Python test gate interpreter, overnight hooks moved to `examples/`). PLAN Section B requires these to be disclosed in `v0.1.1` rather than claiming byte-identity with `v0.1.0`.
- P8. The repository's existing evidence statements (`README.md:141-170`, `docs/BENCHMARK_RESULTS.md`, `docs/BENCHMARK_PROTOCOL.md`) claim conformance evidence only and expressly disclaim benchmark superiority, external comparison and independent reproduction.
- P9. The accepted public notice text is fixed by PLAN Section B (quoted verbatim in N-2 below).

## 3. Items from the brief or plan not independently verified here

- B1. Memo reasoning for STOP. Not read; the positioning text must not restate it as fact.
- B2. The four projects' self-descriptions. To be quoted from each README at a pinned commit by Tasks 05–07.
- B3. GitHub behaviour on archival (read-only repository, banner). Treated here as the reason in-repo text must stay true across archival; Task 11's HUMAN_INBOX instruction remains the only archival step.

## 4. Contract rules (normative for Tasks 05 and 08 and their reviewers)

- N-1. Names are frozen. Use exactly the forms in P1. No new names, taglines, codenames, "legacy"/"classic" suffixes, or product-style phrases such as "the evalopt kernel" capitalised as a name. The descriptive phrase "acceptance policy kernel" already in use may remain. The existing README tagline ("Make acceptance policy explicit and replayable.") may remain because it still describes what the frozen kernel does; it appears after the notice, never above it.
- N-2. Canonical notice. The text fixed by PLAN Section B is the only STOP notice and is reproduced verbatim wherever the notice appears:

  > Standalone feature development has ended. This repository preserves the acceptance kernel and its research record. For new systems, use the alternatives listed below. Existing evidence remains subject to its original versions and limitations. Evalopt evaluates supplied evidence against policy; it is not a semantic truth oracle.

  Placement: first block of `README.md` (before the tagline), top of `CONTRIBUTING.md`, the `v0.1.1` release notes, the CHANGELOG maintenance note, and the top of `docs/portfolio.md`. The README copy is followed by one line of links: migration map, portfolio index, final-release notes, STOP decision record. Where "listed below" would be false (a file with no alternatives list), the sentence is replaced by "For new systems, use the alternatives in the migration map." No other edits to the notice.
- N-3. Status vocabulary and required evidence. Each phrase may be used only when its evidence exists in a committed REPORT or in a verifiable public record:

  | Phrase | Required evidence | Allowed from |
  |---|---|---|
  | "Standalone feature development has ended." | The STOP decision record (`docs/decisions/archive-standalone.md`) merged on main | Now |
  | "`v0.1.1` is the final planned release and changes no kernel behaviour." | Accepted Task 08 diff showing only the version literal under `src/` | Deprecation PR |
  | "`v0.1.1` is published." | `gh release view v0.1.1` non-draft, `verify_pypi_release.py` pass and `gh attestation verify` pass recorded in Task 10's REPORT | After Task 10 |
  | "This repository is archived." | Never written into the repository by this run. GitHub's own banner is the evidence after the human acts (B3) | Human only |
  | "deprecated" | Applies to the compatibility surfaces (already true) and to the distribution as a whole from `v0.1.1` onward, meaning no further feature development; it never means yanked, broken or removed | Deprecation PR |
  | "preserved" / "retained" | Applies to kernel, research record, tags, assets, history; backed by Task 02 preservation control | Now |

  Phrases not in this table ("abandoned", "unmaintained", "end of life", "sunset", "superseded", "replaced by") are not used.
- N-4. Pre- and post-event truth. Because the README merges before the tag and cannot be edited after archival, every README sentence must be true before publication, after publication, and after archival. Therefore the README says "final planned release" rather than "published", pins the install line to the version in the same commit (Task 08 moves it to `0.1.1` only in the version-bump commit), and says of archival: "The maintainer may archive this repository; archival makes it read-only on GitHub and does not change published releases."
- N-5. No comparative or causal claims. Positioning never says a destination is better, more secure, more widely adopted, or that it supersedes evalopt, and never says evalopt failed, is unsafe or does not work. The reason for STOP is stated once, in the decision record, as the maintainer's decision: "The maintainer ended standalone development and directs new work to existing tools for each job." The memo is referenced by hash in the decision record only (PLAN Section A), not quoted in public prose.
- N-6. Existing evidence text is untouched. The evidence ladder, conformance results, protocol status and all "does not claim" sentences (P8) stay as written. The notice adds the sentence "Existing evidence remains subject to its original versions and limitations" and nothing else about evidence.
- N-7. Portfolio descriptions. One entry per project, in this fixed form: "`<Project>` — `<self-description quoted from its README at commit <sha>>`. Independent of evalopt: no package dependency, no runtime import, no shared runtime." The evalopt row reads: "`evalopt-graph` — acceptance policy kernel; standalone feature development has ended; kernel and research record preserved." For ARCI the attribution sentence about adapted hashing provenance is kept as attribution, phrased "adapted from", never as a dependency (PLAN Section C, frozen contract 4). The index contains no ranking, no "suite", "platform", "stack", "ecosystem" or "umbrella" wording, and no arrow of succession between projects. "Portfolio" is used only because the plan uses it.
- N-8. Release-notes shape for `docs/releases/v0.1.1.md` (written by Task 08): title "evalopt-graph v0.1.1 — final planned release, no capability change"; the notice; "What changed" (version literal under `src/`; documentation listed by file); "Inherited since v0.1.0" (one line referring to the CHANGELOG `[Unreleased]` entries, now dated); "What did not change" (ten exports, kernel bytes equal to baseline main `fc3045d` except the version literal, zero runtime dependencies, reason codes, replay); "Verify the release" (the `v0.1.0` command pattern with `0.1.1`); "Migration" (link); "Archival" (future human action, not performed). The notes never say "byte-identical to v0.1.0".
- N-9. Contribution and issue wording (Task 05). `CONTRIBUTING.md`, the README "Community and security" section and the issue-template contact links are changed so they invite only: private security reports (unchanged channel), and corrections to documentation accuracy. They state that feature requests, new integrations, adapters and benchmark proposals are not accepted. The feature issue form is disabled or redirected rather than deleted. Nothing closes existing issues or PRs (Task 05 constraint).
- N-10. Security wording (bounded). `SECURITY.md` keeps the private reporting channel and the response targets. The sentence "Only the latest patch release receives security fixes" is bounded to: "Security reports remain welcome. Fixes are at the maintainer's discretion and are not scheduled; if one is released it is a patch release with no feature change." The supported-versions table is not deleted. This is the one place where "final planned release" matters: it leaves room for a security-only patch without making a promise.
- N-11. Deprecated-surface wording. Replace "for one migration cycle" (P6) with "retained unchanged; no removal release is planned" in README and architecture text, because under STOP there is no next cycle in which removal would happen. This is a truthfulness correction, not a semantic change; the code is untouched (no runtime warnings, Task 08).
- N-12. Positioning lives in documentation and release metadata only. No deprecation warning, docstring edit, console-script message or package-metadata classifier change is made under `src/` (frozen kernel bytes; Task 08 "no added runtime warnings"). The `pyproject.toml` `description` is left unchanged in this run unless Task 08 explicitly accepts a one-line change; the README long description already carries the notice to PyPI.
- N-13. Memo separation. Any sentence in public prose that originates in the memo or the brief and is not independently checked is phrased as a decision ("the maintainer has decided", "directs new work to") rather than as a finding ("research shows", "has been found"). The STOP decision record carries a short "Memo findings versus checked facts" table so readers can see which is which.
- N-14. Links. Public links point to immutable commit URLs for research and evidence where PLAN Section B asks for it, and to `main` paths only for living documents (README, migration map, portfolio index).

## 5. Templates

README head (order is part of the contract):

```text
# evalopt-graph

> Standalone feature development has ended. ... (notice verbatim)
> Migration map · Portfolio index · Final release notes · Decision record

**Make acceptance policy explicit and replayable.**
(existing content unchanged from here, except the sections named in N-9 and N-11)
```

Portfolio row:

```text
| <Project> | <quoted self-description> (README @ <sha>) | Independent of evalopt: no package dependency, no runtime import, no shared runtime. | <link> |
```

Status sentence bank (the only approved forms):

```text
Standalone feature development has ended.
v0.1.1 is the final planned release; it changes no kernel behaviour.
The maintainer may archive this repository; archival makes it read-only and does not change published releases.
The compatibility surfaces are deprecated and retained unchanged; no removal release is planned.
```

## 6. Reviewer checklist for Tasks 05 and 08 output

1. The notice text matches N-2 byte for byte in every placement; link line present in README.
2. No phrase from the N-3 "not used" list; "published" and "archived" absent from in-repo prose.
3. README example, printed outputs and generated figures unchanged (`tests/test_figures.py` passes).
4. No comparative or causal claim about any destination or about evalopt's quality (N-5).
5. Evidence sections unchanged (diff shows no edits under "Evidence, not a truth oracle" or the evidence docs).
6. Portfolio rows match N-7 form; ARCI attribution present and phrased as adaptation.
7. Release notes match N-8 headings; "byte-identical to v0.1.0" absent; inherited changes referenced.
8. Contribution and issue wording invites only security reports and documentation corrections; no issue or PR closed.
9. `SECURITY.md` keeps the private channel; bounded sentence per N-10.
10. "one migration cycle" no longer appears in README or architecture text.
11. No changes under `src/` except the version literal; `python3 -B plan/exec/preservation.py` passes.

## 7. Reopening conditions

- `v0.1.1` publication evidence arrives: the pre-authorised wording in N-3 row 3 may be used in the final report and release page; README is not re-edited for it.
- Archival happens: no in-repo change is possible or needed; the HUMAN_INBOX records it.
- A security-only patch is released after `v0.1.1`: "final planned release" is already compatible; the CHANGELOG gains the patch entry; an ADR records that STOP still holds.
- A portfolio project renames, archives or changes its self-description: its row is re-quoted at a new pinned commit by a reviewed documentation change; evalopt's own names never change.
- Publication is blocked at the deadline: public prose already says "final planned release", so nothing becomes false; the final report says "prepared or blocked", per PLAN Section G.

## 8. Alternatives considered and not proposed

- Writing "archived" into the README in advance of archival. Rejected: false until the human acts, and unfixable afterwards because the repository becomes read-only.
- Renaming the repository or distribution (for example an "-archive" suffix). Prohibited by the brief and the plan.
- Adding a `DeprecationWarning` on import or a CLI banner. Prohibited: kernel bytes are frozen and Task 08 forbids added runtime warnings.
- Yanking `0.1.0` on PyPI or replacing release assets. Prohibited by CONTRACT.md.
- Saying "final release" without "planned". Rejected: it would conflict with the security policy's patch wording and could become false; "final planned release" is true in every reachable end state.
- Changing the PyPI one-line description. Not proposed: outside Task 08's file list; the README long description already carries the notice.
