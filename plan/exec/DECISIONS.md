# Execution decisions — 20261013


| Decision | Rule |
|---|---|
| Execute STOP, not another improvement sprint or benchmark | Memo recommendation is preapproved |
| Include the final no-capability-change release | Explicit release authorization and memo S4; confirmed through Fable consultation |
| Use current public main; preserve the benchmark branches separately | Repository boundaries and reversible integration |
| Interpret `/plan` as repository-relative; keep raw logs private | Commit requirement, portability and privacy |
| Preserve kernel bytes relative to current main, while disclosing inherited changes since v0.1.0 | Verified repository state and evidence honesty |

| Decision | Rule |
|---|---|
| Keep all new public interfaces and integrations out of scope | STOP and memo prohibitions |
| Use native authorized deployment approval only after exact artifact review; never alter protections | Explicit publishing authorization and existing approval mechanism |
| Open other-repository README PRs without merging their mains | Narrower cross-repository authorization |
| Keep single-reviewed work unmerged during Fable outages | The stricter two-review merge requirement |
| Leave archival, external outreach and unavailable interactive actions in HUMAN_INBOX | Explicit human-only boundaries |


## Run identity

- Baseline: `fc3045dbda29c1d274747329ceb6724a783b0df7`.
- Budget begins: `2026-10-12T19:22:18Z`; release admission closes `2026-10-13T03:37:18Z`; task admission closes `2026-10-13T04:37:18Z`; hard deadline `2026-10-13T05:22:18Z`.
- Plan SHA-256: `697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c`; copied verbatim from the accepted user message, without its implementation-request prefix. The historical final acceptance line is preserved.
- Memo SHA-256: `e307514fc800c2ff37c8d1a6d9a454bbf4d4addf53acd38611cbbc50b5695e81`.
- Root controls orchestration. No old benchmark campaign is resumed.

## Task01 probe decisions

- Add `--safe-mode` to worker/reviewer invocations to isolate global customizations; native subscription authentication remains enabled. No model substitution.
- Terminal JSON does not expose effective effort; record requested effort and that observability limit.
- Provision uv0.11.29 in run-private tooling because installed global uv is0.12.5; do not replace global tooling.
- Task00 review found terminal blank lines in extracted tasks. Trim those task files only; preserve PLAN.md verbatim and record the failed initial committed-diff check.
