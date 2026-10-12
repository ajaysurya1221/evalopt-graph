# Task 04 independent review, round 1

REVIEW 04 — Reviewer Astra (Codex independent review lane) | Verdict REVISE | Findings by severity below | Required changes F1–F6 | Follow-ups: re-review the revised immutable commit; this is not release approval.

Reviewed immutable commit: `80816612c0ad9ccae4350095869e9fa77515187e` in `/Users/ajay/Developer/.evalopt-worktrees/wt-semantics-04`.

Review basis: actual three-file commit, accepted Task03 ADRs and Task04 contract, unchanged kernel baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`, the independently prepared primary-source receipts, and decisive source reads. No target files were edited. Only this central review record was written. No model/runtime call, credential or `.env` access, package installation, or source change occurred. Public source requests were read-only.

## Findings

### F1 — P2: VSA text reverses the compromised-verifier limitation

Location: `docs/migration-sources.md:25` at the reviewed commit.

The sentence says the v1.2 verification procedure “excludes a compromised verifier.” That reads as a protection provided by verification. The primary specification explicitly says a VSA does not protect against compromise of its verifier and consumers must choose trusted verifiers carefully. This reverses a material trust boundary in an appendix intended to prevent signature-equals-truth claims.

Evidence: [SLSA v1.2 immutable source, lines 316–318](https://github.com/slsa-framework/slsa/blob/ae7fc76215004e8fae250c877eff8919bf048e3b/spec/verification_summary.md#L316-L318), independently retrieved in the source preflight; [current official VSA page](https://slsa.dev/spec/v1.2/verification_summary#how-to-verify).

Required fix: replace the ending with “does not protect against verifier compromise.” Preserve Approved v1.2 as status context only and Retired v1.0 as the cited historical reference. No route change is requested.

### F2 — P2: Deserialization does perform validation

Location: `docs/migration.md:70`, entry 12; reflect the correction in `docs/migration-coverage.md:31`.

“Deserializing validates or authorizes nothing” is false. `AcceptanceInput.from_dict()` calls the constructor and constructs nested `ClaimRecord` values; these invoke schema, shape, type, range, and nonempty-field checks. `RetrievedArtifact.from_dict()` uses strict base64 decoding and calls a constructor that rejects empty final locators and media types. This also contradicts map entry 8's correct constructor-validation description.

Evidence at the baseline: `kernel.py:153–213, 229–242`; `ClaimRecord` validation at `kernel.py:116–125`; `attestation.py:130–153`. In contrast, attestation/assessment deserialization does not call `validate_record_hash()`, and decision deserialization does not call `validate()` or replay.

Required fix: distinguish construction/decoding validation from record integrity and policy authorization. A precise compact replacement is: “Deserialization may enforce constructor, type/shape, and base64 checks; it does not by itself establish record-hash validity, replay, or policy authorization.” Keep the existing warning that `from_dict` is not uniform.

### F3 — P2: Witness attestors are not signed identities

Location: `docs/migration.md:65`, entry 7; inspect corresponding coverage text at `docs/migration-coverage.md:26`.

“Witness attestors and functionaries ... are signed identities under Witness trust roots” conflates evidence-producing interfaces with authorized signers. Witness defines an attestor as a programming interface that records asserted facts in a versioned schema. Functionaries are separately represented by trusted public keys or certificate roots and constraints; collection signers must map to the configured step's functionary. An attestor is not thereby an authenticated identity, and direct public keys need not be X.509 trust roots.

Evidence: [immutable Witness attestor documentation, lines 1–13](https://github.com/in-toto/witness/blob/1eaafd56616bdf6c136e80ab92a9a0944e6c0ced/docs/concepts/attestor.md#L1-L13), retrieved during this review; [official Attestors](https://witness.dev/docs/docs/concepts/attestor/); [official policy functionary schema](https://witness.dev/docs/docs/concepts/policy/#functionary-object). Access date: 2026-10-12 UTC / 2026-10-13 Asia/Kolkata.

Required fix: either limit the analogy to “Witness policy-authorized functionaries identify permitted collection signers through public keys or certificate trust rules,” or explicitly distinguish attestors from functionaries. Add the attestor primary-source anchor to WITNESS if the term remains. Keep the stable/legacy evalopt authority distinction unchanged.

### F4 — P2: Bound unsupported-equivalence claims to the inspected sources

Locations: `docs/migration.md:71` (entry 13), `docs/migration.md:64` (entry 6), `docs/migration-coverage.md:25`, and source-method wording at `docs/migration-sources.md:78–79`.

“No other tool replays an evalopt decision” is an unbounded ecosystem claim. This review and the supplied evidence examine a finite set of route documentation and pinned sibling sources; they cannot establish absence across all tools. Likewise, “No destination publishes...” and “No routed destination defines a claim-support relation” should be claims about the inspected sources and these exact semantics, not assertions about every capability or publication of the destination projects. The appendix's assertion that every limit is paraphrased from a primary source obscures these reviewer/author inferences: the preflight explicitly distinguished them from documented guarantees.

Required fix: use finite wording, for example: “The inspected route sources provide no supported mechanism for replaying evalopt decision records” and “No equivalent to this exact claim-support relation is established by the inspected sources.” State in the appendix that documented capabilities are source-backed and non-equivalence conclusions are bounded interpretations of that source set. Retain the four approved dispositions, seven routes, and no automatic/lossless mapping rule.

### F5 — P3: Name the hash allowlists instead of calling all allowlists digests

Locations: `docs/migration.md:59` and `docs/migration-coverage.md:20`.

The policy has three different allowlists: `allowed_verifiers` contains `(id, version)` pairs, while `allowed_authority_policies` and `authorized_record_sha256` contain lowercase SHA-256 strings. The unqualified phrases “its allowlists are exact SHA-256 digests” and “allowlists validated as 64-hex lowercase digests” wrongly include the verifier list.

Evidence: baseline `kernel.py:55–57, 89–97`.

Required fix: identify `allowed_authority_policies` and `authorized_record_sha256` as the digest allowlists, with verifier authorization separately using ID/version pairs. No policy or source change is requested.

### F6 — P3: Two retrieval-receipt rows lack their immutable source mapping

Locations: `docs/migration-sources.md:23, 25, 57–58, 69, 71`.

The appendix says every receipt corresponds to the revision linked above, but the SLSA v1.1 receipt has no v1.1 source revision or URL anywhere in the appendix. The GitHub Available rules receipt gives the correct digest but links only the About source at that commit; the live Available URL does not identify the raw snapshot behind that receipt. This leaves the displayed retrieval evidence partially unreconstructible from the public appendix.

Required fix: link the GitHub Available snapshot at `4b1c2131e25f98e22d54e2e3c450cf7285d469f3/content/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets.md`. Either remove the optional v1.1 receipt/status mention or add its official page and immutable `3e02e587beb414f69b07310eb2ab9f0049b624a6/spec/verification_summary.md` source mapping, dated as context only. These pins already exist in the source preflight; no new route/research is needed.

## Verified content and finite limits

- Exactly the three owned documents were added: 233 lines, no source/test/benchmark changes. The target worktree was clean and at the reviewed SHA on inspection.
- The map and coverage record each contain sixteen entries in the required order and the accepted label distribution. The job table preserves all seven approved routes and their order. Sibling README openings were independently read at the four exact pinned commits; their narrow route paraphrases match those sources. The accepted Task06 audit remains the bounded evidence for the wider dependency/import inventory; this review did not repeat that repository audit.
- Claim digest scope versus whole-input scope is accurate. Attestation `VERIFIED`, support `SUPPORTS`, and acceptance `ACCEPTED` remain distinct. The stable material-consuming authority and deprecated retrieving facade are correctly separated apart from F3's external analogy.
- Canonical JSON hashing, material NFC/LF normalization, lexical case-folding/whitespace normalization, ID-prefix versus record-digest scope, full-decision replay equality, and used-evidence subset semantics match the baseline. Constructor/deserialization wording requires F2.
- Freshness is correctly relative to supplied `observed_at`, using strict age comparison only for freshness-required supporting records. Eligible contradictions precede age checks; future verified evidence becomes malformed. Exact-record authorization, claim/attestation binding, verifier identity/version, and trust checks remain distinguished. No product test execution is inferred from these source reads.
- OPA log-cache replay limitations and SLSA version-specific retirement/approval are correctly bounded apart from F1. Hashes are not described as signatures or semantic truth.
- `v0.1.1` remains prospective; the documents do not falsely claim publication or GitHub archival. They promise no support duration or new feature work. CHANGELOG finalization remains Task08's ownership and later gated release work, not this documentation review's approval.

## Independent checks

- `git show --stat --oneline 80816612c0ad9ccae4350095869e9fa77515187e` and `git diff-tree --no-commit-id --name-status -r <sha>`: only `docs/migration.md`, `docs/migration-sources.md`, `docs/migration-coverage.md` added.
- `git diff --check 80816612^ 80816612`: exit 0, no whitespace findings.
- `git diff --name-only fc3045db 80816612 -- src tests bench`: no output.
- After reading its implementation, `python3 -B plan/exec/preservation.py`: exit 0; baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`; 75 protected files; `errors: []`.
- Read-only Python checks over `git show <sha>:<file>`: map 16 numbered rows, coverage 16 numbered rows; no missing relative-link targets; no `/Users/` or `file://` in the three public documents.
- Public unauthenticated HEAD requests for all 32 unique external URLs found in the three reviewed documents: 32 returned HTTP 200, no unresolved result. This establishes reachability at review time, not correctness of every statement or future availability.
- Baseline and primary-source semantics were inspected directly as described above. No full suite, external-tool execution, live-model evaluation, migration prototype, or interoperability certification was run or claimed.

Required next step: revise only the owned documentation for F1–F6, update the paired coverage dispositions where applicable, run the existing prose/scope/preservation checks, and provide a new immutable commit for the two required reviews. Verdict remains REVISE for `80816612c0ad9ccae4350095869e9fa77515187e`.
