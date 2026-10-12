REVIEW 08 — Reviewer Fable xhigh | Verdict ACCEPT

Fresh independent actual-patch review of `1d8148644984ab7a8548960439b3a9d0adf7f729` ("release: prepare final 0.1.1 deprecation package", author ajaysurya1221, 2026-10-13T03:13:15+05:30) against parent `19369be` in `wt-release-08`. Working tree was clean at that head before and after this review. This is a patch review only; it is not publication, merge, tag or release approval, and the hosted exact-head CI, artifact qualification and publication gates remain outstanding. No target file was edited, no model subprocess, push, release, settings, credential or global change was made. The only central write is this file; reproductions went to new private temp directories and never overwrote the retained `08-scanner-controls-03` originals (verified by hash and mtime afterwards).

## Scope inspected

Read in full: `plan/exec/tasks/08.md`, `tasks/08-review.md`, `reports/08.md`, `reports/08-scan-preflight.md`, `reports/08-scanner-contract.md`, `reports/08-scan-commit-opinion.md`, `reports/08-release-preflight.md`, `.gitleaks.toml` at head, `plan/exec/scanner_controls.py`, the complete 12-file diff, `plan/exec/baseline.json`, `plan/exec/verify.sh`, `plan/logs/08-release-validation.log`, `plan/logs/08-environment.txt`, `plan/logs/08-all-local-history.*`, `plan/artifacts/08-release-validation/conformance.json`, and every file in `plan/artifacts/08-scanner-controls-03`.

## Findings by severity

**High:** none.

**Medium:** none.

**Low / informational (no change required for ACCEPT):**

1. **Unretained verifier output.** REPORT 08 states the pinned `verify_release.py --expected-version 0.1.1` run passed, but no central log contains its success line (`grep -rl 'release identity verified' plan/` is empty; `verify.sh` does not invoke it). The claim is confirmed by this review's own run (exit 0, below). Root should retain that output in the release receipt rather than relying on the report sentence.
2. **Commit-count wording.** The report says "99-commit frozen public mirror"; the scanner logs say "78 commits scanned". Both are correct: `rev-list --all --count` = 99, of which 21 are merge commits that `git log -p` presents without a diff, leaving 78 non-merge commits. CI uses the same flags, so the comparison is like-for-like; wording could state both numbers.
3. **Missing-regex mutant row count.** The mutant retains 40 findings while a per-case count predicts 38. The two extras are benign second detections by `generic-api-key` of the synthetic `access_token = "ghp_…"` control lines inside `compatibility.json` (where only the github-pat entry exists). The script's sensitivity figure (24 lost registered negatives) is computed per registered case and is correct; no change needed.
4. **Git-mode-only exemption (accepted narrowing).** Under `gitleaks dir` the commit field is empty and the five entries can never allow anything: dir-mode results are identical under original and candidate (79 = 79). The only repository invocation is git mode (`ci.yml:172`, `--log-opts="--all"`), so this is the deliberate narrowing from the opinion, not a defect.
5. **Environment log timing.** `08-environment.txt` shows the `.venv` first built with `evalopt-graph==0.1.0` (environment created before the version edit); the later `uv run --frozen` re-synced to 0.1.1 and the verifier passed. Informational only.

## What was verified independently

**Diff and preservation (12 files, +592/−14, `git diff --check` clean, exit 0).**
- `src/tests/bench` vs run baseline `fc3045db`: only `src/evalopt_graph/__init__.py` (`__version__` 0.1.0→0.1.1). `plan/exec/preservation.py` → `{"protected_files": 75, "errors": []}`, exit 0.
- Version consistency: `pyproject.toml:7`, `__init__.py:20`, `uv.lock:80` all `0.1.1`. `uv.lock` and `pyproject.toml` diffs are one line each, so dependency declarations and the resolved graph are unchanged; `uv lock --check` (pinned uv 0.11.29) → "Resolved 34 packages", exit 0.
- CI/release: `ci.yml` changes only the two expected-version literals; `release.yml` changes `RELEASE_VERSION`, the title suffix and the two notes paths to `docs/releases/v0.1.1.md`; `verify_artifacts.py` default only. No action pin, protection, environment, permission or asset-handling line changed; the draft-release refusal/compare logic is intact.
- Historical references retained: `docs/releases/v0.1.0.md` untouched; CHANGELOG `[0.1.0]` entry and link retained; remaining `0.1.0` mentions are historical prose or the bug-template example, not live gates. `verify_release.py`/`verify_installed_release.py` carry no stale version default.
- Inherited changes disclosed: release notes and CHANGELOG name the PR #4 scalar-row fix (author of `624ed11` is "Göktuğ Özkan, MD" <…goktugozkanmd@users.noreply…>, matching the credit), the `sys.executable` test-command inference, the compatibility-warning/docstring wording, the hatchling pin and optional-dependency floors, metadata 2.4 and the helper-asset move. No byte-identical or behavior-identical claim versus v0.1.0; publication/archival are explicitly not claimed. "Sixteen entries" matches `docs/migration.md` (entry 16 present). Links to `blob/v0.1.1/...` are forward references that resolve only after the tag exists; acceptable for release notes.
- Packaging: `plan/` is outside the sdist include roster (`pyproject.toml:57–70`) and outside `ALLOWED_SDIST_ROOTS` in `scripts/verify_artifacts.py`, so `scanner_controls.py` cannot ship.

**Scanner correction (`.gitleaks.toml`, SHA-256 `7b4a8fdb…6788`).**
- Original configuration (SHA-256 `4a228e1a…83aa`, equal to `baseline.json`) is a byte-exact prefix of the candidate; `[extend] useDefault = true` and the existing synthetic OpenAI exception are unchanged; no stock rule is copied, overridden or disabled; no whole file, directory or commit is excluded.
- Each of the five entries (H4, HN, HO, D, T) has exactly: `targetRules` = one stock rule ID (`generic-api-key` ×4, `github-pat` ×1), `condition = "AND"`, `regexTarget = "secret"`, `commits` = one full lowercase 40-hex SHA that exists as a commit object in the frozen mirror, `paths` = `^…$`-anchored escaped exact repository paths, `regexes` = one `^…$`-anchored exact captured value. Group→commit→path assignment equals the preflight/opinion tables (H4: V4 → V4M,V4R; HN/HO: V1M → V1C,V1S; D: V1P → classifier.py; T: V4 → V4C). T's regex `^ghp[_]SYNTHETIC…$` is the exact 40-character stock capture, written so the configuration itself is not a github-pat match.
- Retained 17-finding roster: `history-original.json` identities (commit, file, rule, lines, columns) equal both `plan/logs/public-history-scan.json` (SHA-256 `0b3cbece…f65b`) and the 17-row preflight table exactly; all secrets are `REDACTED`. Candidate on the same mirror → 0 findings, exit 0; refs roster identical before/after/final.
- Fixture (79 registered cases, 24 files, 56 generic-api-key + 23 github-pat): all 79 detected under the original config; all 79 still reported under the shipped candidate in a fresh commit (commit pinning holds). Under the derived matching-commit configuration exactly 17 rows disappear, every one of them an allowed (rule, exact path, exact value) triple, and zero retained rows are allowed triples: changed values, prefix/suffix variants, wrong/near paths, the distinct token on the same line and in the same file all remain reported. Missing-regex mutant loses 24 negatives; OR mutant loses all 62; one-digit commit typo restores exactly the 11 V4 findings (10 + 1); `condition = "AND_typo"` fails config load ("unknown allowlist |condition|"). Legacy OpenAI exception: stock config finds 3, original and candidate each find only `other.py`.
- Patch commit itself: `gitleaks git --redact --config .gitleaks.toml --log-opts="19369be..1d81486"` → 0 findings (also 0 under the baseline config); full lane branch `winddown/20261013/08` (47 commits) → 0 findings. Root's `08-all-local-history` scan (91 commits) also reported none.

## Commands run (exact, all in `wt-release-08` unless noted)

- `git rev-parse HEAD`; `git status --short`; `git diff --stat 19369be 1d8148644984ab7a8548960439b3a9d0adf7f729`; full `git diff` of the ten non-plan files; `git diff --check 19369be 1d81486` → exit 0.
- `git diff --stat fc3045dbda29c1d274747329ceb6724a783b0df7 1d81486 -- src tests bench` → only `__init__.py` (+1/−1).
- `python3 -B plan/exec/preservation.py` → `{"baseline": "fc3045db…", "protected_files": 75, "errors": []}`, exit 0.
- `plan/artifacts/tooling/bin/uv --version` → 0.11.29; `uv lock --check --offline` → Resolved 34 packages, exit 0; `uv run --frozen --extra dev python scripts/verify_release.py --expected-version 0.1.1` → "release identity verified for evalopt-graph 0.1.1", exit 0 (output kept at `/tmp/08-fable-verify-release.out`).
- Hash/prefix checks: `shasum -a 256` on candidate/original/mutant TOMLs and head `.gitleaks.toml`; `diff candidate.toml .gitleaks.toml` → identical; `head -c $(wc -c < original.toml) candidate.toml | diff - original.toml` → identical; `diff` of each mutant vs candidate (only the intended lines differ).
- Python recomputation over the retained JSON outputs (roster equality incl. columns vs retained scan and preflight table; exempt-set/retained-set classification; mutant deltas; dir-mode commit fields; wrong-commit distribution; legacy results) — results as stated above.
- `git -C plan/artifacts/public-scan.git rev-list --all --count` → 99; `--merges --count` → 21; `--no-merges --count` → 78; `show-ref` SHA-256 `48a51f98…ffd3` (equals summary); `cat-file -t` for V4, V1P, V1M → commit.
- Reproduction: `python3 plan/exec/scanner_controls.py --history plan/artifacts/public-scan.git --expected plan/logs/public-history-scan.json --out /tmp/08-fable-review.YKCnd5/controls` → `status PASS`, 17→0, 79/79/62, lost negatives {missing-regex: 24, or-condition: 62}, dir 79, typo 11, exit 0, 24 commands, 6.6 s (new fixture commit `9bbaecd0…`, confirming the controls do not depend on the earlier fixture SHA). Originals untouched afterwards: `summary.json` SHA-256 `c95871b7…5370`, mtime 03:12:11 +0530.
- `gitleaks version` → 8.30.1; range scan, branch scan and baseline-config range scan to `/tmp/08-fable-scan.GGoWED/{range,branch,range-original}.json` → `[]`, exit 0 each.
- `git log -1` for `1d81486` and `624ed11`; `git grep -n '0\.1\.0' 1d81486` (excluding plan, lock, v0.1.0 notes); `git ls-files plan/exec/reports/` (all five 08 preflight/contract/opinion reports are tracked at head, so the config descriptions' cross-reference resolves).

## Required changes

None.

## Follow-ups (root)

1. Retain the `verify_release.py` output and this review's private reproduction paths in the release receipt; the hosted exact-head `Gitleaks / full history` result after push is the authoritative 0-finding evidence for the public repository.
2. Optionally state both commit counts (99 reachable, 78 non-merge scanned) where the report cites the mirror.
3. Codex independent review of the same head (`08-codex-native-review-01` artifacts exist but were not evaluated here) must also ACCEPT before integration; this review does not substitute for it.

## Limits

Read-only review; no Go toolchain, so scanner semantics were taken from executed native controls and the retained source excerpts, not from a rebuilt binary. Controls are finite and specific to Gitleaks 8.30.1 (binary SHA-256 `f414bc2f…2302`), this configuration and this frozen history; they do not certify the absence of other secrets or future scanner behavior. Hosted CI, artifact build/inspection, publication gates and the Codex review remain outstanding. Requested model/effort: Fable 5.1 (`claude-fable-5-1`), xhigh; the effective effort is not observable from inside the session. Nine tool-bearing turns of 20; elapsed about 8 minutes of 20 (start 21:45:55Z, review written 21:53Z). No usage figures are estimated.
