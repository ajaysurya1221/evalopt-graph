REVIEW 10-candidate — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT

## Exact local candidate

Read-only target: `d76d6587ecd51747db6c8094613473bdf3ab896b` in `wt-release-10`, compared with the accepted Task 09 source `95b61a3ff9cbe6dc62acde75cf475958546aafc9`. The target checkout remained clean. This accepts documentation-only artifact correspondence and local installed smoke evidence; it does not approve a release, deployment or future build.

| Candidate | Bytes | Independently recomputed SHA-256 |
|---|---:|---|
| `evalopt_graph-0.1.1-py3-none-any.whl` | 137354 | `d6ac4b9c276a3d13e4b5d41d364ea5f4c55f66363459748a0d4525326b1349b1` |
| `evalopt_graph-0.1.1.tar.gz` | 382133 | `f7af9adf4f28af6dca33d26630bfaf27da087f7e4ce3c15d404c68ceac8fcf93` |

## Findings by severity

No candidate defect found within this correspondence review. Required changes: none.

## Source and archive correspondence

Outside excluded `plan/` records, the exact source diff consists of three ADR files: `docs/decisions/migration-interface.md`, `docs/decisions/routing-boundary.md` and `docs/decisions/winddown-positioning.md`. I mechanically verified that each file changes only three relative plan links into absolute GitHub URLs pinned to the full accepted Task 09 commit: nine replacements total. Every referenced record exists in that immutable local Git object. I made no network request and do not claim independently checked public HTTP resolution.

The new wheel has exactly the same 41 member payloads as the accepted Task 09 wheel, including all source, metadata, license, entry-point and RECORD bytes. All 36 package source files separately match the new pinned source. The ZIP bytes have a different hash because build metadata changed: among the inspected ZipInfo fields, only `date_time` differs for all 41 entries, from 2026-10-12 21:55:44 to 22:12:38, matching the respective commit-derived build epochs. Archive comments match.

The sdist has the same member roster as Task 09. Exactly the three named ADR payloads differ; its other 116 source-file payloads and PKG-INFO are identical. All 119 source files match their current committed paths. PKG-INFO still equals wheel METADATA. The old wheel and sdist retain their previously accepted SHA-256 values; no earlier artifact was replaced.

Both archives pass independent exact-roster, member-name uniqueness, relative-path/traversal, member-type and private-path checks. Neither contains operational plan records, logs, campaign directories, environments, Git metadata or research/results worktrees. Wheel CRC checks pass. All 41 RECORD rows exactly cover the archive and have internally consistent populated digest/size fields; this does not authenticate the producer. Version, license, Python floor, raw README metadata bytes and zero unconditional runtime dependencies remain unchanged.

## Executed checks and evidence

Before using the candidate, I read the completed root `10-candidate/commands.json` and all five associated logs. Preservation of 75 baseline files, frozen lock check, build, corrected pinned Twine 6.2.0 invocation and artifact hygiene all exited zero. Identity records bind the source to `d76d6587ecd51747db6c8094613473bdf3ab896b` and SOURCE_DATE_EPOCH 1791843158.

I separately ran five recorded commands in a new private directory, all exiting zero with no skip: artifact verification, fresh offline uv environment creation, exact-wheel `--no-deps` install, installed API/replay smoke and import/distribution identity checks. The installed package resolves to the fresh environment outside the source checkout, and evalopt-graph is its only installed distribution. The unchanged ten exports, version, ACCEPTED fixture, serialization/replay and CLI version pass. No full suite was repeated because the actual wheel payload and all tests/scripts remain byte-identical to the accepted Task 09 qualification.

Private evidence is retained in `plan/artifacts/10-candidate-codex/`. Archive correspondence receipt SHA-256: `23a34ded0eb8551220b6075b99435d52a124a27d57aa7604b8f08e08203d9147`. Command receipt SHA-256: `97cc262eaa801c051206411693dfcdf965b3bb577cce30359935d9d94d2b8c1e`. ZIP metadata comparison SHA-256: `f7667b2f0d58c5e081901afd8f0fea0c4d3c794d0742ee5050c15cffca33aa9c`.

## Follow-ups and limits

This review does not replace fresh Fable acceptance, the review of excluded operational records, exact-head hosted CI, final public link/render checks, merge/main gates or review of the actual hosted release bundle and published bytes. The old Task 09 SPDX document remains evidence for its old artifact hashes; it must not be represented as the inventory of this candidate. No model call, source/ref mutation, network mutation, tag, push, release or deployment action occurred. Existing root logs and candidate files were not modified.
