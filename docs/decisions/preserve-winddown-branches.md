# Preserve branches during the authorized wind-down merges

## Decision

Temporarily disable `delete_branch_on_merge` in this repository for the authorized wind-down merges. Preserve every merged branch at its reviewed head. Restore the captured original `true` value after the last authorized merge and verify the setting and retained refs. This changes a repository cleanup preference, not a protection, review, status-check or deployment requirement.

## Positions

Astra proposed the reversible one-field setting change. Merging under the observed `true` setting risked server-side deletion despite omitting the client deletion flag. The alternative was to leave the setting unchanged and hand all merges and publication back to the maintainer. A fresh Fable xhigh opinion chose the reversible change with before/after readbacks, unchanged protections and mandatory restoration. An independent Codex review accepted that bounded operational interpretation.

## Rule that decided

The approved plan authorizes own-repository squash merges and the final release while prohibiting branch deletion, including automatic deletion. Satisfying those instructions together precedes the memo's release recommendation; reversibility supports the same choice. No opinion can waive failed source, artifact, CI or publication gates. The plan's Notice-task setting restriction does not grant that executor operational authority; root owns this separately reviewed action.

## Consequences

Use only the native repository endpoint and only the cleanup field. Before each otherwise-authorized merge, require a fresh readback of `false`, accepted reviews and exact-head checks. After each merge, verify the retained head ref and resulting main. Do not alter rulesets, branch protections, required checks, environment protections or bypass actors, and do not use administrative merge. Denied or contradictory readbacks block the dependent action. Failed restoration belongs explicitly in HUMAN_INBOX; no elevated fallback is allowed.

The initial value was `true`. Root changed it to `false` and verified byte-identical main/tag ruleset and PyPI environment responses before the first merge. PR42's head branch was retained after merge. This ADR does not claim that the final restoration has already occurred: the final receipt and readbacks establish that later state.

## Evidence

The run's accepted records are [Fable operational review](https://github.com/ajaysurya1221/evalopt-graph/blob/29ae21eef3e21c905df810dbbd6f6f4344c0ce03/plan/exec/reviews/10-operations-fable.md), [Codex operational review](https://github.com/ajaysurya1221/evalopt-graph/blob/29ae21eef3e21c905df810dbbd6f6f4344c0ce03/plan/exec/reviews/10-branch-preservation-codex.md), and [decision/execution summary](https://github.com/ajaysurya1221/evalopt-graph/blob/29ae21eef3e21c905df810dbbd6f6f4344c0ce03/plan/exec/reports/10-branch-preservation-decision.md). Raw API responses remain privately retained; they contain no authority to broaden this decision. This operational ADR was prepared after the release-source merge and is not part of the v0.1.1 candidate package.
