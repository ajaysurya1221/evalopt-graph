REVIEW 10-BRANCH-PRESERVATION — Reviewer Astra | Verdict ACCEPT

**Accepted scope:** the bounded operational decision to disable automatic branch deletion temporarily in `ajaysurya1221/evalopt-graph`, perform only otherwise-authorized and fully gated own-repository merges, preserve the merged head refs, then restore the captured original setting. This does not accept a source change, artifact, merge candidate, tag or release.

## Authorization correspondence

The approved `PLAN.md` remains byte-identical to digest `697f3fd7fa61b294146fff13868c87d6762d00395f39d8085ba52a111eb22b3c`. Section C simultaneously requires squash PR merges and prohibits automatic branch deletion, administrative bypass and protection changes. Task10 explicitly authorizes the reviewed own-repository merge and forbids protection changes or admin merge. Task11 authorizes the reviewed final-report PR. Temporarily preventing automatic deletion supports these actions without weakening their admission requirements.

`delete_branch_on_merge` is the repository's cleanup preference, distinct from the branch/tag rulesets, status checks, review requirements, environment approval controls and bypass permissions. Setting that one field false preserves additional refs; it does not relax a check or grant merge/deployment authority. Task05's prohibition on changing repository settings binds the Notice task's documentation ownership; it is not permission for that executor to mutate settings and does not prevent this separately reviewed Task10 preservation action. No other setting change is accepted.

I independently agree with the bounded choice in `reviews/10-operations-fable.md`. The deciding rules are the approved own-repository merge authorization together with the stricter no-deletion/no-protection-change boundaries, followed by reversibility. This conclusion does not require the broader assertion that every possible merge would delete its branch: the observed automatic-deletion setting creates a preservation risk that must be removed before this run's otherwise-authorized merges. The immutable approved plan need not be edited; retain the decision and both positions in the required ADR/decision record.

## Evidence inspected

- Approved plan Sections C, Task05, Task10 and Task11; Fable's branch-preservation opinion within `10-operations-fable.md`.
- Retained raw `10-gates-current/repository.json`: `delete_branch_on_merge=true`; the authenticated repository permissions include admin and push. Only squash merges are enabled.
- Retained exact main ruleset 19205651 and tag ruleset 19205653: active, empty bypass-actor lists and `current_user_can_bypass="never"`. Main requires the four identified checks and resolved review threads; v* tag updates/deletion remain prohibited.
- Retained PyPI environment configuration and branch-policy roster, which are outside this change's scope.
- Fresh read-only `gh api repos/ajaysurya1221/evalopt-graph --jq '{full_name, delete_branch_on_merge, allow_squash_merge, allow_merge_commit, allow_rebase_merge, permissions}'` again returned `delete_branch_on_merge=true`, squash true, merge/rebase false and the authenticated admin/push permissions (exit 0).

## Accepted execution boundaries

1. Retain a fresh before-state repository GET, current protection/environment snapshots and the owned head-ref identities before the mutation. If the observed original cleanup value differs from the expected true, do not silently overwrite or assume the old inventory is current.
2. Use only the native repository endpoint with a body containing `delete_branch_on_merge=false`. Do not mutate rulesets, legacy protection, environment protection, bypass actors, review counts, required checks or other repository fields. No elevated/bypass alternative after denial.
3. A fresh GET must show false **before each authorized merge**; otherwise no merge. Independent source/artifact reviews, exact-head required checks and all other plan gates remain mandatory. Use squash with the exact reviewed head and no `--admin` or `--delete-branch`.
4. After each merge, retain readbacks showing the original head branch still exists at its expected head SHA, plus the actual resulting main/PR state. A missing or unexpectedly changed ref is a failure, not permission to recreate or rewrite history silently.
5. Keep the setting false only through the final already-authorized own-repository merge. Restore the captured original true via the same one-field native endpoint, then retain an independent GET showing true, final ref readbacks and unchanged protection/environment configurations. Restore before wrap-up even if an intermediate merge or publication gate stops progress. Re-enabling cleanup is not a request to delete any existing ref.
6. Retain command arguments, UTC times, raw responses, stderr and exit statuses for each step. A denied/uncertain mutation or failed readback blocks dependent merges. An unsuccessful restoration belongs explicitly in HUMAN_INBOX with the exact native restore command; never bypass a denied control or claim restored state without readback.

## Required changes

None to the proposed bounded operational decision. The execution and its readbacks remain unperformed by this reviewer and must be recorded by root before claiming the preservation gate passed.

No GitHub mutation, Git mutation, model call, credential/environment-value read, source edit, rerun, waiver, merge or publication was performed in this review.
