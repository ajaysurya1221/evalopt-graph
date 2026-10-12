# Proposal 03-fable-boundary — Integration boundary and routing contract

- Decision: Integration boundary (PLAN.md Section F, row 3).
- Author: Fable xhigh (requested model `claude-fable-5-1`, requested effort xhigh).
- Stage: blind proposal for comparison. Not an ADR. Not public documentation.
- Lane: `winddown/20261013/03`, worktree `wt-semantics-03`, branch base `4383cd6`.
- Source semantics: baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`.
- Written: 2026-10-12, about 19:55Z.
- Inputs used: the Task 03-P brief; PLAN.md Sections B, C, F; CONTRACT.md; `pyproject.toml`; `docs/architecture.md`; `README.md`; `SECURITY.md`; `src/evalopt_graph/__init__.py`, `kernel.py`, `attestation.py`; a search of public docs and source for destination names.
- Deliberately not read: the memo, Astra proposals, other model proposals, the four portfolio repositories, any destination's live documentation.

## 1. What this proposal decides and what it cannot change

Decides: how the migration guide routes a user's job to an existing domain tool, standard, platform feature or independent project; what each route may and may not claim; where routing text may live; how destinations are cited.

Cannot change (PLAN.md Section F): no new wedge, adapter, predicate, policy module, action, hook, shared schema or common dependency. The four projects remain independent. STOP is fixed.

## 2. Independently checked facts (repository at `fc3045d`)

- D1. `pyproject.toml` declares `dependencies = []`. Optional extras `llm` (anthropic, openai), `yaml` (pyyaml) and `dev` exist and are pre-existing; none names a routed destination.
- D2. No file under `src/evalopt_graph`, `README.md`, `docs/`, `CONTRIBUTING.md`, `SECURITY.md`, `CHANGELOG.md` or `.github/` mentions OPA, Rego, in-toto, Witness, SLSA, VSA, Sigstore, GitHub rulesets, required status checks, Actseal, Dorian, Frontier Scout or ARCI. Routing text will be new and will have one source of truth.
- D3. The kernel runs no checks, retrieves nothing, signs nothing and enforces nothing (`kernel.py:461-468`, `kernel.py:307`, `attestation.py:12`, `SECURITY.md:44`; details in the interface proposal, K6 and K11). Every route therefore describes a job the host did around the kernel, or a job the kernel did with project-specific semantics.
- D4. The compatibility host (`graph.py`), CLI, providers, Codex bridge, research loop, claim ledger, filesystem evidence adapters and Harbor verifier mapping are deprecated host surfaces outside `__all__` (`docs/architecture.md:104-107`). They are orchestration and adapter code, not policy authorities.
- D5. The Harbor adapter is a verifier-side JSON mapping that imports only the kernel (`harbor_adapter.py:1-15`); Harbor itself is not a dependency. It is the existing precedent for "integration conformance without a dependency" and must not be extended.

## 3. Items from the brief or plan not independently verified here

- B1. SLSA VSA v1.0 is Retired (brief; PLAN Section B; URL `https://slsa.dev/spec/v1.0/verification_summary`). Task 04 records a dated check.
- B2. What OPA, in-toto, Witness and GitHub rulesets or required checks do, beyond the job names in the brief. Task 04 cites each primary source at a pinned version with an access date; this proposal names only the job, never a feature of the destination.
- B3. The four projects' domains as named in the brief: Actseal (action-policy qualification), Dorian (code-claim warrants), Frontier Scout (PR scope), ARCI (stochastic regression; PLAN Task 07D calls it preregistered statistical regression). Tasks 06 and 07A–07D verify against each repository.

## 4. Contract rules (normative for Tasks 04, 05 and 07A–07D and their reviewers)

- R-1. Closed route table. The migration guide routes exactly these seven jobs, in this order, and no others:

  | # | User's job | Destination | Route kind | Covers | Does not cover | Mandatory disclaimer |
  |---|---|---|---|---|---|---|
  | 1 | General policy evaluation | OPA | Policy engine (project) | Authoring and evaluating policy over a host-supplied input document | evalopt's five-state precedence, reason codes, record authorization, claim support | "No policy translation is provided; a `GovernancePolicy` must be re-authored in the destination's own language." |
  | 2 | Software provenance and attestation verification | in-toto and Witness | Specification and project | Signed attestations about software artifacts and verification of them against policy | evalopt's unsigned in-process evidence records about retrieved documents and text claims | "evalopt records are not in-toto statements; no predicate type exists or will be created." |
  | 3 | Native merge enforcement | GitHub rulesets and required status checks | Platform feature | Preventing merges until named checks pass | What a check means; evidence; claims; any decision semantics | "evalopt never enforced a merge; the host did. Required gates in a policy are analogous in purpose to required checks and are not required checks." |
  | 4 | Action-policy qualification | Actseal | Independent project | Its own domain, in its own words | Anything evalopt did | Independence sentence (R-6) |
  | 5 | Code-claim warrants | Dorian | Independent project | Its own domain, in its own words | Anything evalopt did; `ClaimRecord` is not a warrant | Independence sentence (R-6) |
  | 6 | PR scope | Frontier Scout | Independent project | Its own domain, in its own words | Anything evalopt did; receipts and signing rails are its own | Independence sentence (R-6) |
  | 7 | Stochastic regression | ARCI | Independent project | Its own domain, in its own words; preregistered statistical semantics are its own | Anything evalopt did; adapted hashing provenance is attribution, not dependency | Independence sentence (R-6) plus attribution sentence |

  SLSA VSA is not a route row. It appears only as a "historical prior art" note attached to the `AcceptanceDecision` and terminal-states entries, marked Retired with a dated check (B1), and is never offered as a destination.
- R-2. Route by job, never by type. The guide never says "replace `<export>` with `<tool>`". The fixed sentence form is: "If your job is `<job>`, the tool for that job is `<destination>`. The evalopt construct you used for it was `<construct>`; that construct is not `<destination's construct>` (see the migration map entry)."
- R-3. One destination per job. Two names appear together only where the brief lists them jointly (in-toto and Witness; rulesets and required status checks). No row lists alternatives, runners-up or "or similar".
- R-4. Unrouted jobs are named, not hidden. The guide carries a short list titled "No destination recommended (host-owned)": the agent orchestration loop (`graph`, `cli`), provider clients, the Codex bridge, research mode and the claim ledger, filesystem evidence adapters, the Harbor verifier mapping, lexical claim support, and replay of evalopt records. Each line says it is retained unchanged in `0.1.x` and that users who need it pin `0.1.x`. No destination is invented for them.
- R-5. No wedge. The documentation must not propose, sketch, link to as planned, or list as future work any adapter, importer, exporter, predicate type, Rego module, Witness attestor, GitHub Action, pre-commit hook, CLI flag, or shared library connecting evalopt to a destination or to a portfolio project. The guide contains no code sample that uses a destination; it links to the destination's own documentation only. The Harbor adapter (D5) is described as an existing, frozen precedent and is not extended.
- R-6. No common dependency. Each portfolio row carries the independence sentence: "Independent of evalopt: no package dependency, no runtime import, no shared runtime." No row says "shares", "compatible evidence format", "common schema", "same hashing" or "built on". ARCI's adapted hashing provenance is described as "adapted from evalopt source, with attribution" and nothing more. evalopt's optional extras (D1) are not extended, and no destination becomes an optional extra.
- R-7. Citation discipline. Every destination is cited from its own primary source: a specification page or the project's own documentation or README, with version or revision and access date, in the appendix defined by the interface contract. Status notes (Retired, deprecated, archived) are carried through. Prohibited about any destination: "industry standard", "widely adopted", "de facto", "recommended by", "certified", "conformant", "endorsed", comparisons with other tools, and any statement about destination behaviour that the cited page does not make. Standards are called "specification"; tools and portfolio projects are called "project"; GitHub features are called "platform feature".
- R-8. Minimum disclaimers on every route row and on the README summary: hashes are content digests, not signatures; evalopt attestations are unsigned records, not semantic truth; the five decision states do not map automatically or losslessly to any destination's outcomes; evalopt never ran checks or enforced anything. These may be printed once above the table if the table is the only place routes appear in that file.
- R-9. Placement and single source of truth. The route table lives in `docs/migration.md` (Task 04). The README alternatives matrix (Task 05) copies the same seven jobs and destinations in the same order, with the R-8 disclaimers, and adds nothing. `docs/portfolio.md` carries rows 4–7 only, with the R-6 sentences, and does not describe routes 1–3. No other file (CHANGELOG, release notes, issue templates, SECURITY) introduces a route; they link to the migration map.
- R-10. Ordering and framing. Rows 1–3 (specification, project, platform feature) precede rows 4–7 (independent projects) and the table is split by a one-line caption between them: "The following four projects are independent of evalopt and of each other; they are listed because they own jobs evalopt users sometimes asked about, not as successors." This prevents reading the portfolio as a replacement for the kernel.
- R-11. Security reports stay home. Vulnerability reports about evalopt go to evalopt's private advisory channel (`SECURITY.md`), not to any destination. The guide says that reports about a destination belong with that destination. No route changes the security policy.
- R-12. Research record is not routed. The guide does not route benchmark, conformance or protocol material anywhere; `docs/BENCHMARK_RESULTS.md` and `docs/BENCHMARK_PROTOCOL.md` remain as evidence under their original versions and limitations (notice sentence in the positioning contract).
- R-13. Boundary statement for the decision record. The STOP decision record states in one paragraph: no integration, adapter, predicate, policy language, benchmark programme or shared runtime dependency is created; routes are documentation; the four projects remain independent; the kernel is preserved and frozen; this is checked by `python3 -B plan/exec/preservation.py` and by the absence of new files under `src/`, `tests/` and `bench/`.

## 5. Templates

Route row text (per R-2, printed under the table for each row):

```text
**<Job>.** If your job is <job>, the tool for that job is <destination> [<appendix key>].
The evalopt construct you used for it was <construct>; it is not <destination construct>.
Re-author the policy or record in <destination>'s own constructs. Nothing is converted.
```

Portfolio row text (rows 4–7):

```text
**<Project>** — <self-description quoted from its README at commit <sha>> [<appendix key>].
Independent of evalopt: no package dependency, no runtime import, no shared runtime.
```

Unrouted list line:

```text
- <surface or job>: host-owned; retained unchanged in 0.1.x; no destination recommended.
```

## 6. Reviewer checklist for routing text

1. Exactly seven route rows, brief order, destinations exactly as named in R-1; SLSA VSA absent from the table and present only as a Retired prior-art note with a dated check.
2. Every row uses the R-2 sentence form; no "replace `<export>` with" phrasing anywhere.
3. R-4 unrouted list present with every listed surface; no invented destination.
4. No code sample uses a destination; no "future work", "planned adapter", "roadmap" or similar text (R-5).
5. Every portfolio row has the R-6 sentence; ARCI attribution phrased as adaptation; none of the prohibited words in R-6 or R-7.
6. Appendix has a primary source, version or revision and access date for each destination; no comparative or adoption claims.
7. R-8 disclaimers present on each row or once above the table in every file that shows routes.
8. README matrix and portfolio index match the migration map in jobs, destinations and order; no other file introduces a route (grep for each destination name across the repository).
9. `pyproject.toml` dependencies and extras unchanged; no new files under `src/`, `tests/`, `bench/`; preservation control passes.
10. Security policy channel unchanged and not redirected.

## 7. Reopening conditions

- A destination is retired, archived, renamed or its cited page changes: its row's status note and appendix entry are updated by a reviewed documentation change; no replacement destination is added without an ADR.
- A destination publishes evalopt-specific support (an importer, predicate or policy pack): it does not create equivalence or a route change; mentioning it requires an ADR and the R-8 disclaimers remain.
- A portfolio project gains a dependency on evalopt, or evalopt on it: independence sentences become false; a portfolio audit (as in Task 06) and an ADR are required before any wording change.
- A new specification supersedes VSA: the prior-art note stays historical; a new route is not added by this rule alone.
- A reviewer shows a route describes a destination feature the cited page does not state: the sentence is removed or re-cited; the route itself does not change.

## 8. Alternatives considered and not proposed

- Routing by export type (one destination per export). Rejected: implies drop-in replacement and contradicts the four-label scheme in the interface contract.
- Listing the four projects as successors or an "evalopt family". Rejected: the brief requires independence; they own different jobs.
- Keeping SLSA VSA as a current route with a caveat. Rejected: the cited specification is Retired; historical prior art only.
- Offering several candidate tools per job (for example additional policy engines). Rejected: the brief fixes the routes, and each extra name would need unverified comparative wording.
- A thin compatibility package, example repository or GitHub Action demonstrating a route. Prohibited: a wedge and a new artifact under STOP.
- Routing the research record to a benchmark venue or registry. Rejected: no new benchmark programme; evidence stays under its original versions and limitations.
