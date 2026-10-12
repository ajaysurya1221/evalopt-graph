# Task10 publication-gate preflight

Status: read-only source and installed-CLI inspection, **not release acceptance or deployment approval**. Exact source: `cb5f3ceae4e149843dc37c0390668faaa3dc91b6`. The four verifiers, release workflow, version-bearing configuration and SBOM generator inspected below are byte-unchanged from baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`. This report does not repeat semantic migration or scanner-exception reviews.

Only this report was written. No live workflow, tag, push, model call, credential access, `.env` read, build, installation, release download or deployment request occurred. Installed `gh` is 2.97.0; its local help confirmed the commands/attestation flags below. One unauthenticated read of official GitHub REST documentation confirmed the pending-deployment API shape; no repository/API state was queried.

## 1. What the existing code actually proves

| Source at the pinned commit | Existing check | Limit relevant to release authority |
|---|---|---|
| `scripts/verify_release.py:35–40` | Project name/version, empty required dependencies, Python floor and installed verifier | Uses the currently imported/installed package; caller must sync the exact candidate environment. Does not inspect a newly built wheel. |
| `scripts/verify_release.py:42–55` | Expected tag name, annotated tag when requested, tag commit equals HEAD and exact supplied main ref | Does not discover fresh remote state itself. `--main-ref` must be freshly fetched. Does not check required CI, reviews or publication permission. |
| `scripts/verify_artifacts.py:90–131` | Wheel payload roots, metadata 2.4, version/name, MIT license, Markdown README, Python floor, no unconditional runtime requirement | Metadata/hygiene inspection, not a source-to-artifact provenance proof or full test suite. |
| `scripts/verify_artifacts.py:134–175` | Sdist public allowlist, required public files, root name, metadata version/name | Inspects regular file members. Exact produced archive inventory remains part of artifact review; passing this function alone does not establish every archive-member property. |
| `scripts/verify_artifacts.py:178–199` | Exactly one wheel and one sdist, no unexpected regular output files other than uv's `.gitignore` marker | Does not bind these bytes to a Git ref, workflow run, checksum manifest, PyPI or GitHub. |
| `scripts/verify_installed_release.py:12–43` | Exact ordered ten exports, package and distribution version, no unconditional dependencies | An installed-wheel smoke gate, not unchanged implementation-byte proof. |
| `scripts/verify_installed_release.py:45–68` | One ACCEPTED decision, validation, serialization round trip, replay and CLI version | Does not exercise all five terminal states or replace the kernel characterization suite. |
| `scripts/verify_pypi_release.py:25–65` | Fresh venv, no-deps binary-only uncached install via explicit PyPI index, bounded attempts, installed verifier | Does not compare downloaded distribution hashes with the approved hosted bundle; does not validate PyPI's sdist, release assets or attestations. Preserve separate channel-byte checks. |

Run Python without optimization: these verifiers use assertions. Use a clean environment outside the source checkout for installed-wheel verification and retain the resolved imported package path; editable source imports do not qualify the wheel.

## 2. Existing workflow sequence and concrete prerequisites

`.github/workflows/release.yml:3–10` starts on a semantic-version tag and serializes per ref without cancelling a prior run. `:20–30` requires its reusable CI workflow before build. Before tagging, root separately needs exact PR/main required checks and both accepted reviews; the release workflow is not a replacement for those gates.

`:49–57` fetches current remote main, syncs the frozen environment and requires the tag's commit to equal that current main. **Do not advance main between the intended tagged release commit and this gate.** A mismatch is a real block; do not move the tag to repair it.

`:58–92` sets SOURCE_DATE_EPOCH from the tagged commit, builds distributions once, checks them, emits checksums/SPDX and two attestation types, then retains `release-bundle` for seven days. Root should retain the exact run/attempt and downloaded bytes before that retention expires.

`:94–149` downloads that bundle and creates a draft with four assets. Existing published release is rejected; an existing draft must have exactly the same number and bytes of assets. It does edit draft title/notes before checking the existing asset set, so record any partial failure honestly; never describe this path as fully atomic. No existing asset replacement is allowed by the script.

`:151–171` waits on environment `pypi`, then publishes the same bundle's distributions with existing OIDC Trusted Publishing. `:173–190` performs the clean PyPI wheel smoke. Only after that, `:192–207` publishes the GitHub draft and checks that it is Latest. A workflow waiting for pypi approval is therefore expected; only predecessor jobs must be complete at that point. Publication is not complete until the downstream jobs and independent byte checks finish.

## 3. Live version-bearing fields Task08 must align

These are still **0.1.0 at this inspected head**, so this head is not ready to tag v0.1.1:

- `pyproject.toml:7`; `src/evalopt_graph/__init__.py:20`; root package version `uv.lock:80`.
- CI artifact/installed expectations at `.github/workflows/ci.yml:112` and `:148`.
- Release `RELEASE_VERSION` at `.github/workflows/release.yml:16`; current release title at `:117`; notes paths at `:126` and `:148`.
- Artifact verifier default at `scripts/verify_artifacts.py:181` should follow the approved Task08 metadata update, although all release invocations should pass `--version 0.1.1` explicitly.
- Add `docs/releases/v0.1.1.md`; update only current README/CHANGELOG release pointers after Task05 relinquishes ownership. Historical v0.1.0 references remain historical. No source change except the approved version literal, dependency upgrade or workflow-pin change is required for these fields.

The build pin is hatchling 1.32.4 (`pyproject.toml:2`), both archive metadata versions are 2.4 (`:53`, `:56`), release uv is 0.11.29 (`release.yml:17`) and twine is 6.2.0 (`:64`). Keep those pins. Wheel packages only `src/evalopt_graph` (`pyproject.toml:51–53`); sdist uses an explicit allowlist (`:57–71`) with no plan, operational logs, uv.lock or `.github`. Artifact checks additionally reject `plan` as an sdist root and non-package wheel content (`verify_artifacts.py:14–29`, `:100–103`, `:150–153`), common private/cache components and personal home paths (`:30–87`). Actual built archives, including metadata README content and new shipped docs, still need inspection.

## 4. Qualification commands before native approval

The variables below are assigned by root from reviewed records, not inferred from branch names: `RELEASE_SHA`, `RELEASE_RUN`, `RELEASE_ATTEMPT`, `RUN_ARTIFACTS`, and the pinned `UV_BIN`. Repository is `ajaysurya1221/evalopt-graph`, version is `0.1.1`. This is a runbook; none of these live/publication commands was executed in this preflight.

**Candidate before merge/tag:** run the approved full verification lane, then:

```bash
"$UV_BIN" lock --check
"$UV_BIN" sync --frozen --extra dev
"$UV_BIN" run --frozen --extra dev python scripts/verify_release.py --expected-version 0.1.1
SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)" "$UV_BIN" build --out-dir "$RUN_ARTIFACTS/candidate-dist"
"$UV_BIN" x --from twine==6.2.0 twine check "$RUN_ARTIFACTS"/candidate-dist/*
python scripts/verify_artifacts.py "$RUN_ARTIFACTS/candidate-dist" --version 0.1.1
```

Install that single wheel with `python -m pip install --no-deps <exact-wheel>` into an isolated clean venv, change to a neutral directory, and run the reviewed absolute-path `scripts/verify_installed_release.py --version 0.1.1` with that venv's Python. Preserve archive inventories, hashes, checks and both reviews. Candidate artifacts are not automatically the later hosted artifacts.

**Exact tagged main, before push:** the approved annotated tag verifier is:

```bash
"$UV_BIN" run --frozen --extra dev python scripts/verify_release.py   --expected-version 0.1.1 --tag v0.1.1   --main-ref refs/remotes/origin/main --require-annotated-tag
```

Root must have freshly fetched the correct public main, recorded clean scope/preservation, checked tag absence and the budget, and passed required CI/two-review gates. A local tag check is not remote tag/workflow evidence.

**Actual hosted bundle, while pypi waits:** retain the exact run and attempt records/jobs, artifact roster, tag object and peeled commit. Require repository/workflow/event/tag/source SHA to match the accepted release and predecessor jobs to succeed. Select exactly one non-expired `release-bundle` artifact of that run and download to a new empty directory:

```bash
gh api "repos/ajaysurya1221/evalopt-graph/actions/runs/$RELEASE_RUN"
gh api --paginate "repos/ajaysurya1221/evalopt-graph/actions/runs/$RELEASE_RUN/attempts/$RELEASE_ATTEMPT/jobs"
gh api "repos/ajaysurya1221/evalopt-graph/actions/runs/$RELEASE_RUN/artifacts"
gh run download "$RELEASE_RUN" --repo ajaysurya1221/evalopt-graph   --name release-bundle --dir "$RUN_ARTIFACTS/hosted-bundle"
gh release download v0.1.1 --repo ajaysurya1221/evalopt-graph   --dir "$RUN_ARTIFACTS/github-draft"
```

Never omit the run ID or release tag and never use overwrite/skip-existing flags. Verify exactly two distributions plus SHA256SUMS.txt and `evalopt-graph-0.1.1.spdx.json`; the four draft assets must be byte-identical to those four bundle files. Re-run twine, artifact hygiene and clean wheel install on **hosted bundle bytes**, not only local candidates. From the bundle's dist directory, `shasum -a 256 -c ../release-assets/SHA256SUMS.txt` must pass; also require exactly the two intended filenames/digests in the manifest, with no absolute/traversal entries.

SPDX is an archive-level release inventory, not a complete dependency/source-file SBOM: `scripts/generate_spdx_sbom.py:40–85` emits one file and package per archive. Require its package versions, filenames and SHA256 values to match the two reviewed archive bytes. The checksum file covers distributions only (`release.yml:69`); it does not independently bind the SPDX file. Retain the SPDX asset hash and compare its JSON content to the authenticated SPDX predicate as well as its bytes across bundle/draft/published assets.

For each exact hosted wheel and sdist, installed gh supports:

```bash
gh attestation verify "$ARTIFACT" --repo ajaysurya1221/evalopt-graph   --signer-workflow ajaysurya1221/evalopt-graph/.github/workflows/release.yml   --source-ref refs/tags/v0.1.1 --source-digest "$RELEASE_SHA"   --signer-digest "$RELEASE_SHA" --deny-self-hosted-runners --format json
```

This command's default predicate is SLSA provenance v1. Repeat with `--predicate-type https://spdx.dev/Document` for the SBOM attestation. Require the verified subject digest to equal each reviewed artifact; inspect certificate/source/workflow binding and the verified statement's run invocation against the selected run/attempt, retaining the actual verification output. Statement metadata is still workflow-supplied; an authenticated workflow assertion is not semantic truth. Independent artifact/release review must accept these exact bytes and identity records before native approval.

## 5. Native pypi approval gate

Official [pending-deployment API documentation](https://docs.github.com/en/rest/actions/workflow-runs#review-pending-deployments-for-a-workflow-run) confirms GET/POST at `repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments`; POST accepts integer `environment_ids`, `state` and `comment`. GET exposes `current_user_can_approve`. Required-reviewer eligibility and deployments permission still govern access.

After the preceding exact artifact review, root must freshly GET that endpoint for the selected release run, require the pending environment name `pypi`, its actual environment ID and `current_user_can_approve: true`. Record a structured approval body binding the reviewed release SHA, run and artifact receipt; use the existing native endpoint only. Example execution shape after those conditions hold:

```bash
gh api --method POST   "repos/ajaysurya1221/evalopt-graph/actions/runs/$RELEASE_RUN/pending_deployments"   --input "$RUN_ARTIFACTS/deployment-review.json"
```

The JSON body contains only the current pypi environment ID, `state: "approved"` and the review comment. Preserve response and subsequent deployment/job state. A denied/ineligible/uncertain request is not approval: leave the exact action in HUMAN_INBOX. Do not use an admin bypass or change protections. Earlier self-review eligibility is not fresh permission for this deployment.

## 6. Verification after publication

Wait for the same run's publish-pypi, verify-pypi and publish-github-release jobs; preserve actual outcomes and failures. Then:

```bash
python scripts/verify_pypi_release.py --version 0.1.1 --attempts 6 --delay-seconds 10
gh release view v0.1.1 --repo ajaysurya1221/evalopt-graph   --json tagName,isDraft,isPrerelease,url,assets,publishedAt,targetCommitish
gh release download v0.1.1 --repo ajaysurya1221/evalopt-graph   --dir "$RUN_ARTIFACTS/github-published"
```

Use a new destination. Require published/non-prerelease status and the exact tag; peel the tag to RELEASE_SHA rather than trusting the release's potentially branch-valued targetCommitish. Compare all four downloaded assets byte-for-byte to the accepted hosted bundle. Re-run manifest and provenance/SBOM attestation verification on the actual downloaded distribution bytes.

Independently retrieve the versioned PyPI JSON at `https://pypi.org/pypi/evalopt-graph/0.1.1/json`. Require the expected name/version and exactly the intended wheel/sdist filenames; record their sizes, package types, yanked states, declared SHA256 digests and HTTPS download URLs. Download both exact versioned files, compute hashes locally and compare **each** against PyPI's digest, the hosted bundle, SHA256SUMS and GitHub's corresponding asset; require byte equality across channels. Verify both archives with `verify_artifacts.py` in the two-file PyPI directory and run a clean no-deps installed-wheel smoke there. This is required because the existing PyPI smoke alone proves none of those cross-channel equalities and never opens the PyPI sdist. Keep any alternative pip-index/configuration route out of the verification environment; never infer the publisher or exact bytes solely from installed metadata.

Retain actual run/attempt IDs, tag object/commit, both distribution hashes/sizes, manifest/SPDX hashes, artifact IDs, accepted reviews, PyPI metadata/receipts, attestation results and public release URL. A local candidate and hosted build are distinct evidence unless their bytes were actually compared. Do not claim PyPI-publisher attestation verification merely because GitHub provenance verification passed; name the verified attestation system and predicate precisely.

## 7. Concrete blocks and limitations

1. Current head still has all live 0.1.0 identities; planned Task08 alignment and qualification must precede any v0.1.1 tag.
2. Source version, package shape and installed smoke are not cross-channel identity gates. Exact hosted-bundle and post-publication byte checks above remain necessary root work; no new product verifier is requested here.
3. The workflow deliberately requires tag = current main, an exact four-asset draft, successful required CI, and successful protected publication. A race, differing pre-existing asset, failed job or denied native approval blocks that stage; no gate is waived or artifact replaced.
4. The seven-day artifact retention and 10-hour run budget are finite. Retain evidence promptly; if publication cannot finish, report the exact prepared/blocked stage and preserve the existing tag/draft/artifacts.
5. No current tag absence, PyPI availability, live permissions, run success, archive contents, signer verification, release status or byte reproducibility is established by this preflight. Required source/test/scanner reviews and the approved Task10 time cutoff remain separate gates.
