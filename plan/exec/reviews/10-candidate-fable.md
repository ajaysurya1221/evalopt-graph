REVIEW 10-CANDIDATE — Reviewer Fable high | Verdict ACCEPT

Scope: fresh read-only LOCAL ARTIFACT acceptance only. No broad final-source or operational-record re-review. Reviewer checkout: /Users/ajay/Developer/.evalopt-worktrees/wt-release-10-r1 at 7043a0879a8a5491c110bd7d8a9f466700f920b7 (clean). Candidate under review: central plan/artifacts/10-candidate (private, ignored), built at d76d6587ecd51747db6c8094613473bdf3ab896b. This verdict does not claim a build at 7043a08, a tag, a hosted bundle, provenance, CI or publication.

## Identity (independently recomputed, 2026-10-13)

| File | Bytes | SHA256 |
|---|---|---|
| dist/evalopt_graph-0.1.1-py3-none-any.whl | 137354 | d6ac4b9c276a3d13e4b5d41d364ea5f4c55f66363459748a0d4525326b1349b1 |
| dist/evalopt_graph-0.1.1.tar.gz | 382133 | f7af9adf4f28af6dca33d26630bfaf27da087f7e4ce3c15d404c68ceac8fcf93 |

Both match the identities stated in the review assignment. identity.json records head d76d6587… and source_date_epoch 1791843158; that epoch equals the committer time of d76d658 (2026-10-12 22:12:38 UTC), every wheel zip header timestamp and every sdist member mtime. Candidate bytes were unchanged after review (re-hashed at the end; mtimes 03:43:11 +0530 retained).

Root records at 7043 for the candidate: commands.json (preservation 75 protected files/0 errors; `uv lock --check` exit 0; `uv build` exit 0; `twine check` exit 0; verify_artifacts exit 0) with logs 00–04 consistent with those exits. `git diff d76d658..7043a08` touches only plan/exec/reports/07D-r1.md (four trailing spaces), plan/exec/reports/10-integration-corrections.md (new) and plan/exec/reports/10-pr-description.md (one sentence). `git diff --stat d76d658 7043a08 -- src tests bench/harbor docs scripts CHANGELOG.md CODE_OF_CONDUCT.md CONTRIBUTING.md LICENSE README.md SECURITY.md pyproject.toml .gitignore uv.lock` is empty, so all packaged inputs at 7043 equal d76.

## Checks performed (all in this worktree or a unique private temp dir; nothing written to the candidate directory or Git)

1. Wheel members: 41 entries, 0 duplicates, no absolute/`..`/backslash paths, no directory entries, no symlink or special entries (36 package files mode 0100644; 5 dist-info entries carry mode 0644 without type bits, hatchling's normal output, S_ISLNK false, identical to the 09 wheel), `ZipFile.testzip()` clean, empty archive comment. RECORD: 41 entries, every member's sha256/size matches, no RECORD entry without a member, RECORD self-entry blank.
2. Wheel source correspondence: all 36 `evalopt_graph/*` members byte-equal `git show d76d658:src/<path>` and `git show 7043a08:src/<path>`. licenses/LICENSE equals LICENSE at d76. METADATA body equals README.md bytes at d76. Non-package members are exactly METADATA, WHEEL, entry_points.txt, licenses/LICENSE, RECORD.
3. Wheel metadata: Metadata-Version 2.4, Name evalopt-graph, Version 0.1.1, License-Expression MIT, Requires-Python >=3.10, generator hatchling 1.32.4, tag py3-none-any. Requires-Dist has 12 entries, all gated by `extra ==` (all/dev/llm/yaml); required runtime dependencies are empty.
4. Sdist members: 120 members, 120 regular files, 0 directories/symlinks/hardlinks/devices, 0 duplicates, no escape paths, single root `evalopt_graph-0.1.1`, uid/gid 0 with empty uname/gname, modes 0644/0755 only, single mtime 1791843158.
5. Sdist source correspondence: all 119 non-PKG-INFO files byte-equal the same path at d76d658 and at 7043a08. PKG-INFO is byte-identical to the wheel METADATA.
6. Hygiene: no member path under plan/, no `.log`, `.env`, `__pycache__`, `.pyc/.pyo`, `.github` or hidden top-level entries in either archive. Byte scan of every member for `/Users/ajay`, worktree names, `.evalopt-worktrees` and `plan/exec`: the only hits are the nine `plan/exec` substrings inside the three ADR documents, all in the form `https://github.com/ajaysurya1221/evalopt-graph/blob/95b61a3ff9cbe6dc62acde75cf475958546aafc9/plan/exec/...`; zero relative `../../plan` links remain.
7. Comparison with accepted 09 artifacts (plan/artifacts/09-qualification/dist, wheel 40d7a69f…, sdist dba71cc7…): wheel member names identical; all 41 wheel payloads byte-identical; all 41 zip header timestamps differ (21:55:44 vs 22:12:38 UTC), which fully explains the differing wheel hash. Sdist member names identical; exactly 3 payloads differ (docs/decisions/migration-interface.md, routing-boundary.md, winddown-positioning.md); applying the single replacement `](../../plan/exec/` → `](https://github.com/ajaysurya1221/evalopt-graph/blob/95b61a3f…/plan/exec/` to each 09 payload (3 occurrences per file, 9 total) reproduces the 10 payload exactly. This matches `git diff 95b61a3 d76d658 -- docs`. The seven referenced plan/exec targets all exist at commit 95b61a3, which is an ancestor of HEAD.
8. verify_artifacts rerun (this checkout, pinned uv, interpreter 3.13.12): `uv run --offline --no-project --python 3.13.12 python3 scripts/verify_artifacts.py <10-candidate>/dist --version 0.1.1` → "verified wheel and sdist hygiene for evalopt-graph 0.1.1", exit 0. scripts/verify_artifacts.py and scripts/verify_installed_release.py are unchanged from 95b61a3 through 7043a08.
9. Clean outside-checkout installed-wheel smoke (cwd and venv in a fresh /tmp directory, no network): `uv venv --offline --python 3.13.12`; `uv pip install --offline --no-deps <wheel>` installed exactly one package; `python scripts/verify_installed_release.py --version 0.1.1` → "installed evalopt-graph 0.1.1 API and replay verified", exit 0; import identity shows module under the venv site-packages, importlib version 0.1.1, `__all__` of exactly the ten frozen exports in order, and the venv contains only evalopt-graph (no pip).
10. Twine rerun offline: `uv tool run --offline --from twine==6.2.0 twine check` on both candidate files → PASSED, PASSED.

## Findings by severity

- Blocking: none.
- Major: none.
- Minor: the 10-candidate directory carries no hash/size record of its own (identity.json has head and epoch only) and no archive-inspection record comparable to 09's archive-inspection.json. The SHA256/size values above are recorded here as the independent binding. The only local SPDX (09-qualification/candidate.spdx.json) references the 09 hashes 40d7a69f…/dba71cc7… and must not be reused or presented for the 10 bytes.
- Observation: the dist-info zip entries' external attributes omit the regular-file type bits. This is hatchling's standard output, identical to the accepted 09 wheel, and not a symlink or special member.

## Required changes

None for local candidate acceptance.

## Follow-ups (outside this gate)

- Root should retain a hash/size inspection record for 10-candidate next to identity.json, and any SPDX used for release must be generated from the actual hosted bundle bytes, not from the 09 local SPDX.
- Hosted bundle review, provenance/SBOM attestation verification, hosted CI at the exact head, tag and native publish permissions remain separate gates and are not covered here.

## Limits

- No network: GitHub reachability of the nine pinned URLs was not tested; only the local existence of commit 95b61a3 and of each referenced path at that commit was verified. Local remote-tracking refs show 95b61a3 on origin/winddown/20261013/09, /10 and /10-r1, but no fetch was performed.
- The full 422-test suite was not rerun; runtime and tests are byte-identical between 95b61a3, d76d658 and 7043a08 for all packaged inputs, and the installed-wheel API/replay smoke was rerun.
- The Codex 10-candidate review was not read before this verdict.
- Requested effort high, 20 turns / 20 minutes; this review used 8 turns including the write. Private temp outputs remain under /tmp/fable-10cand-inspect.4taCzf and /tmp/fable-10cand-smoke.4qm8lW; no retained bytes were modified.
