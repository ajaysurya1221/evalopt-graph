# Terminal-Bench transfer: incomplete feasibility study

**The transfer stage ended with 58 executed attempts and 14 unstarted rows.** All 72 scheduled rows remain in the report. Among the 27 available verifier rewards per arm, upstream succeeded on **23/27** and eval-opt on **19/27**. Missing outcomes leave the full-schedule C-minus-B difference between **−36.11 and +13.89 percentage points**. These are conservative identification bounds, not a confidence interval or evidence of superiority.

Two explicitly approved, failure-informed admission amendments allowed limited continuation after preserved boundary failures. A later failure outside the approved class stopped execution; the operator explicitly approved finalizing the incomplete study. Each executed row ran once. No timeout was retried, repaired or retrospectively graded. The [execution history](operations/README.md) discloses all three phases, four unscored timeouts, three retained STOPs and three missing external completion acknowledgments.

## Outcomes and missingness

| Arm | Scheduled / executed / unstarted | Available rewards | Successes among available rewards | Missing rewards | Full-schedule success bounds |
| --- | ---: | ---: | ---: | ---: | ---: |
| B — pinned upstream | 36 / 29 / 7 | 27 | 23/27 (85.19%) | 9 | 63.89%–88.89% |
| C — eval-opt | 36 / 29 / 7 | 27 | 19/27 (70.37%) | 9 | 52.78%–77.78% |

Each arm's nine missing rewards comprise two executed timeouts without a retained verifier reward and seven unstarted rows. Missing rewards are null, not silently assigned failure or zero consumption. The available-case percentages are conditional on observed coverage; missingness is not assumed random. The full-schedule bounds assign each unavailable binary outcome both possible values. The paired difference bounds use the unfavorable assignment for eval-opt at the lower end and the reverse at the upper end. Repeated attempts do not create additional independent tasks.

[Per-row outcomes](bundle/reports/outcomes.json), [all attempts](bundle/reports/attempts.json) and the [unchanged frozen analysis](bundle/reports/analysis.json) preserve these distinctions. Execution status `completed` means the run ended, not that its verifier awarded success. Each arm has 27 retained complete captures and verified execution boundaries; the four additional executions retain missing capture and null rewards. The all-three-success counts in the analysis are observed fully successful task groups, not proof that the unavailable groups failed.

This is the preregistered 12-task **Terminal-Bench 2.0 feasibility subset**, pinned to `69671fbaac6d67a7ef0dfec016cc38a64ef7a77c`, with original task semantics, required services and per-task limits retained. It is not an official leaderboard score. Conditions remain Harbor 0.24.0, Codex CLI 0.154.0, `gpt-6-astra`, requested effort `ultra`, and ChatGPT subscription authentication. No API billing or model substitution was introduced. The [registration](../transfer-registration-2026-10-10/README.md) predates admission; [amendment provenance](operations/finalization.json) records the later changes to admission and delivery scope.

## Measured resources

The registered accounting view retains **54 complete, three partial and one unavailable** attempt record. Known counters from runtime-blocked attempts remain included once. The 14 unstarted rows consumed no recorded trial attempt; their absent outcomes are still unknown. Trial 55's executed but unavailable consumption is unknown, not zero.

| Arm | Complete / partial / unavailable attempts | Input tokens, observed lower bound | Output tokens, observed lower bound | Model calls, observed lower bound | Tool calls, observed lower bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| B | 27 / 1 / 1 | 40,964,832 | 367,946 | 1,252 | 1,139 |
| C | 27 / 2 / 0 | 45,503,253 | 351,164 | 1,101 | 1,010 |

These lower bounds already include complete-attempt totals and partial-only components. Do not add those components again. Complete-subset summed parent wall times are 7,251.344 seconds for B and 5,246.523 seconds for C; they are not total study elapsed time. The legacy accounting view excludes partial records; use `all_attempt_resources.registered_accounting` for the registered distinction. No efficiency comparison, token-matching or dollar-cost claim is supported. Setup, verification and engineering-assistant overhead are outside these trial counters.

## Reproduce the retained evidence

From the repository root with **CPython 3.13.12**, run:

```sh
python3.13 -I -B results/skill-workflows-v1/transfer-comparison-2026-10-10/reproduce.py --source .
```

The standard-library entrypoint verifies the entire outer file roster, the fixed inner evidence bundle, trusted source identities, all 58 retained attempts, all 72 schedule rows and the frozen reward/counter analysis. It runs no models, containers, original verifiers or candidate code. The [fresh local replay receipt](validation.json) records a clean environment with no third-party distributions. [Private QA summaries](operations/finalization.json) separately bind full-byte preservation, unchanged frozen accounting and runtime projections, and [native/external journal correspondence](operations/journal-mapping.json). Public replay verifies those notes' file identities; it does not independently reconstruct omitted raw logs, archive bytes or process observations.

The inner bundle identity is `6ac536cef0fa72f52dfd066e3c45861a61c5044ca3c7d0e82166b6ab1837e62d`. The private frozen report export is `4327db0ccd2ccee61dcc1c31db92b8075be49a60c1f1c08aa186ed06d2998232`. [CHECKSUMS.json](CHECKSUMS.json) binds this publication package; hashes identify bytes, not authenticated producers. Frozen exporter documents retain their creation-time “candidate” and local-export wording; that does not override this stopped-study report or imply that a local exporter performed network publication.

## What this study establishes

| Evidence class | Result and limit |
| --- | --- |
| Authored held-out workflow comparison | [432 final outcomes](../heldout-comparison-2026-10-10/README.md): B and C each 132/144 valid completions; primary difference 0.00 points, paired 95% interval −2.08 to +2.08. No demonstrated upgrade or equivalence claim. |
| External transfer | 54 available rewards within 72 scheduled rows; descriptive success and missing-outcome bounds above. Incomplete, amended feasibility study; no superiority or official leaderboard claim. |
| Engineering conformance and replay | Separately reviewed controls, byte preservation and retained-artifact arithmetic. These are not additional live trials or independent verifier execution. |
| Independent replication | Not established. This is a maintainer-run study with separated authoring, grading and review roles; it does not meet the independent-human-authorship requirement. |

The acceptance kernel U/M/G comparison belongs to the authored suite and is not applied to this transfer stage. Outcome-dependent stopping and post-freeze amendments prevent an uninterrupted frozen-run claim. The transfer result does not establish an upgrade or alter the registered primary conclusion.
