# V4 difficulty screen: complete, difficulty not validated

**All 16 upstream-B trials finished. The frozen result is 14 valid and functional completions, two unresolved grading-contract disputes, and no demonstrated completed functional failures.** The registered difficulty gate fails. No larger benchmark starts, and this upstream-only screen provides no estimate of eval-opt's benefit.

The response-contract correction has finite positive operational evidence: all 16 responses satisfy the declared response contract and accurately report the observed checks. That does not establish task correctness for the two disputed rows or fix the remaining semantic contract mismatch.

| Frozen measure | Result |
|---|---:|
| Original rows finalized / scheduled | 16 / 16 |
| Functional and valid completion | 14 true, 0 false, 2 unresolved |
| Response contract valid / check claims supported | 16 / 16 each |
| Ordinary repair and implementation completion | 8 / 8 |
| Tasks succeeding in both attempts | 7 / 8 |
| Tasks with genuine completed functional failures in both attempts | 0 / 8 |
| Timeouts / observed boundary violations / retries | 0 / 0 / 0 |
| Complete native usage records | 16 / 16 |

Counts come from the unchanged [frozen report](report.json), [per-trial inputs](inputs.json) and [case/witness projection](case-evidence.json). `semantic_failure_evidence_valid=true` means the evidence is eligible for assessing failure; it does not itself mean the task failed. Completion claims, unsupported-success and refusal aggregates retain two unknown outcomes rather than treating disputed tasks as passes or failures.

## Task results and the dispute

| Task | Attempt 1 | Attempt 2 |
|---|---|---|
| Backup reachability collection | Unresolved dispute | Unresolved dispute |
| Chunked escaped tokenizer | Success | Success |
| Dependency fair dispatch | Success | Success |
| Fare product itinerary | Success | Success |
| HTTP variant revalidation | Success | Success |
| Inherited glob policy | Success | Success |
| MVCC predicate serialization | Success | Success |
| Ordered tree three-way merge | Success | Success |

The backup-review responses supplied supported witnesses for the delta-base defect using the globally permitted finding kind `data-loss`. Its frozen defect obligation accepts only `incorrect-result`, while the delivered task binding does not disclose that narrower kind constraint. This produces an empty obligation match and a contract dispute in both repetitions. The separate expiry findings map normally. The [retained semantic diagnosis](semantic-dispute.json) records the evidence; it is a diagnosis, not a new grade. Both original outcomes remain null, with no rerun, rewritten check or retrospective correction.

The [registered gate](../difficulty-registration-2026-10-12/README.md) requires 4–12 successes, no unresolved tasks, and at least two tasks with genuine failures in both attempts, including an ordinary repair/implementation task. This screen has 14 known successes, two unresolved outcomes and no qualifying failures. Even resolving both disputes favorably would not supply the required failure evidence. The difficulty conclusion therefore does not depend on calling those disputes model errors.

## What was measured

Eight fresh authored tasks received two fresh isolated attempts using the complete Matt Pocock workflow bundle at `b0618bc436ad893b3c5e84e55fba86586d34a404`. Native returned identity and settings were checked against `gpt-6-astra`, `ultra`, Codex 0.154.0, Harbor 0.24.0 and CPython 3.13.12. Each sequential trial had a 600-second agent limit, one CPU, 2 GiB memory and one parent with at most two concurrent children at depth one. The [preregistration](../difficulty-registration-2026-10-12/registration.json) fixes source, skills, task order, verifier, continuation rules and analysis before execution.

All 16 original attempts ended normally; the sole operator exited successfully at 2026-10-12 14:04:12 UTC. Fresh process, container and existing-lock checks established quiescence before native replay and full-byte verification. The [endpoint audit](endpoint-audit.json) and [separate endpoint review](endpoint-review.json) reconcile 6,110 retained files, all 16 attempt seals, 32 stopped archives, 236 verifier container joins and 16 released owned networks. These checks establish correspondence within retained controller custody, not cryptographic producer authentication.

Callable trials retain 216 case records. Review trials use retained baseline/candidate witness executions; their case rosters are oracle references, explicitly marked `not_executed_by_review_contract` in the public projection. Those entries are not failed or silently missing executions. Ten retained review witnesses account for 20 additional verifier containers.

The [offline package](../offline-package-2026-10-12/README.md) records 586 tests and 264 subtests with zero skips for v4 admission. Those controls did not cover the live finding-kind/obligation combination that caused the dispute. Passing offline controls is therefore reported alongside the discovered limitation.

## Resources and secondary acceptance policies

| Measured resource | Total |
|---|---:|
| Input tokens | 11,385,116 |
| Output tokens | 169,883 |
| Owned model response records | 437 |
| Tool calls | 387 |
| Controller time, including setup, capture and verification | 3,962.880 seconds |

All 16 attempts have complete native token/call accounting, including children without duplicated ownership. Separate agent-only wall time is unavailable. These are measured resources, not dollar costs, token-matched conditions or efficiency evidence.

U accepts every stopped output; M requires trustworthy visible checks; G applies the frozen evalopt-graph acceptance policy to the same stopped outputs. Hidden grades are used only afterward for comparison.

| Policy | Accepted / 16 | False rejection among resolved rows | Incorrect acceptance among resolved rows | Unknown outcomes | Artifact failures / abstentions |
|---|---:|---:|---:|---:|---:|
| U | 16 | 0 | 0 | 2 | 0 / 0 |
| M | 14 | 2 | 0 | 2 | 0 / 0 |
| G | 14 | 2 | 0 | 2 | 0 / 0 |

M and G reject the two successful inherited-glob-policy outputs because of the deliberately obsolete visible check. They accept the two disputed backup-review outputs; their correctness remains unknown. Zero known incorrect acceptances does not mean all acceptances were correct. This is a secondary stopped-output comparison, not a test of how either policy would change agent behavior.

## Reproduce the unchanged report

From a fresh checkout, use CPython **3.13.12**:

```sh
python3 -I -B results/skill-workflows-v4/difficulty-2026-10-12/reproduce.py \
  --repo . --bundle results/skill-workflows-v4/difficulty-2026-10-12
```

The command checks the public checksum roster, pinned source and registration, then recomputes the frozen report from retained typed records. It invokes no model, Docker container, candidate code or private trajectory. Full raw capture stays private; the public packet contains sanitized projections and correspondence hashes. Public replay proves consistency, not independent live replication. `checksums.json` covers every other file in this packet.

Report SHA-256: `754eb66f0b0425e19f9f41eb55abd53896119a3420a13de3bb7a44ba31cc1f68`.
Registration SHA-256: `5c75186aeb6081b4a7dac4b10704c9992cda7f55b62acc8ae64718c5dd06b0ac`.

## Review, CI and limits

This is a maintainer-run study with separated AI implementation and review roles. The endpoint reviewer previously authored task assets, so that review explicitly excludes independent oracle validation; a separate semantic reviewer checked the dispute diagnosis. It is not independent human replication. The [claim-to-evidence table](CLAIMS.md) distinguishes offline controls, live observations, replay and interpretation.

Before model dispatch, all ten independent CI lanes passed in each of three exact-head runs at `14575abf2ecd02b3f33962f481b2f14bff6cab5b`. The original concurrency cancellation remains preserved, followed by one unchanged-source rerun. The unchanged full-history scanner and its dependent aggregate remained red: eleven findings were independently adjudicated as nonsecret checksums or a synthetic test token. This was a disclosed external operational disposition, not globally green CI or a scanner suppression. See the [CI disposition](../ci-disposition-2026-10-12/README.md) and [launch CI record](launch-ci.json). Any later publication-head checks are separate from this prelaunch evidence.

All v1/v2/v3 results and v4 frozen sources remain unchanged. The eight tasks are the problem units; repeated attempts are not 16 independent tasks. No eval-opt treatment arm was run, no effect-size or superiority claim is supported, and the sample is a finite difficulty screen rather than a power calculation.

The next engineering recommendation is to align declared finding kinds with task-level obligation matching and test every allowed kind against supported witnesses before freezing another version. Further task authoring should target interacting constraints that produce genuine completed functional failures under the same limits. Those are recommendations only: this authorized screen ends with this report; no further benchmark is dispatched.
