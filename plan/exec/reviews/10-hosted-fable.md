REVIEW 10-HOSTED — Reviewer Fable xhigh | Verdict ACCEPT | Findings by severity | Required changes | Follow-ups

Scope: fresh, independent, read-only review of the ACTUAL HOSTED release artifact for v0.1.1. This record is the artifact gate before the native `pypi` deployment approval. It is not deployment approval and not publication acceptance. Nothing was approved, mutated, pushed, tagged, downloaded anew or re-signed. Only this file was written, plus private temp checks under `/tmp/fable-10-hosted-Vz10Az` and `/tmp/fable-10-cert-*` (my own scratch, not records).

Reviewed at 2026-10-12T22:42Z to 22:49Z UTC. Model requested: Fable xhigh. Observable model: claude-fable-5-1. No subagent, credential, `.env` or network call. No Codex hosted verdict was read before this verdict; no `10-hosted-codex*` file existed in the reviews directory at start.

## Identity under review (actual bytes, independently hashed)

| File | SHA-256 | Bytes |
|---|---|---|
| bundle/dist/evalopt_graph-0.1.1-py3-none-any.whl | d6cffc1a0f1b56b087805ee18662d11863d6063b231b2d8e97d64a3430c8e739 | 137354 |
| bundle/dist/evalopt_graph-0.1.1.tar.gz | 2c49351a7c6343b31faf3b9ff2c7359cc51a41f6249559c31f388be600facf10 | 382132 |
| bundle/release-assets/SHA256SUMS.txt | 7d7661547846d824f0709288d4730a73352903a4e58e9e63e6a68bfd7ca52e22 | 196 |
| bundle/release-assets/evalopt-graph-0.1.1.spdx.json | 9dee6be448e411d3190ea8ae25eb4fef2801feaa8dcdbd9065628c04ea95ff29 | 4232 |

Root records at `plan/artifacts/10-hosted/`: run 38317836286 attempt 1, workflow `.github/workflows/release.yml`, event push, head_branch `v0.1.1`, head_sha 8c8b7f4583a161947578fdd62d4c6658a1956f55, repository ajaysurya1221/evalopt-graph (id 1306570239). Artifact roster: `release-bundle` id 11777777419 (518238 bytes, not expired, expires 2026-10-19T22:39:56Z) plus a CI artifact `ci-distributions` id 11777822304 from the reusable CI job, which is not the release bundle. Draft release id RE_kwDOTeCt_84YgCJ-, tagName v0.1.1, isDraft true, isPrerelease false, exactly 4 assets whose GitHub-reported digests equal the table above.

Local repository facts (this worktree, no fetch): `refs/tags/v0.1.1` = annotated tag object b5b96001bb2fcc0059183bcc0a2a2151129f1404 peeling to 8c8b7f4583a1…; `refs/remotes/origin/main` = 8c8b7f4583a1…; commit timestamp 1791844401 = 2026-10-12T22:33:21Z. The `.gitignore` subject sha256 684888c0ebb17f374298b65ee2807526c066094c701bcc7ebbe1c1095f494fc1 equals sha256 of the single byte `*`, which is the marker file `uv build` writes into its output directory.

## Checks performed and results

All commands run from `/Users/ajay/Developer/.evalopt-worktrees/wt-publication-10` at HEAD 8c8b7f4 unless noted. H = `/Users/ajay/Developer/.evalopt-worktrees/wt-control-00/plan/artifacts/10-hosted`. UV = `…/wt-control-00/plan/artifacts/tooling/bin/uv` (uv 0.11.29). PY313 = uv-cached CPython 3.13.12.

1. `shasum -a 256 bundle/dist/* bundle/release-assets/* github-draft/*` → the four bundle digests match the table; the four draft digests are identical. `cmp` on each bundle/draft pair → IDENTICAL ×4. No symlinks under bundle or github-draft.
2. `cat -A SHA256SUMS.txt` → exactly 2 lines, two-space separators, relative filenames, LF endings, no absolute or traversal entries. `(cd bundle/dist && shasum -a 256 -c ../release-assets/SHA256SUMS.txt)` → both OK, exit 0.
3. SPDX asset: SPDX-2.3, 2 files + 2 packages, each `fileName`/`packageFileName`, SHA256 and `versionInfo` 0.1.1 match the two distributions exactly; `created` 2026-10-12T22:33:21Z equals the commit timestamp. SPDX attestation predicate (both verification outputs) compared as parsed JSON to the asset → equal (semantic equality True). Both SPDX outputs are byte-identical; both provenance outputs are byte-identical, as expected for one statement covering multiple subjects.
4. Wheel archive (`zipinfo`, Python zipfile): 41 members, 0 directories, no duplicates, no absolute/`..` paths, roots `evalopt_graph` and `evalopt_graph-0.1.1.dist-info` only, no symlinks, all modes 0644, all date_time 2026-10-12 22:33:20, `testzip` clean, no archive comment. RECORD: 41 entries, every member listed, no stale entries, all sha256/size values recomputed and matched (RECORD self-entry blank). WHEEL: hatchling 1.32.4, py3-none-any, purelib. entry_points: `evalopt = evalopt_graph.cli:main`. METADATA 2.4, Name evalopt-graph, Version 0.1.1, License-Expression MIT, Requires-Python >=3.10, every Requires-Dist carries an `extra ==` marker, so zero required dependencies; `Description-Content-Type: text/markdown`; long description byte-equals README.md at 8c8b7f4. `licenses/LICENSE` byte-equals LICENSE at 8c8b7f4. METADATA byte-equals sdist PKG-INFO.
5. Sdist archive (Python tarfile): 120 members, all regular files (no dirs, symlinks, hardlinks), no duplicates, no unsafe paths, single root `evalopt_graph-0.1.1/`, uid/gid 0/0 with empty names, all mtimes 1791844401, gzip header mtime 1791844401, PAX format. Modes: 116×0644, 4×0755; the 0755 set equals exactly the `100755` blobs at 8c8b7f4 that the sdist includes (solve.sh, minimal_policy.py, test.sh, smoke_test.sh).
6. Source binding: all 119 non-PKG-INFO sdist members byte-equal `git cat-file -p 8c8b7f4:<path>` (0 mismatches, 0 not-in-tree). All 36 wheel package files byte-equal `src/evalopt_graph/*` at 8c8b7f4, equal the sdist's 36 `src/evalopt_graph` files, and the git tree has exactly 36 files there. Of 301 tree paths, 182 are excluded from the sdist: 163 `plan/`, 9 `.github/`, 8 `examples/`, `uv.lock`, `.gitleaks.toml`. No operational logs, caches, `.env`, `.pyc` or `plan` content inside either archive. Grep of extracted archives for home paths, worktree paths and credential-shaped strings → no hits.
7. `$UV tool run --offline --from twine==6.2.0 twine check <wheel> <sdist>` → PASSED ×2, exit 0.
8. `$PY313 scripts/verify_artifacts.py $H/bundle/dist --version 0.1.1` → "verified wheel and sdist hygiene for evalopt-graph 0.1.1", exit 0.
9. Private clean venv: `$UV venv --offline --python 3.13.12 /tmp/fable-10-hosted-Vz10Az/venv` → CPython 3.13.12; `$UV pip install --offline --python <venv> --no-deps <hosted wheel>` → `+ evalopt-graph==0.1.1`, one package only; from the neutral temp cwd, `<venv>/bin/python …/scripts/verify_installed_release.py --version 0.1.1` → "installed evalopt-graph 0.1.1 API and replay verified", exit 0. Import identity resolved to the venv's site-packages (not the source checkout); `importlib.metadata` version 0.1.1; unconditional Requires-Dist list empty; `__all__` is the ordered ten exports; `evalopt --version` → `evalopt 0.1.1`.
10. Root records re-read: twine, verify_artifacts, venv/install, installed smoke and import identity all exit 0 with the same outputs. Root's venv used 3.13.12 and `--no-deps --offline`; its import path is inside `clean-venv`.
11. Run/job records: `jobs-224035.json` lists 13 jobs; 12 completed with conclusion success on GitHub-hosted `ubuntu-latest`/`macos-latest`/`windows-latest` runners (runner group "GitHub Actions"), all with run 38317836286, attempt 1, head_sha 8c8b7f4. The 13th, "Publish to PyPI", is `waiting` with no conclusion. `runs-initial.json` shows exactly one release.yml run for v0.1.1. Run `referenced_workflows` pins ci.yml at 8c8b7f4 on `refs/tags/v0.1.1`.
12. Attestation receipts (independently read, not re-executed): all four `gh attestation verify … --format json` records show exit 0, empty stderr, and the exact flags: `--repo`, `--signer-workflow ajaysurya1221/evalopt-graph/.github/workflows/release.yml`, `--source-ref refs/tags/v0.1.1`, `--source-digest` and `--signer-digest` 8c8b7f4…, `--deny-self-hosted-runners`, plus `--predicate-type https://spdx.dev/Document` for the SBOM pair. Each verificationResult: statement type in-toto v1; predicateType `https://slsa.dev/provenance/v1` or `https://spdx.dev/Document/v2.3`; subjects `.gitignore` (684888c0…), the wheel (d6cffc1a…) and the sdist (2c49351a…); certificate issuer `https://token.actions.githubusercontent.com`; SAN `…/release.yml@refs/tags/v0.1.1`; sourceRepositoryDigest, buildConfigDigest, buildSignerDigest and githubWorkflowSHA all 8c8b7f4…; sourceRepositoryRef refs/tags/v0.1.1; repository id 1306570239, owner id 74526464; runnerEnvironment github-hosted; buildTrigger push; runInvocationURI `…/actions/runs/38317836286/attempts/1`. SLSA predicate: buildType `https://actions.github.io/buildtypes/workflow/v1`, externalParameters workflow path/ref/repository match, resolvedDependencies gitCommit 8c8b7f4 at refs/tags/v0.1.1, invocationId run 38317836286 attempt 1. Rekor entries: logIndex 3236673874 (integratedTime 1791844794 = 22:39:54Z) and 3236674079 (1791844795 = 22:39:55Z), inside the "Build and attest release" job window 22:39:42Z–22:40:00Z.
13. Receipt internals: the DSSE envelope payload (base64) decodes to a statement identical to `verificationResult.statement` in each record. The embedded Fulcio leaf certificate, decoded with `openssl x509`/`asn1parse`, has issuer `O=sigstore.dev, CN=sigstore-intermediate`, validity 22:39:53Z–22:49:53Z (provenance) and 22:39:55Z–22:49:55Z (SBOM), critical SAN URI `https://github.com/ajaysurya1221/evalopt-graph/.github/workflows/release.yml@refs/tags/v0.1.1`, and extensions 1.3.6.1.4.1.57264.1.{3,6,10,13,14,21} carrying 8c8b7f4…, refs/tags/v0.1.1, the repository URI, `github-hosted`, and `https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38317836286/attempts/1`. These agree with gh's summary fields.

## Findings by severity

Blocking: none.

High: none.

Medium: none.

Low:
- L1. The attested subject roster has three entries, but only two distributions are released. The third subject is `.gitignore` with sha256 of the single byte `*`, i.e. the marker `uv build` writes into `dist/`. Cause, from release.yml at 8c8b7f4: `subject-path: "dist/*"` (lines 77 and 81) glob-matches the dotfile, while `upload-artifact … include-hidden-files: false` (line 91) and `sha256sum -- *` (line 69, no dotglob) exclude it. Effect on identity: none. Each distribution is independently digest-bound as its own subject, both verify commands matched their own subject digests, and the extra subject is not shipped in the bundle, draft, manifest or SPDX. Effect on hygiene: cosmetic inconsistency between the attestation and the SBOM/release inventory; the SBOM attestation names a subject the SBOM does not describe. Not a block, and not something to repair on this tag.
- L2. The draft release reports `targetCommitish: "main"`, a branch value. Post-publication verification must peel `refs/tags/v0.1.1` to 8c8b7f4 rather than trust that field, as the preflight already prescribes.

Informational:
- The provenance and SBOM receipts for wheel and sdist are the same two statements, so there are two signed attestations covering both files, not four distinct ones. That is correct for this workflow.
- Local candidate archives from earlier tasks have different bytes due to a different SOURCE_DATE_EPOCH; they were not treated as hosted evidence here.

## Required changes

None for this artifact gate.

## Follow-ups

- F1 (future workflow, not this release): narrow the attestation `subject-path` to `dist/*.whl` and `dist/*.tar.gz` or use a checksum manifest as subjects, so attested subjects equal released files. Any such change is a reviewed workflow edit for a later release; do not re-run or replace v0.1.1 for it.
- F2: after publication, perform preflight Section 6 in full: PyPI JSON per-file digests, downloaded PyPI bytes versus these exact hashes, published asset bytes versus the bundle, and attestation verification on the downloaded bytes. Name the attestation system precisely; this review verified only GitHub Sigstore provenance/SBOM receipts, not PyPI publisher attestations.
- F3: retain the bundle evidence before artifact 11777777419 expires on 2026-10-19T22:39:56Z (already downloaded under `10-hosted/`).

## Explicit release and deployment limits

- This ACCEPT covers exactly the bytes in the identity table, the `release-bundle` artifact 11777777419 of run 38317836286 attempt 1, and the four draft assets as observed at 22:40:58Z to 22:41:01Z UTC. It does not cover any later GitHub, PyPI or repository state.
- No independent network cryptographic rerun of `gh attestation verify` was performed; I read root's retained native receipts and independently checked their internal consistency (DSSE payload, certificate extensions, Rekor times, subject digests) against the hashed bytes and run records. Those receipts carry exit 0 and complete JSON output.
- The full 422-test suite was not rebuilt here; prior accepted source/CI reviews cover it and every archive byte was shown equal to 8c8b7f4.
- Deployment approval remains a separate root action under PLAN Release authority and preflight Section 5: a fresh GET of `pending_deployments` must show environment `pypi` with `current_user_can_approve: true`, and the approval body must bind run 38317836286, source 8c8b7f4 and these hashes. If GitHub denies or requires an unavailable interactive action, record it in HUMAN_INBOX; no bypass, protection change or replacement release.
- Publication is not complete until publish-pypi, verify-pypi and publish-github-release succeed and the Section 6 cross-channel byte checks pass. Until then the honest status is "release prepared, awaiting pypi approval".

## Spend

Requested xhigh, 20 turns, 20 minutes. Used about 12 turns and about 7 minutes of wall clock at write time (22:42:23Z to 22:49Z). Exact token and cache counts are not observable from inside this session; one Bash call exceeded 120 s and was backgrounded, then read back. No model, billing or network calls.
