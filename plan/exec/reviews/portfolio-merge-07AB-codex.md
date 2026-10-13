REVIEW portfolio-merge-07AB — Reviewer Astra | Verdict ACCEPT

Acceptance is for exact source/review correspondence and current hosted CI below. **Actseal merge remains operationally BLOCKED by its automatic branch-deletion setting; Dorian is READY under the observed native requirements.** Neither observation executes a merge. New user authorization permits these reviewed sibling README merges; it does not authorize branch deletion, an administrative bypass, weakened protections, a release or archival.

## Exact candidates and retained independent reviews

| PR | Exact accepted/current head | Unchanged current base/main | Complete diff |
|---|---|---|---|
| Actseal [70](https://github.com/ajaysurya1221/actseal/pull/70) | `52dbc14554486e8ff9e31455d550bfc3d43f139e` | `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b` | README.md only: one paragraph, one removal/one addition |
| Dorian [44](https://github.com/ajaysurya1221/dorian/pull/44) | `5222f256ba23c2fa345fb5a2f6d033c336dcbcc1` | `eeb193792fac8a66b18f5222287a8fcf336dda08` | README.md only: ten added lines |

Fresh REST PR/files/commit/main records, native PR metadata and before/after reads agree. Each PR has the single reviewed commit, with its parent equal to the unchanged base; there is no intervening base change or added source requiring a different candidate review. Both are OPEN, non-draft, MERGEABLE/CLEAN with no auto-merge request. Both target worktrees remain clean at their reviewed heads.

Public README bytes fetched at each exact head equal `git show <head>:README.md`. SHA-256 values are Actseal `7b0dc4bf9857cf8885fdaf04578605b831caea2a8235579613ac3b7a4dba8724` and Dorian `7a62147b21927909b67a8f131696058d33967a7a72e77e0aea45941f5c830ca0`. Source, dependencies, NOTICE, schema/statistical contracts and frozen files are absent from both diffs; independence and evidence-boundary language remains the previously accepted wording.

Read applicable Actseal AGENTS/CLAUDE, current v1 state, contribution rules, stability and interface contracts; read Dorian CONTRIBUTING and VALIDATION_HONESTY. No Dorian AGENTS file is present in this reviewed checkout. Prior exact-candidate Codex and fresh Fable records each say ACCEPT and remain applicable because the complete head/base pair is unchanged. No fresh model call or full suite is claimed in this premerge inspection. Earlier independent local checks retain their original provenance and disclosed skips; fresh hosted checks are listed separately below.

## Complete current run/attempt/job/step roster

All current runs listed below remain attempt 1, completed/success, bind the exact candidate head and have all jobs and reported steps successful. No failed, cancelled, skipped or pending job/step was found; no rerun was requested.

| Repository | Run | Workflow/event | Jobs | Reported steps |
|---|---:|---|---:|---:|
| Actseal | 38312773157 | CI / push | 6 | 71 |
| Actseal | 38312827368 | CI / pull_request | 6 | 71 |
| Actseal | 38312827325 | Gitleaks / pull_request | 1 | 6 |
| Actseal | 38312827338 | Dependency review / pull_request | 1 | 3 |
| Actseal | 38312827339 | CodeQL / pull_request | 1 | 8 |
| Dorian | 38315042449 | ci / pull_request | 3 | 30 |
| Dorian | 38315042552 | security / pull_request | 1 | 11 |

Actseal totals **15 workflow jobs / 159 reported steps**. Each CI run individually covers Linux/macOS Python 3.12/3.13, committed assets/regeneration and the required aggregate. The three security/review lanes independently pass; their results are not inferred from the aggregate. Native status rollup has 17 success entries: these include the 15 workflow checks, a separate CodeQL service check and advisory CodeRabbit status. The REST check-run roster is 16 because CodeRabbit is a status, not an additional workflow run.

Dorian totals **4 workflow jobs / 41 reported steps**: Python 3.11/3.12/3.13 plus SCA/SAST. Its five-entry success rollup includes advisory CodeRabbit; the REST check-run roster contains the four workflow jobs. The retained workflow definitions run the full tests and lint, and security audits the exported project dependency set and first-party source. These API observations do not independently recount test assertions or imply zero test-case skips. No release/live-model workflow was required or run for this README diff.

## Native requirements versus offline reviews

**Actseal:** active main ruleset `24679548`, no bypass actors, exact `refs/heads/main`. It requires a pull request, squash-only merge, linear history, resolved review threads, strict current-base status checks and CodeQL scanning (high-or-higher security alerts/errors). Its required approving-review count is **0**, code-owner and last-push approval are false. Four required contexts — CI / required, CodeQL / Python, Dependency review and Gitleaks / full history — all pass; `gh pr checks 70 --required` exits 0. There are zero GitHub review records, requested reviewers and review threads. Thus no missing native human approval is inferred from absent hosted reviews; the accepted Codex/Fable files are the separately required offline pair.

**Dorian:** active `protect-main` ruleset `17612546` targets the default branch and disallows deletion/non-fast-forward updates; no bypass actors. It configures **no required status-check or approving-review rule**. `gh pr checks 44 --required` exits 1 with exactly “no required checks reported”; this is preserved as absence of a configured context, not fabricated green required-check output or a failed test. Both actual configured PR workflows nevertheless pass under the user's review/CI gate. There are zero GitHub review records, requested reviewers and review threads. Tag protection `17612548` is separately inventoried and must remain untouched.

Legacy `/branches/main/protection` returns 404 for both repositories. Their active rulesets, including Actseal's review/check rules, are still effective; 404 is not treated as proof of no protection. Authenticated repository permissions include push/maintain/admin for both, but admin capability is not permission to bypass. Neither repository is archived.

## Operational blocker and root-owned follow-through

- **Actseal: HOLD immediate merge.** Fresh repository metadata still has `delete_branch_on_merge=true`. Omitting a CLI deletion flag does not neutralize that server preference. Root must resolve branch retention through the separately authorized/reviewed narrow operational path, retain exact setting/protection readbacks, and require false before the normal merge; restore its captured original value after the authorized merge sequence. This review performs no setting mutation and does not independently broaden setting authority. No approval, rule or status-check bypass is permissible.
- **Dorian: READY at this endpoint.** `delete_branch_on_merge=false` already preserves the head ref. Squash is enabled; normal exact-head squash is consistent with the accepted plan even though Dorian also permits other merge modes. No settings change is needed for Dorian.
- Immediately before either mutation, root should re-read exact head/base and required controls. Use normal exact-head merge, no `--admin` or branch deletion. Verify retained head refs, resulting tree/main and the resulting-main workflow evidence afterwards. If a head/base/requirement changes, this finite premerge review no longer establishes that later endpoint.

## Evidence and exact retained review bindings

All 55 read-only native capture commands are retained with stdout, stderr, argument vectors, UTC intervals and exit statuses in private `plan/artifacts/portfolio-merge-20261013-review-a/`. Observation interval: **2026-10-13 02:16:19.985899–02:18:26.468429 UTC**. All ordinary GET/GraphQL/query/check commands succeeded except the two explicitly explained legacy-protection 404s and Dorian's no-required-check result. Current run rosters, heads and bases were unchanged in the final readbacks. Evidence-manifest SHA-256: `4bdc473ea86c3529b93f58240b949ada76c44aad5cedb9ff3d595c9686ba74d9`.

| Accepted source review | SHA-256 |
|---|---|
| `07A-codex.md` | `714943af1109c273b060d1137c6828d45fc779065ea48c332264c91915e4dfa0` |
| `07A-fable.md` | `b9431a89c54cb7a93f2bada9be06862c10a13660fa0ca2c6337648b2bfa968ee` |
| `07B-codex.md` | `b9f4c1a5714cdd971c43f7816d3a224a8baf3fb55868ceb504abe130af46ed34` |
| `07B-fable.md` | `167c9615e249e74c0164a42215924e87195d1c414fe59d2781bf62067c4415d2` |

Only this sanitized review and the authorized private capture directory were written. No repository source, branch, setting, review state, CI run, credential, environment, tag, artifact or release was changed. No Fable/model call or new paid work occurred. Required source changes: none.

Reviewed at 2026-10-13T02:19:52.280575+00:00
