REVIEW 10-INTEGRATION-R1 — Reviewer Fable high | Verdict ACCEPT

## Target and bounds

- Target: `7043a0879a8a5491c110bd7d8a9f466700f920b7` on `winddown/20261013/10-r1` in `wt-release-10-r1`; baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`. `git rev-parse HEAD` matched; `git status` clean at start; the target was never edited, staged or committed.
- Scope: fresh read-only final SOURCE/integration/privacy review of the complete baseline-to-head diff, the shipped delta since accepted Task 09 source `95b61a3`, the correction delta since `d76d658`, and the PR body. This is not artifact acceptance, hosted CI, merge permission, deployment approval or publication; those gates remain separate.
- Provenance read (not re-reviewed): PLAN B/C, `tasks/10.md`, `reviews/08-fable.md`, `09-fable.md`, `09-codex.md`, `07D-codex-final.md`, `control-packet-fable-final.md`, the Task 09/10 reports and the central `10-gates-current.md` report. No Codex final integration review was read before this verdict (`10-integration-codex.md`, `10-integration-codex-final.md`, `10-candidate-codex.md` remained unread).
- No network, model, subagent, build, install, full-suite, credential or `.env` access. Only this file was written, in `wt-control-00`, left unstaged. Native effort is not observable; tool-turn counts below are self-reported and carry no authority.

## Commands and results (all read-only, all exit 0 unless stated)

| Check | Command | Result |
|---|---|---|
| Roster | `git diff --stat/--name-status fc3045db..7043a087` | 187 files, +7057/−90: 11 modified (templates ×3, ci.yml, release.yml, .gitignore, .gitleaks.toml, CHANGELOG, CONTRIBUTING, README, SECURITY, pyproject, verify_artifacts.py, `__init__.py`, uv.lock), 9 new `docs/` files, 167 new `plan/exec/` records |
| Version-only source | `git diff --stat fc3045db..HEAD -- src tests bench results` | only `src/evalopt_graph/__init__.py` `__version__` 0.1.0→0.1.1 |
| Preservation | `python3 -B plan/exec/preservation.py` | `{"baseline": "fc3045db…", "protected_files": 75, "errors": []}` |
| Zero runtime deps | `pyproject.toml` at HEAD; `git diff -- pyproject.toml uv.lock` | `dependencies = []` unchanged; both diffs are the single version line |
| Action pins / protections | `git diff fc3045db..HEAD -- .github/workflows \| grep uses:` | no `uses:` or `permissions:` line changed; ci.yml: two expected-version literals; release.yml: `RELEASE_VERSION`, title suffix, two notes paths |
| No frozen-research merge | `git log --merges fc3045db..HEAD`; `git rev-list --parents`; `merge-base --is-ancestor feat/* HEAD` | zero merges; all 39 commits single-parent; none of the five `feat/*` heads is an ancestor; no `results/` or `bench/` change |
| Tags | `git tag`; `git rev-parse -q --verify refs/tags/v0.1.1` | only `v0.1.0`; no local v0.1.1 |
| Whitespace gate | `git diff --check fc3045db..7043a087` | exit 0, no output |
| d76→head correction | `git diff d76d658..7043a087`; trailing-space count in `07D-r1.md` | 3 files: four whitespace-only lines in `07D-r1.md` (d76: 4 trailing-space lines, head: 0), new `10-integration-corrections.md`, one PR-body sentence |
| 95b→head shipped delta | `git diff 95b61a3..7043a087 -- . ':!plan'` | exactly 9 link rewrites across 3 ADRs (3 each); no other shipped byte changed; `git grep '\.\./\.\./plan' -- docs` empty |
| Link targets | `git rev-parse 95b61a3:<path>` vs `HEAD:<path>` for 7 unique paths | all 7 blob ids identical (03-astra/fable-{boundary,interface,positioning}.md, 03-tiebreak.md); `95b61a3` is an ancestor of HEAD and present on `origin/winddown/20261013/{09,10,10-r1}` |
| Root HTTP evidence | `cat plan/artifacts/10-prepush/links.json` | 7 entries, each `status: 200`, `final_url` equals `url`; URL set equals the 7 unique URLs in the ADRs. Not re-fetched (no network) |
| Prepush scan receipt | `plan/artifacts/10-prepush/scan-command.json`, `scan.log`, `scan.json` | gitleaks 8.30.1 `git --log-opts=--all` with shipped config: 97 commits, "no leaks found", `[]`, exit 0 |
| Allowlists | `grep -c '^\[\[allowlists\]\]'` baseline vs head | 1 → 6 (five new, each AND of exact commit + path + rule + captured value) |
| Packaging excludes | `pyproject.toml` sdist `include`/wheel `packages` | sdist roster has no `/plan`, `/.github`, `/.gitleaks.toml`; wheel packages `src/evalopt_graph` only; `.gitignore` adds `/plan/{logs,scratch,artifacts}/` |
| Privacy, added lines since `4fcce23` | `git diff 4fcce23..HEAD \| grep '^+'` with secret/email/token/key patterns | zero matches for emails, `ghp_`/`sk-`/AKIA tokens, private keys, api_key/password/Bearer assignments |
| Privacy, shipped files | `git grep -nE '/Users/\|/private/tmp' HEAD -- . ':!plan'` | only pre-existing regex/test fixtures in `scripts/verify_artifacts.py`, `permissions.py`, `unattended.py`, two tests; no run paths |
| Lane correspondence | `tasks/03,04,05,08.md` file lists vs roster | every shipped change falls in an accepted lane: 03 ADRs; 04 migration map/sources/coverage; 05 README/CONTRIBUTING/SECURITY/templates/portfolio/CHANGELOG wording; 08 version fields, CI/release literals, verifier default, release notes, scanner exceptions |
| PR body figures | grep in `reports/08.md`, `09.md`, `reviews/08-codex.md`, `docs/migration-coverage.md`, `CHANGELOG.md` | 422 tests, 32 conformance cases, sixteen entries, 5 allowlists, 17 historical occurrences, 62 negatives, 79 fixture findings, scalar-row credit all corroborated by committed records |
| Central state | `git -C wt-control-00 rev-parse HEAD`; `git worktree list` | central HEAD `7ebd125`, parent `29da14b`; target not an ancestor of central (see P3-3) |

## Findings by severity

**P1 (blocking):** none.

**P2 (must fix before merge):** none.

**P3 (informational; no change to the target required):**

1. **STATUS.md understates two lanes within its own tree.** At `7043a08`, `plan/exec/STATUS.md` records 07C "freshFable queued" and 09 "fresh Fable artifact review active", while `reviews/07C-fable.md` and `reviews/09-fable.md` (both `Verdict ACCEPT`) are committed in the same tree, and 07D is "REVIEW" with `07D-fable.md` still untracked centrally. The snapshot under-claims rather than over-claims, so it is honest in the direction that matters; refresh it in the Task 11 closeout rather than by a new release-lane commit.
2. **Machine-local absolute paths in public operational records.** 49 added lines since `4fcce23` (and 66 files at HEAD, 26 already at the accepted control packet) contain `/Users/ajay/Developer/.evalopt-worktrees/...` or a `/private/tmp/...` reviewer directory. No credential, email or token accompanies them, the username matches the public account prefix, and the convention pre-dates this diff. Accepted as consistent with the already-accepted control packet; future records could name worktrees rather than absolute paths.
3. **Central control branch diverged from the target.** `wt-control-00` is at `7ebd125` ("constrain review tools after rejected mixed-model attempt"), parented on `29da14b`. It contains a one-line `supervise.py` change and four DECISIONS lines not in the target, and lacks `d76d658`/`7043a08` (ADR link rebinding, whitespace fix, both Task 10 reports, PR-body sentence). Root must pick the exact PR head deliberately; if integration produces a new head, that head needs its own exact-head checks and reviews. The target itself is unaffected.
4. **No DECISIONS entry for the post-95b rebinding.** `DECISIONS.md` ends at the 21:59 UTC qualification-invocation entry; the ADR-link rebinding and whitespace correction are recorded only in `reports/10-doc-link-closure.md` and `reports/10-integration-corrections.md`. Adequate as evidence; an optional closeout entry would make the decision log self-contained.
5. **Scanner descriptions reference a tracked plan path.** The five allowlist descriptions cite `plan/exec/reports/08-scan-preflight.md`, which is tracked and will exist on main after merge; `.gitleaks.toml` is not in the sdist. Informational.

## Verified correspondence (independent of REPORT claims)

- Product diff equals accepted 03/04/05/08 scope plus the 9 ADR links accepted in principle by the Task 09 Fable follow-up; no converter, schema, predicate, adapter, dependency, benchmark or runtime change exists in the roster.
- Kernel and all `src/`, `tests/`, `bench/` bytes are baseline-identical except the version literal; ten exports in `__all__` unchanged.
- Shipped notice, CHANGELOG, release notes and CONTRIBUTING state the STOP decision prospectively, disclose inherited post-v0.1.0 changes with contributor credit, and make no publication, archival, byte-identity or benchmark claim. Release-notes links are tag-bound (`blob/v0.1.1/...`) and resolve only after the tag, as `09-render.md` already records.
- PR body (`reports/10-pr-description.md`) is accurate at this head: it names the preserved baseline, version-only source change, sixteen-entry map, scanner exception scope, private retention of raw native evidence, and explicitly claims no publication.
- Historical failed/partial attempts (07B PARTIAL, `uv x` exit 2, first REVISE rounds) remain in Git alongside their superseding records; nothing was rewritten.

## Required changes

None for exact `7043a0879a8a5491c110bd7d8a9f466700f920b7`.

## Follow-ups (outside this verdict)

1. Fresh source-archive qualification at `7043a08`: the sdist payload differs from the accepted 09 candidate in exactly the three ADR files; the wheel packages only `src/` so its payload is unchanged (timestamps follow the new commit epoch). The separate candidate review owns this.
2. Independent Codex final integration review, exact-head hosted required checks (`CI / required`, `CodeQL / Python`, `Dependency review`, `Gitleaks / full history`), then merge with `--match-head-commit` only; the central `10-gates-current.md` report shows `delete_branch_on_merge=true`, which conflicts with the plan's no-branch-deletion rule and must be resolved or recorded as blocked before merge. No protection change is authorized by this review.
3. Resolve P3-3 (central/target divergence) before opening or updating the PR.
4. Closeout (Task 11) should refresh `STATUS.md` and may add the DECISIONS entry noted in P3-4.

## Limits

No network fetch of the seven URLs (root's `links.json` is the HTTP evidence); no rebuild, install or test rerun beyond `preservation.py`; hosted CI, attestations, tag and publication unverified here by design. Self-reported: 7 tool turns before this write, well under the requested 20, all Bash read-only; the native counter is authoritative, not this sentence.
