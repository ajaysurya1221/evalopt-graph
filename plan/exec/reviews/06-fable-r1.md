REVIEW 06 — Reviewer Fable high | Verdict REVISE

Reviewed commit: `47efbc98677f39c474545823c426bf611ca7bc33` on lane `winddown/20261013/06` versus control base `4383cd6` in `wt-portfolio-06`. Diff: one added file, `plan/exec/audits/portfolio-independence.md` (184 lines); `git diff --check 4383cd6 47efbc9` clean; lane working tree clean. Central REPORT `plan/exec/reports/06.md` read. Task spec `tasks/06.md`, execution spec `tasks/06-execution.md`, `tasks/07A.md`, PLAN.md sections A–C (frozen contract 4: no new evalopt dependency, preserve attribution, 48 frozen entries) and CONTRACT.md read explicitly. Review session was read-only: no edit, commit, network or model call in actseal, dorian, frontier-scout or agent-reliability-ci; only this review file was written.

## Summary

The substantive audit conclusions are independently confirmed: 0 of 4 repositories declare or lock an evalopt package, 0 of 4 import evalopt at runtime, the only evalopt references are adapted-source attribution (ARCI) and design attribution / documentation links / planning records (actseal), and all 48 ARCI `FROZEN.sha256` entries verify. No dependency-removal work was manufactured; no target repository was modified (all four heads match the audit, working trees clean, reflogs show only fast-forward pulls). The record is, however, an evidentiary document, and it misstates its own evidence bounds in four places and gives Task 07A guidance that conflicts with the 07A spec. Those are text corrections only; no re-audit is required.

## Findings by severity

### Medium

**F1 — Search scope claim about actseal linked worktrees is false (audit §2 and §6).**
§2 says the three linked worktrees under `actseal/.worktrees/` "were inside the search scope below and produced no hits"; §6 lists `.worktrees` among included dotfiles. Independent check: `actseal/.gitignore:19` ignores `.worktrees/` (`git check-ignore -v` confirms), and ripgrep without `--no-ignore` honours it, so `rg --files --hidden -g '!.git' -g '!.venv' /Users/ajay/Developer/actseal | grep -c '/\.worktrees/'` returns 0. Searching the worktrees directly (`rg -n -i --hidden -g '!.git' -g '!.venv' -c evalopt actseal/.worktrees`) returns 36 lines across 24 files: README.md, NOTICE, tests/docs/test_readme.py, docs/decisions/0002, plan/SOURCES.md, plan/PLAN.md, plan/RECONCILIATION.md, plan/VERIFICATION.md in each of `ci-artifact-actions`, `presence-docs` and `uv-environments`. These are the same class A/D files as on main, so the S6 conclusion is unchanged, but the audit asserts a search it did not perform.

### Low

**F2 — Audit header timestamp is wrong.** Header: "Audited 2026-10-12 19:46–20:05 UTC". Supervisor record `plan/logs/06-audit/start.json` gives `started_at 2026-10-12T19:46:32Z` and `finish.json` gives `elapsed_seconds 334.281` (end ≈ 19:52:07Z); the audit commit is dated 2026-10-13T01:21:13+05:30 = 19:51:13Z; the REPORT itself states 19:46:37Z–19:51:52Z. 20:05 UTC is after the process ended. Adjudication: the REPORT window is correct; the audit header must be corrected to match.

**F3 — Bold "Result P" overgeneralises built/installed evidence (audit §4).** "0 of 4 repositories declare, lock, build or install an evalopt package." Declare/lock is fully observed for 4 of 4 (confirmed: deps `[]`, `[]`, `['pydantic>=2.0']`, `['pydantic>=2.7,<3','pyyaml>=6,<7']`; `grep -c -i evalopt` on uv.lock/requirements.txt = 0 each; uv.lock `name =` entries 61/29/26). "Build" rests on one stale artifact set, `actseal/dist/actseal-0.1.0-py3-none-any.whl` and `.tar.gz` dated 6 Oct, built before the current 1.0.1 head; no artifacts exist for the other three. "Install" rests on three local venvs (actseal py3.12, frontier-scout py3.14, ARCI py3.13); dorian has no `.venv`. The section body and §8 state these limits honestly, but the bold result line does not. Adjudication: root's concern is upheld; the bold line must be narrowed to what was observed.

**F4 — Frozen-manifest breakdown miscounts two groups (audit §7).** Text says "four `docs/*.md`" and "29 files under `tests/acceptance/`". Actual: three `docs/*.md` (AGENT_SEMANTICS, STATISTICS, TRUST_MODEL), four `docs/design/*.md`, 30 under `tests/acceptance/`, plus `tests/__init__.py`. The total of 48 and the verification result are correct.

**F5 — Task 07A guidance conflicts with the 07A spec (audit §6, actseal table, and REPORT open issues).** The audit says "Any 07A README edit must keep or co-update this test." `tasks/07A.md` is README-only and says "Preserve NOTICE, source, tests, metadata and plans", so co-updating `tests/docs/test_readme.py` is not available to 07A. The guidance must say the README edit has to retain the pinned URL. The guard is also stricter than the audit records: `test_related_projects_are_three_sentences_naming_four_repositories` requires the "Related projects" section to be one paragraph of exactly three sentences, to contain the `COMPARISON` string ("gates repeated-trial agent regressions … accepted-action risk and coverage"), to end with "against supplied evidence.", and to contain `(<url>)` for all four `RELATED_REPOSITORIES` including `https://github.com/ajaysurya1221/evalopt-graph`.

### Informational (no change required)

- REPORT says "15 tool turns"; the supervisor's `native.json` records `num_turns 30`. Different counting bases; neither affects the findings. Requested effort high, model `claude-fable-5-1`, cost recorded by root at 2.77 USD; no web fetch/search requests in usage.
- The audit's statement that the frontier-scout dogfood settings hold 56 allow / 12 deny / 21 ask with PreToolUse and PostToolUse hooks is confirmed.
- Both pinned attribution commits exist: ARCI `d13dd94…` (merge of PR #10, 2026-10-06) and evalopt `9bbc192…` (2026-10-05, pyproject version 0.1.0).

## Required changes (one revision commit on the lane, audit file only; then refresh the SHA in the central REPORT)

1. §2 and §6: replace the worktree sentence with the truth: `.worktrees/` is gitignored and was excluded by ripgrep's ignore rules; either state it was not searched, or report the direct-search result (36 lines in 24 files, same README/NOTICE/test/ADR/plan files as main, class A/D, zero imports or manifests). Remove `.worktrees` from the §6 included-dotfiles list unless the direct search is added.
2. Header: correct the window to the supervised span (19:46–19:52 UTC) or the REPORT's 19:46:37Z–19:51:52Z.
3. §4 bold Result P: narrow to "0 of 4 declare or lock an evalopt package; no evalopt package is present in the only built artifacts on disk (actseal 0.1.0, pre-1.0.1) or in the three local environments observed (dorian has none)."
4. §7: "three `docs/*.md`" and "30 files under `tests/acceptance/`".
5. Actseal table row for `tests/docs/test_readme.py:191` and the REPORT open-issues sentence: replace "keep or co-update this test" with "07A is README-only and must retain the pinned evalopt-graph URL and satisfy the guard's three-sentence, `COMPARISON` and closing-phrase constraints; the test is not in 07A scope."

No change to findings, classifications, heads, counts or dispositions is required.

## Follow-ups

- Task 07A executor: read `test_related_projects_are_three_sentences_naming_four_repositories` before editing the "Related projects" paragraph; run `uv run --frozen pytest -m "not integration and not packaging"` as the 07A spec requires.
- Root: when integrating, note that the central REPORT will need its commit SHA updated after the revision commit.
- Optional, not blocking: if a future audit wants built-artifact evidence for the current heads, it would require building, which is outside this read-only task.

## Checks performed by the reviewer (all read-only)

| Check | Command (abridged) | Result |
|---|---|---|
| Diff scope | `git diff --name-status 4383cd6 47efbc9`; `git diff --check` | 1 file added; clean |
| Heads | `git -C <repo> rev-parse HEAD`, `--abbrev-ref`, `describe --tags`, `log -1 --format=%cI %s`, `remote -v`, `status --short`, `reflog -3` | All four heads, tags, messages, remotes match the audit; `main`; clean; reflogs show only fast-forward pulls |
| actseal worktrees | `git -C actseal worktree list`; `git check-ignore -v .worktrees` | 3 linked worktrees at 9ec4193/3549413/9289cda; `.gitignore:19 .worktrees/` |
| Manifests | `python3` tomllib over each `pyproject.toml`; `ls` depth-1 manifest names | Matches audit §4 exactly (names, versions, deps, extras, groups, uv.sources, build-system); only uv.lock/requirements.txt present |
| Locks | `grep -c -i evalopt uv.lock\|requirements.txt`; `grep -c '^name = ' uv.lock` | 0/0/0/0; 61/29/26; frontier-scout requirements.txt is `pydantic>=2.0` only |
| Strict search | `rg -n --hidden -g '!.git' -g '!.venv' -g '!node_modules' -g '!*.egg-info' -g '!.mypy_cache' -g '!.pytest_cache' -g '!.ruff_cache' 'evalopt[-_]graph' <repo>` | 8 / 0 / 0 / 6 |
| Case-insensitive search | same globs, `-i 'evalopt'` | 12 / 0 / 0 / 6; every hit line and file:line matches the audit's classification tables |
| Import search | same globs, `-t py -e '^\s*(from\|import)\s+evalopt' -e 'import_module\(\s*["'"'"']evalopt'`; `rg --files -t py` | 0 / 0 / 0 / 0 imports; 129 / 150 / 58 / 148 files (485 total) |
| Worktree search | `rg -n -i --hidden -g '!.git' -g '!.venv' -c evalopt actseal/.worktrees`; `rg --files` from root | 36 lines, 24 files; 0 worktree paths listed from root |
| Built artifacts | `unzip -l` / `unzip -p '*/METADATA'` on the wheel; `tar -tzf` sdist | 0 evalopt paths; `Requires-Dist` only `laya`-extra lines; artifacts dated 6 Oct, version 0.1.0 |
| Installed envs | `ls <repo>/.venv/lib/python*/site-packages/*evalopt*` | None in actseal (3.12), frontier-scout (3.14), ARCI (3.13); dorian has no `.venv` |
| Frozen manifest | `shasum -a 256 -c FROZEN.sha256`; `wc -l`; non-blank; distinct paths; `git ls-files --error-unmatch` + `git diff --quiet HEAD` per path; `shasum` of manifest; `git rev-parse HEAD:FROZEN.sha256`; `git log -1 -- FROZEN.sha256` | 48 OK, exit 0; 48/48/48; 48 tracked, 0 differ; `c57d097d…a3e2`; blob `3904622f…`; `e304e816…` 2026-10-03T15:27:18Z; `src/arci/hashing.py` is listed |
| Attribution lines | `sed -n` on actseal `NOTICE:12`, `README.md:181`, ADR 0002 lines 18/22, `plan/SOURCES.md:129,141`, `plan/VERIFICATION.md:19`; ARCI `src/arci/hashing.py:6-7`, `NOTICE:4-9`; `grep -c -i evalopt src/arci/schema.py` | All match the audit verbatim; schema.py has 0 inline mentions |
| Pinned commits | `git cat-file -t`, `git log -1` for `d13dd94…` (ARCI) and `9bbc192…` (evalopt) | Both exist with the dates/messages the audit gives |
| Guard test | `tests/docs/test_readme.py` lines 136, 187–192, 636–645 | Constraints as stated in F5 |
| Operating contracts | existence of actseal CLAUDE.md/AGENTS.md/NOTICE/plan/CONTRACTS.md/plan/v1/STATE.md, dorian CONTRIBUTING.md (no AGENTS/CLAUDE), frontier-scout CLAUDE.md/AGENTS.md/.claude/settings.json, ARCI AGENTS.md/NOTICE; quoted rules | All present/absent as the audit states; quoted rules found (`dorian CONTRIBUTING.md:43`, `frontier-scout CLAUDE.md:15`, `ARCI AGENTS.md:17`) |
| README sibling claims | grep of dorian, frontier-scout, ARCI READMEs | dorian names no sibling; frontier-scout names only Notari; ARCI names frontier-scout once (`README.md:179`) and never evalopt |
| Timing | `plan/logs/06-audit/start.json`, `finish.json`, `native.json`; commit `%cI` | start 19:46:32Z, elapsed 334.281 s, DONE, head `47efbc9…`; commit 19:51:13Z |

Verdict REVISE: the audit's decisive observations are correct and independently reproduced, but the evidentiary record must not claim a search it did not run (F1), a window it did not occupy (F2), or evidence it did not observe (F3), and its 07A guidance must match the 07A spec (F5). After the five text corrections above, a fresh review can ACCEPT without re-auditing.
