REVIEW 11-terminal-operations — Reviewer Astra | Verdict ACCEPT

## Scope and findings

Accepted the actual PR43 merge, restoration of the sole temporarily changed cleanup preference, preservation of both merged branch refs, and independent recomputation of the retained final Fable usage inventory. No correction is required for these bounded operational records. This is not a review of the separately pending terminal-receipt/addendum text or a substitute for the final-main CI review.

## Merge and unchanged candidate

- Retained `11-merge-r1` records bind four review files by SHA-256; all four hashes independently match their actual central files. They include the exact source pair, hosted PR-CI review and PR-body review. The required-check command exited 0. The native command was `gh pr merge 43 --repo ajaysurya1221/evalopt-graph --squash --match-head-commit ba5db20743e632f6295a2d9bfbda7867e6579978`; no administrative or branch-deletion flag was used, and it exited 0.
- GitHub reports PR43 merged at **2026-10-12 23:14:19 UTC** to **`b52c87539932c4b0682049f88eeeb5a433523150`**. Fresh main and PR GETs independently confirm that source and exact head `ba5db20743e632f6295a2d9bfbda7867e6579978`.
- The actual GitHub main-commit tree is **`ec2198320003800ae6f75f9b105467d2aeac2455`**, exactly equal to the locally reviewed candidate tree. This gate confirms correspondence, not a changed package or replacement v0.1.1 artifact.
- The initial `11-merge` capture contains only the read-only pre-merge PR response/command/stderr. Its body equals the accepted body file byte-for-byte, including the trailing LF; comparing that response against only a stripped expected string would falsely fail. The corrected `11-merge-r1` capture compares equal exact bytes. This was a local predicate correction before the recorded mutation, not a source repair, changed PR text, ignored review, CI waiver or retry of a completed merge.

## Restoration and preserved authority

The retained restore body is exactly `{"delete_branch_on_merge": true}`. Before restoration, the cleanup value was false; the successful native PATCH response and subsequent readbacks report true, which equals the captured original value. A separate fresh read-only GET independently confirms true and confirms the repository remains unarchived.

Fresh complete API response bytes for both rulesets and the PyPI environment equal the originals captured before the first wind-down merge, and also equal the retained before/after restoration responses:

| Complete response | SHA-256 |
|---|---|
| Main ruleset 19205651 | `20814605878d9d6d5315cdf725e96d76eadbf63967f562e6c96cbc1a4eb7ca05` |
| Tag ruleset 19205653 | `cf056c68df094c94dbfa987584dce113f1cdd673457ee09413de2043081a568a` |
| PyPI environment | `441028d22cc7d78b6fd4a5c6b5f8bc26cb977f7160604fb6a40951ff761d0914` |

Both merged refs remain present at their accepted heads: `winddown/20261013/10-r1` at `7043a0879a8a5491c110bd7d8a9f466700f920b7`, and `winddown/20261013/11` at `ba5db20743e632f6295a2d9bfbda7867e6579978`. This verifies those two refs, not the still separate complete-lane reconciliation.

Fresh observations ran **2026-10-12 23:16:42.167360–23:16:44.448421 UTC**. Nine native GitHub GET commands all exited 0; complete raw responses, stderr, command/exit/timing metadata and a SHA-256 manifest are retained privately in `plan/artifacts/11-terminal-operations-codex/`. No GitHub or Git mutation was performed by this review.

## Independently recomputed usage

Recomputed `11-usage-inventory/snapshot-03` with Python standard-library JSON readers, SHA-256 and decimal arithmetic, rather than trusting its summary or invoking the inventory implementation. All **140 retained input files** match their manifest size/hash; all **50 native result identities** are unique by session/UUID/result index and complete, with no duplicate source-byte identity. This verifies all inventoried inputs, not unretained sessions outside the roster.

- **50 attempted CLI invocations:** 44 supervised and 6 direct. The supervised outcomes are **38 DONE / 6 PARTIAL**, and all finish receipts are present. Native subtypes are 48 success / 2 turn-limit errors; native result success is not conflated with supervisor acceptance.
- Requested supervised efforts: 30 high / 14 xhigh. Requested cap histogram and recorded counters match the raw records; effective effort is still not independently exposed.
- Fable 5.1 totals: **16,516 input; 1,030,219 output; 25,832,473 cache-read; 3,262,241 cache-creation tokens**. **412,954 thinking tokens** are separately observed, not added to output again. Fifty Fable modelUsage entries have first-party/list-price metadata.
- Rejected auxiliary Haiku remains represented once: **1,670 input / 63 output**, with its own native model key and list-price estimate. Its presence is not retroactive authorization or an accepted model substitution.
- Exact modelUsage list-price sum is **`123.3810332499999970002` USD**; native total-cost sum is **`123.38103324999999700` USD**, agreeing at their reported precision. A display rounded to **$123.381033** is accurate. Neither is an observed subscription charge.
- Native totals independently match: 885 turns, 15,108,079 duration milliseconds and 13,651,139 API-duration milliseconds. Concurrent summed durations are not wall-clock run time.

Snapshot capture was **2026-10-12 23:14:30.018796–23:14:30.049779 UTC**. It reports no unknown usage, open supervised attempt, duplicate conflict, changed input or new start during capture. Its `incomplete_snapshot: true` flag remains retained: root may identify this as the last finite inventory only after confirming no later model calls, and must not rewrite that flag or fabricate an all-account total. Attributable Astra/Codex token/cost totals remain unavailable. No paid probe or model call was made here.

## Required changes and remaining scope

None for the reviewed merge/restoration/usage evidence. Final-main hosted CI is being independently reviewed elsewhere; the terminal receipt/addendum and complete remote-lane reconciliation still need their own correspondence check. Existing published assets, sibling main branches, repository archival, outreach and any future release remain outside this operational acceptance.

Reviewed at 2026-10-12T23:18:01.109407+00:00
