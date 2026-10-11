# Small difficulty screen: completed, difficulty not validated

All **16 registered upstream trials finished**. The eight ordinary repair and implementation attempts all passed the retained functional checks, so the screen did not demonstrate the ordinary-task difficulty required by its preregistered gate. **No larger benchmark was started or authorized.**

The reporting diagnosis found a separate measurement defect: the prompt omitted response fields that the grader required. All 16 responses accurately repeated the supplied initial check, but the frozen grader rejected their response envelopes. This also prevented semantic evaluation of four review responses. Those four failures are **not demonstrated review misses**. See the [separate retained-evidence diagnosis](../reporting-diagnosis-2026-10-11/README.md).

## Original results and their limits

The [original report](report.json), [per-trial inputs](inputs.json), [case and phase evidence](case-evidence.json), and frozen source remain unchanged. The diagnosis does not replace grades or assign counterfactual live outcomes.

| Measure | Frozen result | Interpretation after diagnosis |
|---|---:|---|
| Scheduled / finalized / retained attempts | 16 / 16 / 16 | All original rows accounted for; no retries or missing attempts |
| Functional success | 12/16 | Four review failures were caused by an undeclared response-envelope gate |
| Ordinary repair and implementation success | 8/8 | No ordinary failure headroom; larger-study gate fails |
| Valid completion / supported reporting | 0/16 / 0/16 | Required envelope fields were not declared; not evidence of false check reporting |
| Responses matching the supplied initial check | 16/16 | Separately audited phase correspondence, not a replacement completion grade |
| Timeouts / observed boundary violations | 0 / 0 | Retained execution and boundary records reconcile |
| Complete usage records | 16/16 | Token/call accounting complete; agent-only wall time unavailable |

The frozen `unsupported_success=false` values also require caution: the grader defaults this field to false when the response envelope is invalid. They do not independently establish absence of unsupported completion claims. The raw report records no task disputes; the separately published prompt/grader discrepancy is a post-run measurement diagnosis, not a mutation of that field.

| Task | Original functional successes | Scope |
|---|---:|---|
| Atomic migration batches | 2/2 | Ordinary repair |
| Calendar override expansion | 2/2 | Ordinary repair |
| Cyclic module exports | 2/2 | Ordinary implementation |
| Incremental build invalidation | 2/2 | Ordinary implementation |
| Media range precedence | 0/2 | Review semantics skipped by the envelope gate |
| Replica placement quorums | 0/2 | Review semantics skipped by the envelope gate |
| Snapshot delta compatibility | 2/2 | Constraint preservation |
| Stale vector distance fixture | 2/2 | Unavailable or misleading evidence |

All 18 retained review witnesses were supported and together covered the published obligations. This is a finite retained-record audit, without candidate re-execution. It does not turn the frozen four failures into newly observed successful trials. The raw gate remains `difficulty_not_validated`; its ordinary-failure criterion fails even before accounting for the review-label defect.

## Conditions and measured resources

This fixed development screen used eight fresh tasks and two attempts each, with only the complete upstream B bundle pinned to `b0618bc436ad893b3c5e84e55fba86586d34a404`. Conditions were Codex 0.154.0, Harbor 0.24.0, `gpt-6-astra` / `ultra`, existing subscription authentication, a 600-second agent limit, one CPU, 2 GiB RAM, sequential trials, and a parent with at most two concurrent children at delegation depth one. The controller confirmed the registered runtime identities. The portable eval-opt v3 skill was **not** injected into this screen.

The frozen [registration](../difficulty-registration-2026-10-11/registration.json) and [protocol](../../../bench/harbor/skill-workflows-v3/PROTOCOL.md) retain the complete task order, gates and conditions. Registration digest: `f19253f9e47586e6568c37b112a584a1479ecdff4b8e69d1aafa54208d17b569`.

| Resource | Retained total | Scope |
|---|---:|---|
| Input tokens | 10,085,409 | Parent and child usage without copied-history double counting |
| Output tokens | 157,844 | Same accounting scope |
| Model calls | 426 | All 16 retained attempts |
| Tool calls | 373 | All 16 retained attempts |
| Controller elapsed seconds | 3,328.69 | Includes setup, agent execution, capture and visible/hidden verification |

Agent-only wall time is unavailable in all 16 usage records. Controller elapsed time must not be relabeled as model or agent time. This screen is neither token-matched nor an efficiency comparison; no dollar costs are inferred from subscription consumption.

## Acceptance policies are secondary and instrument-limited

The retained U/M/G comparison accepts 16/16 under U and rejects 16/16 under M and G. The raw labels count all U acceptances as incorrect because original valid completion is false throughout. Since the undeclared response contract affects those labels, this is not evidence that universal rejection improves reliability. Coverage is zero for M and G. These are stopped-output decisions, not a live comparison of workflow behavior.

## Evidence and reproduction

An independent AI reviewer checked all **5,771 retained campaign files**, 2,921 directory identities, 16 final seals, 16 owned-network releases and 214 verifier-container closures. Original evidence bytes remained unchanged across endpoint auditing and extraction. A second frozen native replay reproduced the full report byte-for-byte. [Endpoint summary](endpoint-summary.json) and [review scope](review-scope.json) contain the corresponding digests and limits.

Using CPython **3.13.12**, run from a fresh repository checkout:

```sh
python -I -B results/skill-workflows-v3/difficulty-2026-10-11/reproduce.py \
  --repo . --bundle results/skill-workflows-v3/difficulty-2026-10-11
python -I -B results/skill-workflows-v3/reporting-diagnosis-2026-10-11/reproduce.py
python -I -B results/skill-workflows-v3/response-contract-correction-2026-10-11/apply_verify.py \
  --repo "$(pwd -P)" --output-dir "$(pwd -P)/response-contract-offline-check"
```

The first command checks the packet roster and checksums, imports only seven hash-pinned pure modules from temporary copies, and reconstructs the original report from retained projections. The diagnosis separately reproduces its bounded interpretation. The prospective correction is applied only to a fresh temporary source copy for offline controls; choose a new output path if the example already exists. None of these commands invokes a candidate, model or live verifier.

| Claim | Evidence | Limit |
|---|---|---|
| All 16 original rows finalized | `inputs.json`, `endpoint-summary.json` | Retained controller custody and independent AI review |
| Frozen report reproduces | `reproduce.py`, `receipt.json`, `report.json` | Projection consistency, not independent live replication |
| Initial checks were accurately quoted | Separate diagnosis and per-row projections | Does not establish full task completion |
| Difficulty is not validated | Registered gate; ordinary 8/8 results | Small development screen, not an estimate of general capability |
| Response declaration has an offline repair | Separate exact-base correction artifact | Prospective only; no repaired live results |

An initial closeout replay command incorrectly used a relative output path and was rejected by the CLI's absolute-path precondition. The retained failure was followed by an unchanged-source replay with an absolute output path; no campaign data or grading was repaired. The private original failure and subsequent replay logs are retained.

This is a maintainer-run study with separated AI authoring and review roles. Public artifacts omit credentials, native session identifiers, host paths and raw conversation histories. Hashes establish correspondence under that custody; they do not authenticate authorship. All v1/v2 results remain intact. **No workflow superiority, eval-opt efficacy, fresh replication or upgrade is established.**
