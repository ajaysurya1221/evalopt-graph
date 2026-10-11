# Eval-opt v2 development: complete, not ready for held-out evaluation

**All 48 revision-1 trials finished. Every arm scored 11/12 valid completion and 12/12 functional success. The registered difficulty gate failed, so this study ends as `development_not_ready`.** No held-out trial or second development revision is admitted. These development results do not establish an eval-opt upgrade.

| Arm | Configuration | Valid completion | Functional success | Unknown outcomes |
|---|---|---:|---:|---:|
| A | No workflow bundle | 11/12 | 12/12 | 0 |
| B | Complete pinned upstream bundle | 11/12 | 12/12 | 0 |
| C | Full eval-opt v2 | 11/12 | 12/12 | 0 |
| D | C with its evidence/dispute procedure mechanically removed | 11/12 | 12/12 | 0 |

The frozen [report](report.json) and [per-trial inputs](inputs.json) retain every scheduled row and attempt. The development gate required B to complete **4–10 of 12 tasks**, including both success and failure on the four ordinary repair/implementation tasks. B completed **11/12 overall and 4/4 ordinary tasks**. This checks difficulty range; it is not a power calculation. There is one attempt per task/arm, so all-three-attempt consistency and confirmatory confidence intervals are not available.

## What the shared failure means

Every arm's only invalid completion is `signed-hex-offset-contract`. All four candidates passed **9/9 functional cases**. The frozen claim check marked their structured `checks` record unsupported: it reported exit code **0**, while the controller's post-stop visible check observed **1**.

There is a measurement limitation here. The initial controller record supplied with the task said exit **0**, and the visible instructions told agents to preserve the controller-provided check record when available. Separate review of the retained responses found that C and D explicitly disclosed the legacy check's exit **1** in free text while explaining that their structured fields preserved the supplied record. The frozen grader compared those fields with the post-stop observation. Calling this simply a failure to notice or disclose the failed check would misrepresent the evidence.

We preserve the four frozen failures and the `unsupported_success` labels. This packet makes no corrected-grade claim and does not automatically turn the ambiguity into a contract dispute. The [endpoint summary](endpoint-summary.json) records the initial, reported and post-stop exits, separate-review disclosure flags, and original record hashes; [case evidence](case-evidence.json) keeps structured agent claims separate from controller observations. The free-text disclosure flags are separate maintainer-reviewed annotations linked to private-source hashes; the public replayer cannot independently verify omitted prose. A later adjudication would require a separately versioned analysis. Even removing this ambiguity would not supply the missing ordinary-task difficulty range.

The frozen report records no incorrect refusals, boundary violations, unknown task outcomes or contract disputes. Those are finite observations in this development suite, not general guarantees.

## What was captured

[case-evidence.json](case-evidence.json) joins every trial to its frozen case roster and includes **224 retained callable case results**, all passing, and **16 retained review-witness records**. Each projection separates execution, semantic evidence availability, completion, capture, native lifecycle, container boundary and accounting. It references raw records by SHA-256; agent text, witness inputs, command text, native session identities and credentials are omitted.

The review tasks also have **188 registered reference-case entries across the four arms**. The frozen review verifier executes submitted witnesses, not the full reference roster. These entries are explicitly labeled `not_executed_by_review_contract`, with `source=derived_roster_join` and null execution fields. They are neither executed cases nor native `not_run` observations. Two clean review tasks have no submitted witnesses. The blocker-report task has no callable case roster. [project_evidence.py](project_evidence.py) documents and implements this bounded projection; it does not independently grade candidate code.

The controller retained 48 finalized attempts with no retries in this round. Endpoint review verified **9,406 campaign files**, **8,790 retained artifact hashes**, all 48 owned-network release chains, and confirmed capture, case boundaries, provenance and required lifecycle constraints. Forty attempt usage records were complete; eight were partial because retained native usage contained aborted turns. Partial usage did not become invented exact totals. The [endpoint summary](endpoint-summary.json), [receipt](receipt.json) and [review](review.json) distinguish retained-record correspondence from producer authentication.

## Resources and secondary acceptance policies

The totals below are the recorded lower bounds. A has complete totals; B/C/D do not. All four arms lack usable agent-only timing, and no efficiency or dollar-cost claim is made.

| Arm | Complete / partial attempt accounting | Input tokens | Output tokens | Model calls | Tool calls |
|---|---:|---:|---:|---:|---:|
| A | 12 / 0 | 2,150,540 | 34,372 | 144 | 119 |
| B | 9 / 3 | 4,962,436 | 68,048 | 231 | 198 |
| C | 9 / 3 | 3,012,292 | 48,763 | 163 | 141 |
| D | 10 / 2 | 2,649,611 | 43,644 | 145 | 123 |

The summed controller duration is **5,317.116108501941 seconds** over 48 attempts. It includes setup, agent work, stopped-file capture, visible checks and hidden verification. It is not agent-only time or total elapsed wall time including operator pauses.

U/M/G were applied to the same stopped outputs. These are secondary acceptance decisions, not new model trials or evidence that the kernel changed earlier agent behavior. Their error labels inherit the frozen completion rule and its disclosed check-record ambiguity.

| Policy | Accepted / 48 | Approval coverage | Incorrect acceptance | False rejection | Abstention | Artifact failures |
|---|---:|---:|---:|---:|---:|---:|
| U — accept every stopped output | 48 | 100% | 4 | 0 | 0 | 0 |
| M — minimal visible-evidence policy | 40 | 83.33% | 0 | 4 | 0 | 0 |
| G — frozen evalopt-graph policy | 40 | 83.33% | 0 | 0 | 4 | 0 |

## Registration, preservation and reproduction

This is the single complete development revision after the [original round stopped](../development-round-zero-stopped-2026-10-11/README.md) with 3 finalized, 1 unfinalized and 44 unstarted rows. Those original outcomes remain separate; none was imported into this round. The [prospective repair controls](../development-revision-1-offline-2026-10-11/README.md) and [revision registration](../development-revision-1-registration-2026-10-11/README.md) describe the owned-network repair and unchanged tasks, skills, model, grader, parser, analysis and schedule.

The execution source was commit `0280860299799aaf2bf650cebca4a379b71c6bc4`. The registration payload pin is `d792728a37e4d1725f8d9d68b5a0bea9ab9bdeb86942afe53eddb68e370cfd62`. Actual runtime review confirmed Codex **0.154.0**, **gpt-6-astra**, **ultra**; Harbor **0.24.0**, subscription authentication and the registered 600-second/one-CPU/2-GB limits were retained. There was no model substitution or API-billing fallback. The 990-file original-round seal and the 8,852-file v1 preservation check passed at closeout.

Use **CPython 3.13.12**, a fresh checkout of this publication commit, and `-I -B`. No pip packages or private campaign are required for public arithmetic reproduction:

```sh
python3.13 -I -B results/skill-workflows-v2/development-revision-1-2026-10-11/reproduce.py \
  --bundle results/skill-workflows-v2/development-revision-1-2026-10-11 \
  --repo .
```

The command verifies the flat public file inventory, hashes seven pure analysis modules and the registration, and reconstructs the full frozen report from sanitized inputs. It checks canonical typed equality and exact registered-order timing arithmetic. [arithmetic-review.json](arithmetic-review.json) records 18 synthetic controls plus separate nine-scenario reducer parity review. The evidence projector separately passed 14 synthetic tests and independent negative probes.

This is public arithmetic reproduction. Separate maintainer-side review replayed native evidence and checked raw-to-public correspondence; it is not independent human authorship, cryptographic producer authentication, public native-history replay, a new live-model replication or unrestricted review judging. Raw native histories and candidate response text remain private. All public bytes are listed in [checksums.json](checksums.json).

| Claim | Inspectable evidence | Limit |
|---|---|---|
| 48 finalized rows, four equal 11/12 scores, failed admission gate | [report.json](report.json), [inputs.json](inputs.json), [reproduce.py](reproduce.py) | Development only; no superiority claim |
| Every case roster is represented and review references are distinguished | [case-evidence.json](case-evidence.json), [project_evidence.py](project_evidence.py) | Reference cases were not all executed; no public candidate regrading |
| Four structured-check mismatches include an initial/post-stop ambiguity | [endpoint-summary.json](endpoint-summary.json), [case-evidence.json](case-evidence.json) | Frozen grades retained; free-text findings are separately reviewed projections |
| Accounting remains complete/partial per attempt | [inputs.json](inputs.json), [report.json](report.json) | Incomplete totals are lower bounds; no efficiency conclusion |
| Existing compatibility and v2 controls passed unchanged source | [push run](https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38120016270), [PR run attempt 1](https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38120018434/attempts/1), [PR run attempt 2](https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38120018434/attempts/2) | PR attempt 1 had a transient v1 Git fixture error; only the failed job was rerun on unchanged source. Private downloaded logs are not public artifacts |
| Endpoint and public projection received separate review | [receipt.json](receipt.json), [review.json](review.json), [arithmetic-review.json](arithmetic-review.json) | Separated AI roles in a maintainer-run study |

The skill and measurement implementation are available for review. This experiment's stopping rule leaves harder-task validation and any claim of benefit unestablished.
