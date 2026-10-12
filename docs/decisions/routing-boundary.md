# ADR: Routing and integration boundary

Status: accepted. Recorded 2026-10-12 (Task 03); VSA wording revised 2026-10-12 UTC in Task 03 revision 1. Decision 3 of the plan's three bias-control decisions. A documentation contract only.

## Decision

There is no wedge integration. The migration map routes exactly seven jobs, in the plan's order, one destination each, as job-oriented pointers and never as tested drop-in replacements:

| User's job | Destination |
|---|---|
| General policy evaluation | OPA |
| Software provenance and attestation verification | in-toto and Witness |
| Native merge enforcement | GitHub rulesets and required checks |
| Action-policy qualification | Actseal |
| Code-claim warrants | Dorian |
| PR scope | Frontier Scout |
| Stochastic regression | ARCI |

External standards and tools are cited from primary documentation with access dates. The four projects are described by concise paraphrases verified against each project's current README and contracts (Tasks 06 and 07A to 07D). They are independent of evalopt and of each other: no successor, conformance or drop-in claim; no package coupling; ARCI's adapted hashing provenance stays attributed as adaptation, never as a dependency. No statement about user demand appears unless proven. The cited SLSA VSA v1.0, a retired version, is historical prior art, not a route; the Approved v1.2 page is source-status context only (see [archive-standalone.md](archive-standalone.md)) and adds no route.

Every route leaves domain semantics and enforcement with their owners and keeps policy evaluation, evidence integrity, producer authentication, semantic claim support and operational enforcement separate. The host keeps policy protection, identity, retrieval, isolation and the action that follows a decision. A content hash binds bytes; a trusted signature binds a statement to an identity within its verification system; neither proves a claim true. Unrouted deprecated host surfaces are described once, in the map's sixteenth entry; other files link there.

## Positions (Astra, Fable)

Fable xhigh ([`03-fable-boundary.md`](../../plan/exec/decisions/03-fable-boundary.md), commit `0663549f652bb868c3a5ad040fb67d6a7bed4663`): a closed route table with per-row disclaimers and a fixed sentence form, verbatim project self-descriptions at a pinned commit, a separate unrouted-surfaces list and a user-demand caption.

Astra ([`03-astra-boundary.md`](../../plan/exec/decisions/03-astra-boundary.md), commit `aa28b4c73c1bb5e3928e3318d5d40c0e697fc0ef` on control; lane copy `068a2fc`): concise job-oriented pointers, primary-source citations, paraphrases from current contracts, explicit separation of concerns and host obligations.

Fresh Fable xhigh tie-break ([`03-tiebreak.md`](../../plan/exec/reports/03-tiebreak.md), commit `0a7d374`): choose Astra's concise forms; verbatim quotation can import wording too long or context-bound for an index; the fixed row sentence adds no checked content; the demand caption is unsupported and struck; the unrouted list duplicates map entry sixteen.

## Rule that decided

STOP (no new integration); the plan's alternatives matrix with its hash and attestation limits; frozen contract 4 (no new evalopt dependency, attribution preserved); and this decision's "cannot change" column: no new wedge, adapter or common dependency.

## Consequences

Task 04 holds the single route table; Task 05's README matrix and `docs/portfolio.md` reproduce the same jobs, destinations and order without adding routes. Tasks 07A to 07D open narrow README pull requests in the sibling repositories, unmerged by this run. Security reports about evalopt stay with evalopt's private channel. A new integration request belongs outside this run and is governed by the reopening conditions in [archive-standalone.md](archive-standalone.md).
