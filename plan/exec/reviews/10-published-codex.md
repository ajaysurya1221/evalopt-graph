REVIEW 10-published — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT

## Decision and observation window

Accept the published-channel evidence for evalopt-graph 0.1.1, independently observed between 2026-10-12 22:59:36.193912 and 22:59:45.086673 UTC. I did not read an eventual Fable publication review before reaching this verdict. This confirms the bounded publication checks below; it does not assert future availability, semantic correctness, adoption or production reliability.

No blocking or nonblocking publication defect was found within this scope. Required changes: none.

## Fresh public state

Fresh read-only GitHub API responses show release ID 411050622 at `https://github.com/ajaysurya1221/evalopt-graph/releases/tag/v0.1.1`, published at 2026-10-12 22:56:37 UTC, draft false and prerelease false. It is the latest release at this observation. The tag ref resolves to annotated object `b5b96001bb2fcc0059183bcc0a2a2151129f1404`, which peels to source `8c8b7f4583a161947578fdd62d4c6658a1956f55`.

Fresh exact-attempt API records bind release run 38317836286, attempt 1, to that source, tag, push event and `.github/workflows/release.yml`. The run is completed/success. All 15 jobs and all 123 reported steps are completed/success; none is skipped, cancelled or pending in that endpoint.

## Independently downloaded bytes

I freshly downloaded all four public GitHub release assets and both PyPI distribution files. The PyPI version endpoint and both file requests returned HTTP 200 without redirect. Its exact two-file roster has version 0.1.1, Python >=3.10, the expected wheel/sdist types and neither file is yanked.

| File | Bytes | Independently computed SHA-256 |
|---|---:|---|
| `evalopt_graph-0.1.1-py3-none-any.whl` | 137354 | `d6cffc1a0f1b56b087805ee18662d11863d6063b231b2d8e97d64a3430c8e739` |
| `evalopt_graph-0.1.1.tar.gz` | 382132 | `2c49351a7c6343b31faf3b9ff2c7359cc51a41f6249559c31f388be600facf10` |
| `SHA256SUMS.txt` | 196 | `7d7661547846d824f0709288d4730a73352903a4e58e9e63e6a68bfd7ca52e22` |
| `evalopt-graph-0.1.1.spdx.json` | 4232 | `9dee6be448e411d3190ea8ae25eb4fef2801feaa8dcdbd9065628c04ea95ff29` |

Every freshly downloaded GitHub asset equals the previously accepted hosted bundle, retained draft bytes and root's post-publication download. Both fresh PyPI archives equal those same hosted/GitHub bytes and root's PyPI downloads. Actual sizes and digests match both public channels' metadata. The checksum manifest exactly covers the two archives. Earlier hosted review independently established complete source/archive correspondence, RECORD consistency and path hygiene for these identical bytes; this review does not pretend to have rerun the whole source suite.

## Fresh attestation and install checks

I read and checked all four root native attestation records against the actual public PyPI archive paths, then independently ran four new `gh attestation verify` commands on my own PyPI downloads. All passed with exact predicate filters `https://slsa.dev/provenance/v1` and `https://spdx.dev/Document/v2.3`, repository/signer-workflow restrictions, exact source and signer digests, tag ref and denial of self-hosted runners.

Decoded DSSE payloads equal the returned verified statements. Subject hashes match both actual distribution files. Certificate and provenance claims bind the GitHub Actions issuer `https://token.actions.githubusercontent.com`, repository `ajaysurya1221/evalopt-graph`, source/signer/config digest `8c8b7f4583a161947578fdd62d4c6658a1956f55`, workflow `.github/workflows/release.yml@refs/tags/v0.1.1`, github-hosted runner and exact invocation `https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38317836286/attempts/1`. The signed SPDX predicate equals the public SPDX asset as JSON.

The signed roster still contains `.gitignore` digest `684888c0ebb17f374298b65ee2807526c066094c701bcc7ebbe1c1095f494fc1` alongside the two archives. As established in the hosted review, this matches the local one-byte uv marker, but the hosted marker itself was not retained or independently recovered. The extra metadata subject does not invalidate the two individually verified archive bindings. The SPDX document inventories two archives, not all three subjects or a full dependency tree.

I reran artifact hygiene on the fresh PyPI files, created another isolated environment outside the source checkout, installed the exact wheel offline with --no-deps, and passed the installed version, ten-export API, serialization/replay and CLI smoke. The module resolves to that environment's site-packages, with evalopt-graph its only installed distribution. Root's separately retained online PyPI clean-install command also exited zero; I distinguish that supplied execution from my own fresh-download/offline-install check.

## Evidence and limits

Sixteen independent commands exited zero, plus three successful direct HTTPS reads; no check was skipped. Private evidence is under `plan/artifacts/10-published-codex/`. Receipt SHA-256 `1da0559571d2cc093d247b3086b4fcc49c98a6ab60b5d04cfba3500bc37527dc`; command-index SHA-256 `48d4fa14a045196d68b93804a5ef960c1d76afd11bf816619a0d24478f1abb1f`; captured PyPI metadata SHA-256 `6b9a89b2c31df70343253d89520acce3e25793f0301ba7963ed6db987a7948c4`.

These checks verify GitHub Sigstore workflow attestations on bytes served by PyPI; they do not constitute independent verification of separate PyPI publisher attestations. No deployment approval, source/ref/settings mutation, model call or public write occurred. The source worktree remained clean. Final report/privacy review and other-repository PR dispositions remain separate closeout work.
