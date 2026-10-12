# 04 kernel semantics preflight

Status: factual preparation for Fable04 and independent review. This is not review acceptance, a migration design, or approval of a replacement implementation.

Source baseline: `fc3045dbda29c1d274747329ceb6724a783b0df7` (`fc3045db`). The completed inspection read baseline bytes with `git show`; the worktree HEAD at inspection was `766d1ef576d70f3524b22f513e2693c1609e9480`. The inspected `kernel.py`, `attestation.py`, and `docs/architecture.md` had no diff from that baseline. All line references below describe the baseline. This report persists those completed findings without a new exploration pass.

Scope and limits: read-only source and relevant test-source inspection, with no source edits, test execution, external retrieval, model/runtime calls, or benchmark execution. Test-source references establish specified cases, not a fresh passing run. These facts characterize the finite baseline implementation and do not establish semantic truth, authenticated execution, deployed behavior, external-tool equivalence, or independent reproduction.

## Ten stable exports

The package-root stable export list is exactly the ten symbols below: [src/evalopt_graph/__init__.py](../../../src/evalopt_graph/__init__.py), lines 21–32. The kernel repeats this list at [src/evalopt_graph/kernel.py](../../../src/evalopt_graph/kernel.py), lines 549–560.

| Export | Responsibility | Non-equivalence and limitation | Baseline source |
| --- | --- | --- | --- |
| `GovernancePolicy` | Immutable requirements for gates, claims, trust, evaluator threshold, evidence age, permitted verifier identities, permitted adapter-policy hashes, and exact authorized record hashes. | Declares requirements; does not run checks or protect policy from an untrusted producer. Defaults require no gates, evaluator, or particular claim. | [kernel.py](../../../src/evalopt_graph/kernel.py):44–104 |
| `ClaimRecord` | Claim ID, text, type, subject, stance, and linked assessment IDs. | Claim digest binds stripped text/type/subject/stance, excluding the claim ID and assessment links. The complete input hash includes those excluded fields. A claim record is not confirmation. | [kernel.py](../../../src/evalopt_graph/kernel.py):107–137; [attestation.py](../../../src/evalopt_graph/attestation.py):75–84 |
| `EvidenceRequest` | Proposal containing adapter ID, locator, selector, and optional expected raw hash/final locator. | Contains no authority or trust-setting fields. Exactly one selector is required at issuance, not construction. Optional expected hash/locator checks apply only when supplied and truthy. | [attestation.py](../../../src/evalopt_graph/attestation.py):156–181, 505–525 |
| `EvidenceMaterial` | Alias of `RetrievedArtifact`: immutable bytes plus host-supplied final locator, retrieval time, and media type. Serialization base64-encodes bytes. | Does not retrieve material, authenticate it, or establish source correctness. | [kernel.py](../../../src/evalopt_graph/kernel.py):32; [attestation.py](../../../src/evalopt_graph/attestation.py):123–153 |
| `EvidenceAttestation` | Binds adapter policy, declared processing/retrieval metadata, raw/normalized/selected hashes, selected text, and issuance status. | Record validation checks structural/hash consistency. Without original material, it cannot rehash original bytes or prove retrieval occurred. Attestation `VERIFIED` differs from acceptance `ACCEPTED`. | [attestation.py](../../../src/evalopt_graph/attestation.py):184–268 |
| `SupportAssessment` | Binds one exact claim digest to one attestation record, with relation, verifier ID/version, and reason. | Hash validation does not rerun the verifier. Built-in support uses normalized exact text matching, a polarity heuristic, and subject checks; it is not general entailment or truth verification. | [attestation.py](../../../src/evalopt_graph/attestation.py):271–309, 363–381 |
| `EvidenceAuthority` | Immutable collection of controller-supplied adapter-policy mappings. `issue(request, material, observed_at=..., claim=...)` derives an attestation and lexical support assessment from host-retrieved material. Unknown adapters issue `UNSUPPORTED` records. | Does not retrieve material or authenticate the controller. Distinct from the deprecated retrieving facade with the same class name. | [kernel.py](../../../src/evalopt_graph/kernel.py):305–359 |
| `AcceptanceInput` | Immutable typed observations: time, gates, criteria, claims, contradictions, evidence, host-reported test weakening, optional evaluator score. | Validates/normalizes structure; does not discover test weakening, execute tests, grade output, or authenticate observations. Several malformed constructions raise `ValueError` before evaluation. | [kernel.py](../../../src/evalopt_graph/kernel.py):140–246 |
| `AcceptanceDecision` | Status/reasons and hashes of policy, full input, used evidence, and decision. | `validate()` checks schema, known status, and self-hash. `replay()` recomputes acceptance and compares the whole decision. Those checks are different. | [kernel.py](../../../src/evalopt_graph/kernel.py):249–302 |
| `evaluate_acceptance` | Pure deterministic acceptance transition with ordered terminal precedence. Derives load-bearing claims from required IDs, central claim types, critical-text detection, and criterion overlap. | Does not run a workflow or choose the operational action following its result. | [kernel.py](../../../src/evalopt_graph/kernel.py):410–546; [architecture.md](../../../docs/architecture.md):29–35 |

## 1. Five terminal states and reason codes

Precedence is: malformed input → `FAILED`; explicit block → `BLOCKED`; observed gate/score failure → `FAILED`; missing required mechanism → `UNSUPPORTED`; insufficient required evidence → `UNVERIFIED`; otherwise `ACCEPTED`. Only reasons in the winning category are returned, not every accumulated issue. Source: [kernel.py](../../../src/evalopt_graph/kernel.py):536–546.

| State/category | Exact reason codes |
| --- | --- |
| `FAILED`, malformed | `invalid_observation_time`, `invalid_attestation_record`, `invalid_support_record`, `duplicate_attestation`, `duplicate_support_assessment`, `duplicate_claim`, `evidence_from_future`, `duplicate_gate_observation` |
| `BLOCKED` | `tests_weakened`, `unresolved_blocking_contradiction`, `potential_critical_claim_conflict:<left>:<right>` |
| `FAILED`, observed failure | `required_gate_failed:<gate>`, `quality_threshold_not_met` |
| `UNSUPPORTED` | `required_gate_unavailable:<gate>`, `evaluator_unavailable` |
| `UNVERIFIED` | `required_claim_missing:<id>`, `central_claim_disqualified:<id>`, `central_claim_contradicted:<id>`, `central_claim_stale:<id>`, `central_claim_unverified:<id>`, `critical_criterion_unverified:<index>` |
| `ACCEPTED` | `policy_satisfied` |

Generation sites: [kernel.py](../../../src/evalopt_graph/kernel.py):437–488, 493–546. The malformed-input precedence applies to successfully constructed input values; it does not turn all constructor errors into a terminal decision.

Missing or `NOT_CONFIGURED` required gates are unavailable. Every other result except exact `PASS` is a failure. An authorized contradicting support assessment makes its load-bearing claim `UNVERIFIED`, rather than automatically yielding `BLOCKED`. An attestation's own `BLOCKED` or `FAILED` status does not automatically become the acceptance status: a structurally valid unusable record generally leaves a relevant claim unverified. Source: [kernel.py](../../../src/evalopt_graph/kernel.py):378–407, 461–466, 507–518.

The five attestation statuses (`VERIFIED`, `BLOCKED`, `UNVERIFIED`, `UNSUPPORTED`, `FAILED`) and four support relations (`SUPPORTS`, `CONTRADICTS`, `INSUFFICIENT`, `NOT_ASSESSED`) are separate vocabularies from the five acceptance states. Source: [attestation.py](../../../src/evalopt_graph/attestation.py):22–39.

## 2. Serialization and hash binding

Record hashes use SHA-256 over sorted, compact UTF-8 JSON, retaining Unicode and prohibiting NaN. Material normalization is separately UTF-8/NFC/LF. Lexical support comparison additionally case-folds and collapses whitespace. These normalizations are not interchangeable. Sources: [attestation.py](../../../src/evalopt_graph/attestation.py):44–55, 316–319, 363–365.

Attestation and assessment IDs use a 24-hex hash prefix; record binding uses the complete SHA-256 digest. An assessment binds the exact attestation record hash and claim digest. Sources: [attestation.py](../../../src/evalopt_graph/attestation.py):422–424, 452–481.

Decision `input_sha256` covers the entire serialized input. Decision `evidence_sha256` contains deduplicated records used by evaluation, including eligible contradicting records, rather than a complete inventory of all evidence supplied. Malformed-input decisions omit used evidence. Sources: [kernel.py](../../../src/evalopt_graph/kernel.py):215–246, 264–280, 395–406, 536–546.

Serialization is not a uniform `from_dict` API: policy, claim, and stable authority expose `to_dict` without a matching classmethod, while the request, material, attestation, assessment, input, and decision provide `from_dict`. Deserialization does not establish record validation or authorization. Sources: [kernel.py](../../../src/evalopt_graph/kernel.py):99–104, 127–137, 229–246, 282–302, 325–329; [attestation.py](../../../src/evalopt_graph/attestation.py):138–181, 211–218, 287–294.

## 3. Replay

`AcceptanceDecision.replay(policy, input_)` is equality against `evaluate_acceptance(policy, input_)`. It establishes reproducibility under the supplied records. It does not rerun tests, re-retrieve material, rerun lexical issuance, refresh timestamps, or establish truth of host observations. A self-consistent fabricated decision can satisfy `validate()` while failing replay. Source: [kernel.py](../../../src/evalopt_graph/kernel.py):292–302; host storage/replay boundary: [README.md](../../../README.md):125–127.

The completed inspection read deterministic round-trip/replay test cases at [tests/test_kernel.py](../../../tests/test_kernel.py):98–110. Those test sources were not executed during this preflight.

## 4. Host authentication and signatures

The stable schemas/functions provide content hashes, not a signature/key/identity verification protocol. Protection of controller policy and authorized records belongs to the host, along with retrieval, isolation, credentials, persistence, and operational enforcement. In-process evaluation is explicitly not an authentication or isolation boundary. Sources: [architecture.md](../../../docs/architecture.md):29–35, 111–117, 125–130; stable record fields and validation: [kernel.py](../../../src/evalopt_graph/kernel.py):44–58, 249–302; [attestation.py](../../../src/evalopt_graph/attestation.py):184–309.

Consequently, `EvidenceAuthority`, a policy hash, a source-class label, or a valid record hash does not establish an authenticated signer, verified remote identity, protected execution, source correctness, or deployed behavior. Attestation binds bytes and declared processing; authority depends on host-controlled policy and authorization. Sources: [architecture.md](../../../docs/architecture.md):52–63, 125–128.

## 5. Freshness and record authority

Claim-support eligibility requires all of the following: valid assessment and attestation records; `SUPPORTS` or `CONTRADICTS`; exact claim digest; exact attestation-record binding; permitted verifier ID/version; `VERIFIED` attestation; permitted adapter-policy hash; both exact attestation and assessment hashes authorized; sufficient trust. Naming an allowed adapter or verifier does not authorize a new record. Source: [kernel.py](../../../src/evalopt_graph/kernel.py):373–390.

Freshness is relative to `AcceptanceInput.observed_at`, not the machine clock. Empty material retrieval time is replaced by issuance `observed_at`. Future verified evidence is malformed. Maximum age is checked only for supporting evidence whose attestation declares `freshness_required=True`, with strict `age > limit`. Eligible contradictions are processed before the age check and therefore remain contradicting even when old. Sources: [attestation.py](../../../src/evalopt_graph/attestation.py):499–504; [kernel.py](../../../src/evalopt_graph/kernel.py):391–407, 450–455.

Successful replay therefore does not establish present-day freshness. Trust in the supplied timestamps and protection of the authorization allowlists remain host responsibilities. The source tests explicitly distinguish structurally valid records from authorization at [tests/test_kernel.py](../../../tests/test_kernel.py):191–197; no fresh test run was performed here.

## 6. Deprecated host surfaces

Historical graph, standalone CLI, provider clients, Codex bridge, research loop, and filesystem adapters remain deprecated compatibility surfaces for one migration cycle. They are outside the ten stable package-root exports and cannot define a second stable acceptance authority. Sources: [README.md](../../../README.md):182–184; [architecture.md](../../../docs/architecture.md):101–107; lazy root compatibility imports: [src/evalopt_graph/__init__.py](../../../src/evalopt_graph/__init__.py):34–117.

The same-name authority distinction is consequential: `evalopt_graph.EvidenceAuthority` imports the pure stable authority from `kernel.py`, while `evalopt_graph.attestation.EvidenceAuthority` lazily resolves to the deprecated retrieving facade. The facade accepts adapter objects, owns a clock, retrieves through `attest`, and offers revalidation. It is not a drop-in equivalent of stable `issue`. Sources: [src/evalopt_graph/__init__.py](../../../src/evalopt_graph/__init__.py):7–18; [attestation.py](../../../src/evalopt_graph/attestation.py):658–676; [evidence_adapters.py](../../../src/evalopt_graph/evidence_adapters.py):161–250.

The compatibility host is process-local and provides no durable checkpoint guarantee. Source: [architecture.md](../../../docs/architecture.md):129. Compatibility availability is not a stable API promise, a durable workflow guarantee, or evidence of equivalent behavior in an external replacement.
