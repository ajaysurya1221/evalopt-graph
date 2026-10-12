REVIEW 10-MAIN-CI — Reviewer Astra | Verdict ACCEPT

**Scope:** actual main CI evidence for `8c8b7f4583a161947578fdd62d4c6658a1956f55` only. This is not approval of a tag, deployment, release artifacts or publication. GitHub's separate dynamic dependency-update work is inventoried below, including one still-active run.

## Findings and exact-main correspondence

No blocking discrepancy in the expected CI/CodeQL main-push evidence.

- Fresh remote `refs/heads/main` reads before and after collection returned exactly `8c8b7f4583a161947578fdd62d4c6658a1956f55`. Capture interval: **2026-10-12 22:34:58–22:37:21 UTC**.
- Independent local object checks show the main commit and accepted PR head `7043a0879a8a5491c110bd7d8a9f466700f920b7` both have tree `cb072ceb034d4ccf5fdf9bc1cbd485fc58a84e37`. This tree correspondence is additional evidence; the main gate is supported by its own actual push runs rather than inherited PR status.
- CI run **38317333493**, attempt 1, and CodeQL run **38317333455**, attempt 1, are `event=push`, `head_branch=main`, exact main SHA, completed/success. Every expected independent job is present: **11 jobs and 95 reported steps**, all completed/success. There are no failed, cancelled or skipped reported steps in those two workflows. This does not imply that every underlying test case had no skips.
- Explicit current-attempt job endpoints have `total_count` equal to returned job count (10 and 1), so no expected job page is omitted. Each job has matching run ID, attempt and exact main SHA. The expected CI matrix matches the candidate workflow already reviewed and the byte-identical main tree: five Ubuntu versions, macOS, quality/build, clean Windows wheel, Gitleaks and required aggregate, plus CodeQL.
- All before/after exact-head run rosters have `total_count=8` and eight records. The same eight IDs remain present, all on attempt 1 and the exact main SHA. Five were initially active dynamic dependency-update runs; their changing states were retained without overwriting the first snapshot.

## Expected main job roster

| Run / attempt | Job ID | Job | Result |
|---|---:|---|---|
| 38317333493 / 1 | 115036984500 | Gitleaks / full history | success |
| 38317333493 / 1 | 115036984704 | macOS / Python 3.14 | success |
| 38317333493 / 1 | 115036984725 | Ubuntu / Python 3.12 | success |
| 38317333493 / 1 | 115036984727 | Ubuntu / Python 3.14 | success |
| 38317333493 / 1 | 115036984745 | Quality, demos, smoke, and artifacts | success |
| 38317333493 / 1 | 115036984776 | Ubuntu / Python 3.13 | success |
| 38317333493 / 1 | 115036984865 | Ubuntu / Python 3.10 | success |
| 38317333493 / 1 | 115036984871 | Ubuntu / Python 3.11 | success |
| 38317333493 / 1 | 115037146631 | Windows / clean wheel / Python 3.14 | success |
| 38317333493 / 1 | 115037263849 | CI / required | success |
| 38317333455 / 1 | 115036983820 | CodeQL / Python | success |

The dependency-review workflow was a PR gate and was accepted separately for PR42. Its absence from the main-push workflow set is not an omitted expected main job.

## Separate dynamic-run inventory at final read

All six runs below use `event=dynamic`, attempt 1, the same main SHA, and one job each. They are GitHub dependency maintenance, not product CI lanes or authorization to merge dependency updates.

| Run | Dynamic purpose | Job ID | Captured state |
|---|---|---:|---|
| 38317338006 | Configured Graph Update: uv | 115037001399 | completed/success; five successful steps |
| 38317460883 | uv anthropic update | 115037404650 | completed/success; five successful steps |
| 38317462957 | uv openai update | 115037412654 | completed/success; five successful steps |
| 38317466959 | github/codeql-action init/analyze update | 115037426042 | **in progress**; Run Dependabot active, post-step pending |
| 38317468279 | actions/upload-artifact update | 115037429031 | completed/success; five successful steps |
| 38317469242 | actions/download-artifact update | 115037431812 | completed/success; five successful steps |

The active dynamic run is not called complete or green. In accordance with the bounded assignment, I did not wait for this unrelated update to finish or promote it to a release prerequisite. Any resulting update PRs remain outside the run's implementation scope. No failure in an expected main gate was observed.

## Retained evidence and checks

All new raw data is under ignored `plan/artifacts/10-main-ci/codex-current/`. It contains separate initial/poll/final rosters, before/after main refs, every run's metadata, explicit attempt-1 jobs and step records for all eight runs, stderr and UTC/exit metadata for each GET. The after-roster brackets the final job captures; `SHA256.json` hashes the retained capture files. All API commands exited 0.

Read-only commands used existing authenticated `gh api` GETs for the main ref, exact-head run roster, individual runs and `/actions/runs/<id>/attempts/1/jobs?per_page=100`. A Python assertion pass verified main identity, complete roster equality, current attempts and every expected job/step success. `git rev-parse <main>^{tree} <accepted-head>^{tree}` verified equal trees. One unchanged-state poll waited at least 60 seconds; the review ended after the required lanes were verified, without an unrelated dynamic-run wait.

## Remaining boundaries

No rerun, mutation, waiver, tag, release or deployment action was performed. This review establishes the expected workflows on actual main. Annotated-tag identity, exact release workflow artifacts, environment approval eligibility and published-byte/attestation verification remain later independent gates.
