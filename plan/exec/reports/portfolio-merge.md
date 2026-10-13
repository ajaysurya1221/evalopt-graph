REPORT portfolio-merge — Status PARTIAL (3 of 4 requested merges completed; one native approval blocker)

## Changes

The 13 October 2026 user authorization permits merging the four already reviewed portfolio README PRs. Dorian44, ARCI14 and Actseal70 were normally squash-merged at their unchanged accepted heads. Their resulting trees equal their reviewed candidate trees, only README.md changed relative to each previous main, and every source branch remains retained. Frontier81 remains open because GitHub requires one approving review and the authenticated PR author cannot self-approve.

No sibling product code, package dependencies, frozen files, release, tag or archival state changed. Evalopt main and historical evidence remain untouched. New follow-up documents, operational ADR and review records stay on the existing control branch.

## Tests and verification

- Fresh complete exact-head native workflow/job/step inspection: all four original PR candidates passed their configured execution lanes. Conditional ARCI steps and native-vs-offline reviews remain distinct in the review records.
- `git diff --check`: PASS on the control follow-up; source diff checks previously passed in the fresh independent source reviews.
- Native exact-head squash commands: exit 0 for Dorian44, ARCI14 and Actseal70. Independent native commit/parent/tree/compare/ref checks substantiate the actual merge outcomes.
- Actseal's reviewed cleanup-preference procedure: only general `delete_branch_on_merge` toggled true→false→true; separate readbacks passed; complete relevant rulesets/environments unchanged. Source branch retention checked after restoration.
- ARCI's complete 48-entry frozen manifest: freshly verified from local retained accepted bytes and committed blobs against baseline; remote merged tree equals the accepted tree. No fresh installed-main test claim is made from that object comparison.
- Resulting-main hosted CI: independent ACCEPT for Actseal (8 jobs/85 successful steps), Dorian (4 jobs/41 successful steps) and ARCI (4 successful jobs;49 successful steps/4 expected conditional skips). All are original attempt1 runs on the exact squash commits. Frontier remains unchanged and native-approval-blocked in the final readback.

## Deviations

The former cross-repository no-merge restriction is superseded only for these four PRs by explicit user authorization. No protection was weakened. Frontier Scout's older local instructions describing an admin/protection-relaxation workflow are overridden by the approved no-bypass boundary. The bounded Actseal branch-preservation choice is recorded in `docs/decisions/portfolio-readme-merge-2026-10-13.md` and has independent Codex and fresh Fable ACCEPT records.

## Open issues

Frontier Scout81 requires an eligible GitHub reviewer's native approval. Its source, main and settings remain unchanged. Eventual merge must preserve its source branch because automatic branch cleanup is enabled. Evalopt archival remains the user's decision and action.

## Spend

One additional Fable firstParty call, canonical claude-fable-5-1, xhigh requested, 243.777 seconds, seven native-reported turns; native usage and the USD1.9558935 list-price estimate are separately recorded in PORTFOLIO_MERGE_FOLLOWUP.md. This estimate is not a subscription charge. Attributable Astra usage is unavailable. Original wind-down usage records are unchanged.
