REVIEW 10-hosted-artifacts — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT

## Exact hosted bundle reviewed

Accept the inspected hosted artifact bytes for release run `38317836286`, attempt 1, source `8c8b7f4583a161947578fdd62d4c6658a1956f55`, annotated tag `v0.1.1` with tag object `b5b96001bb2fcc0059183bcc0a2a2151129f1404`. This is an artifact verdict before deployment approval, not a claim that PyPI or the GitHub release has been published. I did not read the fresh Fable review before this verdict.

| Retained bundle/draft asset | Bytes | Independently computed SHA-256 |
|---|---:|---|
| `evalopt_graph-0.1.1-py3-none-any.whl` | 137354 | `d6cffc1a0f1b56b087805ee18662d11863d6063b231b2d8e97d64a3430c8e739` |
| `evalopt_graph-0.1.1.tar.gz` | 382132 | `2c49351a7c6343b31faf3b9ff2c7359cc51a41f6249559c31f388be600facf10` |
| `SHA256SUMS.txt` | 196 | `7d7661547846d824f0709288d4730a73352903a4e58e9e63e6a68bfd7ca52e22` |
| `evalopt-graph-0.1.1.spdx.json` | 4232 | `9dee6be448e411d3190ea8ae25eb4fef2801feaa8dcdbd9065628c04ea95ff29` |

## Findings by severity

No blocking artifact defect found. One bounded scope observation is recorded below: both signed statements include a third `.gitignore` subject in addition to the two distributions. This does not invalidate the independently checked subject bindings for these distributions, and no artifact or workflow change is required for this verdict.

## Actual source, archive and channel correspondence

The read-only `wt-publication-10` HEAD matches the exact source, remains clean, and the local annotated tag object peels to it. I read the actual archive bytes and compared every shipped source file against this Git commit: all 36 wheel source files and all 119 sdist source files match exactly. The complete source rosters match the configured inclusion rules. Wheel ZIP CRC, unique member names, safe relative paths and regular-member checks pass; no symlink, special member, absolute path or traversal entry is present. Operational plan records, private logs/campaigns, environments, Git metadata and research/results worktrees are excluded. A literal private-user-path scan of every member also found no match; this is a bounded hygiene check, not a universal secrecy assertion.

All 41 wheel RECORD rows cover the exact member roster and have consistent populated digests and sizes. RECORD establishes internal consistency, not producer authentication. Wheel METADATA and sdist PKG-INFO are byte-identical; metadata binds version 0.1.1, Python >=3.10, MIT and no unconditional runtime dependencies. The license and raw README metadata body equal committed source bytes.

The retained release bundle contains exactly the two distributions, checksum file and SPDX asset. Each is byte-identical to its independently compared retained GitHub draft asset. The draft metadata reports v0.1.1, draft true, prerelease false and exactly those four assets, with matching sizes and digests. Root's successful bundle-download receipt names run 38317836286 and `release-bundle`; its retained artifact roster binds artifact ID 11777777419 to the same source/run. No inference is made from the draft's targetCommitish string alone.

SHA256SUMS has exactly the two expected distribution entries, both recomputed successfully. The SPDX document is a two-archive inventory: both file/package checksum pairs, version and verification-code values match the actual bytes. Its timestamp matches source epoch 1791844401. I reran the pinned source generator at that epoch and obtained byte-identical SPDX output. This is not a full dependency inventory or proof of semantic correctness.

## Native attestation verification and exact identity

I inspected all four original root `gh attestation verify` command/output records: provenance and SPDX for each distribution, all exited zero. I independently reran the four verifications with repository, signer workflow, exact source and signer digest, tag ref and denial of self-hosted runners. All four fresh commands exited zero. I then independently repeated both SPDX checks with the exact `--predicate-type https://spdx.dev/Document/v2.3`; both exited zero. The actual signed predicate URI is versioned v2.3, not the unversioned initial filter spelling.

For every result, I decoded the DSSE payload and checked equality to the returned verified statement, each distribution's actual subject hash and the complete three-subject roster. Certificate claims bind the GitHub Actions issuer `https://token.actions.githubusercontent.com`, repository `ajaysurya1221/evalopt-graph` (ID 1306570239; owner ID 74526464), workflow `.github/workflows/release.yml`, ref `refs/tags/v0.1.1`, source/build-signer/config digest `8c8b7f4583a161947578fdd62d4c6658a1956f55`, github-hosted runner and invocation `https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38317836286/attempts/1`.

The provenance predicate additionally binds that exact resolved Git dependency, workflow/ref/repository and run invocation. The signed SPDX predicate is JSON-equal to the retained SPDX asset. Verified transparency timestamps are 2026-10-12 22:39:54 UTC for provenance and 22:39:55 UTC for SPDX. These native signature checks and identity constraints authenticate the workflow statements about the named bytes; they do not turn their content into a semantic truth oracle.

## Additional `.gitignore` subject

Both statements name `.gitignore` with SHA-256 `684888c0ebb17f374298b65ee2807526c066094c701bcc7ebbe1c1095f494fc1`, plus exactly the wheel and sdist hashes above. This digest matches the local pinned-uv distribution marker consisting of the single byte `*`, without a newline. The hosted marker itself was not retained in the release bundle, so I do not claim independent recovery or inspection of its hosted contents.

The tagged workflow attests `dist/*`; its upload step explicitly excludes hidden files. The observed bundle/draft remains exactly four assets, with no extra distribution or executable payload. The checksum and SPDX files intentionally inventory the two archives, while the signed subject roster is broader. Because both required archives are individually digest-bound and independently verified, this extra metadata subject does not undermine their source/workflow authentication. Do not describe the signed roster as exactly two subjects or the SPDX document as a complete inventory of all three subjects. Preserve the observation without modifying the existing attestation or assets.

## Independently executed finite checks

Artifact hygiene verifier, fresh offline no-deps wheel installation into a new environment outside the source checkout, installed ten-export/API/serialization/replay/CLI smoke, isolated import/distribution identity and SPDX reproduction all passed. The only distribution in that environment is evalopt-graph and its module resolves to its own site-packages. Ten primary commands and two exact-SPDX follow-ups exited zero with no skips. I did not repeat the entire source suite or use its prior success as a substitute for checking these hosted bytes.

Private independent evidence is under `plan/artifacts/10-hosted-codex/`. Archive receipt SHA-256 `3eb1b828124384236cf4c539bd2c8d813c03a3a0ef1f7232e2e5377b3329b7be`; primary command receipt `e5bc380c3da50d31b2a69c01bda26f51b585946e7c85b3aa93c8380ed2941435`; exact-SPDX command receipt `4199e5c34e0fbda443376065deb0cee0352847d5e8fec00f4f66f536c0757d69`.

## Required changes and remaining gates

No changes required for this actual-byte artifact verdict. Fresh independent Fable acceptance, native exact-deployment eligibility, current workflow/predecessor checks and post-publication GitHub/PyPI byte verification remain separate obligations. I performed no deployment approval, source/ref/settings edit, model call, publication action or replacement of evidence. Root's earlier exploratory assumptions about a newline marker and an unversioned returned predicate are analysis corrections, not artifact mutations or failures of the retained successful native verifications.
