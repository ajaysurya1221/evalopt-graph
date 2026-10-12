# 04 primary sources preflight

Status: factual source preparation for Task04 and independent review. This is not a migration design, review acceptance, product evaluation, or reconsideration of the approved STOP decision. Approved frozen route choices remain unchanged. The SLSA v1.2 material below is status context only, not an added route.

Access date for every source below: **2026-10-12 UTC / 2026-10-13 Asia/Kolkata**. The tool clock during retrieval reported `2026-10-12 20:22:56 UTC`. Live primary pages were read through web retrieval. Public GitHub API GETs resolved revisions; immutable raw-source GETs retrieved the ten source files in the receipt table. No authenticated requests, credentials or `.env` reads, network writes, source edits, model/runtime calls, installations, or tests were performed. Only this report was written. Existing kernel facts were not re-explored.

Revision timestamps below are repository commit timestamps, not document publication dates or proof that the live site was built from that exact commit. Immutable source snapshots corroborate the cited content; rendered pages establish the observed current status and product-documentation variant. Unversioned documentation is not an assertion about a tested binary version.

## OPA philosophy

Publisher: Open Policy Agent contributors. Version: current unversioned documentation. Revision: `89ed3cf26b7b8f8b758edc6b26d55efa022c1c85`, commit timestamp `2026-10-12T12:49:16Z`. Sources: [live Philosophy](https://www.openpolicyagent.org/docs/philosophy), [immutable source](https://github.com/open-policy-agent/opa/blob/89ed3cf26b7b8f8b758edc6b26d55efa022c1c85/docs/docs/philosophy/index.md).

Supported capability: services submit queries; OPA evaluates policies and data and returns results. Rego consumes structured data and can return arbitrary structured decisions. Policy management is separated from the service. Context may come from loaded data, query input, or synchronous external-data builtins.

Explicit distinction: authorization and authentication are different; policy may consume authentication results. Non-equivalence inference: a policy result alone does not authenticate supplied facts, prove their truth, establish application enforcement, or provide a fixed five-state acceptance taxonomy. Reproducing a result requires its actual evaluation context; policy text alone is insufficient. Source anchors: the live page's “What is OPA?” and “The OPA Document Model,” and the immutable source's opening authentication distinction.

## OPA decision logs

Publisher/version/revision: same OPA snapshot above. Sources: [live Decision Logs](https://www.openpolicyagent.org/docs/management-decision-logs), [immutable source](https://github.com/open-policy-agent/opa/blob/89ed3cf26b7b8f8b758edc6b26d55efa022c1c85/docs/docs/management-decision-logs.md).

Supported capability: configurable logs record policy query information, input, result, bundle revisions, and metadata for auditing/debugging. `nd_builtin_cache` records nondeterministic builtin input/output mappings intended for debugging and decision replay. Source anchors: immutable lines 64–84.

Explicit limits: the cache can be omitted when it exceeds the upload-size limit (lines 109–113); masking can erase or modify input/result/cache fields (128–216); drop policies and rate limits can omit events (265–305). Non-equivalence inference: logging is not automatically a complete, self-contained replay package, an authenticated observation, or proof of external effects. Bundle revision metadata does not itself contain the referenced policy/data bytes. Conversely, saying OPA has no replay support would contradict the documented cache facility. No claim of universal determinism or complete log retention is supported here.

## in-toto Statement

Publisher: in-toto project. Version: Statement schema `https://in-toto.io/Statement/v1`, current `spec/v1` documentation. Revision: `fd2609c16bcb0ac53443e2b4612977f997e8f9a5`, commit timestamp `2026-09-14T13:38:55Z`. Sources: [current Statement](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md), [immutable Statement](https://github.com/in-toto/attestation/blob/fd2609c16bcb0ac53443e2b4612977f997e8f9a5/spec/v1/statement.md#L1-L65).

Supported capability: the Statement binds a predicate type and its parameters to subject artifacts. Each subject requires a digest; artifact matching is by digest regardless of content type. Name/URI semantics depend on producer/consumer context. `predicateType` identifies predicate semantics; the predicate object can be absent when the type fully describes it.

Non-equivalence inference: a Statement is a typed artifact assertion, not a signature by itself, a claim-support verifier, or a complete acceptance/replay algorithm. Digest binding identifies the addressed bytes; it does not establish the truth of the predicate. Predicate semantics and consumer checks remain necessary.

## in-toto Envelope

Publisher/version/revision: same in-toto snapshot; Envelope specification recommends DSSE v1.0 and links DSSE tag `v1.0.2`. Sources: [current Envelope](https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md), [immutable Envelope](https://github.com/in-toto/attestation/blob/fd2609c16bcb0ac53443e2b4612977f997e8f9a5/spec/v1/envelope.md#L1-L58).

Supported capability: the outer layer handles serialization and authentication through signatures. The signature covers payload and payload type; standard DSSE payloads contain base64-encoded JSON Statements. Consumers obtain authenticated predicate information by verifying signatures and parsing the signed Statement; media-type labels alone are not authoritative predicate identifiers.

Non-equivalence inference: successful cryptographic verification authenticates a signed assertion relative to accepted keys/trust rules. It does not establish predicate truth, source correctness, claim entailment, policy satisfaction, or that an external action occurred. An unsigned record hash is not a substitute for an envelope signature, and an envelope does not supply application-specific acceptance semantics or replay.

## Witness policies and verification

Publisher: in-toto Witness contributors. Version: current unversioned policy documentation; documented policy payload type `https://witness.testifysec.com/policy/v0.1`. Revision: `1eaafd56616bdf6c136e80ab92a9a0944e6c0ced`, commit timestamp `2026-09-21T18:33:19Z`. Sources: [live Policies](https://witness.dev/docs/docs/concepts/policy/), [immutable policy documentation](https://github.com/in-toto/witness/blob/1eaafd56616bdf6c136e80ab92a9a0944e6c0ced/docs/concepts/policy.md#L1-L51).

Supported capability: signed policies specify trusted functionaries, expected attestations, and embedded Rego checks. Verification checks collection signatures/trust roots, signer-to-step authorization, optionally trusted timestamps, configured material/product consistency between steps, and Rego results. Invalid collection signatures exclude those collections. Exit zero denotes policy satisfaction; other exits cover error or policy failure. Policies have expiration, and expired policies fail evaluation.

Non-equivalence inference: trusted signatures and metadata predicates do not independently establish semantic truth, honest signers, hidden correctness, or deployed behavior. Policy expiration is distinct from a general evidence-age rule. The documented exit convention does not establish an equivalent five-state decision taxonomy, exact reason codes, or byte-identical decision replay. This preflight did not execute Witness or validate an integration. Anchors: “Verification Process” and “Schema.”

## GitHub rulesets

Publisher: GitHub. Version: current rendered GitHub.com documentation at the `/en/repositories/` URLs below, not a pinned server release. Source revision: `4b1c2131e25f98e22d54e2e3c450cf7285d469f3`, commit timestamp `2026-10-12T18:37:08Z`. Primary sources: [About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets), [Available rules](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets); immutable sources: [About](https://github.com/github/docs/blob/4b1c2131e25f98e22d54e2e3c450cf7285d469f3/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets.md), [Available](https://github.com/github/docs/blob/4b1c2131e25f98e22d54e2e3c450cf7285d469f3/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md#L170-L194). Source templates contain product-conditionals and reusable content; the rendered variant governs claims here.

Supported capability: configured rules govern targeted branches, tags, and pushes. Applicable protections aggregate; the stricter overlapping rule applies. Active rules enforce; disabled rules do not. Bypass permissions may be granted. Required checks can gate merging, and their expected source can be restricted to a selected GitHub App. Strict checks require the branch to be current with its base; loose checks do not.

Explicit limit: write-capable people/integrations can set check states; expected-App restrictions narrow accepted sources. Non-equivalence inference: green status is an assertion by the accepted check producer, not proof of test quality or semantic truth. Rulesets enforce configured repository operations; they do not define general evidence semantics, signed evidence envelopes, or deterministic decision replay. Reading documentation proves no particular repository has those protections enabled. No repository configuration was inspected or changed.

## SLSA VSA: retired v1.0 reference and exact status context

Publisher: SLSA project / OpenSSF, hosted under the Linux Foundation. The approved cited reference is [SLSA v1.0 Verification Summary Attestation](https://slsa.dev/spec/v1.0/verification_summary), observed **Retired** on the access date. Its predicate identifier is `https://slsa.dev/verification_summary/v1`; this identifier is not a pin to the v1.0 document. Immutable source: [v1.0 snapshot](https://github.com/slsa-framework/slsa/blob/7d5078a986b4783bc8eab32b8e2804187b4cdbb0/spec/verification_summary.md), revision `7d5078a986b4783bc8eab32b8e2804187b4cdbb0`, commit timestamp `2026-04-13T11:26:37Z`.

Supported historical capability: a verifier reports artifact verification against policy, including a result and SLSA levels, allowing consumers to delegate trust. Consumers must accept specific signer/verifier pairs. `inputAttestations` is optional; when nonempty it must describe all attestations used and include their digests. The v1.0 policy descriptor requires a URI, not a mandatory policy digest. Source anchors: “Model,” “verifier,” “policy,” and “inputAttestations” (immutable lines 119–175).

Non-equivalence inference: delegated verification is not independent policy replay. Optional evidence references and a policy URI alone do not guarantee complete replay inputs. A verifier's signed success assertion is not semantic truth or a replacement for trusting the verifier.

Status context only: [v1.1 VSA](https://slsa.dev/spec/v1.1/verification_summary) was also observed **Retired**, while [v1.2 VSA](https://slsa.dev/spec/v1.2/verification_summary) was observed **Approved** and current. Do not generalize retirement of the cited v1.0 document to all VSA versions. The v1.2 “How to verify” section requires more than signature validity: subject, predicate type, verifier identity, intended resource, result, and expected levels are checked. It explicitly excludes protection against a compromised verifier. This status evidence does not change approved routes.

Context revisions: [v1.1 immutable source](https://github.com/slsa-framework/slsa/blob/3e02e587beb414f69b07310eb2ab9f0049b624a6/spec/verification_summary.md), revision `3e02e587beb414f69b07310eb2ab9f0049b624a6`, `2026-04-13T11:24:50Z`; [v1.2 immutable source](https://github.com/slsa-framework/slsa/blob/ae7fc76215004e8fae250c877eff8919bf048e3b/spec/verification_summary.md#L273-L318), revision `ae7fc76215004e8fae250c877eff8919bf048e3b`, `2026-04-14T09:47:40Z`. Version retirement/approval above was read from the rendered official pages; source snapshots preserve specification content.

## Immutable-source retrieval receipts

SHA-256 values below were computed over the raw bytes returned by public `raw.githubusercontent.com` GETs at the exact revisions linked above. They identify this source retrieval only; they are not publisher signatures or claims about deployed software. Raw files were held in memory and not saved separately.

| Source | Lines | Retrieved raw-content SHA-256 |
| --- | ---: | --- |
| OPA Philosophy | 208 | `45994eb4259a0acfb00e276cd1a005adf8598d3658eb31e48af3d5ce329cb535` |
| OPA Decision Logs | 316 | `7c73cc040f357e129229cebc616fc82bd23a27719a06acc5e814f1fa99ba4040` |
| in-toto Statement | 73 | `cbe684a18b812b8b613d9202eb43b2ea24477f91a2ad6ca5be935185a455ebea` |
| in-toto Envelope | 110 | `c02c65880ccc117bbdecc6c916d5108541c1a864de67f8f9082efbaf15265d11` |
| Witness Policies | 257 | `fb544966139983d9288c247384af73e0a79259b6f8f111cfd84b6d1660882dd1` |
| GitHub About rulesets | 72 | `ad074c0507552b396bd5d506a7e80875c5664dd7e6f0e496f5a1dbc1bd039810` |
| GitHub Available rules | 372 | `e86f78f0f8ccca0aa3a8608f1c90f9797f9ed4e8f40739892038613c77bb084e` |
| SLSA v1.0 VSA | 294 | `0c3de8a496fc9a98c125a8897794dc91535fbf48fb7892046c06668da89e0717` |
| SLSA v1.1 VSA, status context | 418 | `306dddca4ab124e3dbe646260db5bbdddd1c577505767ab3e30ca86c18bece59` |
| SLSA v1.2 VSA, status context | 432 | `71adb7cc46a537c5a9b81fa8b14ae11cbc61ac91cc62c66197d1c1da8d92ccb0` |

Finite conclusion: these primary sources substantiate the capabilities and limits stated above. They do not establish a working migration, feature parity, a passing conformance suite, an active hosted protection, authenticated truth, or a replacement decision/replay contract. No acceptance verdict is issued.
