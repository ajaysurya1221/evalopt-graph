# Eval-opt v2 offline measurement package

**477 tests and 268 subtests passed, with zero failures or skips in the required local v2 controls.** This package contains no live model trials and establishes no performance improvement over v1, upstream, or the ablation.

The [portable skill](../../../skills/eval-opt-v2/SKILL.md), [controller](../../../bench/harbor/skill-workflows-v2/README.md) and [prospective protocol](../../../bench/harbor/skill-workflows-v2/PROTOCOL.md) are separate from v1. All 8,852 files from `2deb53feb2bf20061a754b80ff93fccafeac5af7` retain their original bytes and executable modes. No stable kernel API changed.

## Evidence

| Claim | Retained evidence | Limit |
|---|---|---|
| Five audited grading regressions and the new semantic/capture controls pass | [Source-bound control receipt](controls.json) | Finite authored controls, not unrestricted review judging or agent performance. |
| Twelve fresh development tasks have passing oracle and relevant incorrect controls | [Task controls](development-task-controls.json) | Difficulty is unmeasured until the development gate runs. |
| Real Docker/Harbor capture and complete-row replay work in the tested cases | [Independent review](review.md) and [case roster](controls.json) | Native telemetry is synthetic in these offline integration controls; no model was called. |
| V1 reports and stable installed API remain reproducible | [Compatibility receipt](compatibility.json) and [wheel check](wheel.json) | Original optional legacy skips are listed separately; no new live replication. |
| C/D isolate the instructional procedure | [Ablation implementation](../../../bench/harbor/skill-workflows-v2/evalopt_v2/ablation.py) and its retained controls | Both arms receive the same repaired harness and shared response contract. |

The [separate AI review](review.json) records its exact source coverage and checks. Authoring and review roles were separated within a maintainer-run study. This is neither independent human authorship nor independent replication. Earlier review findings were repaired before this receipt; their repairs include response-envelope headroom, partial evidence semantics, dispute propagation, immutable retry admission and source-bound replay.

## Reproduce

From this exact repository revision, run the standard-library receipt check in a fresh environment:

```sh
python3.13 -I -B results/skill-workflows-v2/offline-package-2026-10-11/reproduce.py
```

It verifies [artifact checksums](checksums.json), reviewed/tested source identities, the projected case roster and summary. It executes no candidate code, tests, models or Docker commands. Digests identify retained bytes; they do not authenticate a producer or prove a past test run. Raw local JUnit includes host metadata and is retained privately; the public receipt contains only case names and outcomes, with hashes of the raw files.

To rerun controls, follow the [controller README](../../../bench/harbor/skill-workflows-v2/README.md). The default run deliberately skips explicitly opted-in Docker/upstream controls. The zero-skip run for this receipt supplied `EVALOPT_V2_UPSTREAM_CONTROL`, `EVALOPT_V2_AGENT_CONTROL_IMAGE` and `EVALOPT_V2_DOCKER_CONTROL_IMAGE` using the pinned local inputs recorded in `controls.json`. No image pulls or model calls occur in that test selection.

## Next admission

The first live stage is 48 development trials across A/B/C/D. It requires the source-bound offline admission receipt, exact runtime and subscription availability. Held-out evaluation additionally requires the registered development difficulty gate; offline success cannot waive it. The primary live contrast is C minus D. External transfer is deferred. The sealed held-out tasks are not published in this offline package.
