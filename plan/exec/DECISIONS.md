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

## 2026-10-12 20:55 UTC — Task04 revision gate

Both independent reviews returned REVISE for migration author head8081661. Codex identified six source/wording corrections, including the compromised-verifier limitation and Witness attestor/functionary distinction; fresh Fable identified deserialization, bounded replay claims and context-only SLSA citations. Root combines the required corrections in one documentation-only revision. Fable's suggested replacement that could imply kernel checks establish provenance or truth is not adopted; the accepted evidence boundary and primary sources decide the wording. This is a correction within the fixed contract, not a reopened design choice. Original reviews are retained. Native review elapsed471.035 seconds; the supervisor reports PARTIAL because the written verdict is REVISE, not because the process failed.

A fresh read-only full-history scan with the unchanged stock-extended configuration still reports exactly the same17 diagnosed nonsecret occurrences in six historical paths. No new finding comes from the operational packet or migration draft. This is diagnostic evidence only; Task08 still requires the narrow correction, adversarial controls and two independent reviews. Raw redacted result and exit1 are retained privately.

## 2026-10-12 21:10 UTC — Task04 accepted and scanner scope narrowed prospectively

Task04 final Codex and fresh Fable reviews ACCEPT exact 8f60a3a. Root integrated both author commits unchanged; protected 75-file check passed. Root and Codex independently confirmed four added links return HTTP200. Optional citation improvement is deferred to avoid mutating accepted bytes; the claim remains supported and no required finding remains. CHANGELOG disclosure remains Task05/08. Fable final review native elapsed379.992s.

The root requested a read-only Fable xhigh opinion on narrowing historical scanner exceptions to exact commits in addition to rule/path/value AND constraints. Fable recommends ADD exact historical commit constraints; native source inspection shows this does not skip fragments when the regex check is present. Root accepts the narrower reversible design, subject to native positive/negative controls and both actual-patch reviews. This supersedes the earlier scanner-contract limitation about later identical values: new commit occurrences must stay detectable. No configuration has changed yet. Opinion native elapsed363.668s; self-reported tool counts are not CLI native turn evidence.

## 2026-10-12 21:13 UTC — Scanner design verification corrections

Independent Codex source review supports the exact-commit AND design and corrects two details in the retained Fable consultation: an invalid condition value is a configuration load error (only an omitted recognized condition defaults to OR); fresh-commit negatives alone cannot detect a missing regex because the commit mismatch masks it. Actual controls will therefore include a derived configuration changing only the commit lists to the fixture commit, with wrong/near paths, changed captured values and unrelated same-line/same-file secrets, plus missing-regex and OR mutation sentinels. Native dir-mode checks will separately prove empty commit metadata rejects the exemption at matching paths. Source suffixes beyond the stock token capture are not mislabeled changed captures. Root independently read the cited config parser and fragment-level gate. These corrections preserve the narrower chosen design; no opinion waives native tests or actual-patch reviews.

Public main remains fc3045d, with only existing v0.1.0 tag/release at this read. Four sibling repository read-only API checks show push permission and unarchived main branches. No public push, merge, tag, deployment approval or release has occurred in this run yet.

Timestamp correction: the two preceding heading times were manual transcription errors, corrected against native clock and commit timestamps. Git history retains the original text; execution timing is established by retained native start/finish records, not these narrative headings.

## Task05 acceptance and parallel release/portfolio admission

Task05 corrected head c8f2b1d has independent Codex and fresh Fable ACCEPT. Root inspected its full revision, reran figures/preservation and checked actual GitHub desktop1280x900/phone390x844 rendering; phone table requires21px horizontal overflow, accessible through native scroll. Accepted source integrated without changes. Its preview branch was pushed for rendering while the final Fable review was still pending; this is a reversible authorized review branch, not a main merge/publication claim. Both final reviews are now accepted. Main-target links to the new documents remain pending until merge. Native author379.522s, first review230.344s, revision136.697s, finalreview185.461s.

Task08 and the independent Task07A/B README lanes are now admitted after accepted04/05/06. Each retains its own worktree, file ownership and environment. No release tag or sibling-main merge is authorized by this admission alone.

## 2026-10-12 21:45 UTC — Release candidate and portfolio review state

Task08 candidate1d814864 is prepared without release/tag/publication. Native scanner controls pass79cases and reproduce original17historical findings before exact exceptions; currentalllocalhistoryscan also exits0. Scope remains finite and exact-headhostedCI is stillrequired. Every75protectedsource/test/benchfile matchesbaseline after permittedversionnormalization. Rootfulltests422pass. Task07B originalheadlessauthor returned while a background suite was pending, withoutREPORT/commit; supervisor correctlyrecordsPARTIAL. Fresh independentvalidation1119pass/1optionaldependency skip supplies attributed evidence for an explicitly queued completion, never retroactiveDONE. Task07C must replace historicalneverdepended language with supportedcurrentstate; no audit expansion or guardchange.

## 2026-10-12 21:55 UTC — Task08 accepted; artifact qualification admitted

Codex and fresh Fable xhigh independently ACCEPT exact release patch1d814864. Both independently reproduced the native scanner controls. The fixed public mirror has99 reachable commits; Gitleaks processed78 nonmerge diff-bearing commits. Separate local-all-ref scan processed91 native commits. These counts are not interchangeable, and neither local scan establishes hosted CI. Root is retaining an explicit release-identity output during Task09 to resolve the review's logging observation. Candidate source is integrated unchanged; no tag, merge or publication is yet approved.

## 2026-10-12 21:59 UTC — Qualification invocation correction

The earlier publication preflight's `uv x` spelling is unsupported in pinned uv0.11.29. Task09 retained the actual exit2 failure and changed only the command invocation to `uv tool run --from twine==6.2.0 twine check`. Both unchanged candidate archives then passed. The original preflight and failed output remain historical records; future runbooks use the supported spelling. RECORD hashes establish internal consistency, never producer authentication.
