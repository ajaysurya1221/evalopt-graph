# Migration map: source appendix

Companion to [migration.md](migration.md). Keys are the ones used in the map and in
[migration-coverage.md](migration-coverage.md).

Retrieval basis. Live pages were read and immutable snapshots retrieved on 2026-10-12 UTC by the
wind-down run's control lane, which recorded the revisions, commit timestamps and raw-content digests
below. Revision timestamps are repository commit times, not publication dates, and do not prove the
live site was built from that commit; rendered pages establish the observed status, snapshots preserve
the content. Unversioned documentation is not an assertion about any tested binary. Sibling heads were
recorded by the run's read-only portfolio audit on 2026-10-12 UTC. No source here establishes a working
migration, feature parity, a passing conformance suite, an endorsement or an adoption claim.

## External sources

| Key | Title | Publisher | URL | Version or revision | Accessed | Status note |
|---|---|---|---|---|---|---|
| OPA-PHIL | Philosophy | Open Policy Agent contributors | <https://www.openpolicyagent.org/docs/philosophy> | Unversioned docs; source revision [`89ed3cf`](https://github.com/open-policy-agent/opa/blob/89ed3cf26b7b8f8b758edc6b26d55efa022c1c85/docs/docs/philosophy/index.md), commit 2026-10-12T12:49:16Z | 2026-10-12 UTC | Current. Services submit queries; OPA evaluates policy and data and returns structured results; policy management is separate from the service; authorization is distinct from authentication, and policy may consume authentication results. A result alone does not authenticate supplied facts or fix a decision taxonomy. |
| OPA-LOGS | Decision Logs | Open Policy Agent contributors | <https://www.openpolicyagent.org/docs/management-decision-logs> | Same revision; source [`management-decision-logs.md`](https://github.com/open-policy-agent/opa/blob/89ed3cf26b7b8f8b758edc6b26d55efa022c1c85/docs/docs/management-decision-logs.md) | 2026-10-12 UTC | Current. Logs record query, input, result, bundle revisions and metadata; `nd_builtin_cache` records non-deterministic builtin input and output for debugging and replay. The cache can be omitted above the upload-size limit; masking can erase or modify fields; drop policies and rate limits can omit events. Neither "no replay" nor "guaranteed full replay" is supported. |
| ITA-STMT | Attestation Framework: Statement (spec/v1) | in-toto project | <https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md> | Schema `https://in-toto.io/Statement/v1`; snapshot [`fd2609c`](https://github.com/in-toto/attestation/blob/fd2609c16bcb0ac53443e2b4612977f997e8f9a5/spec/v1/statement.md), commit 2026-09-14T13:38:55Z | 2026-10-12 UTC | Current. A Statement binds a predicate type and parameters to subject artifacts; each subject requires a digest and matching is by digest. A Statement is a typed artifact assertion, not a signature, a claim-support verifier or an acceptance algorithm. |
| ITA-ENV | Attestation Framework: Envelope | in-toto project | <https://github.com/in-toto/attestation/blob/main/spec/v1/envelope.md> | Recommends DSSE v1.0 and links DSSE `v1.0.2`; snapshot [`fd2609c`](https://github.com/in-toto/attestation/blob/fd2609c16bcb0ac53443e2b4612977f997e8f9a5/spec/v1/envelope.md) | 2026-10-12 UTC | Current. The envelope handles serialization and authentication through signatures covering payload and payload type. Verification authenticates a signed statement relative to accepted keys and trust rules; it does not establish predicate truth or policy satisfaction. |
| WITNESS | Witness repository; Policies (concepts) | in-toto Witness contributors | <https://github.com/in-toto/witness>; <https://witness.dev/docs/docs/concepts/policy/> | Unversioned docs; policy payload type `https://witness.testifysec.com/policy/v0.1`; snapshot [`1eaafd5`](https://github.com/in-toto/witness/blob/1eaafd56616bdf6c136e80ab92a9a0944e6c0ced/docs/concepts/policy.md), commit 2026-09-21T18:33:19Z | 2026-10-12 UTC | Current. Signed policies name trusted functionaries, expected attestations and embedded Rego checks; verification checks collection signatures and trust roots, signer-to-step authorization, optional trusted timestamps, material and product consistency and Rego results; policies expire; exit zero means satisfied. No five-state taxonomy, reason codes or byte-identical replay is documented. Not executed by this run. |
| GH-RULES | About rulesets; Available rules for rulesets | GitHub | <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets>; <https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets> | Rendered GitHub.com docs, not a pinned server release; source revision [`4b1c213`](https://github.com/github/docs/blob/4b1c2131e25f98e22d54e2e3c450cf7285d469f3/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets.md), commit 2026-10-12T18:37:08Z | 2026-10-12 UTC | Current. Rules govern targeted branches, tags and pushes; the stricter overlapping rule applies; bypass permissions exist; required checks can gate merging and their source can be restricted to a selected App; strict checks require an up-to-date branch. A green check is the producer's assertion, not proof of test quality. No repository configuration was inspected. |
| SLSA-VSA-1.0 | Verification Summary Attestation, SLSA v1.0 | SLSA project (OpenSSF) | <https://slsa.dev/spec/v1.0/verification_summary> | v1.0; predicate id `https://slsa.dev/verification_summary/v1` is not a pin to this document; snapshot [`7d5078a`](https://github.com/slsa-framework/slsa/blob/7d5078a986b4783bc8eab32b8e2804187b4cdbb0/spec/verification_summary.md), commit 2026-04-13T11:26:37Z | 2026-10-12 UTC | **Retired** on the access date. Historical prior art only, never a destination. A verifier reports an artifact's verification against policy; consumers must accept specific signer and verifier pairs; `inputAttestations` is optional and the policy descriptor needs a URI, not a digest. Delegated verification is not independent replay. |
| SLSA-VSA-1.2 | Verification Summary Attestation, SLSA v1.2 | SLSA project (OpenSSF) | <https://slsa.dev/spec/v1.2/verification_summary> | v1.2; snapshot [`ae7fc76`](https://github.com/slsa-framework/slsa/blob/ae7fc76215004e8fae250c877eff8919bf048e3b/spec/verification_summary.md), commit 2026-04-14T09:47:40Z | 2026-10-12 UTC | **Approved** on the access date; the v1.1 page was observed Retired. Status context only, not a route: retirement of v1.0 does not generalize to other versions. Its verification procedure checks subject, predicate type, verifier identity, resource, result and levels and excludes a compromised verifier. |

## Sibling projects (independent of evalopt)

| Key | Title | Publisher | URL | Revision | Accessed | Status note |
|---|---|---|---|---|---|---|
| ACTSEAL | Actseal README | ajaysurya1221 | <https://github.com/ajaysurya1221/actseal/blob/111afb3cf0dbab94e7bdf7917e800ba6faaeac0b/README.md> | `111afb3`, six commits after `v1.0.1` | 2026-10-12 UTC | Declares no evalopt dependency and imports none; its NOTICE names evalopt's public design as an influence and includes no evalopt source. Replay there checks consistency and does not authenticate responses or prove label truth, in its own words. |
| DORIAN | dorian README | ajaysurya1221 | <https://github.com/ajaysurya1221/dorian/blob/eeb193792fac8a66b18f5222287a8fcf336dda08/README.md> | `eeb1937`, tag `v1.4.1` | 2026-10-12 UTC | Declares no evalopt dependency, imports none and does not mention evalopt. A claim there is only as strong as its checker, in its own words. |
| FSCOUT | Frontier Scout README | ajaysurya1221 | <https://github.com/ajaysurya1221/frontier-scout/blob/e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c/README.md> | `e34d4a6`, one commit after `v2.2.0` | 2026-10-12 UTC | Declares no evalopt dependency, imports none and does not mention evalopt. Research preview; unsigned receipts cannot authenticate approval, in its own words. |
| ARCI | agent-reliability-ci README and NOTICE | ajaysurya1221 | <https://github.com/ajaysurya1221/agent-reliability-ci/blob/a5adc834f74f5546fa3585b4ce6adfc96e2c37a3/README.md>; <https://github.com/ajaysurya1221/agent-reliability-ci/blob/a5adc834f74f5546fa3585b4ce6adfc96e2c37a3/NOTICE> | `a5adc83`; project version 0.7.0, no PyPI package per its README | 2026-10-12 UTC | Declares no evalopt dependency and imports none. `src/arci/hashing.py` adapts evalopt's canonical JSON hashing helpers from `attestation.py` under MIT with attribution, and its NOTICE records the self-sealing decision pattern from `kernel.py`; both are attributed adaptation inside ARCI's frozen manifest, not a dependency. PASS there means relative non-inferiority, in its own words. |

## evalopt baseline files at `fc3045d`

All `file:line` references in the map and coverage record resolve against these immutable URLs.
`__version__` is `"0.1.0"` at `__init__.py:20` of this commit; main carries changes since the
`v0.1.0` tag, disclosed in the [CHANGELOG](../CHANGELOG.md) and the
[archive decision](decisions/archive-standalone.md).

| File | Immutable URL |
|---|---|
| `__init__.py` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/src/evalopt_graph/__init__.py> |
| `kernel.py` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/src/evalopt_graph/kernel.py> |
| `attestation.py` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/src/evalopt_graph/attestation.py> |
| `evidence_adapters.py` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/src/evalopt_graph/evidence_adapters.py> |
| `architecture.md` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/docs/architecture.md> |
| `README.md` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/README.md> |
| `SECURITY.md` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/SECURITY.md> |
| `tests/test_kernel.py` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/tests/test_kernel.py> |
| `CHANGELOG.md` | <https://github.com/ajaysurya1221/evalopt-graph/blob/fc3045dbda29c1d274747329ceb6724a783b0df7/CHANGELOG.md> |

## Retrieval receipts

SHA-256 over the raw bytes returned for each immutable snapshot at the revision linked above, as
recorded by the control lane on 2026-10-12 UTC. They identify that retrieval only; they are not
publisher signatures and say nothing about deployed software.

| Source | Lines | Raw-content SHA-256 |
|---|---:|---|
| OPA Philosophy | 208 | `45994eb4259a0acfb00e276cd1a005adf8598d3658eb31e48af3d5ce329cb535` |
| OPA Decision Logs | 316 | `7c73cc040f357e129229cebc616fc82bd23a27719a06acc5e814f1fa99ba4040` |
| in-toto Statement | 73 | `cbe684a18b812b8b613d9202eb43b2ea24477f91a2ad6ca5be935185a455ebea` |
| in-toto Envelope | 110 | `c02c65880ccc117bbdecc6c916d5108541c1a864de67f8f9082efbaf15265d11` |
| Witness Policies | 257 | `fb544966139983d9288c247384af73e0a79259b6f8f111cfd84b6d1660882dd1` |
| GitHub About rulesets | 72 | `ad074c0507552b396bd5d506a7e80875c5664dd7e6f0e496f5a1dbc1bd039810` |
| GitHub Available rules | 372 | `e86f78f0f8ccca0aa3a8608f1c90f9797f9ed4e8f40739892038613c77bb084e` |
| SLSA v1.0 VSA | 294 | `0c3de8a496fc9a98c125a8897794dc91535fbf48fb7892046c06668da89e0717` |
| SLSA v1.1 VSA (status context) | 418 | `306dddca4ab124e3dbe646260db5bbdddd1c577505767ab3e30ca86c18bece59` |
| SLSA v1.2 VSA (status context) | 432 | `71adb7cc46a537c5a9b81fa8b14ae11cbc61ac91cc62c66197d1c1da8d92ccb0` |

## Attribution of findings

The overlap and demand conclusions that led to STOP belong to the maintainer's private research
memo, as recorded in [archive-standalone.md](decisions/archive-standalone.md); this appendix does
not re-verify them. Every capability or limit stated above is paraphrased from the cited primary
source, and every evalopt fact from the cited baseline lines.
