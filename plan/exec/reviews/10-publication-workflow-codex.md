REVIEW 10-PUBLICATION-WORKFLOW — Reviewer Astra | Verdict ACCEPT

**Accepted scope:** terminal workflow execution, exact run/tag/source identity, native deployment records and actual GitHub publication metadata. Package contents, independently downloaded channel bytes and attestation verification are separate root-owned checks and are not established by this review.

## Actual terminal result

Release run **38317836286**, current attempt **1**, is **completed/success**. It remains a push of `v0.1.1` from source **`8c8b7f4583a161947578fdd62d4c6658a1956f55`**, using `.github/workflows/release.yml`; its referenced reusable CI workflow is pinned to the same commit and tag ref.

Initial and final tag-ref reads agree on annotated object **`b5b96001bb2fcc0059183bcc0a2a2151129f1404`**. The final tag-object response names `v0.1.1` and targets the exact source commit. No rerun, changed attempt or tag replacement is indicated by these records.

The explicit attempt-1 jobs response contains **15 jobs**, matching `total_count=15` and the expected full workflow roster. All jobs have the exact run ID, attempt and source SHA and are completed/success. **All 123 reported steps are completed/success**, with no skipped, failed or cancelled reported steps. This is hosted job/step evidence, not a statement that every underlying test case had no skips.

| Job ID | Job | Conclusion |
|---:|---|---|
| 115038612793 | Required checks / Gitleaks / full history | success |
| 115038612943 | Required checks / Quality, demos, smoke, and artifacts | success |
| 115038612973 | Required checks / Ubuntu / Python 3.10 | success |
| 115038613016 | Required checks / Ubuntu / Python 3.13 | success |
| 115038613034 | Required checks / Ubuntu / Python 3.12 | success |
| 115038613054 | Required checks / macOS / Python 3.14 | success |
| 115038613059 | Required checks / Ubuntu / Python 3.14 | success |
| 115038613083 | Required checks / Ubuntu / Python 3.11 | success |
| 115038749197 | Required checks / Windows / clean wheel / Python 3.14 | success |
| 115038847413 | Required checks / CI / required | success |
| 115038876394 | Build and attest release | success |
| 115038974024 | Draft GitHub release | success |
| 115039018286 | Publish to PyPI | success |
| 115043727519 | Verify clean PyPI install | success |
| 115043811665 | Publish GitHub release | success |

## Actual downstream execution, not inferred from approval

- **PyPI publishing:** job 115039018286 ran 22:55:44–22:56:07 UTC. Its download and Trusted Publishing steps, post-step and job conclusion succeeded.
- **Clean PyPI verification:** job 115043727519 ran 22:56:14–22:56:25 UTC. `Install from PyPI and verify replay` succeeded. This is hosted verification performed by the workflow, distinct from an independent local channel install or downloaded-byte comparison.
- **GitHub publication:** job 115043811665 ran 22:56:27–22:56:40 UTC. `Publish draft as Latest` succeeded.
- **Deployment:** the exact-source/tag `pypi` deployment is ID **7025528904**. Its retained status history progresses from waiting through queued/in_progress to **success**, with the latest status 19670141685 at 22:56:08 UTC and a log URL bound to this run's PyPI job. Both initial and final current pending-deployment reads return `[]`.
- The exact run's approval-history API records `approved`, actor `ajaysurya1221`, environment `pypi` ID **18433764700**. This confirms native gate history; the successful downstream records above, rather than that approval alone, establish workflow completion. I issued no approval.

## Published GitHub metadata

Both the by-tag release response after completion and the repository's Latest release endpoint identify release **411050622**, tag **`v0.1.1`**, `draft=false`, `prerelease=false`, **`immutable=true`**, published at **2026-10-12 22:56:37 UTC**.

The four assets are uploaded and retain their previously observed IDs and API-reported digests:

| Asset ID | Name | API-reported SHA-256 |
|---:|---|---|
| 635191448 | evalopt_graph-0.1.1-py3-none-any.whl | `d6cffc1a0f1b56b087805ee18662d11863d6063b231b2d8e97d64a3430c8e739` |
| 635191452 | evalopt_graph-0.1.1.tar.gz | `2c49351a7c6343b31faf3b9ff2c7359cc51a41f6249559c31f388be600facf10` |
| 635191449 | evalopt-graph-0.1.1.spdx.json | `9dee6be448e411d3190ea8ae25eb4fef2801feaa8dcdbd9065628c04ea95ff29` |
| 635191447 | SHA256SUMS.txt | `7d7661547846d824f0709288d4730a73352903a4e58e9e63e6a68bfd7ca52e22` |

These are API metadata, not hashes recomputed from downloads by this reviewer. No artifact bytes were downloaded or inspected.

## Evidence and checks

Raw initial/poll/final run records, full current-attempt jobs and steps, tag ref/object, pending deployments, deployment roster/status history, approval history and release metadata are retained under ignored `plan/artifacts/10-publication-workflow-codex/`. Each API call has stderr and UTC/exit metadata; `SHA256.json` hashes the capture files. Capture interval: **2026-10-12 22:56:18–22:57:59 UTC**. One poll waited 30 seconds.

An independent read-only Python assertion pass verified the expected 15-job set, count completeness, all run/job identities and 123 step conclusions, the annotated-tag target, empty final pending queue and published Latest release identity. The initial by-tag release GET returned HTTP 404 (gh exit 1) while clean-PyPI verification was still active; the response is retained, and subsequent by-tag/Latest reads succeeded after GitHub publication. All other recorded API calls exited 0. This transient pre-publication response was not treated as a workflow failure or suppressed.

## Findings, required changes and limits

No blocking discrepancy in this bounded workflow/publication-metadata review. No required correction.

The accepted record does not replace root's independent checks of the actual GitHub/PyPI bytes, clean installs, checksum correspondence or attestation signatures. It also does not establish final-report completion, branch-setting restoration or repository archival. No model call, credential/environment-value read, Git mutation, repository/settings change, deployment approval, rerun, waiver or package download was performed.
