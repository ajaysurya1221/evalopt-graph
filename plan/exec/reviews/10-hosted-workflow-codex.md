REVIEW 10-HOSTED-WORKFLOW — Reviewer Astra | Verdict ACCEPT

**Accepted scope:** release-run/tag/source/workflow identity and successful predecessor CI, build and draft-release lanes only. This does **not** approve the deployment, inspect or accept package contents, verify downloaded artifact bytes or attestations, or establish completed publication.

## Exact identity

- Run **38317836286**, current attempt **1**, `event=push`, branch/ref name `v0.1.1`, workflow `.github/workflows/release.yml`, source SHA **`8c8b7f4583a161947578fdd62d4c6658a1956f55`**.
- Initial and final tag-ref reads return an annotated tag object, **`b5b96001bb2fcc0059183bcc0a2a2151129f1404`**. Its tag name is `v0.1.1`; the object points directly to that exact source commit. This establishes annotated-tag identity, not a cryptographic signature claim.
- A fresh remote main-ref read still returns the same source SHA. The run's `referenced_workflows` identifies the repository's reusable CI workflow at that SHA with `ref=refs/tags/v0.1.1`.
- I read the exact committed release workflow with `git show 8c8b7f4583a161947578fdd62d4c6658a1956f55:.github/workflows/release.yml`. Its configured version is 0.1.1; dependencies are reusable CI → build/attest → draft release → environment-gated PyPI publication → clean-PyPI verification → GitHub publication. The observed roster matches the materialized jobs for this waiting stage.

## Successful predecessor roster

The explicit `/attempts/1/jobs` response reports 13 jobs and returns all 13. Every job is associated with the exact source/run/attempt. The following **12 predecessor jobs and all their 108 reported steps** are completed/success, without failed, cancelled or skipped reported steps:

| Job ID | Job |
|---:|---|
| 115038612793 | Required checks / Gitleaks / full history |
| 115038612943 | Required checks / Quality, demos, smoke, and artifacts |
| 115038612973 | Required checks / Ubuntu / Python 3.10 |
| 115038613016 | Required checks / Ubuntu / Python 3.13 |
| 115038613034 | Required checks / Ubuntu / Python 3.12 |
| 115038613054 | Required checks / macOS / Python 3.14 |
| 115038613059 | Required checks / Ubuntu / Python 3.14 |
| 115038613083 | Required checks / Ubuntu / Python 3.11 |
| 115038749197 | Required checks / Windows / clean wheel / Python 3.14 |
| 115038847413 | Required checks / CI / required |
| 115038876394 | Build and attest release |
| 115038974024 | Draft GitHub release |

The build's successful reported steps include release-identity verification, reproducible timestamp, distribution build and validation, checksums/SPDX generation, build-provenance and SBOM attestation, and bundle upload. The draft job successfully reports checking out release notes, downloading the release bundle and creating/refreshing the draft. These are hosted execution observations; they are not my independent inspection of artifact bytes, package behavior or attestation signatures.

The final run metadata remains **`status=waiting`, `conclusion=null`**. Job **115039018286, Publish to PyPI**, is waiting with null conclusion and no executed steps. The later verification/publication jobs are dependent future stages, not omitted successful jobs. No completed-release claim is warranted.

## Artifact and draft metadata inventory

The run's artifact roster contains exactly two non-expired artifacts:

| Artifact ID | Name | API-reported archive digest |
|---:|---|---|
| 11777822304 | ci-distributions | `sha256:87b9df98e7e16d5746e7d37fccd54655fc465cf29fd0669132d7af4e4a6e657b` |
| 11777777419 | release-bundle | `sha256:9bf36617e0b321a9c849edefa486a5038ad9cfbd3ac78a0cc5ce892ef07f86bc` |

These are metadata digests, not locally recomputed hashes. The release bundle, rather than the reusable CI artifact, is the release workflow's downstream input.

The authenticated release-list response contains one matching **draft** release, ID **411050622**, tag `v0.1.1`, `draft=true`, `published_at=null`, with four uploaded asset metadata records: `evalopt_graph-0.1.1-py3-none-any.whl`, `evalopt_graph-0.1.1.tar.gz`, `evalopt-graph-0.1.1.spdx.json` and `SHA256SUMS.txt`. I downloaded none of these and make no package-content or byte-equivalence claim.

The earlier direct tag-based release lookup returned HTTP 404 (gh exit 1); that raw response and the interrupted assertion are retained. I did not interpret that route's response as proof the draft was absent. The subsequent authenticated release-list GET exited 0 and independently provided the draft metadata above. No workflow rerun or release mutation was needed or performed.

## Actual waiting gate and limits

A read-only pending-deployments response for this exact run lists environment `pypi`, ID **18433764700**, with **`current_user_can_approve=true`**. This is current API eligibility evidence for that run, distinct from the old environment configuration. It is not approval and cannot replace the separate exact-byte/attestation review. No approval endpoint was called. Root must retain and satisfy the remaining review gates and refresh eligibility before any eventual approval.

## Evidence retained and verification

Raw initial, second-poll and final responses are retained separately under ignored `plan/artifacts/10-hosted/codex-predecessors/`, including tag ref/object, remote main ref, exact run/attempt metadata, all jobs/steps, artifact rosters, pending deployment, draft lookup and release list. Each GET has stderr and timestamped exit metadata; `SHA256.json` hashes the capture files. The run-identity capture interval is **2026-10-12 22:39:35–22:41:37 UTC**, with the draft-list lookup following it. The repeated unchanged-state check waited at least 60 seconds.

A read-only Python assertion pass verified the annotated-tag chain, exact run/source/workflow identity, expected 12 predecessor names, complete 13-job count, every predecessor step success, and the unexecuted waiting PyPI job. All GETs succeeded except the disclosed direct tag-release lookup. No package downloads, model calls, credential/environment-value reads, Git mutations, reruns, waivers, deployment approvals or publication actions occurred.

## Required changes

None to this predecessor-workflow evidence. Retain its finite scope and complete the independent artifact, approval and post-publication gates separately.
