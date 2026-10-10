# Supplemental engineering review

This receipt describes an authorized Claude Code review of **19 selected public files**, followed by maintainer adjudication against the complete public artifacts and frozen code. It records **zero scored benchmark trials**. It is supplemental engineering work, not an independent benchmark replication or validation of workflow superiority.

| Retained attempt | Observed outcome |
| --- | --- |
| 1 | Authentication failed; exit 1. No model response was verified. Native failed-attempt token counters reported zero; this is not an independently audited billing statement. |
| 2 | Completed; exit 0. The observed native response model was **`claude-opus-5-5`** using Claude Code **2.1.281**. |

The original failure remains retained. The retry used identical command arguments, prompt and staged inputs. Its recorded environment-name allowlist added only `USER`, with no names removed; the username value and authentication data are excluded. The retry binds the original receipt's hash. This is evidence of the recorded correction, not provider authentication.

**Effort and turn limits remain qualified.** Both attempts requested `max` effort. Native telemetry reported active per-turn effort but did not establish the effective named or numeric level after possible caps. The completed attempt reported **25 native turns despite `--max-turns 20`**. Turn-limit conformance is not established; the receipt preserves the discrepancy. Native turns are not treated as a model-call count.

The successful attempt's final native `modelUsage` reported:

| Token category | Reported count |
| --- | ---: |
| `inputTokens` | 18 |
| `cacheCreationInputTokens` | 113,598 |
| `cacheReadInputTokens` | 356,845 |
| `outputTokens` | 60,076 |
| `thinkingTokens`, already included in `outputTokens` | 53,336 |

These categories are retained as reported. Thinking tokens are **not added again**, and mirrored `result.usage` counters are not additional consumption. These figures cover the retained supplemental review attempts, not all engineering work or campaign overhead. Authentication diagnosis, staging, adjudication, engineering-assistant usage and other unmeasured work are outside them. No dollar cost or efficiency claim is made.

The reviewer supplied ten numbered items and two hash-convention questions. These were suggestions requiring adjudication, not ten established defects. Inspection of the complete evidence resolved staging-only concerns and confirmed canonical-object versus literal-file hashes and nested package identities. Maintainers accepted limited outer-document clarifications; the adjudications did not justify changing grades, statistical rules, frozen bundles or runtime source.

[supplemental-review-receipt.json](supplemental-review-receipt.json) preserves the attempt, source, shared-input, findings and adjudication identities. The recorded checkout commit and exact staging-manifest identity have separate meanings. `CHECKSUMS.json` binds these package files by literal-byte SHA-256. Raw logs, provider metadata, prompts, private paths, account identifiers and credentials are excluded. The public projection supports inspection of the supplied receipt and its arithmetic; it cannot independently replay the private review or authenticate the producer.
