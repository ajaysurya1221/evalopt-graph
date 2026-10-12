REVIEW 09 — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT

## Scope and immutable identity

Accept the local candidate artifact qualification for source `95b61a3ff9cbe6dc62acde75cf475958546aafc9` in `wt-verification-09`. The checkout was clean before and after this review. This is local artifact acceptance, not permission to merge, tag, approve deployment or claim publication.

| Candidate | Bytes | Independently recomputed SHA-256 |
|---|---:|---|
| `evalopt_graph-0.1.1-py3-none-any.whl` | 137354 | `40d7a69ffed18309ac4c873b291e652f73af14d73c593bef9fdae15343604ba3` |
| `evalopt_graph-0.1.1.tar.gz` | 382094 | `dba71cc7c0ab4ed20083d8aa33a941a5d7310eeaf732cceb96022527ed591f98` |

## Findings by severity

No blocking or nonblocking candidate defect found in this finite qualification scope. No source or artifact changes are required by this review.

## Independently verified evidence

I read the actual archives rather than relying on the executor inventory. Both archives have unique, safe relative member names and contain no symlinks or special entries. Wheel ZIP CRC validation passed. All 36 wheel source files match the pinned Git source bytes; its source roster is exact. All 119 sdist source files match their committed paths and the configured inclusion roster; its sole additional metadata file, PKG-INFO, equals wheel METADATA. The license and raw UTF-8 README metadata body match their committed source bytes.

The wheel's 41 RECORD entries cover its exact member roster; every populated digest and size is internally consistent. This is corruption/integrity checking, not producer authentication. Metadata identifies evalopt-graph 0.1.1, Python >=3.10 and MIT, with no unconditional runtime dependency. The exact archive rosters exclude the operational plan, private logs, campaign directories, environments, Git metadata and research/results worktrees. No literal private user path was found in any member. This bounded exclusion check is not an assertion that arbitrary code or prose is globally secret-free.

In a newly created private verification directory outside the source checkout, I reran `scripts/verify_artifacts.py` and installed the exact local wheel with pinned uv 0.11.29, `--offline --no-deps`, into a fresh Python 3.13 environment. `scripts/verify_installed_release.py --version 0.1.1` passed. The module resolved to that environment's site-packages; its only installed distribution was evalopt-graph. The expected ordered ten-export API, version, ACCEPTED fixture, serialization/replay and CLI version passed. These fixtures do not establish every behavioral outcome or semantic truth.

I independently recomputed the archive SHA-1/SHA-256 values and checked each SPDX file/package entry, version, verification-code calculation and timestamp against commit epoch 1791842144. Regenerating the existing SPDX document with that epoch produced byte-identical output. It is an unsigned two-archive inventory, not authenticated producer provenance or a full transitive dependency inventory.

All six separately recorded verification commands exited zero, with no skipped command. Retained private evidence is under `plan/artifacts/09-codex-independent/attempt-02/`: archive receipt SHA-256 `ece829edba926d1478d3b98bb4a9e0de3df2eb9c80d3f0351627bb4138e63352`, command receipt SHA-256 `3e711a5fd393d4166f0faa15d0c2026b3adb6ce527425766621fc4ee79ce219d`.

## Executor record review and retained errors

I inspected the original qualification command records and logs, including the full 14-stage runbook, release identity, build, corrected Twine and clean-install records. Those records show 422 passing tests with no skipped-test summary, three demos, 32 authored conformance cases and preservation of 75 protected baseline files after the permitted version normalization. The expected failing scenario inside the smoke script is asserted by that script; the enclosing smoke gate passed. I did not independently rerun the full suite in this artifact review, and do not attribute the executor's suite as my own execution.

The initial `uv x` invocation exited 2 before Twine ran; its original record is preserved. The subsequent supported `uv tool run --from twine==6.2.0 twine check` passed the unchanged candidate bytes. My earlier publication preflight had repeated the unsupported spelling; the current decision record and this review supersede that command without rewriting its history.

My first archive-inspection attempt also exited 1: default `email.message_from_bytes` payload decoding altered non-ASCII README text before comparison. The corrected check compares the raw metadata body bytes, which equal the committed README exactly (18282 bytes). The candidate was never modified. A read-only search initially used the wrong SBOM script filename and exited 2; the actual `generate_spdx_sbom.py` was then read and used. These reviewer-tool errors and their diagnosis are retained privately; they are not candidate defects or hidden successes.

## Required changes

None for the inspected local candidate artifacts.

## Follow-ups and limits

Fresh Fable artifact acceptance, final integration/privacy and rendered-link review, exact-head hosted checks, merge/main validation, annotated tag and release workflow, exact hosted-bundle review, native deployment eligibility and post-publication byte/attestation checks remain separate gates. A later hosted build may produce different bytes and needs its own review. No network publication, live workflow, tag, push, model call or source edit occurred in this review. No existing evidence was overwritten.
