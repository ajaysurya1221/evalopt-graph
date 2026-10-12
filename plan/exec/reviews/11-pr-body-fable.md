REVIEW 11-BODY — Reviewer Fable high | Verdict ACCEPT

Scope: read-only wording review of the draft PR43 body at plan/artifacts/11-pr/body.md (control worktree) against plan/exec/FINAL_REPORT.md, plan/exec/release-receipt.json and plan/exec/reports/11-root-verification.md as they exist at candidate ba5db20743e632f6295a2d9bfbda7867e6579978. The three evidence files in the closeout worktree are byte-identical to that commit (git diff against the candidate is empty). This is not a source review and not hosted CI acceptance; no other review verdicts were consulted. Requested and observable model: Fable 5.1 (claude-fable-5-1), high effort. No model, subagent, network or credential calls were made. No mutation other than this file.

Checked claims (body sentence -> evidence)

- "actual v0.1.1 publication" -> FINAL_REPORT "v0.1.1 is published"; receipt published_at 2026-10-12T22:56:37Z, release_url to tag v0.1.1, is_latest true. Accurate.
- "release receipt binds the published GitHub/PyPI bytes to the reviewed source and release workflow" -> receipt source 8c8b7f4 (merged from reviewed head 7043 with identical trees per FINAL_REPORT), run 38317836286 attempt 1, four GitHub asset SHA-256s, two PyPI file SHA-256s equal to their GitHub counterparts, four attestation bindings with runInvocationURI. Accurate.
- "no package capability or existing release asset changes" -> FINAL_REPORT: no converter/adapter/predicate/integration/dependency added; v0.1.0 tag and asset identities unchanged; 11-root-verification: src/tests/bench and release workflow/metadata unchanged relative to released source, no new build or upload. Accurate.
- "migration coverage, preserved research, four independent README PRs, and human-owned archival actions" -> S3 16/16, study PRs 33–36 untouched, four PR table rows, S10 "deliberately not executed". Accurate.
- "distinguishes completed publication from this PR's own review/CI/merge and the subsequent restoration of the temporary branch-cleanup preference" -> FINAL_REPORT paragraph 2 and branch-preference paragraph say exactly this; 11-root-verification closes with "Final PR/current-main CI, branch retention and restoration remain later separate gates". Accurate; this is the key published-vs-pending distinction and it is drawn correctly.
- "retained in a separate terminal receipt on the control branch" -> FINAL_REPORT "terminal follow-through record on the retained control branch". Accurate.
- "Historical partial/revised records remain preserved; outreach is draft only" -> FINAL_REPORT: PARTIAL Fable attempt and Dorian executor preserved, not relabelled; OUTREACH_DRAFTS not posted. Accurate.
- "complete existing local runbook passed (422 tests, 32 authored conformance cases, 75 protected-file checks)" -> 11-root-verification: complete verify.sh, 422 tests, 32 conformance cases, 75 protected bytes. Numbers match.
- "11 run-local controls, lint/format, document links and a bounded secret scan" -> 11/11 run-local controls, Ruff check/format, local-link existence checks, Gitleaks on plan/exec described as bounded hygiene. Accurate.
- "Independent Codex and fresh Fable review of this exact closeout head and current hosted CI are required before merge" -> consistent with FINAL_REPORT review-gate paragraph and the contract. Accurate; does not claim they have passed.
- "Four sibling README PRs remain open and are not merged by this run" -> FINAL_REPORT "All four remain unmerged by this run". Accurate.

Negative checks: the body does not claim any sibling-repository merge, does not claim archival, does not claim outreach was posted, does not claim new capability, does not claim this PR's CI or reviews have passed, and does not claim the restoration of the auto-delete preference has happened.

Findings by severity

- High: none.
- Medium: none.
- Low (optional wording): "artifact smoke" in the validation sentence. The runbook step is scripts/smoke_test.sh, which 11-root-verification calls the "compatibility smoke" (offline import, unit tests, simulated CLI scenarios including one that writes artifacts). It is not a wheel/sdist smoke of the closeout head; the installed-from-PyPI smoke in FINAL_REPORT belongs to the release endpoint, not to this candidate. "compatibility smoke" would match the cited evidence exactly. Not misleading as to release status, so not a required change.
- Informational: the task described a four-paragraph body; the file has three paragraphs. Content is complete; no action needed unless a four-paragraph shape is itself a requirement elsewhere.
- Informational: the body does not name the candidate SHA. Acceptable for a PR body because the independent reviews bind the exact head; the body's "this exact closeout head" is consistent with that.

Required changes: none.

Limits: wording review only; I did not re-run tests, re-download published bytes, or query GitHub/PyPI. Hosted CI for the candidate, the Codex and fresh Fable source reviews, branch retention and the preference restoration remain separate open gates and are correctly described as such in the body.
