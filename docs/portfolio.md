# Portfolio index

One index of the four independent domain projects maintained alongside evalopt, and the status of
evalopt itself. Each description is paraphrased from the project's own README at the linked commit,
checked on 2026-10-12 UTC for the [migration map](migration.md); the source rows are keys `ACTSEAL`,
`DORIAN`, `FSCOUT` and `ARCI` in [migration-sources.md](migration-sources.md). The projects are
independent of evalopt and of each other: none depends on evalopt, none imports it, none is a
successor, conformance target or drop-in for it, and no adoption, performance or superiority claim is
made here. Each project's own README, contracts and limits govern; this page adds no package, import
or shared runtime and preserves existing attribution.

## Four jobs

| Job | Project | What it does, in its own terms | Limits, in its own terms |
| --- | --- | --- | --- |
| Action-policy qualification | [Actseal](https://github.com/ajaysurya1221/actseal) ([README at `111afb3`](https://github.com/ajaysurya1221/actseal/blob/111afb3cf0dbab94e7bdf7917e800ba6faaeac0b/README.md)) | Tests a model's action policy under a frozen policy against recorded evaluation evidence and replays that evidence offline; the application owns execution. | Replay checks consistency; it does not authenticate responses or prove label truth. Its NOTICE names evalopt's public design as an influence and includes no evalopt source. |
| Code-claim warrants | [Dorian](https://github.com/ajaysurya1221/dorian) ([README at `eeb1937`, tag `v1.4.1`](https://github.com/ajaysurya1221/dorian/blob/eeb193792fac8a66b18f5222287a8fcf336dda08/README.md)) | Turns explicit code claims into checks sealed beside the code, re-runs affected checks when sources change and revokes the warrant when a load-bearing check fails. | A claim is only as strong as its checker. Dorian does not mention evalopt. |
| PR scope and native-control compilation | [Frontier Scout](https://github.com/ajaysurya1221/frontier-scout) ([README at `e34d4a6`](https://github.com/ajaysurya1221/frontier-scout/blob/e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c/README.md)) | Checks a diff against the base commit's scope policy and compiles the same policy into Claude Code permissions and hooks. | A research preview; unsigned receipts cannot authenticate approval. Frontier Scout does not mention evalopt. |
| Preregistered stochastic regression | [ARCI](https://github.com/ajaysurya1221/agent-reliability-ci) ([README at `a5adc83`](https://github.com/ajaysurya1221/agent-reliability-ci/blob/a5adc834f74f5546fa3585b4ce6adfc96e2c37a3/README.md), [NOTICE](https://github.com/ajaysurya1221/agent-reliability-ci/blob/a5adc834f74f5546fa3585b4ce6adfc96e2c37a3/NOTICE)) | Freezes a repeated experiment, gates a change on relative non-inferiority and exports a replayable failure. | `PASS` means relative non-inferiority, not absolute reliability. `src/arci/hashing.py` adapts evalopt's canonical JSON hashing helpers from `attestation.py` under MIT with attribution, and its NOTICE records the self-sealing decision pattern from `kernel.py`; both are attributed adaptation inside ARCI's frozen manifest, not a dependency. No PyPI package, per its README. |

The jobs appear in the order of the [migration map's](migration.md#where-each-job-goes) route table,
which also routes general policy evaluation, provenance verification and native merge enforcement to
external tools. This index adds no route.

## Ended standalone experiments

| Project | Status |
| --- | --- |
| evalopt (`evalopt-graph`, import `evalopt_graph`) | Standalone feature development has ended ([archive decision](decisions/archive-standalone.md)). The repository preserves the acceptance kernel with its ten stable exports and the research record: the v1 to v4 studies, the benchmark branches kept out of main, frozen sources, tags, release assets and attribution. Where each evalopt concept goes is in the [migration map](migration.md); existing records remain subject to the version that produced them. Archival of the repository is a separate human action that this page does not claim has happened. The final deprecation release is tracked on the public [releases page](https://github.com/ajaysurya1221/evalopt-graph/releases) and is not asserted here. |

## What this index is not

- Not a dependency declaration. The wind-down independence audit found no package dependency and no
  runtime import of evalopt in any of the four projects; the only evalopt-derived code is ARCI's
  attributed adaptation, which stays attributed as adaptation.
- Not a successor, conformance, endorsement or adoption statement for any project.
- Not a substitute for each project's own documentation, which governs its semantics and limits.
