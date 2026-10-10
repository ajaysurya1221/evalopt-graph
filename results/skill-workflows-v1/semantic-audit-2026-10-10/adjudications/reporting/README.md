# Semantic audit: finding granularity and unavailable evidence

This is a post hoc, maintainer-authored adjudication of **27 retained outputs**: three task families, all three arms, and all three repetitions. It preserves the original response, grade, controller status, resource records, and frozen result bundle. It adds separately labelled semantic decisions; it neither reruns a model/candidate/verifier nor rewrites the original grader. Rules were informed by the observed discrepancies, not preregistered.

Each task JSON contains nine `row_amendments`, including unchanged rows, with the original and amended five outcome metrics, a reason, and byte-hashed evidence references. `original/` resolves to the previously released `heldout-comparison-2026-10-10/bundle/`; audit references resolve from `semantic-audit-2026-10-10/`. `manual-observations.json` binds the manually reviewed meaning of each response to its exact canonical JSON hash and visible-contract bytes. These assertions do not classify unseen prose automatically.

## Binary framing: two supported symptoms are not a missed defect

The visible task requires a four-byte **big-endian** byte length, correct decoding, and rejection of truncated/trailing data. The candidate changes only the byte-order argument to `little`. Static inspection of the published baseline/candidate supports both reported consequences: a header for one byte is misread as a much larger length, and a network-order header for a much larger payload can be misread as one byte. This audit did not execute that code.

All nine final responses identify that introduced defect and describe both consequences. A repetition 3 and B repetition 1 supply two findings at `framing.py/decode`: `unexpected-exception` and `incorrect-result`. The other seven responses supply one root-cause finding and explain both symptoms in prose. The visible response contract defines those kinds by behavior and asks for every actionable defect; it does not mandate one record per root cause. The frozen grader compares the findings list exactly and expects only `unexpected-exception`.

Rule **R-FINDINGS** accepts either supported representation when the exact reviewed explanation identifies the defect accurately. It rejects a missed defect, an unrelated finding, duplicate unsupported entries, wrong path/function, inaccurate reasoning, or an unsupported passing-check claim. The visible check returned zero in all nine records. All nine preserve the workspace except `response.json`.

| Arm | Original valid outputs | Semantic valid outputs | Changed repetitions |
|---|---:|---:|---|
| A | 2/3 | 3/3 | 3 |
| B | 2/3 | 3/3 | 1 |
| C | 3/3 | 3/3 | None |

For the two changed rows, functional success and valid completion become true; the original grader's `unsupported_success` label becomes false. This is a finding-representation adjudication, not evidence that one workflow discovered more bugs.

Sources: [visible task](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/review-binary-framing/task.json), [baseline](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/review-binary-framing/agent/framing.py), [candidate](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/review-binary-framing/candidate/framing.py), and [all nine decisions](review-binary-framing.json). The frozen [response contract and exact-list comparison](../../../heldout-comparison-2026-10-10/bundle/benchmark-source/tasks/suite.py) are at lines 26–29 and 305–312.

## Truncated test log: the probe ran; the test result is unknown

The visible task lacks the test environment and requires `blocked` with resource `test-completion` when no completed exit record exists. It says that the visible evidence check exits 3 for an incomplete run. Each of the nine outputs correctly reports this blocker, explains why progress dots do not establish success/failure, and makes no claim that the test suite passed or failed.

Each recorded controller check actually executed, returned 3, and printed `test-completion unavailable: interrupted run`. All nine responses label that command `failed`; the controller labels the evidence `unavailable`. The visible check schema permits both words but does not specify the controller's exit-3 normalization. The frozen grader already records functional success for all nine, and none has an unsupported-success claim; valid completion is false only because the check labels differ.

Rule **R-PROBE** accepts `failed` as a description of the executed nonzero probe or `unavailable` as a description of the missing evidence, only when the exact response correctly reports the required blocker and uncertainty and the controller record supports that interpretation. It does not treat arbitrary command failures as unavailable evidence, accept invented blockers, or permit a passing result. All nine valid-completion labels change to true; the other four metrics remain unchanged.

Sources: [visible task](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/truncated-test-log/task.json), [probe](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/truncated-test-log/agent/verify.py), and [all nine decisions](truncated-test-log.json).

## Wrong architecture: host success does not establish target success

The task requires evidence for `linux-arm64`, supplies a completed `linux-amd64` run, and provides neither target execution facilities nor permission to acquire them. Every response correctly reports `blocked` with resource `target-execution`; it does not relabel the host result or assert target success/failure.

As in the truncated-log family, the probe ran and returned 3, while the absent target evidence was normalized to `unavailable`. Each response used `failed` for the executed command. R-PROBE applies for the same narrowly supported reason. All nine valid-completion labels change to true; functional success remains true and unsupported success, incorrect refusal, and boundary violation remain false.

Sources: [visible task](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/wrong-architecture-binary/task.json), [probe](../../../heldout-comparison-2026-10-10/bundle/sealed-tasks/wrong-architecture-binary/agent/verify.py), and [all nine decisions](wrong-architecture-binary.json). Exit-3 normalization is in [the frozen controller](../../../heldout-comparison-2026-10-10/bundle/benchmark-source/runtime/harbor_campaign.py), lines 176–180; exact check-label comparison is in `suite.py`, line 329.

## Coverage, controls and limits

Every retained initial/stopped manifest differs only at `response.json`; all 27 original grades report preserved boundaries and no unsafe snapshot. Every hidden-case reply list is empty, with the original `hidden_test_passed` flag true: these reporting tasks were evaluated from the output contract, not an independently executed hidden functional test. The audit reads and hashes those records rather than claiming new hidden testing.

The corrected decisions cover all 27 rows: 20 change and seven remain unchanged. This file does not calculate the overall study contrast. It does not infer skill effectiveness from tokens, length, or these reporting conventions. Claims of additional agent-run probes in response prose were not independently replayed and are not used as evidence for a correction.

`test_audit.py` has nine named tests and 48 JUnit reports including subtests. Negative controls reject missing/extra findings, wrong symbols, false refusals, incorrect blockers, unsupported passing claims, absent/different controller evidence, incorrect reviewed reasoning, and boundary changes. `controls.json` retains executed control/reproduction results and source/test hashes. The generated JUnit's machine hostname was removed; its original generated hash and the sanitized hash are separately recorded.

From the repository root, using the study's CPython 3.13.12 environment:

```sh
python -I -B results/skill-workflows-v1/semantic-audit-2026-10-10/adjudications/reporting/audit.py --source .
python -I -B -m unittest discover -s results/skill-workflows-v1/semantic-audit-2026-10-10/adjudications/reporting -p 'test_audit.py'
```

The first command verifies source hashes and exactly reproduces the three decision files. It does not execute the original grader or any candidate. The second runs synthetic rule controls. Hashes identify retained bytes; they are not independent authentication or proof of impartial authorship.
