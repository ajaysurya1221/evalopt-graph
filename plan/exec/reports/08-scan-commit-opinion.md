# REPORT 08-SCAN-OPINION — Status DONE

Read-only security design consultation by Fable 5.1 (requested effort xhigh) before the root-owned Task 08 scanner correction. One bounded question was answered from the retained Gitleaks 8.30.1 source (upstream `83d9cd684c87d95d656c1458ef04895a7f1cbd8e`), the two control reports, the installed CLI help, the retained redacted scan report and the repository's CI scan step. No candidate configuration was written, no scan was run, no fixture was created and no target file was altered. This is an opinion with evidence; it is not a review, not an approval and not a substitute for the native controls and the two actual-patch reviews.

## Decision: ADD exact commit constraints

Each of the five group entries (H4, HN, HO, D, T) should be a top-level targeted `[[allowlists]]` entry with `condition = "AND"`, `regexTarget = "secret"`, the diagnosed `targetRules`, the anchored exact path regexes, the anchored exact captured-secret regex, **and** a `commits` list holding only the full 40-hex SHA(s) in which that group's occurrences actually exist. The path and value constraints stay exactly as approved in `08-scan-preflight.md`; the commit list is added to them, never substituted for them.

Group-to-commit assignment (from the retained report's `Commit` fields: 11 findings at V4, 2 at V1P, 4 at V1M):

| Group | Rule | Commits allowed | Paths allowed |
|---|---|---|---|
| H4 | generic-api-key | V4 only | V4M, V4R |
| HN | generic-api-key | V1M only | V1C, V1S |
| HO | generic-api-key | V1M only | V1C, V1S |
| D | generic-api-key | V1P only | V1P |
| T | github-pat | V4 only | V4C |

Do not list all three SHAs in every entry. The `commits` list is OR within itself exactly like `paths` and `regexes`, so a shared list would create unreviewed cross-product permissions (for example H4 at V4M inside V1M, which never existed).

Non-executable placeholder shape, one entry per group (root writes the actual patch):

```toml
[[allowlists]]
description = "<group>: nonsecret <kind> already public at <commit alias>; see plan/exec/reports/08-scan-preflight.md"
targetRules = ["<diagnosed-rule-id>"]
condition = "AND"
regexTarget = "secret"
commits = ["<full-40-hex-sha-lowercase>"]
paths = ['''^<escaped-exact-path-1>$''', '''^<escaped-exact-path-2>$''']
regexes = ['''^<escaped-exact-captured-Secret>$''']
```

## Source-line evidence

All line numbers refer to the retained copies under `plan/artifacts/gitleaks-8.30.1-source/` (SHA-256 values re-hashed locally and matching `manifest.json`).

**1. `commits` participates in the same AND at finding time; it does not trigger an earlier whole-commit bypass when `regexes` is present.**

- `detect_detect.go:767-816` (`checkCommitOrPathAllowed`) is the fragment-level gate, called for global allowlists at `:302` and for rule allowlists at `:388`. Under AND it records the commit check (`:785-787`) and path check (`:788-790`), then hits `if len(a.Regexes) > 0 { continue }` at `:791-793` (and the stopword equivalent at `:794-796`) **before** `isAllowed` is assigned at `:798`. An AND entry containing `regexes` therefore never skips a fragment, whether or not it also has `commits`.
- `detect_detect.go:823-891` (`checkFindingAllowed`) is the per-finding gate, called inside the per-match loop for global allowlists at `:562` and rule allowlists at `:568`. Under AND it appends the commit check from `fragment.CommitSHA` (`:851-854`), the path check (`:855-858`), the regex check against the extracted Secret (`:859-861`) and stopwords (`:862-864`), then requires `allTrue` (`:866`, `:893-900`). A finding that fails any one check is appended at `:573`. So the same value in a commit outside the list fails the commit check and is reported, which is exactly the property the question asks for.
- Two shapes that **would** create a whole-fragment bypass, and must be excluded by review: (a) an AND entry with `commits` and/or `paths` but no `regexes`/`stopwords` reaches `isAllowed = allTrue(...)` at `:798` and `detectRule` returns early at `:388-391`; (b) an entry whose `condition` is omitted or misspelled parses as OR (`config_config.go:323-324`) and then `:801` allows the whole fragment on commit **or** path, and `:868` allows any finding on regex alone. Keeping `regexes` and the literal `condition = "AND"` is therefore load-bearing, with or without commits.

**2. Commit metadata exists at match time and is compared exactly.**

- `finding.Commit` is copied from `fragment.CommitSHA` at `detect_detect.go:489`, and the same `fragment.CommitSHA` is what `:852` tests. The retained report `plan/logs/public-history-scan.json` (SHA-256 `0b3cbece…f65b`, unchanged) shows every one of the 17 `Commit` fields as a full 40-character lowercase SHA, which is therefore the exact string the detector saw.
- `config_allowlist.go:84-92` normalizes configured commits with `TrimSpace` + `ToLower` into `commitMap`; `:117-133` (`CommitAllowed`) does an exact map lookup of `ToLower(c)`. There is no prefix or short-hash matching (the TODO at `:63-64` says so). Consequence: the configuration must carry the full 40-hex SHA; a truncated, mistyped or rebased SHA makes the entry inert, which fails closed (the findings stay visible and CI fails).
- `CommitAllowed("")` returns false at `:118-120`. In `gitleaks dir`, `stdin` and pre-commit modes `fragment.CommitSHA` is empty, so a commit-bearing AND entry can never allow anything there. The repository's only scanner invocation is git mode: `.github/workflows/ci.yml:172` runs `gitleaks git --redact --config .gitleaks.toml --log-opts="--all" .`. The six affected paths are absent from `main` HEAD (checked with `git cat-file -e main:<path>` for all six), so no working-tree scan needs the exemption. The three commits exist locally as commit objects.

**3. How top-level targeted allowlists are transformed.**

- `config_config.go:228-242`: each top-level `[[allowlists]]` is parsed by `parseAllowlist` (`:318-363`), which copies `Commits` verbatim at `:353` and calls `Validate()` at `:359`, building `commitMap`, `pathPat` and `regexPat`. Entries with `targetRules` are held in `ruleAllowlists` and are **not** appended to the global list (`:233-241`).
- After `extendDefault` runs (`:250-252`), and only at extend depth 0, the targeted entries are appended to the named rule's `Allowlists` (`:269-277`); an unknown rule ID is a load error (`:273`). `extend()` keeps stock regex, entropy, secret group, path and keywords unless the user config defines the same rule (`:459-477`); a targeted top-level entry defines no rule, so stock detection is untouched.
- Because the pointer is appended, the validated `commitMap` survives into `r.Allowlists`. Those entries are then evaluated only at `detectRule:388` (skipped by the `continue` above) and at `detectRule:568` (finding-level AND). Global non-targeted entries, such as the existing synthetic OpenAI exception, are evaluated at `:302` and `:562` under the same rules.

## Consequences of ADD

1. **Strictly narrower, no new suppression.** The exemption universe becomes "findings produced from fragments whose commit is V4, V1P or V1M, in the listed path, under the listed rule, whose extracted Secret equals the listed literal". Within those commits, path AND secret are still required, so unrelated findings in those commits stay visible. The original all-refs scan shows those commits produced exactly the 17 classified findings and nothing else.
2. **Identical strings in later commits stay detectable.** Any new commit, cherry-pick, rebase, squash, or merge-side fragment carrying the same value at the same path has a different SHA and fails the commit check at `:852-853`. This closes the scanner-contract Limit 1 ("will also exempt an identical value under the same rule in the same allowed path if encountered again").
3. **Control 1 becomes a complete enumeration, not a snapshot.** Commits are immutable, so the set of fragments carrying the three SHAs is fixed as long as the git-log options stay fixed. A 17→0 comparison with full identity (commit, file, rule, start/end line, start/end column, redacted value digest) therefore proves everything the entries can ever suppress. Keep `--log-opts="--all"` and the other flags identical between the before and after runs; different log options (for example `-m`) can present the same diff under a merge SHA, which would then be reported, not suppressed.
4. **Fail-closed on configuration error.** Wrong rule ID: load error. Wrong or short SHA: entry inert, 17 findings remain, exit 1. Omitted `regexes`: whole-fragment bypass, which the new-commit controls below detect. Omitted or misspelled `condition`: OR semantics, which the same controls detect.
5. **The exemption is git-mode only.** The stdin capture-boundary technique used in the preflight will keep showing 17 findings under the candidate configuration. That is the expected behaviour of `CommitAllowed("")`, not a defect, and it must not be "fixed" by adding a parallel entry without `commits`; such an entry would reopen the gap that ADD closes. If a future working-tree scan ever needs these files exempt, that is a separate decision needing its own review.
6. **New-commit negative controls no longer prove path/value anchoring by themselves.** Under the shipped configuration any control placed in a fresh commit is reported because the commit check already fails, and trace logging (`:870-888`) emits only when an allow succeeds, so the output cannot show whether the path or value anchor also held. The anchors are still worth proving, both as defence in depth and because the preflight's controls 2-4 were written to prove them. The derived-configuration control below restores that proof at negligible cost.
7. **Finer than fingerprints.** A `.gitleaksignore` fingerprint is commit:file:rule:start-line (`detect_detect.go:711-715`) and cannot separate two findings on one line. The commit-pinned AND entry is commit AND path AND rule AND exact extracted value, so two different captured values on one line are handled separately, as the preflight requires for the sealed manifest.

## Native controls required before acceptance (root runs; none were run here)

All runs must record: `gitleaks version` output (8.30.1), SHA-256 of the configuration used, the exact command line, the exact refs scanned, the "N commits scanned." count from the log, the exit code, and must keep the original report. Use `--report-format json --report-path -` or a file; never print unredacted captures of unknown values.

Positive controls (git mode, the fixed public mirror, flags identical to `ci.yml:172`):

- **P1 Baseline reproduction.** Original configuration (SHA-256 `4a228e1a…83aa`) → exactly 17 findings, exit 1, identities equal to the retained roster including columns.
- **P2 Candidate configuration.** Same mirror, same flags → 0 findings, exit 0, same commit count. The identity diff between P1 and P2 must be exactly the 17 occurrences, nothing more and nothing fewer.
- **P3 Load check.** The candidate configuration loads with no "target rule ID … does not exist", no "must contain at least one check" and no "unknown allowlist |condition|" error; every `commits` element is 40 lowercase hex characters equal to one of the three retained SHAs.

Negative controls under the **shipped** candidate configuration (must be git mode with real new commits in a throwaway clone or fixture repository, not stdin, because new SHAs are the point):

- **N1 Later identical value.** Commit each approved value (for T, the exact 40-character capture) into (a) its exact permitted path, (b) a different path and (c) a near-matching path. All must be reported under the original rule. This is the headline property and also detects a missing-`regexes` bypass and OR misconfiguration (an OR entry would allow (a) by path at `:801` and (b)/(c) by regex at `:868`).
- **N2 Distinct value in permitted path.** Commit a changed value and a finite synthetic stock-rule credential into each permitted path, including on a line that also contains the approved value. All must be reported.

Negative controls under a **derived control configuration** that is byte-identical to the shipped candidate except that every `commits = [...]` line is deleted (prove this with `diff`; the derived file is a test artifact and must never be committed as `.gitleaks.toml`):

- **N3 Path anchoring.** Preflight control 2: each approved value in a different path and a near-matching path → reported.
- **N4 Value anchoring.** Preflight controls 3-4: prefix/suffix/regex-metacharacter variants, changed values, a different 40-character token-shaped value for T, and distinct synthetic credentials on the same line as an approved value → reported; only the exact approved value in the exact approved path is exempt. These may run in stdin or dir mode because no commit check is involved.

Optional sentinel: **N5** copy the candidate configuration, alter one hex digit of one SHA, rerun P2 → that group's findings must reappear. This demonstrates exact commit matching and that a typo cannot widen scope.

Regression: **N6** the existing synthetic OpenAI fixture exception still works unchanged and unrelated stock rules still fire (preflight control 5). Both the fresh Fable security review and the Codex diff review of the actual patch plus these control outputs remain required before merge.

## Changes

Only this file was created: `plan/exec/reports/08-scan-commit-opinion.md` in the `wt-control-00` worktree, as assigned. No commit was made; root commits in that worktree. Nothing else was written, staged or modified in any worktree.

## Tests (commands + results)

Read-only inspection only; no scanner run, fixture, or configuration change.

- `cat plan/exec/reports/08-scan-preflight.md`, `cat plan/exec/reports/08-scanner-contract.md` → read in full.
- `shasum -a 256 plan/artifacts/gitleaks-8.30.1-source/*` → `config_allowlist.go` `5fac8234…d7f`, `config_config.go` `c7366086…71a`, `detect_detect.go` `2bac563a…d13`, all equal to `manifest.json`.
- `cat -n`/`sed -n` over the three Go files → line references above.
- `gitleaks version` → `8.30.1`; `gitleaks git --help` → confirms `--log-opts`, `--config`, `--redact`, `--report-path -`.
- `git cat-file -t` for V4, V1P, V1M → all `commit`; `git cat-file -e main:<path>` for the six paths → all absent at `main` HEAD.
- `grep -o '"Commit": *"[^"]*"' plan/logs/public-history-scan.json | sort | uniq -c` → 11×V4, 2×V1P, 4×V1M, all full 40-hex lowercase; report SHA-256 unchanged `0b3cbece…f65b`.
- `shasum -a 256 .gitleaks.toml` → `4a228e1a…83aa`, matching `plan/exec/baseline.json`; the file was read, not modified.
- `grep -rn 'gitleaks (git|dir|…)'` → single invocation at `.github/workflows/ci.yml:172`, git mode with `--log-opts="--all"`.

## Deviations (with reason)

None. The report was written to the assigned absolute path in `wt-control-00` rather than this session's `wt-control-review-01` worktree because the task names that path explicitly.

## Open issues

- `sources/git.go`, which populates `fragment.CommitSHA` and adds gitleaks' own `git log` arguments, is not in the retained source set. Evidence that the compared string is the full lowercase SHA comes from `detect_detect.go:489` and the retained report's `Commit` fields; P1/P2 would expose any mismatch as a fail-closed residual.
- No Go toolchain is installed, so the semantics above were read, not executed. P1-P3 and N1-N6 are the executable evidence.
- The git-mode-only consequence (item 5) is accepted here; it is a deliberate narrowing, not an omission.

## Spend

Requested model/effort: Fable 5.1 (`claude-fable-5-1`), xhigh. Observed model id: `claude-fable-5-1`; the effective effort setting is not observable from inside the session. Usage and elapsed time are not estimated, per task instruction. Five tool-bearing turns preceded the report write, which was the sixth, within the 15-turn request.
