# Branch-preservation operational decision

Decision recorded before the native setting request at 2026-10-12T22:29:56.469184+00:00: adopt Position A from the fresh Fable xhigh opinion in reviews/10-operations-fable.md, subject to the independent Codex operational review. Temporarily set this repository's general delete_branch_on_merge setting to false using its native REST endpoint before any authorized merge. Verify readback false. Preserve all rulesets, branch protections, environment protections and bypass actors. Restore its recorded initial true value after the last authorized own-repository merge and verify each retained branch. No sibling setting changes.

Positions: Astra proposed the reversible setting change because an authorized merge with the current true value would trigger forbidden server-side branch deletion. The alternative was to defer all merges and publication to HUMAN_INBOX. Fable independently chose the reversible setting change; the complete one-paragraph opinion is retained in its review.

Rule: the user's explicit no-deletion requirement and authorized own-repository merge/release scope, then memo S4, then the more reversible option. A general branch cleanup preference is not an approval/protection bypass. Denied or unexpected readback blocks merge; no elevated retry. Failed restoration becomes an explicit HUMAN_INBOX item.

This record is a prospective decision, not evidence that the setting was changed or a merge occurred. Raw before/PATCH/after responses will establish actual state. The formal ADR will be included in the reviewed final-report branch; the exact release candidate remains 7043a0879a8a5491c110bd7d8a9f466700f920b7.

Actual execution: after both independent operational reviews ACCEPTED, native repository GET confirmed true, a single PATCH set delete_branch_on_merge=false, and a fresh GET confirmed false. Complete before/after responses for main ruleset19205651, tag ruleset19205653 and the pypi environment were identical. Commands, UTC times, exits and raw responses are retained in private artifacts/10-branch-preservation with a SHA256 inventory. Restoration to true remains mandatory after the final own-repository merge.
