# Proposal 03-fable-interface — Public migration interface contract

- Decision: Public migration interface (PLAN.md Section F, row 1).
- Author: Fable xhigh (requested model `claude-fable-5-1`, requested effort xhigh).
- Stage: blind proposal for comparison. Not an ADR. Not public documentation.
- Lane: `winddown/20261013/03`, worktree `wt-semantics-03`, branch base `4383cd6`.
- Source semantics: baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`. All kernel line references below are to that baseline.
- Written: 2026-10-12, about 19:55Z.
- Inputs used: `plan/exec/tasks/03-proposals-brief.md`; `plan/exec/PLAN.md` Sections B, C, F; `plan/exec/CONTRACT.md`; `docs/architecture.md`; `README.md`; `SECURITY.md`; `CONTRIBUTING.md`; `CHANGELOG.md`; `pyproject.toml`; `src/evalopt_graph/__init__.py`, `kernel.py`, `attestation.py`, `harbor_adapter.py`; `tests/test_kernel.py` test names.
- Deliberately not read: the research memo, any Astra proposal, any other model's proposal, the four portfolio repositories, any external standard's live page.

## 1. What this proposal decides and what it cannot change

Decides: the structure of the capability map that Task 04 writes to `docs/migration.md`, the non-equivalence label scheme, the per-entry migration-instruction format, the source-reference appendix format and the coverage record.

Cannot change (PLAN.md Section F): the ten stable exports, any schema identifier, reason codes, serialization, replay, fail-closed precedence, zero runtime dependencies. No converter, adapter, predicate, schema extension or example mapping file may be created. STOP is fixed.

## 2. Independently checked facts (frozen kernel at `fc3045d`)

These are what the labels in Section 4 are grounded in. Each is verifiable by reading the cited lines.

- K1. Ten exports. `kernel.py` `__all__` and `__init__.py` `__all__` list exactly: GovernancePolicy, ClaimRecord, EvidenceRequest, EvidenceMaterial, EvidenceAttestation, SupportAssessment, EvidenceAuthority, AcceptanceInput, AcceptanceDecision, evaluate_acceptance. `EvidenceMaterial` is an alias of `attestation.RetrievedArtifact` (`kernel.py:32`). `__version__` is `"0.1.0"`.
- K2. Two different five-value status vocabularies exist. Decision statuses are `{ACCEPTED, BLOCKED, UNVERIFIED, UNSUPPORTED, FAILED}` (`kernel.py:33`). Attestation statuses are `{VERIFIED, BLOCKED, UNVERIFIED, UNSUPPORTED, FAILED}` (`attestation.py:22-28`). `VERIFIED` is never a decision status; `ACCEPTED` is never an attestation status. Support relations are a third vocabulary `{SUPPORTS, CONTRADICTS, INSUFFICIENT, NOT_ASSESSED}` (`attestation.py:29-35`).
- K3. Precedence is fixed and fail-closed (`kernel.py:536-546`, `docs/architecture.md:67-75`): malformed input → `FAILED` with no evidence hashes; any block → `BLOCKED`; any observed gate or score failure → `FAILED`; any unavailable required mechanism → `UNSUPPORTED`; any incomplete required evidence → `UNVERIFIED`; otherwise `ACCEPTED` with the single reason `policy_satisfied`. `FAILED` therefore has two distinct causes that only the reason codes separate.
- K4. Reason codes present in source: `invalid_observation_time`, `invalid_attestation_record`, `invalid_support_record`, `duplicate_attestation`, `duplicate_support_assessment`, `duplicate_claim`, `evidence_from_future`, `duplicate_gate_observation`, `required_gate_unavailable:<gate>`, `required_gate_failed:<gate>`, `tests_weakened`, `evaluator_unavailable`, `quality_threshold_not_met`, `unresolved_blocking_contradiction`, `potential_critical_claim_conflict:<id>:<id>`, `required_claim_missing:<id>`, `central_claim_disqualified:<id>`, `central_claim_contradicted:<id>`, `central_claim_stale:<id>`, `central_claim_unverified:<id>`, `critical_criterion_unverified:<index>`, `policy_satisfied` (`kernel.py:429-546`). They are evalopt identifiers with no external registry.
- K5. Hash binding. Every record hash is SHA-256 over canonical JSON: sorted keys, compact separators, `ensure_ascii=False`, `allow_nan=False`, UTF-8 (`attestation.py:44-51`). Text canonicalization is `utf8-nfc-lf@1` (`attestation.py:37`). Record identifiers are `att-`/`sup-` plus the first 24 hex characters of the hash of the record without its id (`attestation.py:226, 301, 422, 479`). `AcceptanceDecision.record_sha256` covers schema, status, reasons, policy hash, input hash and evidence hashes (`kernel.py:271-281`).
- K6. No signatures anywhere. The only cryptographic import is `hashlib.sha256` (`attestation.py:12`). A search of `src/evalopt_graph` for HMAC, DSSE, Sigstore or key types finds only prose and "failure signature" strings. `SECURITY.md:44` states the kernel is not a signature system. A record hash identifies content; it does not identify a producer, prove possession of a key, or protect the policy from whoever controls the policy.
- K7. Replay is recomputation equality: `replay(policy, input_)` returns `self == evaluate_acceptance(policy, input_)` (`kernel.py:301-302`). `validate()` checks schema, status membership and the record hash only (`kernel.py:292-299`). `README.md:19`: replay establishes consistency with the stored input, not the truth of the input.
- K8. Record authority. A support record can count only if the verifier pair is in `allowed_verifiers`, the attestation status is `VERIFIED`, the attestation's `policy_sha256` is in `allowed_authority_policies`, both record hashes are in `authorized_record_sha256`, and the trust tier meets `minimum_trust` (`kernel.py:376-390`). All allowlists are plain fields of `GovernancePolicy` (`kernel.py:55-57`); their protection is the host's job (`docs/architecture.md`, "The host owns").
- K9. Freshness. A `VERIFIED` attestation retrieved after `observed_at` makes the input malformed (`evidence_from_future`, `kernel.py:449-455`). A `freshness_required` attestation older than `max_evidence_age_seconds` is stale and yields `central_claim_stale:<id>` (`kernel.py:399-404, 514`). There is no clock source in the kernel; both timestamps are host-supplied strings.
- K10. Claim support is lexical. The only shipped verifier is `("evalopt.lexical_support", "2")` (`attestation.py:475-476`; default allowlist `kernel.py:55`). `SUPPORTS` requires an exact normalized match of claim and selected text (`attestation.py:374`). It is not entailment, not semantic verification, and not a judgment about the world.
- K11. The host supplies every observation. Gate results are host strings; only `"PASS"` passes, `None`/`"NOT_CONFIGURED"` is unsupported, anything else fails (`kernel.py:461-466`). `tests_weakened` is a host boolean (`kernel.py:468`). `EvidenceMaterial` is host-retrieved bytes with a host-supplied locator and time (`attestation.py:124-131`). `EvidenceAuthority.issue` consumes material "already retrieved by a host" (`kernel.py:307`). The kernel runs nothing, fetches nothing and enforces nothing.
- K12. Deprecated host surfaces. `__init__.py` lazily resolves 69 historical root names via `_LEGACY`; the modules `graph`, `cli` (console script `evalopt`), `providers`, `codex_bridge`, `research_mode`, `claim_ledger`, `evidence_adapters` (plus seven compatibility adapter names re-exported lazily from `attestation.py`), `harbor_adapter` and related helpers are outside `__all__`. `docs/architecture.md:104-107` and `README.md:183` call them deprecated compatibility surfaces "for one migration cycle".
- K13. Schema identifiers are all project-local: `evalopt.governance-policy.v1`, `evalopt.acceptance-input.v1`, `evalopt.acceptance-decision.v1`, `evalopt.evidence-attestation.v1` (shared by attestation and support records), `evalopt.evidence-authority.v1`, `evalopt.claim-identity.v1`, and the Harbor adapter's `evalopt.harbor-observation.v1`, `evalopt.run-identity.v1`, `evalopt.harbor-decision.v1`. None is an in-toto predicate type, an OPA input contract, or any external schema.
- K14. No public document in the repository currently mentions OPA, in-toto, Witness, SLSA, GitHub rulesets or any of the four portfolio projects. The migration map is therefore the first and only source of those statements.

## 3. Items taken from the brief and not independently verified here

- B1. SLSA VSA v1.0 is marked Retired. Stated in the brief and PLAN Section B with the URL `https://slsa.dev/spec/v1.0/verification_summary`. Task 04 must record a dated check against that page before the public map says it.
- B2. The domains of Actseal, Dorian, Frontier Scout and ARCI as summarized in the brief. Tasks 06 and 07A–07D verify against each repository.
- B3. Any memo finding. The memo was not read at this stage. Memo-derived sentences may appear in public prose only as the maintainer's decision, never as an independently checked fact (Task 03 constraint).

## 4. Contract rules (normative for Task 04 and its reviewers)

- I-1. Roster closure. The map has exactly sixteen entries: the ten exports in `__all__` order, then the six topics in the brief's order (terminal states/reasons; serialization/hash binding; replay; host authentication/signatures; freshness/record authority; deprecated host surfaces). Each entry heading uses the roster name verbatim. No entry is merged, split or added. The coverage record is a sixteen-row table whose first column repeats those headings.
- I-2. Four labels, each with a decision test and a required sentence form:
  - `ANALOGY` (conceptual analogy): the destination has a construct that serves a similar purpose. Required form: "`<evalopt construct>` is analogous in purpose to `<destination construct>`; it is not that construct." An `ANALOGY` entry must carry at least one `NOT-EQUIVALENT` statement.
  - `HOST` (host responsibility): the kernel never performed this; the host always did. Required form: "evalopt never did X; the host did X; there is nothing to migrate from evalopt for X." A destination may be named only as where hosts commonly do X.
  - `PROJECT` (project-specific semantics): the meaning exists only in the frozen kernel source and tests. Required form: "Defined only by `<file:line>` at `fc3045d`; no destination; preserved by pinning `evalopt-graph==0.1.x` and storing policy, input and decision together."
  - `NOT-EQUIVALENT` (unsupported equivalence): an equivalence a reader might assume and the map explicitly denies. Required form: "`<X>` is not `<Y>`: `<reason with kernel or appendix reference>`."
  Every entry carries one primary label and may carry secondary labels. Labels are printed in a fixed-width tag at the start of each entry so reviewers can grep them.
- I-3. Closed destination set. The only destinations a entry may name are those in the accepted routing contract (proposal `03-fable-boundary` or its ADR). An entry may say "destination: none". No entry may introduce a tool, standard, library or project outside that set, even as "see also".
- I-4. Prohibited vocabulary in any sentence about a mapping: "equivalent", "drop-in", "lossless", "automatic", "converter", "converts to", "1:1", "conforms to", "implements <standard>", "compatible with <standard>", "signed", "verified by <tool>", "certified", "endorsed", "supersedes", "successor". Permitted: "analogous in purpose to", "serves a similar purpose as", "hosts commonly use", "is not represented in", "would need to be re-authored as".
- I-5. Five-state rule. The decision states appear only as the precedence list in K3, in that order, with the reason codes in K4. Any table that places evalopt states beside another tool's outcomes must be captioned "illustrative analogy, not a mapping" and must state at least: (a) `FAILED` has two causes (malformed input; observed failure) separated only by reason codes; (b) the `UNSUPPORTED`/`UNVERIFIED` distinction (mechanism unavailable versus evidence incomplete) has no counterpart in a pass/fail vocabulary; (c) precedence means the same facts can yield a different status in a tool that reports the first failure or aggregates; (d) attestation `VERIFIED` is not decision `ACCEPTED` (K2). The map promises no automatic or lossless mapping of the five states anywhere.
- I-6. Hash rule. Every mention of a hash, digest or `*_sha256` field says it is a content digest that binds bytes or records and is not a signature, does not identify a producer, and does not protect an allowlist from whoever controls the policy (K5, K6, K8). The phrase "exact-record authorization" must be followed, on first use, by "a host-protected allowlist, not a trust root".
- I-7. Attestation rule. In evalopt, "attestation" means an unsigned, content-bound record issued in-process from host-supplied material (K6, K11). Every entry that uses the word disambiguates it, in the same paragraph, from signed attestations in the in-toto and SLSA sense. Attestations are never described as truth, correctness, provenance of a build, or proof that a source is trustworthy.
- I-8. Replay rule. Replay is recomputation equality against stored policy and input (K7). The map never calls it an audit, a proof, a verification of the run, or evidence that the host ran the checks. The required sentence is: "Replay shows that this decision is the one the frozen kernel produces for this stored policy and input. It shows nothing about whether the input was true."
- I-9. Migration-instruction format. Each entry ends with three fixed sub-headings: "To keep evalopt behaviour" (pin `0.1.x`; store policy, input and decision together; nothing changes); "To move the job" (name the job, name the destination from I-3, say the policy or record must be re-authored in the destination's own constructs; no file conversion is offered); "What does not carry over" (a list). Instructions contain no code other than links to the existing README example; no scripts; no partial converters.
- I-10. Source references. A single appendix lists every external source with: key, title, publisher, URL, version or revision, access date, and a status note (for example "Retired", "current", "repository README at commit <sha>"). Every external statement in the map cites a key. The map contains no unresolved research citation markers of any kind.
- I-11. Evidence labelling. Each entry's kernel-meaning sentence cites `file:line` at `fc3045d`. Each external statement cites an appendix key. Any sentence that comes from the brief or the memo without an independent check is suffixed "(maintainer decision)" or "(stated in brief; checked <date>)". Sentences without one of these three forms are not permitted in the normative parts of the map.
- I-12. No new artifacts. The deliverable is one Markdown map, its appendix and the coverage record. No JSON Schema, example records in other formats, predicate definitions, Rego, policy files, or test fixtures are added. `src/`, `tests/`, `bench/` are untouched (Task 02 preservation control).
- I-13. Deprecated surfaces entry. Lists the modules named in K12 and refers to the 69 lazy names by reference to `_LEGACY` rather than claiming a destination for each. States: retained unchanged in `0.1.1`; no new features; orchestration is host-owned; no destination is recommended for the compatibility loop, provider clients, Codex bridge, research loop, claim ledger, filesystem adapters or the Harbor verifier mapping.
- I-14. Compatibility statement. The map says that `v0.1.1` changes no kernel behaviour relative to baseline main `fc3045d` except the version literal, and that main already differs from the `v0.1.0` tag; the inherited changes are disclosed by reference to the CHANGELOG, not restated. The map never says "byte-identical to v0.1.0".
- I-15. Claim-support limit. Every entry touching claims or support states K10 in one sentence: the shipped verifier is exact lexical matching; broader entailment was never provided and is not routed anywhere.
- I-16. Memo separation. The map's introduction has a two-sentence provenance note: which statements are kernel facts (file references), which are maintainer decisions (STOP), and which are external citations (appendix keys). It links the STOP decision record rather than restating its reasoning.

## 5. Templates

Entry template (exact sub-heading names are part of the contract):

```text
### <Roster name>                       [PRIMARY-LABEL] [secondary labels]
Kernel meaning (fc3045d): <one or two sentences> (<file:line>)
Disposition: <label sentence in the required form from I-2>
Destination: <from the closed set> | none
Not equivalent: <X> is not <Y>: <reason> (<ref>)
To keep evalopt behaviour: ...
To move the job: ...
What does not carry over: - ... - ...
Sources: <appendix keys> | none
```

Coverage record (sixteen rows, in roster order):

```text
| # | Roster entry | Primary | Secondary | Destination | Kernel ref | Reviewed by (Codex / Fable) |
```

Appendix row:

```text
| Key | Title | Publisher | URL | Version/revision | Accessed | Status note |
```

## 6. Proposed dispositions for the sixteen entries

Proposed only. Task 04 verifies each against the frozen kernel and the cited primary source; reviewers may change a label with a stated reason.

| # | Entry | Primary | Secondary | Destination | Key non-equivalence |
|---|---|---|---|---|---|
| 1 | GovernancePolicy | PROJECT | ANALOGY | OPA (policy as data); GitHub required checks (for `required_gates` only) | Not a Rego policy; not a ruleset; allowlists are host-protected fields, not a trust root (K8) |
| 2 | ClaimRecord | PROJECT | ANALOGY | Dorian (code-claim warrants) | A claim record is a hashed statement of text, type, subject and stance (`claim-identity.v1`); it is not a warrant and carries no warrant state |
| 3 | EvidenceRequest | HOST | PROJECT | none | Proposal fields from an untrusted producer; not an in-toto subject; expected hashes are hints the authority checks, not signatures |
| 4 | EvidenceMaterial | HOST | — | none | Host-retrieved bytes with host-supplied locator and time; not an attestation, not provenance |
| 5 | EvidenceAttestation | PROJECT | ANALOGY, NOT-EQUIVALENT | in-toto / Witness (attestation concept only) | Unsigned; not an in-toto Statement; no predicate type; binds retrieved content and a selection, not a build or a source's correctness (K5, K6) |
| 6 | SupportAssessment | PROJECT | NOT-EQUIVALENT | none | Lexical exact match by `evalopt.lexical_support/2`; not entailment; not a verification result in any standard's sense (K10) |
| 7 | EvidenceAuthority | PROJECT | HOST, ANALOGY | in-toto / Witness (policy that constrains acceptable attestations, concept only; verify on access) | A set of adapter policies applied in-process to host material; it retrieves nothing and signs nothing |
| 8 | AcceptanceInput | HOST | PROJECT | OPA (an input document, concept only) | Project-local schema; gate strings and `tests_weakened` are host assertions the kernel cannot check (K11) |
| 9 | AcceptanceDecision | PROJECT | ANALOGY, NOT-EQUIVALENT | SLSA VSA v1.0 as historical prior art only (Retired, B1); OPA decision document (concept only) | Unsigned; five states are not PASSED/FAILED; `record_sha256` is not a signature |
| 10 | evaluate_acceptance | PROJECT | ANALOGY | OPA (deterministic evaluation of policy over input, concept only) | Precedence and reason codes are evalopt's; nothing re-implements them |
| 11 | Terminal states/reasons | PROJECT | NOT-EQUIVALENT | none | No automatic or lossless mapping of the five states (I-5); reason codes have no external registry (K4) |
| 12 | Serialization/hash binding | PROJECT | NOT-EQUIVALENT, ANALOGY | in-toto (artifact digest sets, concept only) | Canonical JSON SHA-256 is a content digest, not a signature and not an envelope (K5, K6) |
| 13 | Replay | PROJECT | NOT-EQUIVALENT | none | Recomputation equality; not audit, proof or evidence of execution (K7) |
| 14 | Host authentication/signatures | HOST | NOT-EQUIVALENT | in-toto / Witness (signed attestations for software artifacts); GitHub (platform authentication behind merge enforcement) | The kernel has no signature, key or identity concept (K6); a record hash never authenticates a producer |
| 15 | Freshness/record authority | PROJECT | HOST | none | Timestamps and allowlists are host-supplied and host-protected (K8, K9); the kernel has no clock and no trust root |
| 16 | Deprecated host surfaces | HOST | PROJECT | none | Orchestration, providers, bridges, adapters and the Harbor mapping are host-owned; retained unchanged; nothing in the route table replaces them (K12) |

## 7. Reviewer checklist for Task 04 output

1. Sixteen headings, roster names verbatim, roster order; coverage record has sixteen rows and matches.
2. Every entry has a primary label tag and the required sentence form for that label.
3. Every `ANALOGY` entry has at least one `NOT-EQUIVALENT` line.
4. Grep for each prohibited term in I-4 returns nothing in normative text.
5. Every state table carries the I-5 caption and its four points; `VERIFIED` never appears as a decision status.
6. Every hash mention satisfies I-6; the word "signature" appears only in negations or in the host-authentication entry about external tools.
7. Every "attestation" paragraph disambiguates per I-7.
8. Replay sentence per I-8 present, no "audit"/"proof" wording.
9. Every external statement has an appendix key; the appendix has access dates; the VSA row says Retired with a dated check.
10. No new files under `src/`, `tests/`, `bench/`; `python3 -B plan/exec/preservation.py` passes; `git diff --check` passes.
11. Introduction has the I-16 provenance note; no memo wording presented as fact.

## 8. Reopening conditions

The interface contract is reopened only by an ADR when one of these occurs. None is expected during this run.

- A cited primary source changes status (as VSA did). The entry's appendix row and status note update; the label does not become stronger.
- A destination publishes an evalopt-specific mapping, predicate or importer. That does not create equivalence; mentioning it requires an ADR and the `NOT-EQUIVALENT` lines stay.
- The roster would change. Under STOP the exports and schemas cannot change, so this is a defect in the map, not a kernel change.
- A reviewer shows that a kernel fact in Section 2 is wrong at `fc3045d`. The fact is corrected with a line reference and the dependent labels re-checked.
- A security advisory alters what a record hash is relied on for. Wording tightens; it never loosens.

## 9. Alternatives considered and not proposed

- Three labels without `NOT-EQUIVALENT`. Rejected: the brief requires explicit denial of assumed equivalences; a separate label makes those denials greppable and reviewable.
- A "partial mapping" or "lossy mapping" label. Rejected: it reads as a promise of a mapping; the brief forbids promising a mapping of the states.
- A side-by-side state table as the primary presentation. Rejected: even captioned, it anchors readers on equivalence; allowed only as an illustrative aside under I-5.
- Per-export destinations. Rejected: routing is by job (see the boundary proposal); typing a destination per export implies drop-in replacement.
- Machine-readable mapping file. Rejected: a new artifact and a de facto converter; prohibited by STOP and PLAN Section C, frozen contract 3.
