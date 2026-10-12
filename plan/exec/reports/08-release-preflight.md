REPORT 08-release-preflight — Status DONE | Changes | Tests (commands + results) | Deviations (with reason) | Open issues | Spend.

## Scope and disposition

Read-only preparation for Tasks 08–10. Inspected source baseline `fc3045dbda29c1d274747329ceb6724a783b0df7` from the control worktree; its source, package metadata, lock, workflows and verifier scripts still had no diff against that baseline. Local tag `v0.1.0` resolves to `42a65237303d77d8a38c2ff7d4110cb8b51a7375`. The control branch was `766d1ef576d70f3524b22f513e2693c1609e9480` during inspection and other lanes were adding reports concurrently.

This is a release-preparation inventory, not acceptance of an unbuilt 0.1.1 candidate, live deployment eligibility, or publication. No network requests, builds, live evaluations or Fable subprocesses were performed. Only this report was written.

## Exact live version and wording changes

Line numbers below refer to the unchanged baseline files and may shift after notice work.

| Path:line | Proposed bounded change |
|---|---|
| `pyproject.toml:7` | Root project version 0.1.0 → 0.1.1. Preserve dependency declarations and build pins. |
| `src/evalopt_graph/__init__.py:20` | Only `__version__` literal 0.1.0 → 0.1.1. No other source-byte edit. |
| `uv.lock:80` | Root `evalopt-graph` package version only. No resolver refresh or other package change. |
| `.github/workflows/ci.yml:112` | Artifact verifier's explicit expected version → 0.1.1. |
| `.github/workflows/ci.yml:148` | Installed-wheel verifier's explicit expected version → 0.1.1. |
| `.github/workflows/release.yml:16` | `RELEASE_VERSION` → 0.1.1. |
| `.github/workflows/release.yml:117` | Replace live release title suffix with the accepted deprecation wording. Version itself is interpolated. |
| `.github/workflows/release.yml:126` and `:148` | Both draft-release notes paths → `docs/releases/v0.1.1.md`; preserve immutable-asset protections. |
| `scripts/verify_artifacts.py:181` | Default expected version → 0.1.1; leave validation semantics unchanged. |
| `README.md:47` and `:192` | Update current install example and current release-note navigation after Notice ownership is complete. Preserve old release access. |
| `CHANGELOG.md:6` and `:65` | Add 0.1.1 entry, retain inherited Unreleased facts under the release, and update comparison links without erasing 0.1.0 history. |
| `docs/releases/v0.1.1.md` | New final-release notes with STOP status, migration link, unchanged-from-baseline scope and inherited changes described below. |

The bug-template example/placeholder at `.github/ISSUE_TEMPLATE/bug.yml:15–16` is sample input, not a live identity gate; Notice owns that file. Historical references in `docs/releases/v0.1.0.md`, historical CHANGELOG prose, architecture and benchmark evidence must remain historical. Global search-and-replace is not appropriate.

## Inherited differences that release notes must disclose

`git diff v0.1.0 fc3045db -- src` contains exactly four source paths. The new wind-down run must preserve these baseline implementations, but cannot describe 0.1.1 as byte-identical or behavior-identical to the published 0.1.0 implementation.

1. **Malformed acceptance rows fail closed.** `src/evalopt_graph/kernel.py:159–176` rejects scalar string/bytes containers or rows and converts non-iterable row/container errors into ValueError before checking widths/string fields. `:230–236` passes raw deserialized gate/contradiction rows into that validation rather than pre-converting scalar strings into character tuples. This is inherited from commit `624ed11` / PR #4 and deserves explicit attribution/disclosure. Regression additions are in `tests/test_kernel.py`.
2. **Detected Python checks use the running interpreter.** `src/evalopt_graph/project_detect.py:12–21` quotes `sys.executable` with a Windows-specific branch, and `:106` uses it for the inferred pytest command instead of bare `python`. This changes compatibility-host command inference; it is not new wind-down capability.
3. **Compatibility messages describe external helper locations.** `src/evalopt_graph/permissions.py:613–626` routes warning messages to `examples/claude-code-overnight/` and says the Claude skill is external. Its module docstring and the `epistemic.py:4` docstring change references; no additional decision-logic change appears in those diffs.
4. **Packaging and optional dependency floors already changed before this run.** Relative to v0.1.0, `pyproject.toml:2` has hatchling 1.32.4 instead of 1.31.0; `:34` has anthropic >=1.11.0 and openai >=3.23.0 instead of >=0.40/>=1.40; `:36` has pytest >=9.1.1, ruff >=0.16.10 and jsonschema >=4.26.0,<5 instead of >=8/>=0.6/>=4.25,<5. Corresponding lock changes are inherited. Required runtime dependencies remain empty at `:31`. Metadata 2.4 is explicitly pinned at `:53`/`:56`; overnight helpers/assets were moved outside the package and removed from the sdist include roster. README/figures, hygiene checks and tests were also revised on main.

Safe release wording: the wind-down adds no runtime capability and preserves the verified-main implementation except its version literal; the final distribution incorporates the already-merged fixes and packaging changes listed above. “No dependency changes” must be scoped to this wind-down diff, not the entire v0.1.0→v0.1.1 release delta.

## Package allowlists and privacy

- Wheel payload is only `src/evalopt_graph` plus generated dist-info (`pyproject.toml:51–53`). `scripts/verify_artifacts.py:90–131` rejects other payload roots, checks metadata 2.4, license, version, Python floor and required runtime dependencies.
- Sdist includes only `.gitignore`, `src`, `tests`, `bench/harbor`, `docs`, `scripts`, the named public root documents and `pyproject.toml` (`pyproject.toml:55–81`). `plan/` and `uv.lock` are not in that build include roster.
- The independent verifier's allowed roots at `scripts/verify_artifacts.py:14–29` also exclude `plan/`; `:150–153` rejects nonallowlisted roots and non-Harbor bench content. Wheel/sdist therefore must not contain `plan/exec`, logs, task prompts or reports. Still inspect actual built archives rather than treating configuration as a byte-level receipt.
- Newly written public documentation under `docs/` will ship. The verifier rejects personal absolute home-directory paths at `scripts/verify_artifacts.py:45–87`; source notes should cite public URLs and repo-relative paths, not private memo/worktree locations.

## Existing verification commands and bounded coverage

Run with isolated uv 0.11.29, its directory on PATH for nested commands, no dependency refresh, and no `PYTHONPATH` pointing at a different checkout. This report did not execute these future candidate commands.

```bash
uv lock --check
uv sync --frozen --extra dev
uv run --frozen --extra dev python scripts/verify_release.py --expected-version 0.1.1
export SOURCE_DATE_EPOCH="$(git show -s --format=%ct HEAD)"
uv build --out-dir "$RUN_ARTIFACTS/dist"
uvx --from twine==6.2.0 twine check "$RUN_ARTIFACTS"/dist/*
python scripts/verify_artifacts.py "$RUN_ARTIFACTS/dist" --version 0.1.1
python scripts/generate_spdx_sbom.py --dist-dir "$RUN_ARTIFACTS/dist"   --output "$RUN_ARTIFACTS/evalopt-graph-0.1.1.spdx.json" --version 0.1.1
```

Additionally run the full approved verification runbook. The release-identity script validates pyproject identity and calls the installed-package verifier (`scripts/verify_release.py:35–40`); it therefore needs the candidate installed/synced in its environment, not stale package metadata.

For a clean-wheel smoke, create a fresh environment outside the source checkout, install the single candidate wheel with `python -m pip install --no-deps <exact-wheel-path>`, and use that environment's Python to execute the absolute path to `scripts/verify_installed_release.py --version 0.1.1`. The verifier checks the exact ten-name `__all__`, package/metadata versions, empty required dependencies, one ACCEPTED decision's serialization/replay and the CLI version (`scripts/verify_installed_release.py:12–68`). It is a finite smoke, not comprehensive verification of all five outcomes; the full tests supply broader coverage.

After the reviewed annotated tag exists locally and HEAD is its exact main target:

```bash
uv run --frozen --extra dev python scripts/verify_release.py   --expected-version 0.1.1 --tag v0.1.1   --main-ref refs/remotes/origin/main --require-annotated-tag
```

The optional tag checks enforce matching version, annotated tag type, tag == checked-out HEAD and tag == supplied main ref (`scripts/verify_release.py:42–55`). They do not fetch main or establish hosted green status themselves.

After actual publication:

```bash
python scripts/verify_pypi_release.py --version 0.1.1 --attempts 6 --delay-seconds 10
# In the downloaded public release-assets directory:
shasum -a 256 -c SHA256SUMS.txt
gh attestation verify evalopt_graph-0.1.1-py3-none-any.whl --repo ajaysurya1221/evalopt-graph
gh attestation verify evalopt_graph-0.1.1.tar.gz --repo ajaysurya1221/evalopt-graph
```

The PyPI verifier makes a fresh venv, installs only the requested wheel from the explicit PyPI index with no dependencies/cache, retries at most six times and runs the installed verifier (`scripts/verify_pypi_release.py:25–65`). It does **not** compare PyPI artifact bytes to the workflow bundle. Retain and compare actual public wheel/sdist hashes separately; local candidate hashes are not a substitute for the workflow's published bytes. Attestation verification does not prove semantic correctness.

## Existing release and approval path

The source workflow sequence is Required checks → Build/attest → Draft GitHub release → protected `pypi` publish → clean PyPI install → publish GitHub draft as Latest (`.github/workflows/release.yml:19–207`). It builds once, records SOURCE_DATE_EPOCH, validates the distributions, writes SHA256SUMS/SPDX, creates provenance and SBOM attestations, and uploads one release-bundle. That bundle has a seven-day retention and contains exactly two distributions plus two evidence assets.

The draft step refuses to modify an already published release (`:121–124`), requires four assets (`:119–120`), and compares an existing draft's bytes before retaining them (`:127–142`). Preserve these protections and do not replace an asset. The pypi job uses GitHub OIDC Trusted Publishing and the existing environment (`:151–171`); no API-token provisioning is needed.

Retained Task 01 records, not a new live query, show `pypi` environment ID 18433764700, reviewer ajaysurya1221, `prevent_self_review=false`, and custom deployment branch policies (`plan/logs/01-pypi-environment.json`). The source alone does not establish whether the exact deployment is eligible. At publication time root must fetch the exact run's `/repos/ajaysurya1221/evalopt-graph/actions/runs/<run-id>/pending_deployments`, verify the `pypi` environment/run/tag/head and `current_user_can_approve=true`, and only after artifact review use the existing native review endpoint with that returned environment ID. Preserve the request and response; denial or unavailable interactive approval becomes HUMAN_INBOX, never a protection edit.

Retained main ruleset 19205651 requires `CI / required`, `CodeQL / Python`, `Dependency review` and `Gitleaks / full history`, strict head freshness, resolved review threads and squash-only PR merges; bypass roster is empty. Tag ruleset 19205653 forbids v-tag update/deletion. These observations are from the Task 01 snapshot and require fresh exact-head verification before merge/tag.

## Findings and remaining gates

- **Release-note requirement:** disclose inherited kernel validation, interpreter selection, packaging and optional floor changes. A blanket unchanged-since-0.1.0 claim would be false.
- **Evidence requirement:** actual artifact inspection, installed smoke, public-byte comparison, hosted required checks and eligible native approval are outstanding. This preflight approves none of them.
- **Preservation:** no product edits are necessary beyond the approved version/metadata/notice allowlist; preserve all action pins, review gates, existing release assets and historical evidence.

Spend: read-only Git/file inspection only; no live model tasks, network calls, build artifacts, repository mutations or deployment requests. Codex analysis usage is not separately attributable here.
