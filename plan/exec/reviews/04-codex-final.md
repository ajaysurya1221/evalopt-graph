REVIEW 04 — Reviewer Astra (Codex independent review lane) | Verdict ACCEPT

Reviewed commit: `8f60a3a40cd0f1f1100211009f25cbf920b11dd6` in `wt-semantics-04`, independently inspecting the revision from `80816612c0ad9ccae4350095869e9fa77515187e`. Kernel baseline remains `fc3045dbda29c1d274747329ceb6724a783b0df7`. Review date: 2026-10-13. This accepts the three Task04 documentation files at this exact commit; it does not authorize or assert a release, interoperability, conformance, adoption, or reconsideration of STOP.

## Findings by severity

No unresolved actionable finding in the revision. All six findings in `04-codex-01.md` are resolved:

| Finding | Independently checked resolution |
|---|---|
| F1 — verifier compromise | `docs/migration-sources.md:25` now says v1.2 does **not protect against verifier compromise**, matching the previously inspected primary source. The v1.0/v1.1 Retired and v1.2 Approved observations remain version-specific and dated; v1.2 remains status context. |
| F2 — deserialization | `docs/migration.md:72` distinguishes constructor/type/shape/base64 checks from record-hash validity, replay and policy authorization. `docs/migration-coverage.md:31` cites the validating `AcceptanceInput.from_dict` constructor path and strict `RetrievedArtifact.from_dict` base64 path. Neither wording claims that these checks establish authentication or truth. This matches the unchanged baseline already inspected at `kernel.py:153–242` and `attestation.py:123–153`. |
| F3 — Witness identities | `docs/migration.md:67` and coverage row 7 now name policy-authorized functionaries as permitted collection signers under public keys or certificate trust rules. They no longer equate attestor programming interfaces with signed identities. This matches the previously retrieved Witness policy snapshot. |
| F4 — finite absence claims | Map rows 6, 11 and 13 (`66`, `71`, `73`), the label definition (`56`), corresponding coverage rows, and appendix `78–82` bind non-equivalence to the inspected sources and identify absence as interpretation. The universal claim that no other tool replays evalopt decisions is gone. OPA cache-based replay and its limits remain acknowledged. |
| F5 — distinct allowlist types | Map row 1 (`61`) and coverage row 1 (`20`) distinguish verifier ID/version pairs from the SHA-256 authority-policy and record allowlists, matching `kernel.py:55–57, 89–97`. |
| F6 — receipt traceability | `docs/migration-sources.md:23` now links both GitHub ruleset source files at `4b1c213…`; line `25` supplies the v1.1 official URL, immutable `3e02e58…` snapshot and commit timestamp; receipt row `71` points to that context. The revisions and existing receipt digests match the independent primary-source preflight. |

The additional requested checks also pass:

- **Fable source-key precision:** map rows 9 and 14 (`69`, `74`) and coverage rows 9 and 14 (`28`, `33`) omit `SLSA-VSA-1.2`. Its use is confined to the explicit version-status note and appendix context. Coverage row 9 states that boundary. The added Actseal README line-13 reference at appendix `31` matches the pinned README inspected in the preceding independent review.
- **Durable release-status wording:** map `12–18` identifies the baseline independently of publication, links the public release records, and makes no assertion that v0.1.1 has or has not been published. This resolves the stale prospective wording without creating release authorization.
- **No semantic regression in unchanged rows:** claim-digest versus whole-input scope, three distinct normalization operations, full-digest binding versus shortened IDs, five terminal states and winning-category reasons, exact-record authorization, supplied-time freshness, contradiction-before-age handling, future VERIFIED evidence, and the deprecated retrieving authority remain as independently checked against the baseline in `04-codex-01.md` and the kernel preflight. No compatibility implementation is claimed or supplied.

## Required changes

None for Task04 at the reviewed commit.

## Verification and limits

- Read the complete revision diff and all three resulting documents; compared the fixes with the earlier independent findings and source preflight. `04-r1.md` was treated as author evidence, not acceptance.
- `git rev-parse HEAD` returned the exact reviewed SHA; `git status --short` was clean. The revision changes exactly `docs/migration.md`, `docs/migration-sources.md`, and `docs/migration-coverage.md`. `git diff --check 80816612c0ad9ccae4350095869e9fa77515187e 8f60a3a40cd0f1f1100211009f25cbf920b11dd6` passed.
- A read-only stdlib consistency check confirmed sixteen rows in each map/coverage table; matching entry names, order, labels and external keys; ten stable exports in baseline `__all__` order; label counts 5/4/4/3; twelve defined external keys; all sixteen relative-link occurrences resolve; no substantive row cites VSA v1.2.
- A direct Git comparison confirmed the nine cited baseline files (`__init__.py`, `kernel.py`, `attestation.py`, `evidence_adapters.py`, architecture, README, SECURITY, kernel tests and CHANGELOG) remain byte-identical to `fc3045d`. The full 75-file preservation gate passed in the initial review; root is separately rerunning preservation and scope for this revision. This review does not claim that separate rerun completed.
- Read-only HTTP HEAD checks returned 200 for the four added navigation URLs: the public evalopt releases page, the pinned GitHub Available rules source, the SLSA v1.1 official page, and its pinned source. HEAD success establishes link reachability only, not release content or source semantics. Existing primary-source content, timestamps, digests and observed version statuses reuse the prior independent retrieval recorded in `04-primary-sources-preflight.md`; this review did not refresh their content or execute those products.
- No product test suite was rerun for this prose-only revision. No source, target document, model, credential, `.env`, tag, asset or external service was modified. A lookup found no worktree-root `AGENTS.md`; the applicable workspace instructions and `plan/exec/CONTRACT.md` govern this assigned review. This review file is the only write.

## Follow-ups

Task05/08 must complete the inherited CHANGELOG disclosure, including the `624ed11` scalar-row fix, before a release; the archive decision already identifies it. Root retains integration, preservation and release gates. Acceptance here is confined to Task04 documentation at the immutable reviewed commit.
