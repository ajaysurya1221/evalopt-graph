REPORT 10-gates-current — Status DONE

Read-only GitHub gate inventory for `ajaysurya1221/evalopt-graph`, captured **2026-10-12 22:17:44–22:18:04 UTC**. This report inventories configuration; it neither approves a candidate nor authorizes a merge, tag, deployment approval or release.

## Actual state

- Public repository; `archived=false`; default branch `main`.
- Main is still `fc3045dbda29c1d274747329ceb6724a783b0df7`.
- `GET git/ref/tags/v0.1.1` and `GET releases/tags/v0.1.1` each returned HTTP 404, `Not Found` (gh exit 1). No corresponding tag or release was present at capture time; refresh before creation.
- The repository response reports the currently authenticated account's permissions as `admin=true`, `maintain=true`, `push=true`, `triage=true`, `pull=true`. These permissions do not bypass either ruleset or prove an actual deployment can be approved.
- Repository merge configuration permits squash only: `allow_squash_merge=true`, merge/rebase methods false.
- **Pre-merge conflict requiring resolution:** `delete_branch_on_merge=true`. The approved plan forbids branch deletion, including automatic deletion. Merely omitting a client `--delete-branch` flag does not establish preservation under this repository setting. Root must establish a permitted way to preserve the branch before merging, or record that gate as blocked. I did not change this or any other setting.

## Active rulesets and effective main requirements

`GET rulesets?includes_parents=true` returned exactly two active repository rulesets; each complete detail response and `GET rules/branches/main` are retained.

**Ruleset 19205651, “main protection”**

- Target branch, include `~DEFAULT_BRANCH`, no excluded refs.
- Deletion and non-fast-forward updates prohibited.
- Pull requests required; only squash allowed; required review-thread resolution true; extra approval for unattributed changes true.
- Configured approving review count 0; stale-review dismissal, code-owner review and last-push approval false; explicit required-reviewer list empty. This does not relax the run's independent two-review requirement.
- Strict required-status policy true; `do_not_enforce_on_create=false`.
- Required check names: `CI / required`, `CodeQL / Python`, `Dependency review`, `Gitleaks / full history`. The API records no integration IDs alongside these contexts.
- `bypass_actors=[]`, `current_user_can_bypass="never"`.
- The separate legacy `GET branches/main/protection` returned HTTP 404, `Branch not protected` (gh exit 1). This denotes no legacy protection record; it does **not** negate the active ruleset. The effective-main-rules endpoint independently returned the same four rule types and exact parameters.

**Ruleset 19205653, “protect v* tags”**

- Target tag; include `refs/tags/v*`, no excluded refs.
- Deletion and updates prohibited; no creation prohibition in the returned rule list.
- `bypass_actors=[]`, `current_user_can_bypass="never"`.
- No tag was created or tested by this inventory.

## PyPI environment

- Environment `pypi` exists.
- Required-reviewers protection (ID 60412527) lists one User: `ajaysurya1221` (ID 74526464).
- `prevent_self_review=false`.
- Deployment branch policy: `protected_branches=false`, `custom_branch_policies=true`.
- The policy roster has exactly one entry: ID 55124259, type `tag`, pattern `v*`.
- `can_admins_bypass=true` is a configuration observation only. The approved plan does not authorize bypass or protection changes.
- No wait-timer or additional custom protection was returned by the environment response.
- **Actual deployment approval remains UNVERIFIED.** No candidate release run or pending deployment was selected. Eligibility requires the actual future run's pending-deployment response with `current_user_can_approve=true`, plus the plan's prior artifact/review gates. Reviewer configuration alone is not that evidence. No pending-deployment approval endpoint was called.

## Evidence and commands

The ignored directory `plan/artifacts/10-gates-current/` was verified with `git check-ignore --quiet` before creation. Each API call retains its exact raw JSON stdout, stderr, endpoint, UTC start/finish, elapsed time and exit code; `SHA256.json` records capture-file hashes. Calls used only existing authenticated `gh api` GET requests to:

```text
repos/ajaysurya1221/evalopt-graph
repos/ajaysurya1221/evalopt-graph/git/ref/heads/main
repos/ajaysurya1221/evalopt-graph/git/ref/tags/v0.1.1
repos/ajaysurya1221/evalopt-graph/releases/tags/v0.1.1
repos/ajaysurya1221/evalopt-graph/rulesets?includes_parents=true
repos/ajaysurya1221/evalopt-graph/rulesets/19205651
repos/ajaysurya1221/evalopt-graph/rulesets/19205653
repos/ajaysurya1221/evalopt-graph/rules/branches/main
repos/ajaysurya1221/evalopt-graph/branches/main/protection
repos/ajaysurya1221/evalopt-graph/environments/pypi
repos/ajaysurya1221/evalopt-graph/environments/pypi/deployment-branch-policies
```

All GETs completed. The three expected 404 responses are preserved as nonzero exits rather than called successes. No credential/environment-value reads, model calls, API outside GitHub, Git mutations, pushes, tags, PR changes, merges, reruns, deployment decisions or protection/settings changes occurred. Package, source and candidate CI reviews were not repeated. No publication-readiness conclusion is inferred from this inventory.
