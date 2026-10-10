# Held-out comparison: no demonstrated workflow upgrade

**Upstream and eval-opt each achieved 132 valid completions out of 144 trials (91.67%).** The registered C-minus-B contrast is **0.00 percentage points**, with a paired task-level 95% interval of **−2.08 to +2.08 points**. The registered positive-result and overall-upgrade conditions were not met. This observed tie does not establish equivalence across other tasks or conditions.

The study used 48 distinct authored tasks, eight per category, with three repetitions per arm. All 432 final outcomes are available. One controller interruption required one permitted infrastructure retry, leaving 433 retained attempts. Execution used Codex CLI 0.154.0, Harbor 0.24.0, `gpt-6-astra` and requested reasoning effort `ultra` under the frozen conditions. The task-level analysis treats repetitions as repeated observations, not 144 independent tasks per arm.

| Arm | Valid completion | Functional success | Unsupported success claims | All three repetitions valid |
| --- | ---: | ---: | ---: | ---: |
| A — common tools | 131/144 (90.97%) | 137/144 | 7/144 | 43/48 tasks |
| B — pinned upstream | 132/144 (91.67%) | 138/144 | 6/144 | 43/48 tasks |
| C — eval-opt | 132/144 (91.67%) | 138/144 | 6/144 | 44/48 tasks |

Each arm had zero graded boundary violations and zero incorrect refusals. Runtime status `completed` for all 432 final attempts means execution finished; it does not mean all tasks passed. [Per-trial outcomes](bundle/reports/outcomes.json) and the [frozen analysis](bundle/reports/analysis.json) retain the complete denominators and failures.

The sole primary contrast uses category-stratified paired task/cluster resampling, 20,000 resamples and seed `20261008`. With no unavailable final outcomes, the unfavorable missing-outcome assignment yields the same interval. Ordinary functional-completion differences were all zero across 16 tasks; that bootstrap is degenerate and the registered sufficiency rule remains false. Neither a noninferiority claim nor an overall upgrade follows. The tiny stored primary difference (`1.156…e-18`) is floating-point residue around the exact zero task-average difference. The analysis's sentence about an observed 10-point gain is a static conditional caveat, not a description of this result.

## Acceptance policies on the same stopped outputs

The secondary [kernel report](bundle/reports/kernel.json) evaluates U, M and G on the same 432 final stopped outputs. The hidden grades identify 395 valid and 37 invalid outputs.

| Policy | Accepted / coverage | Invalid outputs accepted | Valid outputs not accepted | Abstentions | Artifact failures | Replay |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| U — accept all | 432/432 (100%) | 37/37 (100%) | 0/395 | 0 | 0 | 432/432 |
| M — minimal visible checks | 378/432 (87.5%) | 19/37 (51.35%) | 36/395 (9.11%) | 0 | 0 | 432/432 |
| G — frozen evalopt-graph | 378/432 (87.5%) | 19/37 (51.35%) | 36/395 (9.11%) | 9 | 0 | 432/432 |

The report's false-rejection measure counts valid outputs that were not accepted, including abstentions; those columns overlap. M and G produced the same aggregate acceptance/error counts here. This does not establish that G improves on M or that policy replay would change an agent's earlier work. The 1,296 replayed decisions reproduce from controller-collected visible evidence; hidden grades remain separate from policy inputs.

## Resources and interruption

[Registered all-attempt accounting](bundle/reports/analysis.json) covers the original interrupted attempt and its retry separately. Across 433 attempts, 417 have complete counters and 16 have partial counters; none has wholly unavailable accounting under the registered amendment.

| Arm | Complete / partial attempts | Input tokens, observed lower bound | Output tokens, observed lower bound | Model calls, observed lower bound | Tool calls, observed lower bound |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | 136 / 9 | 23,944,374 | 306,838 | 1,734 | 1,450 |
| B | 141 / 3 | 45,421,406 | 548,013 | 2,328 | 1,949 |
| C | 140 / 4 | 35,582,188 | 414,300 | 1,943 | 1,656 |

These lower bounds already contain the complete-attempt totals and partial-only components. Do not add them again, or add final-attempt totals to all-attempt totals. Exact summed parent wall times for the complete subsets only are 7,878.598 seconds (A), 13,882.312 (B), and 10,440.062 (C); they are not full-campaign elapsed time. The legacy accounting view excludes partial attempts and labels those counters unavailable; use the registered-accounting view for the amendment's distinction. **No efficiency comparison, token-matching claim or dollar cost is supported.** Setup, verification and engineering-assistant overhead are outside these trial totals.

The [operations note](operations/README.md) preserves the early clean audit pause and the later controller interruption as separate events. The interrupted original attempt has recovered usage but no original stopped snapshot or grade. Run 2's native end and returned-trial list remain unavailable; its 398-attempt correspondence is externally reconstructed from retained permissions and artifacts. The late forensic workspace was not graded. Both attempts remain in the evidence.

## Reproduce and inspect

From the repository root with **CPython 3.13.12**, run:

```sh
python3.13 -I -B results/skill-workflows-v1/heldout-comparison-2026-10-10/reproduce.py --source .
```

The standard-library replay verifies the outer file manifest, the frozen bundle, 48 released task assets, all 432 supplied-reply grades, policy decisions and registered analysis. Git preserves content and executable bits, but not the full POSIX permissions recorded for assets. The replayer first verifies the known bundle identity, copies it into a temporary directory, restores the declared asset modes there, and invokes the unchanged frozen verifier. The checkout and evidence bytes remain untouched. It makes no network/model calls and executes no candidate code or Docker containers. It checks the operations note's file identity but does not independently reconstruct private native logs or the missing controller lifecycle. The [validation receipt](validation.json) records local fresh-environment replay and separately reviewed private reconciliation.

The immutable held-out bundle ID is `6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa`. The private report export ID used for transfer linkage is `75049e332567275d12287036a9f9bd2a2eff1921852c06f5cd5d697b8a94c7fc`; the public report-object digest in [PUBLICATION.json](bundle/PUBLICATION.json) is a different object. [CLAIMS.md](bundle/CLAIMS.md), [UNAVAILABLE.json](bundle/UNAVAILABLE.json), [source identities](bundle/source-lock.json) and [registration](../heldout-registration-2026-10-09/README.md) provide the evidence boundaries. Hashes identify retained bytes; they do not authenticate the producer.

This is a maintainer-run study with separated authoring/grading roles, not independent human validation or independent agent replication. Public grade replay uses supplied hidden-case replies. The development pilot and Terminal-Bench transfer are separate evidence classes; the zero/null pilot and transfer fields in this held-out analysis describe their absence from this package. The [pilot](../development-pilot-2026-10-09/README.md) remains available. Transfer results are not established by this report.

The initial publication commit `a352c38` omitted one globally ignored `.log` fixture, and a fresh checkout normalized 74 regrade asset modes from `0600` to `0644`. Fresh-clone replay correctly failed. The packaging correction explicitly tracks the exact manifest-bound fixture and restores declared modes only in the temporary replay copy. It changes no task, score, frozen inner bundle, trial condition or statistical rule. Historical local replay remains distinct from subsequent public-clone verification.
