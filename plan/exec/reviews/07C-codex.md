REVIEW 07C — Reviewer Astra | Verdict REVISE

Exact reviewed head: `b0a0b14a51f74d195058c395022421567ac54868` in `wt-portfolio-07c`. Base: `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c`. Read the Task 07C and implementation packets, central REPORT, repository contracts, README context and exact diff. The task is README-only; no implementation, policy, signing or receipt behavior changes are authorized or present.

## Findings by severity

### P2 — Bound the independence claim to the audited state

`README.md:334–335` says “Frontier Scout never depended on or imported” evalopt. The retained portfolio audit establishes no declared, locked or runtime-imported evalopt dependency at the recorded repository heads; it is not an exhaustive history/provenance audit. The implementation report likewise cites the current preflight head, not evidence covering every prior Frontier Scout revision. “Never” adds an unnecessary historical claim beyond the task's evidence.

Required change: use current-state wording, for example “Frontier Scout does not depend on or import it and does not inherit its records, states or decisions.” Preserve the STOP clause and all native-control/signing/receipt limits. Do not widen the task into historical research merely to retain “never.”

## Verified scope and boundaries

- Exact assigned HEAD confirmed; target working tree was clean. The full diff adds only one Related projects section, 18 lines, to README.
- An independent byte comparison removed exactly that new section and reproduced the complete base README. Every existing example, policy/signing instruction, figure, limitation, status and unrelated paragraph remains byte-identical.
- Native-control compilation and checking the diff against the base commit's policy agree with AGENTS, CONTRIBUTING and the existing safety-model section. The addition keeps the emit-only/research-preview qualification, GitHub/Sigstore signing rails external, and local receipts unsigned observations without approval authority.
- Current `pyproject.toml`, `requirements.txt` and searches of `frontier_scout/` and `outputs/` contain no evalopt or named sibling package/import references. This corroborates the present-state claim, not a universal historical negative.
- The domain descriptions match the accepted portfolio routes. No successor, drop-in, adoption, semantic-truth, archival or final-release-publication claim is added. No runtime, package, policy, hook, generated configuration, source, test or release tag changed.
- The repository's old protection-relaxation/admin-merge instructions are superseded by this run's narrower approved boundaries and are irrelevant to this review. No merge, protection change or publication was performed.

## Independent commands and results

All commands ran in the task worktree with its existing isolated environment. No cross-repository Python path or package installation was used.

| Command | Actual result |
| --- | --- |
| `git diff --check e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c..b0a0b14a51f74d195058c395022421567ac54868` | Passed, exit 0 |
| `PATH="$PWD/.venv/bin:$PATH" RUFF_NO_CACHE=true make lint` | All checks passed, exit 0 |
| `PATH="$PWD/.venv/bin:$PATH" MYPY_CACHE_DIR=/dev/null PYTHONDONTWRITEBYTECODE=1 make type` | No issues in 13 source files, exit 0 |
| `PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest -p no:cacheprovider tests/test_figures.py tests/test_agent_verify_pr.py tests/test_agent_cli_compile_verify.py -q` | 29 passed in 1.79s, exit 0 |

One reviewer invocation initially supplied `RUFF_NO_CACHE=1`, which this installed Ruff rejects (expects `true` or `false`), so `make lint` exited 2 before linting. The corrected invocation above passed; the failed command was a reviewer environment-value error, not a source failure or an erased check.

## Required changes and remaining gates

Make the bounded present-state wording correction and submit the new immutable head for targeted review. No product code, guard or test change is needed. Root's independent full non-live suite, fresh Fable review, exact-head hosted checks, push and PR remain separate gates; none is claimed as completed here. No network write, model call, credential read or target edit was performed. Only this assigned central review file was written.
