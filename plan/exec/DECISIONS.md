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

## Independent proposal sequence and evidence boundaries

- Fable's three blind proposals completed at lane commit `0663549f652bb868c3a5ad040fb67d6a7bed4663`; native supervision completed with model identity and exit checks. Root read only file metadata and the content-free completion report before committing Astra's independent proposals at `aa28b4c`. Only afterwards did root read the Fable proposal contents.
- Agreement on STOP, the sixteen-entry roster, four relationship categories and all preservation limits is retained. A fresh xhigh consultation resolves the three remaining documentation-form differences. Proposals are not implementation authorization; the accepted plan and owned-path limits prevail.
- Task06's first independent reviews both require correcting the audit's claimed search scope, timestamps, artifact coverage and README-guard handoff. Original reports remain retained; a separate revision report will supersede their inaccurate wording. No dependency removal is justified.
- Public-history scan diagnosis covers seventeen nonsecret findings at fixed historical paths; it is not approval of a scanner patch. Task08 must preserve stock detections and prove exact value-plus-path scope through negative controls and independent review.

## Task06 accepted; additional orchestration check

- Final audit at `f030ccdb5361ef393b2c8ec41181a773da29c706` passed independent Codex and fresh Fable reviews. Root inspected the correction diff and reran the whitespace/scope check before integration. The original report/reviews remain historical; REPORT06-R1 supersedes the inaccurate original wording.
- Workspace contract check `python3 -B -m unittest discover -s tools/tests` ran from `/Users/ajay/Developer`: 32 tests passed in 9.828 seconds. No workspace integration file changed.
- For all remaining inspections, exclude `.env` and credential/authentication stores entirely; command-status probes are sufficient. No secret-file inspection is needed for documentation, package qualification or portfolio README edits.
- Native receipts, not approximate worker self-reports, establish call timing: 03-proposals 19:46:31.296741–19:59:37.097417 UTC, 785.705 seconds; 03-tiebreak 20:01:28.195144–20:03:46.651851 UTC, 138.358 seconds, all on 2026-10-12. The latter worker report's approximate end time is superseded by this retained native interval.

## 2026-10-12 20:25 UTC — Version-specific SLSA wording

Independent primary-source inspection found the cited SLSA VSA v1.0 and v1.1 pages marked Retired, while v1.2 is Approved. Task03/04 must qualify the retired version and record current-version status as context. This corrects a version scope without adding a route or reopening STOP. The immutable approved PLAN is retained as supplied; factual clarification follows its accuracy boundary and no-new-integration constraint. Source evidence is retained in reports/04-primary-sources-preflight.md.

## 2026-10-12 20:27 UTC — Task03 first review and bounded correction

Task03 implementation finalized at 2d5c307 with native DONE in 875.219 seconds. Root inspected the four-file diff and reran preservation (75 files unchanged). Independent Codex and fresh Fable both returned REVISE for incomplete inherited-source disclosure and overbroad identity wording. Fable review itself exited normally; supervisor PARTIAL means its required verdict was not ACCEPT. Original reports/reviews remain retained. Revision1 also narrows VSA status by version and correctly attributes release authority to the human. No protected source or experimental evidence changes are authorized.

## 2026-10-12 20:34 UTC — Task03 accepted; native timing controls

Codex and fresh Fable both ACCEPT the revised immutable 9d306137ab78b473ff3419c4375735819a803cce documentation diff. Root inspected the corrections and independently reran the 75-file preservation control; accepted ADR/proposal bytes are cherry-picked unchanged. Native receipts measure revision1 at 232.951 seconds and final review at 272.611 seconds. Approximate wall times in model-authored reports (including the final review estimate of twelve minutes) are not measurements and are superseded by these external records; final usage accounting will use only native receipts.

Portfolio preparation refreshed all four public main refs, created separate task branches/worktrees, and installed isolated unchanged-lock environments for Actseal, Dorian and ARCI. Frontier has no lock; its 49 existing tool distribution versions were retained exactly. Its first no-build-isolation install failed because the clean environment lacked the declared setuptools backend; normal isolated build using its unchanged build-system requirements succeeded. Both attempts are retained. Imports checked from outside the checkouts point to their own worktrees; versions are 1.0.1, 1.4.1, 2.2.0 and 0.7.0. No primary environment or tracked portfolio file changed. README executors remain unadmitted until Tasks04/05 pass.

## 2026-10-12 20:43 UTC — Requested turn caps and native accounting

The external supervisor enforces wall-clock, owned-process and post-run path-scope constraints and passes the requested CLI `--max-turns` cap. It does not independently enforce a turn counter or equate that flag with terminal JSON `num_turns`. Task01's requested cap of 1 produced native `num_turns` 2; later successful calls likewise reported 24 against requested 20 (02-final-review), 33 against 30 (03-proposals), and 40 against 30 (03-implementation). These are separately retained observations, not proven cap violations: the counters' equivalence is unestablished. Model self-reported assistant/tool counts do not establish enforcement.

This clarification supersedes the overbroad “task wallclock/turn caps” wording in reports/02.md:9 and the claimed “within ... 20-turn limit” in reviews/02-final-review.md:40. Those historical records and native outcomes remain unchanged. Final usage accounting will distinguish requested caps, observed native counts and independently measured elapsed time. No guessed counter comparison or controller change is justified. Independent Codex requested this bounded correction; Fable accepted the preceding operational packet at 2b4f00e and its native review elapsed time was 314.828 seconds.

## 2026-10-12 20:49 UTC — Operational amendment accepted; migration review

The append-only turn-accounting clarification at 4fcce23 passed both targeted Codex and fresh Fable reviews; final records are control-packet-codex-final.md and control-packet-fable-final.md. Native Fable elapsed175.813 seconds. Task04 author completed at8081661 with native elapsed703.517 seconds and three documentation files; independent semantic/source review is in progress. Root preservation confirms75 protected files unchanged. No implementation or publication acceptance follows from the author's DONE record.

A Task05 worktree and isolated unchanged-lock development environment are prepared, but its executor is not admitted until Task04 is accepted and integrated. Four portfolio task briefs are prepared; their executors likewise await accepted Task05 wording. No portfolio README has changed.
