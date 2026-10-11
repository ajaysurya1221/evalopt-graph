# Phase-bound evidence: reviewed offline package

The v3 measurement layer passed **559 tests and 236 reported subtests, with zero failures, errors or skips** in the final suite. These are finite offline controls, including synthetic Docker/Harbor trajectories. **No live model trial or workflow-performance result is included here.**

An agent now reports the controller observation it actually received, identified by its initial phase and content digest. The controller retains that observation, exact prompt and receipt, then records the stopped candidate's separate observation. Pure replay verifies both candidate identities, raw output hashes, registered verifier image, limits and prompt correspondence. A truthful initial report remains supported when the later check changes; it cannot establish final correctness or acceptance.

The [protocol](../../../bench/harbor/skill-workflows-v3/PROTOCOL.md) limits the next study to eight fresh tasks, two attempts each, using upstream arm B. The [portable v3 skill](../../../skills/eval-opt-v3/SKILL.md) is an offline deliverable and is not injected into B. Either difficulty-screen outcome ends with a report; it does not authorize a larger benchmark or an upgrade claim.

## Retained evidence

| Evidence | Observed result | Scope |
|---|---:|---|
| Final complete suite | 559 tests + 236 reported subtests; 0 skips | Current held v3 source, including enabled synthetic Docker controls |
| Focused phase/capture controls | 141 tests; 0 skips | Includes nine actual Docker/Harbor controls; overlaps the final suite |
| Full campaign replay controls | 2 tests; 0 skips | Synthetic native sessions with real Harbor, supervisor, capture, accounting, store and replay |
| Authored task QA | 94 controls over 113 registered cases in 8 tasks | Oracle/reference, mutants, clean reviews, claim separation and boundary controls |
| Preservation | 9,145 baseline files | Original bytes and Git modes preserved at `eb181fa47a2b44c3363034038c288ba821f64d7d` |
| Existing public reports | 4 successful reproductions | v1 held-out, transfer, semantic audit and v2 development revision |

The run groups overlap and must not be added together. The final JUnit file reports 795 total test/subtest results but contains 559 individual `testcase` elements. [Controls](controls.json) publishes those case identities and outcomes and separately records the 236 passed subtests; their individual names are absent from the retained JUnit file.

[Authored controls](task-controls.json) retain five unchanged task groups from the earlier Docker run and three corrected groups rerun after review. All eight task-source digests match the final manifest. This is **not an assertion that all authored Docker controls ran under one runtime version**; the final complete suite separately verifies the current runtime. Before any model outcomes, review repaired a calendar oracle/reference edge case and strengthened two incomplete feature baselines. Empirical task difficulty remains unmeasured.

[Separated AI reviews](reviews.json) cover task authoring, phase capture, semantic reporting and orchestration. A later review caught an inherited coupling between malformed check reports and review functionality; the retained addendum verifies its correction. These are maintainer-run, separate AI author/reviewer roles, not independent human authorship or independent live replication.

[Compatibility evidence](compatibility.json) preserves the four old public reports. A separate legacy kernel test run passed with eight explicit prerequisite skips; it is not represented as a zero-skip group. Existing v1/v2 grades and analyses are unchanged.

## Reproduce the published correspondence

From the repository root, with Python 3.13:

```sh
python3 -I -B results/skill-workflows-v3/offline-package-2026-10-11/reproduce.py
```

This standard-library script checks packet checksums, all 355 listed source files, every preserved baseline file, typed offline results, authored task digests and review-to-source correspondence. It does not import the harness, execute candidate/test code, call Docker or models, or rerun the private controls. It reports retained-evidence consistency; hashes alone do not authenticate a producer.

[Source identities](sources.json), the complete [preservation inventory](preservation.json) and [packet checksums](checksums.json) are retained. Raw private logs and JUnit files remain private; their hashes bind the sanitized projections. Hostnames, machine paths, credentials and native session identities are excluded. The package establishes finite engineering conformance, not task hardness, efficacy, superiority, generality or production safety.
