REPORT 02-baseline — Status DONE | Changes | Tests (commands + results) | Deviations (with reason) | Open issues | Spend.

## Scope and result

Read-only baseline verification at `93028efe269b4e1227f1cb5f16d12b1849cea836` in the Task 02 worktree, against source baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`. No tracked files were changed. Environment creation and private logs were the only writes outside this report.

All 14 stages in `bash plan/exec/verify.sh` completed with exit 0 under isolated uv 0.11.29 after explicitly pinning its directory in PATH. CPython was 3.13.12. No live evaluation or Fable subprocess calls were made.

## Checks

- Frozen lock and development environment: passed; immutable action pins validated in four workflows.
- Test count: 422 collected, above the 408 minimum. Compileall, Ruff lint and format checks passed; 72 files were already formatted.
- Main pytest invocation: 422 passed, zero skipped. The smoke script repeated the same 422 tests successfully; these are not 844 distinct tests.
- Edit, epistemic and unattended demos: passed. The generated conformance fixture passed all 32 authored cases: 8 valid, 12 adapter cases and 12 expected legacy rejections.
- Smoke import and four CLI scenarios: passed, including the expected bounded nonzero stuck-case exit. Preservation verified 75 protected files with zero errors. Source, tests, scripts, package metadata and lockfile had no diff against baseline; working tree was clean.

No configured type-checking gate exists in evalopt; typing is not applicable. This baseline run does not qualify release artifacts or hosted CI; those remain later task gates.

## Retained deviation and correction

The first run (19:31:21–19:31:35 UTC on 2026-10-12) exited 0, but inspection found that `scripts/smoke_test.sh` calls bare `uv`. The runbook had set UV_BIN without prepending its directory to PATH, so that nested command resolved to Homebrew uv 0.12.5. The first log is retained and is not represented as fully pinned verification.

A complete second run (19:32:05–19:32:18 UTC) prepended the isolated tool directory externally and verified bare `uv` resolved to uv 0.11.29 before running the unchanged runbook. It exited 0. Root was notified to fix nested tool resolution in the run-local runbook; this lane made no implementation edits.

## Evidence

Private records are under `plan/artifacts/baseline/`: original and pinned stdout/stderr logs, start/result JSON records, conformance outputs and `baseline-summary.json`. Raw logs remain outside committed reports.

- `verify-baseline-pinned.log` SHA-256: `bfaf2a9cbe2beb07fe26f1428288b81acb79c568e277943cae3bf39675f883bd`
- `verify-baseline.log` SHA-256: `0f4ea6bd841e7091b60cc4362a2feda5010ecaeb918f85fc909d59980cbac045`

## Open issues and spend

No source or baseline-test failure remains. The run-local PATH defect requires root's reviewed correction before later verification. The initial Task 02 control-command issue is outside this baseline invocation and must remain accounted for in the main Task 02 report.

Two full baseline verification runs took approximately 29 seconds combined. This verification lane launched no live evaluations or Fable subprocesses and performed no billing action; Codex analysis usage is not attributed in this report.
