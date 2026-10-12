# Migration map

Standalone feature development of evalopt has ended ([archive-standalone.md](decisions/archive-standalone.md)).
This page tells existing users where each evalopt concept goes, without overstating equivalence.
It is documentation only: there is no converter, schema, adapter, predicate type or policy file, and
nothing under `src/`, `tests/` or `bench/` changes. Its shape is fixed by
[migration-interface.md](decisions/migration-interface.md) and its routes by
[routing-boundary.md](decisions/routing-boundary.md). Sources are listed in
[migration-sources.md](migration-sources.md); the checked inventory is
[migration-coverage.md](migration-coverage.md).

Every `file:line` reference below is to the verified public main commit
`fc3045dbda29c1d274747329ceb6724a783b0df7` (`fc3045d`), linked per file in the appendix. The map is
tied to that baseline, not to a release. Release status, including whether the final deprecation
release `v0.1.1` has been published, is tracked separately on the public
[releases page](https://github.com/ajaysurya1221/evalopt-graph/releases) and is not asserted here.
The baseline already differs from the `v0.1.0` tag; the inherited differences are disclosed in the
[CHANGELOG](../CHANGELOG.md) and enumerated in the archive decision.

## Preservation rule

Keep the original policy, input, decision, evidence records (attestations and assessments), the
material they were issued from where you retained it, and the exact evalopt version and commit
together, as one unit. An evalopt record means what it meant under the version that produced it. A
new tool never retroactively authorizes, re-signs or reinterprets old evidence, and an old record
never becomes evidence under a new tool merely by being carried across.

## Where each job goes

Seven jobs, one destination each, in the plan's order. These are job-oriented pointers, not tested
drop-in replacements. The four sibling projects are independent of evalopt and of each other: no
successor, conformance, endorsement or package coupling is claimed. Each paraphrase is checked
against the destination's own primary documentation (keys in the appendix).

| User's job | Destination | What the destination does, in its own terms | Keys |
|---|---|---|---|
| General policy evaluation | OPA | Evaluates policies over structured data and query input and returns structured decisions; optional decision logs record query, input and result, subject to masking, drop policies and size limits. | OPA-PHIL, OPA-LOGS |
| Software provenance and attestation verification | in-toto attestation framework and Witness | A Statement binds a typed predicate to artifact digests; a DSSE envelope carries signatures; Witness verifies signed attestation collections against a signed policy naming trusted functionaries and embedded Rego checks. | ITA-STMT, ITA-ENV, WITNESS |
| Native merge enforcement | GitHub rulesets and required checks | Rulesets apply configured rules to targeted branches and tags, including required status checks and bypass permissions; check states are set by write-capable producers, optionally restricted to an expected GitHub App. | GH-RULES |
| Action-policy qualification | Actseal | Tests a model's action policy under a frozen policy against recorded evaluation evidence and replays that evidence offline; the application owns execution. | ACTSEAL |
| Code-claim warrants | Dorian | Turns explicit code claims into checks sealed beside the code, re-runs affected checks when sources change and revokes the warrant when a load-bearing check fails. | DORIAN |
| PR scope | Frontier Scout | Checks a diff against the base commit's scope policy and compiles the same policy into Claude Code permissions and hooks; a research preview. | FSCOUT |
| Stochastic regression | ARCI | Freezes a repeated experiment, gates a change on relative non-inferiority and exports a replayable failure; its canonical hashing helpers were adapted from evalopt with attribution, as adaptation and not as a dependency. | ARCI |

SLSA Verification Summary Attestations are not a route. The v1.0 page cited by the wind-down memo
was marked Retired when checked on 2026-10-12 UTC and is historical prior art only. The v1.2 page was
marked Approved on the same check; that is version-status context, not a route, and retirement of
v1.0 says nothing about other versions (keys SLSA-VSA-1.0, SLSA-VSA-1.2).

## The sixteen entries

Ten stable exports in `__all__` order, then six cross-cutting topics. Each row has one primary label
from four: **conceptual analogy** (a destination has a comparable idea, with different semantics),
**host responsibility** (the function stays with the host in every route), **project-specific
semantics** (evalopt-defined meaning with no counterpart to carry over) and **no supported
equivalence** (nothing in the inspected route sources covers it). Shared limits that apply to every row appear once, below
the table.

| # | Entry | Label | Nearest concept elsewhere | Row-specific limit | Source at `fc3045d` | Keys |
|---|---|---|---|---|---|---|
| 1 | `GovernancePolicy` | Conceptual analogy | A policy document that an engine evaluates: OPA policy and data, or a Witness policy. | Declares requirements only; defaults require no gate, evaluator or particular claim, and its `allowed_authority_policies` and `authorized_record_sha256` allowlists are exact SHA-256 digests, while `allowed_verifiers` holds verifier ID and version pairs. Protecting the policy from the producer is the host's job. No field translates automatically into Rego or a Witness policy. | `kernel.py:44–104` | OPA-PHIL, WITNESS |
| 2 | `ClaimRecord` | Project-specific semantics | None. An in-toto subject names an artifact by digest, not a stated claim. | The claim digest covers stripped text, type, subject and stance and excludes the ID and assessment links; the whole-input hash includes them. A claim record is a statement to be checked, not a confirmation. | `kernel.py:107–137`; `attestation.py:75–84` | ITA-STMT |
| 3 | `EvidenceRequest` | Host responsibility | Deciding what to fetch and which span to select is pipeline configuration in every route. | Carries no authority or trust field. Exactly one selector is required at issuance, not at construction; expected-hash and final-locator checks run only when supplied and truthy. The request never retrieves. | `attestation.py:156–181, 505–525` | none |
| 4 | `EvidenceMaterial` | Host responsibility | Artifact bytes the host already holds; an in-toto subject digest names such bytes. | Alias of `RetrievedArtifact`: bytes plus a host-supplied final locator, retrieval time and media type, base64-encoded when serialized. Nothing here retrieves, authenticates or shows the source is correct; an empty retrieval time is replaced by the issuance `observed_at`. | `kernel.py:32`; `attestation.py:123–153, 499` | ITA-STMT |
| 5 | `EvidenceAttestation` | Conceptual analogy | An in-toto Statement or a Witness attestation also binds digests to declared processing. | Unsigned. `VERIFIED` is an attestation status, distinct from the support relation `SUPPORTS` and the acceptance state `ACCEPTED`. Record validation checks structure and hash consistency; without the material it cannot rehash the bytes or show that retrieval happened. | `attestation.py:22–28, 184–268` | ITA-STMT, ITA-ENV, WITNESS |
| 6 | `SupportAssessment` | No supported equivalence | No equivalent to this exact claim-to-evidence support relation is established by the inspected sources; that absence is a bounded interpretation of the cited set, not a documented guarantee. | Binds one exact claim digest to one attestation record with a relation, verifier identity and reason. The built-in verifier uses an exact normalized text match, a polarity heuristic and subject grounding; `SUPPORTS` is lexical support, never general entailment or truth. Hash validation does not rerun the verifier. | `attestation.py:29–34, 271–309, 363–381` | none |
| 7 | `EvidenceAuthority` | Project-specific semantics | Witness policy-authorized functionaries are the nearest idea: a Witness policy identifies permitted collection signers through public keys or certificate trust rules. | The stable authority is an immutable set of adapter policies whose `issue()` consumes material the host already retrieved; an unregistered adapter yields `UNSUPPORTED`. It retrieves nothing and does not authenticate the controller. The deprecated facade of the same name under `evalopt_graph.attestation` retrieves through adapters and owns a clock; it is a different object. | `kernel.py:305–359`; `__init__.py:7–18`; `attestation.py:658–676`; `evidence_adapters.py:161–242` | WITNESS |
| 8 | `AcceptanceInput` | Host responsibility | Query input to an engine (OPA); check states reported to a merge gate (GitHub). | The host assembles typed observations: time, gate results, criteria, claims, contradictions, attestations, assessments, host-reported test weakening and an optional score. Construction validates shape and may raise `ValueError` before any decision exists. It discovers nothing, runs no test and authenticates no observation. | `kernel.py:140–246` | OPA-PHIL, GH-RULES |
| 9 | `AcceptanceDecision` | Conceptual analogy | An engine's logged decision (OPA decision log) or a verifier's result record (Witness; the retired SLSA VSA v1.0 as prior art). | Status, reasons and digests of the policy, the whole input, the used evidence and itself. `validate()` checks schema, known status and self-hash; `replay()` is equality with a fresh evaluation. `evidence_sha256` lists records the evaluation used, not every record supplied, and is empty for malformed input. Unsigned. | `kernel.py:249–302, 536–546` | OPA-LOGS, WITNESS, SLSA-VSA-1.0 |
| 10 | `evaluate_acceptance` | Conceptual analogy | Policy evaluation (OPA), policy verification (Witness) or rule enforcement at merge (GitHub rulesets). | A pure function with fixed precedence: malformed, blocked, failed, unsupported, unverified, accepted; only the winning category's reasons are returned. Load-bearing claims come from required IDs, central claim types, critical text and keyword overlap with criteria. It runs no workflow and chooses no follow-on action. | `kernel.py:410–546`; `architecture.md:29–35` | OPA-PHIL, WITNESS, GH-RULES |
| 11 | Terminal states and reason codes | No supported equivalence | OPA returns arbitrary structured results; Witness reports satisfaction or failure by exit status; GitHub checks report check states. None of the inspected sources defines these five states or these reason strings. | `ACCEPTED`, `BLOCKED`, `UNVERIFIED`, `UNSUPPORTED`, `FAILED` and the exact reason codes are evalopt vocabulary with no automatic or lossless mapping. Do not collapse `UNSUPPORTED`, `UNVERIFIED`, `FAILED` and `BLOCKED` into pass or fail. Attestation statuses and support relations are separate vocabularies from the acceptance states. | `kernel.py:33, 437–488, 493–546`; `attestation.py:22–39` | OPA-PHIL, WITNESS, GH-RULES |
| 12 | Serialization and hash binding | Conceptual analogy | Digest sets over artifacts (in-toto); canonical JSON hashing, which ARCI adapted with attribution. | SHA-256 over sorted, compact UTF-8 JSON with Unicode retained and NaN rejected; material normalization is UTF-8, NFC, LF; lexical comparison additionally case-folds and collapses whitespace; the three are not interchangeable. IDs are 24-hex prefixes while binding uses full digests. `from_dict` is not uniform across the ten exports. Deserialization may enforce constructor, type, shape and base64 checks; it does not by itself establish record-hash validity, replay or policy authorization, and no kernel check establishes authentication or truth. A hash is a content digest, never a signature. | `attestation.py:44–55, 316–319, 364–365, 422–424, 479–481`; `kernel.py:215–246, 263–280` | ITA-STMT, ITA-ENV, ARCI |
| 13 | Replay | Project-specific semantics | OPA decision logs can carry a non-deterministic builtin cache intended for replay; Actseal and ARCI define their own replay of their own records. | `replay()` recomputes the decision from the stored policy and input and compares the whole record. It reruns no test, re-retrieves nothing, reruns no lexical issuance, refreshes no timestamp and establishes no truth about observations. A self-consistent fabricated decision can pass `validate()` and still fail replay. The inspected route sources provide no supported mechanism for replaying evalopt decision records; replay is defined only as equality with evalopt's own `evaluate_acceptance` at the pinned version. | `kernel.py:301–302`; `tests/test_kernel.py:98–110`; `README.md:125–127` | OPA-LOGS, ACTSEAL, ARCI |
| 14 | Host authentication and signatures | Host responsibility | DSSE envelopes (in-toto), Witness trust roots and GitHub's expected-App restriction on checks authenticate producers within their own systems. | The kernel has no signing, key management or signature verification; adapter and verifier identifiers are declared strings, and a valid record hash does not establish who produced it. An external signature verifies identity under that system's keys and rules, not that the signed statement is true. In-process evaluation is not an isolation or authentication boundary. | `architecture.md:29–35, 111–117, 125–128`; `SECURITY.md:44–45`; `kernel.py:44–58, 249–302` | ITA-ENV, WITNESS, GH-RULES |
| 15 | Freshness and record authority | Project-specific semantics | Witness policy expiration and trusted timestamps are a different rule, not an evidence-age rule. | A record counts only when both exact record hashes are in `authorized_record_sha256`, its adapter-policy hash and verifier are permitted, the attestation is `VERIFIED`, the claim digest and attestation binding match exactly and trust suffices; naming an adapter or verifier authorizes no record. Age is measured against the supplied `observed_at`, never the wall clock, with strict `age > limit` only for supporting evidence that declares `freshness_required`; eligible contradictions count before the age check; future-dated verified evidence is malformed. Allowlists and timestamps are host-protected inputs, and replay says nothing about present freshness. | `kernel.py:52, 373–407, 450–455`; `attestation.py:499–504`; `tests/test_kernel.py:191–197` | WITNESS |
| 16 | Deprecated host surfaces | No supported equivalence | Unrouted. The seven routes cover jobs, not these modules. | The graph, standalone CLI, provider clients, Codex bridge, research loop, claim ledger, filesystem adapter, Harbor adapter and the retrieving `EvidenceAuthority` facade are deprecated compatibility surfaces outside `__all__`. They receive no feature work, are not stable API or policy authorities and cannot define a second acceptance path. The compatibility host is process-local with no durable checkpoint. No destination is a drop-in for any of them. | `__init__.py:34–117`; `README.md:182–184`; `architecture.md:105–107, 129`; `evidence_adapters.py:161–242` | none |

## Shared limitations

These apply to every row and are stated once.

- There is no automatic or lossless mapping of the five decision states or of any reason code into
  another system. A destination that publishes evalopt-specific support creates no equivalence.
- Every hash in evalopt is a content digest over canonical JSON or bytes. It binds content; it never
  authenticates a producer, and it is never a signature.
- Attestations and support assessments are unsigned records about host-supplied evidence. They are
  not semantic truth, and lexical support is not general entailment.
- `validate()` checks a retained record for schema, status and self-hash consistency; `replay()`
  recomputes a decision from the stored policy and input. Neither reruns tests, re-retrieves
  material or authenticates observations. Neither reruns reality.
- Freshness is relative to the supplied `observed_at`, not the present wall clock. Authorization
  allowlists, timestamps, retrieval, isolation, policy protection and the action taken after a
  decision are host responsibilities in evalopt and remain so under every route.
- Where a destination signs, verification establishes identity under that system's keys and rules.
  It does not establish that the signed statement is true, that a check was sound or that a claim is
  supported.
- Constructors of the stable types can raise `ValueError` for malformed values before any decision
  exists; a raised error is not a decision state.

## Bounded migration checklist

1. Freeze the unit: policy, input, decision, attestations, assessments, retained material, the
   `evalopt_graph.__version__` literal and the kernel commit that produced them. Store them together.
2. Record which stable export produced each record. Read the inherited differences in the
   [CHANGELOG](../CHANGELOG.md) before pinning a version for later replay.
3. Pick the job route from the table above. For each field you carry across, write down which of the
   four labels applies; carry project-specific and unsupported fields as opaque archived data, not as
   translated meaning.
4. Carry status and reasons verbatim as strings next to the original record. Never fold the five
   states into a two-valued result.
5. Treat evalopt digests as content identifiers only. If the destination signs, obtain a signature
   there under its own identity rules; do not describe an evalopt hash as a signature.
6. Replay old decisions only with the pinned evalopt version. Expect a new tool to produce its own
   decisions over its own inputs, not to replay evalopt's.
7. Keep host responsibilities with the host: retrieval, isolation, credentials, policy protection,
   authentication of observations and the operational action that follows a decision.
8. Leave old evidence under its original versions and limitations. Nothing in this map upgrades it.
