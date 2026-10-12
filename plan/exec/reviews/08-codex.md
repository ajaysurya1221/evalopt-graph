REVIEW 08 — Reviewer Astra (Codex independent review lane) | Verdict ACCEPT

Exact reviewed head: `1d8148644984ab7a8548960439b3a9d0adf7f729`, worktree `wt-release-08`. Exact comparison base: `19369be2f88cfa5f7de269b5ad56204b52cd8242`. Frozen implementation baseline: `fc3045dbda29c1d274747329ceb6724a783b0df7`. Review date: 2026-10-13 IST / 2026-10-12 UTC.

This is acceptance of the Task08 patch at that head, **not publication approval**. The candidate was clean before review and remained unchanged. The approved Task08 and executor contract, central release/scanner preflights, design assessments, actual patch, candidate REPORT, native control implementation, retained source and raw control evidence were inspected independently. The author's DONE report and prior design opinions were not treated as actual-patch acceptance.

## Findings by severity

No unresolved actionable finding.

**Scope and implementation preservation.** The twelve-path diff is limited to the approved versions, current CI/release/artifact version expectations, README/CHANGELOG, new release notes, `.gitleaks.toml`, and the run-local scanner control/report files. `src/evalopt_graph/__init__.py:20` changes only the version literal. The read-only preservation control passed all 75 baseline source/test/bench files after normalizing that one allowed literal, and the approved PLAN digest passed. Direct byte comparison independently confirmed the source-literal-only change. Parsed `pyproject.toml` and `uv.lock` are identical to the comparison base after reverting only the root version in memory: build pin, dependency declarations, optional dependencies and resolved dependency graph are unchanged; required runtime dependencies remain empty. Action `uses` pins are identical; workflow diff inspection shows no permission, protection, job dependency, full-history scan or immutable-release-asset protection changes.

**Release wording and identities.** The current versions consistently move to 0.1.1. Historical 0.1.0 notes remain. `docs/releases/v0.1.1.md:14–38` and CHANGELOG disclose inherited differences since the 0.1.0 tag, including the scalar-row validation fix and PR4 credit, interpreter selection, helper relocation, packaging and optional dependency floors. They distinguish preservation of the main baseline from the larger historical release delta. The notes distinguish hashes, signatures and semantic correctness; publication status comes from the public release record, and archival remains a separate human action. The new run-local files are outside the unchanged package include allowlists; actual distribution-byte qualification remains a later gate.

**Scanner constraints.** `.gitleaks.toml:13–69` adds exactly five entries for H4, HN, HO, D and T. Each has only its diagnosed stock rule, its one exact 40-hex historical commit, its own anchored escaped paths, `condition = "AND"`, `regexTarget = "secret"`, and one exact anchored captured-value expression. There is no cross-product of unrelated groups, whole-file/commit/directory waiver, rule override, commit-free fallback or new global allowance. The original configuration, stock extension and pre-existing synthetic-fixture exception remain an exact prefix.

The retained upstream Gitleaks v8.30.1 source at `83d9cd684c87d95d656c1458ef04895a7f1cbd8e` was re-hashed (3/3 manifest matches) and decisive code read: targeted entries attach only to named rules (`config_config.go:228–277`); AND entries with regexes defer fragment skipping (`detect_detect.go:767–815`); each finding must pass commit, path and extracted-secret checks together (`823–866`); empty commit metadata fails the nonempty commit criterion (`config_allowlist.go:117–133`). Thus these entries do not bypass unrelated findings in an allowed file or commit. This is bounded to the inspected version and configuration.

**Native-control validity.** `plan/exec/scanner_controls.py:112–142` enforces the exact configuration structure. Every one of its 79 registered findings is first required to be detected under the original configuration and expected rule/capture (`261–277`), so undetectable negatives cannot silently count as passing controls. The matching-commit derivative is asserted to differ only in the five commit lists (`283–295`); it tests the path/value constraints while the commit condition is true. The missing-regex and OR mutants test sensitivity to the actual broad-bypass mechanisms (`296–311`). Dir mode verifies empty commit metadata and actual exact relative paths/captures (`312–321`), rather than relying on accidental path mismatch. The T suffix case explicitly preserves the stock 40-character capture and is correctly treated as a positive, while a changed captured token is a negative (`208–215`).

## Independent verification

The candidate native control script was rerun with umask 077 into a **new** private directory, `plan/artifacts/08-codex-native-review-01`; earlier evidence was not overwritten. The 24 commands completed successfully in 6.426 seconds. I also independently classified the raw original reports by the candidate path/rule/capture constraints and compared full finding identities, including columns and captured-value digests, in both the author's final `08-scanner-controls-03` and my new run. Both agree:

| Control | Observed native result |
|---|---|
| Frozen public mirror, original configuration | 17 findings, exit 1; exact historical occurrence roster reproduced, including columns |
| Same mirror, shipped candidate | 0 findings, exit 0; refs identical before, after and at final check |
| Finite fixture, original configuration | 79 findings, all registered captures detected |
| Same fixture, shipped candidate at later commit | Same 79 findings retained |
| Only commit lists rebound to fixture SHA | 17 exact positive findings exempt; all 62 negatives retained, including changed values, wrong/near paths and distinct same-line/same-file findings |
| Missing-regex mutation | 24 required negatives lost: sentinel detects the widening |
| OR mutation | 62 required negatives lost: sentinel detects the widening |
| Shipped candidate in dir mode | All 79 findings retained, each with empty commit metadata and expected exact relative path/capture |
| Wrong historical commit digit | 11 V4 findings reappear |
| Invalid condition | Native configuration-load failure, explicitly checked in stderr |
| Existing fixture exception | Stock-only configuration detects 3; original and candidate each retain only the unrelated-path finding |

Scanner identity: Gitleaks 8.30.1, binary SHA-256 `f414bc2fb952be6c9072b75cb411e3368614ef4b16d48dbd9ad238034afd2302`. Original configuration SHA-256 `4a228e1a8589d22ef37be550c83c5db5e4809cd32a137b0f37374a5bb7ab83aa`; candidate `7b4a8fdbec9031693daecd99272e12c5a08329a55da62e6de9d0280f88366788`. Public ref roster digest `48a51f9811f20b284f65ad49a8c414a5115fc507c17044fd2cfdea712871ffd3`.

**Count distinction:** the frozen mirror has 99 reachable commits according to `git rev-list --all --count`; native Gitleaks logs report **78 commits scanned** and approximately 43.80 MB in each original/candidate comparison. Those are different measurements. Root's separately retained all-local-refs scan reports 91 native commits and no leaks; it is a different ref scope and was read, not independently rerun here. Neither count should be substituted for the other.

Additional independently executed checks:

- `git diff --check 19369be2f88cfa5f7de269b5ad56204b52cd8242 1d8148644984ab7a8548960439b3a9d0adf7f729`: passed.
- `python3 -B plan/exec/preservation.py`: 75 protected files, no errors.
- Pinned `plan/artifacts/tooling/bin/uv --version`: 0.11.29; that binary's `uv lock --check`: passed, resolved 34 packages. The system uv is 0.12.5 and was not substituted.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B scripts/verify_release.py --expected-version 0.1.1`: passed using the candidate's existing environment. This checks installed identity/API/replay, not a fresh wheel install or tag provenance.
- Parsed metadata/lock comparison, exact source-literal comparison, action-pin comparison, native source digest checks and raw report comparisons: passed.

The retained `plan/logs/08-release-validation.log` was inspected and supports the author's 422 passing tests, workflow pins, formatting/lint, demonstrations, 32-case authored conformance result, compatibility smoke and preservation result. The full product suite was not repeated during this review because implementation and tests are frozen; the scanner controls, preservation, lock and release-identity checks above were independently rerun. No live model, credential-file/`.env` access, network write, release, push or settings mutation was performed. Only this assigned review and the explicitly permitted new private native-control artifacts were written; the candidate was not edited.

## Required changes

None for this exact Task08 patch.

## Follow-ups and finite limits

Root must retain separate artifact qualification, exact-head hosted checks, fresh Fable actual-patch acceptance and all existing merge/tag/publication gates. Local Homebrew scanner controls do not authenticate the different hosted Linux binary or establish a hosted result. No line/column selector exists in these allowances; the 17-occurrence claim comes from the fixed native before/after evidence, not a coordinate restriction in TOML. These controls establish behavior for this finite scanner/configuration/history and fixture set, not absence of every secret or correctness under future scanner versions or changed log/decoding options. Keep the 99-reachable/78-native and separate 91-native scope distinctions in final receipts. Original scanner failures remain historical failures.
