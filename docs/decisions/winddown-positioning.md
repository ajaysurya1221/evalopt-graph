# ADR: Naming and positioning during wind-down

Status: accepted. Recorded 2026-10-12 (Task 03). Decision 2 of the plan's three bias-control decisions. A documentation contract only.

## Decision

Names are unchanged: repository and distribution `evalopt-graph`, import package `evalopt_graph`, prose name evalopt. The plan's canonical notice appears once, near the top of README before the implementation overview:

> Standalone feature development has ended. This repository preserves the acceptance kernel and its research record. For new systems, use the alternatives listed below. Existing evidence remains subject to its original versions and limitations. Evalopt evaluates supplied evidence against policy; it is not a semantic truth oracle.

Other files (CONTRIBUTING, bounded SECURITY wording, issue templates, `docs/portfolio.md`, CHANGELOG) carry short, accurate, context-specific notices linking to README and the migration map, never a copy whose "listed below" would be false.

Status words need evidence. "Standalone feature development has ended" is true now. `v0.1.1` is the final deprecation release: no capability added relative to main `fc3045d`, only the version literal changed under `src/`. Inherited differences from `v0.1.0` are disclosed explicitly; no blanket "unchanged since v0.1.0" statement. "Published" waits for a verified release and "archived" for GitHub actually reporting it; both stay prospective in repository text. No performance, adoption, superiority, authentication or production-safety claim.

Intake: the contribution guide closes new standalone feature work and routes migration questions to the map; feature forms point to alternatives; bug reports stay open for final-release issues with a version and reproducible evidence, consistent with the existing `0.1.x` patch policy; private security reporting remains available with a bounded maintenance statement and no promised support period.

Portfolio: Actseal qualifies action policies against supplied evaluation evidence; Dorian records code-claim warrants; Frontier Scout controls PR scope through its native policy and compiler boundary; ARCI tests preregistered stochastic regression conditions. Each description is verified against the project's current README and contracts before its README is edited; none depends on evalopt; adapted-source attribution is preserved. The portfolio index lists the four jobs and places evalopt under ended standalone experiments, archival pending as a human action.

## Positions (Astra, Fable)

Fable xhigh ([`03-fable-positioning.md`](https://github.com/ajaysurya1221/evalopt-graph/blob/95b61a3ff9cbe6dc62acde75cf475958546aafc9/plan/exec/decisions/03-fable-positioning.md), commit `0663549f652bb868c3a5ad040fb67d6a7bed4663`): the canonical notice verbatim in five files with a patched sentence where no list exists; intake narrowed to security reports and documentation corrections; "for one migration cycle" replaced in README and `docs/architecture.md`.

Astra ([`03-astra-positioning.md`](https://github.com/ajaysurya1221/evalopt-graph/blob/95b61a3ff9cbe6dc62acde75cf475958546aafc9/plan/exec/decisions/03-astra-positioning.md), commit `aa28b4c73c1bb5e3928e3318d5d40c0e697fc0ef` on control; lane copy `068a2fc`): the notice once in README, context-specific notices elsewhere, "final deprecation release" wording, bug reports retained, portfolio paraphrases verified against current contracts.

Fresh Fable xhigh tie-break ([`03-tiebreak.md`](https://github.com/ajaysurya1221/evalopt-graph/blob/95b61a3ff9cbe6dc62acde75cf475958546aafc9/plan/exec/reports/03-tiebreak.md), commit `0a7d374`): choose Astra's wording and maintenance model. Five-file repetition plus patching is the drift the accuracy rule forbids; editing `docs/architecture.md` is outside Task 05's file list; narrowing intake conflicts with Task 05 and the patch policy. Both proposals already agreed on prospective status words and on disclosing inherited changes.

## Rule that decided

The plan's fixed notice text and preservation rules; lane ownership (Task 05's file list; Task 08 owns the version literal and release notes); and this decision's "cannot change" column: project names, archival status and evidence limits.

## Consequences

Task 05 edits only README, CONTRIBUTING, bounded SECURITY wording, the three issue templates, `docs/portfolio.md` and CHANGELOG maintenance wording; `docs/architecture.md` is not edited for positioning. The tested README example, generated figures and existing evidence text stay intact.
