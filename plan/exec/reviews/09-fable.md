REVIEW 09 — Reviewer Fable high | Verdict ACCEPT

Scope: independent local candidate-artifact review of REPORT 09 and the retained `plan/artifacts/09-qualification` evidence. Read-only; no source edits, no commits, no push/tag/release, no model calls, no global tool changes. This is local artifact review, not publication approval and not hosted-CI, tagged-provenance or main-merge evidence.

## Exact identities

- Source: `95b61a3ff9cbe6dc62acde75cf475958546aafc9`, worktree `wt-verification-09`, HEAD unchanged and `git status --porcelain` empty before and after review.
- `SOURCE_DATE_EPOCH=1791842144` equals the commit's `%ct`/`%at` (verified with `git show -s`).
- `evalopt_graph-0.1.1-py3-none-any.whl`: 137354 bytes, SHA256 `40d7a69ffed18309ac4c873b291e652f73af14d73c593bef9fdae15343604ba3`.
- `evalopt_graph-0.1.1.tar.gz`: 382094 bytes, SHA256 `dba71cc7c0ab4ed20083d8aa33a941a5d7310eeaf732cceb96022527ed591f98`.
- Both hashes recomputed with `shasum -a 256` and match REPORT 09, `archive-inspection.json` and the two SPDX file entries exactly. Retained artifact bytes were re-hashed after my reproductions and are unchanged.
- Tooling: `plan/artifacts/tooling/bin/uv` reports `uv 0.11.29 (901092ee1 2026-07-15 aarch64-apple-darwin)`; build backend `hatchling 1.32.4` per the wheel's `WHEEL` file; interpreter CPython 3.13.12 (uv-managed).

## Independent checks (all reproduced, not taken from the report)

Private review directory: `/private/tmp/fable-09-review-tUJ98e` (new; no retained output overwritten).

1. Archive member safety (own script, read without extraction): wheel 41 members, sdist 120 members, zero duplicate names, no absolute paths or `..` components, no symlink or special members, single sdist top-level `evalopt_graph-0.1.1/`.
2. Source-to-archive correspondence: all 36 `evalopt_graph/*` wheel files byte-equal to `src/evalopt_graph/*` at HEAD; all 119 sdist payload files byte-equal to their HEAD paths and every one is a `git ls-files` tracked path. Remaining wheel members are exactly METADATA, WHEEL, entry_points.txt (`evalopt = evalopt_graph.cli:main`), licenses/LICENSE, RECORD.
3. RECORD: 40 of 40 non-RECORD entries pass digest and size recomputation; no entries missing or extra. This is internal consistency, not producer authentication.
4. Metadata: `Version: 0.1.1`, `Requires-Python: >=3.10`; sdist PKG-INFO byte-equal to wheel METADATA; every `Requires-Dist` line carries an `extra ==` marker (all/dev/llm/yaml). `pyproject.toml` `dependencies = []`. Installed distribution `requires` filtered to non-extra entries is empty: zero required runtime dependencies.
5. Exclusion of plan/logs/private data: no `plan/`, `logs/`, `.evalopt/`, `.github/`, `.venv/`, `__pycache__` members in either archive; raw byte grep over all members for `/Users/ajay`, `wt-control`, `wt-verification`, `plan/artifacts`, `plan/logs`, `winddown`, `campaign`, `plan/exec` found no private filesystem paths. Hits are only committed public text: `.gitignore` lines naming `plan/artifacts`/`plan/logs` as ignored, benchmark "campaign" wording in README/docs, and `docs/decisions/*.md` relative links to `../../plan/exec/...` (see follow-up 1).
6. Twine: `uv tool run --from twine==6.2.0 twine check <whl> <sdist>` with the pinned uv: both PASSED, exit 0.
7. `scripts/verify_artifacts.py <dist> --version 0.1.1` from the task `.venv`: "verified wheel and sdist hygiene", exit 0.
8. Clean outside-checkout install: fresh `uv venv --python 3.13.12` under the review directory, `uv pip install --no-deps <whl>`; `uv pip list` shows only `evalopt-graph 0.1.1`. `scripts/verify_installed_release.py --version 0.1.1` passed (version, exact ordered ten-export `__all__`, no runtime requirements, ACCEPTED fixture, serialize/restore replay, CLI version), exit 0. Import path resolved to the review venv's site-packages, not a checkout. `__all__` has exactly ten entries in the expected order (GovernancePolicy … evaluate_acceptance). `evalopt --version` prints `evalopt 0.1.1`.
9. Candidate SPDX (`candidate.spdx.json`): SPDX-2.3, two `files` typed ARCHIVE whose SHA256 match the artifacts, two packages each CONTAINS one archive with matching checksums and purl `pkg:pypi/evalopt-graph@0.1.1`. No per-source-file or dependency entries: archive-level only, as the report states. Not a signed attestation.
10. Retained failure preserved separately: `commands.json` records `uv x --from twine==6.2.0 …` exit 2 and `twine.log` holds "unrecognized subcommand 'x'"; I reproduced `uv x` exit 2 on the same pinned binary. `commands-continuation.json`/`twine-supported.log` record the supported `uv tool run` success, exit 0, which I reproduced. Both records are intact and distinct.
11. Retained `complete-verification.log` ends with SMOKE TEST PASSED and preservation `protected_files: 75, errors: []`; `verification/conformance.json` shows 32/32 (12 adapter, 12 legacy rejected, 8 valid) passed. Not re-run by me within this review's turn budget; `release-identity.log` and `identity.json` are consistent with HEAD and epoch.

## Findings by severity

- Blocking: none.
- Medium: none.
- Low (record accuracy): REPORT 09 attributes the first Twine failure to uv 0.11.29 "not supporting `uv x`". That is true of `uv x`, but Task 09 specified `uvx`, and the pinned tooling directory does contain a working `uvx` shim (`uvx 0.11.29`). The failure was a command transcription (`uv x` instead of `uvx`), not a tooling gap. The corrected `uv tool run` is the documented equivalent and the result is valid; no change to artifacts or rules occurred. Wording only.
- Low (SPDX forward references): `documentNamespace` points at a GitHub release download URL for `v0.1.1` and `downloadLocation` at a PyPI files URL, neither of which exists yet. Acceptable for a candidate inventory labelled as such, but this file must not be reused verbatim as a published SBOM without rebinding to actual published bytes/URLs.
- Info: `wheel-env/` retained under the private artifact directory contains symlinks into the user's uv-managed Python; it is private evidence, not shipped, and is covered by `.gitignore`.

## Required changes

None for ACCEPT of the local candidate artifacts. Optional: correct the REPORT 09 sentence per the Low finding above in any later revision; do not alter retained logs.

## Follow-ups (outside this task)

1. `docs/decisions/{migration-interface,routing-boundary,winddown-positioning}.md` contain relative links to `../../plan/exec/...` that resolve in the repository but dangle inside the sdist (plan/ is intentionally excluded). Not a privacy leak; a docs-link quality item for the public-rendering gate owned by root.
2. Hosted CI at exact head, independent review of the hosted build, binding of the SPDX/hashes to actually published bytes, Codex review acceptance, and final privacy/integration review remain required before any publication.

## Tests / limits

- Reviewer: Fable high (claude-fable-5-1), requested and observed. Turn budget 20 / wall clock 20 minutes; completed within budget at 2026-10-12T22:11:40Z.
- Commands and exits as listed above; every reproduced check exited 0 except the deliberately reproduced unsupported `uv x` (exit 2, expected). One reviewer-side false failure occurred when my inspection helper was named `inspect.py` and shadowed the stdlib; it was renamed and the install verification re-run from a clean cwd with exit 0. No retained outputs were modified.
- Not performed: full `plan/exec/verify.sh` re-run (retained log relied on), rendered-docs link check, any network, hosted or publication step.
