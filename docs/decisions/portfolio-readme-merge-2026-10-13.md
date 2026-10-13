# ADR: Preserve branches during the authorized portfolio README merges

## Decision

Merge only the previously reviewed, unchanged README PRs whose current native gates permit an ordinary exact-head squash merge. For Actseal alone, temporarily turn its general `delete_branch_on_merge` preference off, verify it, merge once, and restore its original true value in a finally block. Do not change protection rules or deployment controls. Leave Frontier Scout open because its required GitHub approval is absent.

## Positions (Astra, Fable)

Astra's operational alternatives were A: perform a bounded and verified cleanup-preference toggle to obey both the merge authorization and no-deletion boundary; B: leave Actseal unmerged because that general preference defaults to deleting the source branch. A fresh independent Fable xhigh opinion selected A after inspecting the exact Actseal state; it explicitly rejected importing prior evalopt-specific authority. An independent Codex operational review also accepted the narrowly bounded method.

## Rule that decided

The user's new authorization permits these sibling README merges, while the retained no-branch-deletion and no-protection-bypass boundaries still bind. The cleanup preference is a reversible general repository setting, not a protection rule. The fresh Fable opinion resolves the operational choice without waiving any check. Native review requirements still prevail: Frontier Scout's missing approval is not resolved by this decision.

## Consequences

Actseal PR70 was normally squash-merged to `ad62ec8ff33f858e1759149389f6700c03de6022`. Both preference writes had separate readbacks; true was restored. Its source ref remains at `52dbc14554486e8ff9e31455d550bfc3d43f139e`. Complete relevant ruleset/environment records matched before, during and after the toggle. Dorian and ARCI required no setting change. Frontier Scout received no mutation. All three resulting trees match their reviewed source trees and change only README.md relative to their previous main.

Evidence: `plan/exec/reviews/portfolio-merge-operations-{codex,fable}.md`, actual native receipts retained privately under `plan/artifacts/portfolio-merge-20261013-root/`, and the follow-up report at `plan/exec/PORTFOLIO_MERGE_FOLLOWUP.md`. The raw records remain private. This ADR authorizes no future bypass, account switch, synthetic approval, branch deletion or archival action.
