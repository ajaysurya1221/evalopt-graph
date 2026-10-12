# ADR: Public migration interface

Status: accepted. Recorded 2026-10-12 (Task 03); VSA wording revised 2026-10-12 UTC in Task 03 revision 1. Decision 1 of the plan's three bias-control decisions. A documentation contract only; no product interface, schema or converter.

## Decision

`docs/migration.md` is one compact, navigable map:

- It opens with the preservation rule: keep original policy, input, decision, evidence records, material and source version together; a new tool never retroactively authorizes or reinterprets old evidence.
- One shared limitations section states, once: no automatic or lossless mapping of the five decision states (`ACCEPTED`, `BLOCKED`, `UNVERIFIED`, `UNSUPPORTED`, `FAILED`) or reason codes; hashes are content digests, never producer authentication; evalopt attestations and support assessments are unsigned records about host-supplied evidence, not semantic truth; `validate()` checks a retained record, `replay()` recomputes a decision from stored policy and input, and neither reruns reality.
- Exactly sixteen rows, in `__all__` order then topic order: GovernancePolicy, ClaimRecord, EvidenceRequest, EvidenceMaterial, EvidenceAttestation, SupportAssessment, EvidenceAuthority, AcceptanceInput, AcceptanceDecision, evaluate_acceptance; then terminal states/reasons, serialization/hash binding, replay, host authentication/signatures, freshness/record authority, deprecated host surfaces. Each row carries one primary label from four (conceptual analogy, host responsibility, project-specific semantics, no supported equivalence), its own specific limit, and a `file:line` reference at `fc3045d` plus any appendix key.
- A source appendix lists key, title, publisher, URL, version or revision, access date and status note. SLSA VSA appears only as historical prior art at the cited v1.0 version, which is retired, with a dated check; never as a destination. The later v1.2 page is Approved; that is source-status context recorded in [archive-standalone.md](archive-standalone.md), not a route.
- A separate sixteen-row coverage record holds reviewed dispositions; coverage is an inventory, not interoperability certification.
- Inherited changes since `v0.1.0` are disclosed by CHANGELOG reference, never by a "byte-identical" claim.
- No converter, schema, predicate, example in another format, policy file or test fixture; `src/`, `tests/` and `bench/` stay untouched.

## Positions (Astra, Fable)

Fable xhigh ([`03-fable-interface.md`](../../plan/exec/decisions/03-fable-interface.md), commit `0663549f652bb868c3a5ad040fb67d6a7bed4663`): a fixed per-entry template with repeated disclaimers, greppable label tags, a closed destination set and a prohibited-vocabulary list.

Astra ([`03-astra-interface.md`](../../plan/exec/decisions/03-astra-interface.md), commit `aa28b4c73c1bb5e3928e3318d5d40c0e697fc0ef` on control; lane copy `068a2fc`): a compact guide with the preservation rule first, a job-to-tool table, sixteen compact rows, shared limitations once, a source appendix and a separate coverage record.

Fresh Fable xhigh tie-break ([`03-tiebreak.md`](../../plan/exec/reports/03-tiebreak.md), commit `0a7d374`): choose Astra's compact map; adopt from Fable the roster closure in `__all__` order, one primary label per row, the appendix columns, the dated VSA check and CHANGELOG-referenced disclosure; reject the vocabulary ban, which would forbid truthful negative statements and discussion of signed in-toto or Witness attestations as external signatures.

## Rule that decided

Frozen contract 3 (migration is documentation only: no converter, adapter, schema extension, new predicate or lossless-equivalence claim) and Task 04's acceptance criteria and cap. Per-entry boilerplate roughly triples what Task 04 must write and two reviewers must check, and buries each row's specific limit.

## Consequences

Task 04 writes the map, appendix and coverage record in this shape, checking each row against the frozen kernel and the cited primary source. Reviewers check sixteen rows, one primary label each, the shared limitations section and every cited limit. A destination publishing evalopt-specific support creates no equivalence.
