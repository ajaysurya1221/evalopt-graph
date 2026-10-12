# REPORT 08 scan preflight — Status DONE

Independent read-only classification by Codex. This is a diagnosis of retained scanner findings, not approval of a suppression patch, release, or globally clean history. No scanner configuration, historical source, campaign, or result was changed.

## Scope and evidence

- Scanner: Gitleaks 8.30.1, existing main configuration SHA-256 `4a228e1a8589d22ef37be550c83c5db5e4809cd32a137b0f37374a5bb7ab83aa`.
- Retained redacted public-history report: `plan/logs/public-history-scan.json`, SHA-256 `0b3cbecec773a1c5a52ba31d60f40a8122fbd0eda6b3b5c812c8ec1ddf40f65b`. The retained public mirror currently contains 99 reachable commits. This review inspected its immutable blobs locally; it did not fetch or widen scan scope.
- Exactly 17 findings: 16 `generic-api-key`, one `github-pat`; six affected paths; five unique captured values. None is an authentication credential in its inspected source context.
- All eleven prior v4 findings match the accepted v4 roster by commit, path, rule, line, and column. The other six are in v1 public history. Duplicate fingerprint strings at the single-line sealed manifest represent two distinct column ranges; do not deduplicate by fingerprint alone.
- Root reports a clean main-only history scan. That narrower result is distinct from the 17-finding all-public-refs scan and is not independently rerun here.

## Per-occurrence classification

Path aliases below expand literally; their spelling is part of the proposed narrow scope.

| Alias | Exact repository path |
|---|---|
| V4M | `bench/harbor/skill-workflows-v4/tasks/manifest.json` |
| V4R | `results/skill-workflows-v4/offline-package-2026-10-12/reviews.json` |
| V4C | `results/skill-workflows-v4/offline-package-2026-10-12/compatibility.json` |
| V1P | `results/skill-workflows-v1/transfer-comparison-2026-10-10/operations/bounded-continuation/controller/classifier.py` |
| V1C | `results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-tasks/candidate-manifest.json` |
| V1S | `results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-manifest.json` |

Commit aliases: V4 = `49a379c7001b5b156f9f75b358da03a4367b252e`; V1P = `4c5467e1862dec0da5b53b61293e564040d1e5d0`; V1M = `a352c38a764afeb0f406848ebd14591af21a486b`.

| Finding | Commit | Path | Line:columns | Rule | Nature / value group |
|---|---|---|---|---|---|
| 1 | V4 | V4M | 49:50–124 | generic-api-key | Source checksum H4, tokenizer agent API |
| 2 | V4 | V4M | 56:53–127 | generic-api-key | Source checksum H4, tokenizer mutant-1 API |
| 3 | V4 | V4M | 62:53–127 | generic-api-key | Source checksum H4, tokenizer mutant-2 API |
| 4 | V4 | V4M | 68:53–127 | generic-api-key | Source checksum H4, tokenizer mutant-3 API |
| 5 | V4 | V4M | 74:51–125 | generic-api-key | Source checksum H4, tokenizer oracle API |
| 6 | V4 | V4R | 140:92–166 | generic-api-key | Review source checksum H4, same agent API |
| 7 | V4 | V4R | 147:95–169 | generic-api-key | Review source checksum H4, same mutant-1 API |
| 8 | V4 | V4R | 153:95–169 | generic-api-key | Review source checksum H4, same mutant-2 API |
| 9 | V4 | V4R | 159:95–169 | generic-api-key | Review source checksum H4, same mutant-3 API |
| 10 | V4 | V4R | 165:93–167 | generic-api-key | Review source checksum H4, same oracle API |
| 11 | V1P | V1P | 220:40–81 | generic-api-key | D: ordinary `require` diagnostic, duplicate/unmatched stop issue |
| 12 | V1P | V1P | 239:41–76 | generic-api-key | D: ordinary `require` diagnostic, duplicate/unmatched signal |
| 13 | V4 | V4C | 4282:93–132 | github-pat | T: synthetic pytest parameter captured in a test-name receipt |
| 14 | V1M | V1C | 287:17–97 | generic-api-key | HN: checksum of read-only-source-report `agent/new_api.json` |
| 15 | V1M | V1C | 288:17–97 | generic-api-key | HO: checksum of read-only-source-report `agent/old_api.json` |
| 16 | V1M | V1S | 1:14320–14399 | generic-api-key | HN: same checksum in sealed manifest |
| 17 | V1M | V1S | 1:14408–14487 | generic-api-key | HO: same checksum in sealed manifest |

## Independent source proof and unique values

The three full values below are reproduced SHA-256 checksums, not credentials:

| Group | Occurrences | Exact value or construction | Proof |
|---|---:|---|---|
| H4 | 10 | `429252aed4b6276232a2a509de69c0b779fb21e1a5442cc3ad3721114e284fd3` | SHA-256 independently recomputed from all five `bench/harbor/skill-workflows-v4/tasks/difficulty/chunked-escaped-tokenizer/{agent,mutant-1,mutant-2,mutant-3,oracle}/api.py` blobs at V4; each matches. Manifest and review occurrences bind those same files. |
| HN | 2 | `e814041bd09d1fb4f833aa2ca25ec1d2486633e1a2801310dfb4f14c18e0bd9d` | SHA-256 independently recomputed from `results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-tasks/read-only-source-report/agent/new_api.json` at V1M; candidate and sealed manifests both match. |
| HO | 2 | `100e5b33df33a7f63fe6697fa70525dedc3de5fb3131224b5633acca8279feac` | Same independent check for adjacent `agent/old_api.json` at V1M. |
| D | 2 | `duplicate/unmatched` (19 characters) | Both source lines are ordinary Python assertion/error messages. The scanner interprets nearby `key` and comma/quote syntax as key assignment. No credential read, assignment, or authentication operation occurs in either expression. |
| T | 1 | Legacy GitHub token prefix concatenated with the literal `SYNTHETIC` repeated five times; the rule captures its first 40 characters. | At V4, `tests/test_skill_workflow_publication.py:242` constructs `b"ghp_" + b"SYNTHETIC" * 5` in a parametrized sensitive-content rejection test. Its expanded parameter appears only in the retained passing test name. The source file SHA-256 independently matches `363e337cb047665256daa58ea2939595b2ad57c3d666535e12ab1aa522dd6ae9`. |

The captured synthetic substring is deliberately not expanded here. Its SHA-256 is `605bffde4a070747cd97f5d9e882d2d8c34450602fa857339add63bc1fe33a4f`. The complete expanded test parameter has 49 characters; confusing that with the scanner's 40-character capture would produce an ineffective exception.

A supplementary local stdin extraction fed only the 16 unique already-classified historical source lines to the same scanner/configuration. It produced exactly 17 findings and the five groups/counts above. Expanded matches were inspected in process memory and were not printed or saved. This is capture-boundary verification, not a replacement all-history scan. An initial attempt to emit JSON through `/dev/stdout` was rejected as an unwritable report path; a no-file verbose capture succeeded. Neither attempt changed the retained report.

## Narrow correction eligible for implementation review

Exact captured-value AND exact anchored-path exceptions are justified for these five nonsecret groups, with stock rules retained. Scope each group independently: H4 only V4M/V4R; HN and HO only V1C/V1S; D only V1P; T only V4C. Use an anchored exact literal for each captured value, not a general hash/token pattern, prefix, substring, commit-wide exclusion, file-wide exclusion, or directory exclusion. Escape regex metacharacters and require AND semantics between content and path. If supported without replacing a stock rule, also scope the exception to the diagnosed rule ID.

The implementation must independently demonstrate that only these values in these exact paths are exempt. Do not suppress the six files wholesale, skip full-history scanning, alter old evidence, or infer approval from this diagnosis. Existing failures remain historical failures. A future clean result must name its scanner version, configuration, exact refs/commits, and actual exit status.

## Required negative controls before accepting a correction

1. Reproduce the original 17 findings under the original configuration and zero residual findings under the candidate configuration on the same fixed public mirror; compare exact occurrence identities, including columns.
2. Put every approved value into a different path and a near-matching path. Each must still be reported under its original triggering context. This proves path anchoring and prevents accidental OR semantics.
3. Put a changed value and a distinct synthetic detected credential in each permitted path, including a line that also contains the approved value. Those distinct findings must remain visible. Use finite synthetic controls, never credentials.
4. Test value prefixes/suffixes and regex metacharacter cases. For T, use the exact 40-character capture and a different 40-character token-shaped value; do not merely test the 49-character source expression.
5. Keep unrelated stock-rule detections and the existing exact synthetic-fixture exception working. Require a fresh Fable security review and Codex diff review of the actual patch and control outputs before merge. No source, result, or protection changes are authorized by this report.

## Limits and disposition

All 17 supplied findings are classified; there are no unresolved suspected credentials among this roster. This does not certify the absence of other secrets, authenticate evidence producers, or approve publication. Future added findings, changed values, changed paths, scanner errors, or scope drift require separate review. The remaining work is a narrowly scoped Task08 scanner correction and its negative controls, not a blanket waiver.
