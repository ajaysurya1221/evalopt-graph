REVIEW portfolio-merge-07AB-main — Reviewer Astra | Verdict ACCEPT

Independently accepted the actual normal merges, unchanged reviewed trees, retained branches, restored/unchanged settings and complete resulting-main hosted gates for Actseal PR70 and Dorian PR44. No blocker or required correction remains for these two merge endpoints. This does not cover the other two portfolio repositories or any later reporting packet.

## Actual merges and preserved scope

| Repository / PR | Merged UTC | Resulting current main | Previous main / sole parent | Reviewed head | Equal reviewed/result tree |
|---|---|---|---|---|---|
| Actseal / 70 | 2026-10-13 02:27:46 | `ad62ec8ff33f858e1759149389f6700c03de6022` | `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b` | `52dbc14554486e8ff9e31455d550bfc3d43f139e` | `95b5819235ad1f447301261d349fb5380a25930b` |
| Dorian / 44 | 2026-10-13 02:21:08 | `5962bbeb99ef1c22a44d5dbea8cd77c689ff9b65` | `eeb193792fac8a66b18f5222287a8fcf336dda08` | `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | `98cbda60fa5031f0c5eedbcaf6edb312a082aeb7` |

Fresh PR, main-ref, Git-commit, base-to-main compare and retained-head-ref GETs establish each row. Local pinned `git rev-parse <reviewed-head>^{tree}` independently agrees with the corresponding GitHub main tree. Both complete diffs contain **README.md only**. No source, dependency, version, interface, NOTICE or frozen file change is introduced by either merge. Both heads had the previously accepted Codex and fresh Fable source pair and the independently accepted current-head PR gates in `portfolio-merge-07AB-codex.md`.

Root's recorded merge commands use ordinary `gh pr merge <number> --squash --match-head-commit <exact-reviewed-head>`, exit 0, with neither `--admin` nor `--delete-branch`. Rehashed all 35 Actseal and 14 Dorian command stdout/stderr receipts against their command manifests. The action records and independent GitHub outcomes agree; no force push or direct push to main was used.

## Branch retention and settings

- Actseal's earlier automatic-deletion blocker is resolved. Root changed only `delete_branch_on_merge=false`, merged under that readback, then restored the captured original **true**. Both one-field PATCH commands exited 0. The complete effective branch rules, ruleset roster, full ruleset 24679548, environment roster and complete PyPI environment responses are byte-identical before/while disabled/after restoration. The legacy-protection 404 response remains separately preserved and does not erase active rulesets. Independent fresh rules/environment/PyPI responses match those originals. Fresh final repository metadata still shows true, and `winddown/20261013/07A` remains at exact `52dbc145...` after restoration.
- Dorian already had **false** and required no settings change. Fresh metadata confirms false; complete main ruleset 17612546 and tag ruleset 17612548 match the independently captured premerge responses. `winddown/20261013/07B` remains at exact `5222f256...`.
- Native controls were retained rather than bypassed. Repository admin capability is not used as evidence of permission to waive a rule. No repository was archived, and this review changed no setting or ref.

## Complete resulting-main CI

Every run below is the original **attempt 1**, actual **push** event and exact resulting-main SHA above. All jobs and reported steps finished successfully; there are no failed, cancelled, skipped or pending jobs/steps in these rosters. Before/after head-filtered run inventories contain the same expected run IDs and no new attempt.

| Repository | Run | Workflow | Jobs | Reported steps | Conclusion |
|---|---:|---|---:|---:|---|
| Actseal | 38336991567 | CI | 6 | 71 | success |
| Actseal | 38336991552 | CodeQL | 1 | 8 | success |
| Actseal | 38336991586 | Gitleaks | 1 | 6 | success |
| Dorian | 38336473165 | ci | 3 | 30 | success |
| Dorian | 38336473354 | security | 1 | 11 | success |

**Actseal: 8 jobs / 85 reported steps and 8 actual check runs, all successful.** CI separately covers Linux/macOS Python 3.12/3.13, committed assets/regeneration and the required aggregate. CodeQL and full-history Gitleaks are independent successful lanes. The three applicable main-push required contexts pass. Dependency review is PR-only and passed on the exact reviewed head in run `38312827338/1`; no new main-push Dependency review execution is claimed.

**Dorian: 4 jobs / 41 reported steps and 4 actual check runs, all successful.** The complete Python 3.11/3.12/3.13 test matrix and SCA/SAST lane pass. Dorian has no configured required-status context; that native configuration is distinguished from the user's requirement to verify the actual CI. No additional approval was inferred from offline reviews; native approving-review requirements were independently inventoried before merge.

The actual job/step roster is verified, not merely the workflow aggregate. API job/step success does not independently recount test assertions or establish zero test-case skips. No local full suite, package publication or live-model test was rerun for this postmerge gate. Release/tag-triggered workflows are outside these README main-push gates.

## Evidence and limits

Private raw captures: `plan/artifacts/portfolio-merge-20261013-postmerge-a/`. They contain complete native PR/main/commit/compare/ref/settings records, before/poll/final run rosters, current attempt jobs/steps, check-run rosters and per-command arguments, exit status and timestamps. All **59 independent capture commands** exited 0. Observation interval: **2026-10-13 02:22:52.091369–02:33:56.818520 UTC**. Final readbacks confirm both stated mains and retained branches. Evidence-manifest SHA-256: `9109d89749d96d46500229356ccfd54547355b7733cbc8b626263817fb75d71d`.

Initial Dorian CI and later Actseal CI were observed running, then awaited with unchanged polls spaced at least 30 seconds. Neither was automatically rerun or treated as green before completion. An ancillary local reader initially assumed the Actseal command-manifest field name `name` in Dorian's differently shaped manifest and raised KeyError before verification. The corrected reader used Dorian's actual `label`/`exit_code` fields and verified all 14 hashes and its native merge command; the failed reader supplied no accepted evidence and altered nothing.

Required changes: none. This is read-only endpoint verification under the new explicit portfolio-merge authorization, not permission for a new product change, release, tag movement, branch deletion, repository archival or outreach. Only authorized private captures and this sanitized review were written; no credential, model call, network mutation or target source edit occurred. A later main, changed rule or new CI attempt requires a new scoped check.

Reviewed at 2026-10-13T02:35:49.711170+00:00
