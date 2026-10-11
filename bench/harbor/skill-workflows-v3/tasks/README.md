# Fresh difficulty screen tasks

Eight independently authored development problems for a B-only screen: two ordinary repairs, two bounded implementations and one problem in each remaining category. Each task has two scheduled model attempts; this task bundle does not dispatch them or establish that the suite is difficult enough.

All tasks are new in v3. No previous task, oracle, held-out asset or model score was used as an input to `author.py`. The author and reviewers are separate AI roles in a maintainer-run study, not independent human authorship.

| Task | Category | Callable/reference cases | Interacting source modules | Main controls |
|---|---|---:|---:|---|
| atomic-migration-batches | Ordinary repair | 15 | 3 | Transaction rollback, all dependencies, rename position, committed-ID idempotence |
| calendar-override-expansion | Ordinary repair | 18 | 4 | Replacement before filtering, cancellation/count identities, offset gaps and overlaps, supported-range re-resolution |
| cyclic-module-exports | Bounded implementation | 14 | 3 | Grounded cycles, alias chains, origin deduplication, ambiguity and explicit shadowing |
| incremental-build-invalidation | Bounded implementation | 14 | 3 | Normal/order-only edges, unchanged outputs, failure propagation, selected closure |
| media-range-precedence | Committed review | 12 | 3 | Specificity before quality, zero exclusions, parameter matching, clean review |
| replica-placement-quorums | Mixed review | 12 | 5 in final workspace | Eligibility, physical-node deduplication, diversity, quorum, clean review |
| snapshot-delta-compatibility | Constraint preservation | 16 | 4 | Frozen legacy codec, nested copies, exact bounds, missing/cyclic references |
| stale-vector-distance-fixture | Evidence disagreement | 12 | 4 | Current weighted metric, tag intersection, deterministic ties, truthful phase-bound reporting |

The implementation baselines are deliberately incomplete legacy behavior: the module linker has only one-layer star propagation, without alias or explicit-shadowing support; the build executor always requests work and lacks incremental, restat and failure-propagation rules. Completing them requires implementing the interacting published semantics. Static review also added calendar regressions for a shifted civil time outside the supported UTC range and repeated gap resolution before any model run.

Every implementation `oracle/` is a complete correct source snapshot. Its expected results come from a separately structured `reference.py`, kept outside every agent snapshot. QA executes both independently in fresh candidate processes, with expected results retained by the controller. Incorrect snapshots exercise relevant behavioral failures; arguments must remain unchanged. `verify.py` is a small frozen smoke check and is explicitly not the full contract.

Review tasks retain the correct `baseline/`, the changed `agent/`, and a validated `clean/` control. Every finite witness-domain request is visible in `SPEC.md`, while its expected result remains outside the agent workspace. QA executes every baseline and clean case before treating an empty clean review as correct. Introduced defects have bounded witness/location mappings; missed defects, fabricated findings and misplaced findings fail, while duplicate supported consequences remain neutral. The mixed review has actual committed, staged, unstaged and untracked layers.

The vector task openly states that its frozen visible fixture checks obsolete behavior. Its correct implementation passes functional cases while the post-stop visible check fails. The initial observation and post-stop observation have distinct content-bound identities. QA verifies that truthful reporting of the supplied initial observation remains valid; a wrong claimed result still fails reporting independently of functional success. Neither that stale fixture nor a reporting disagreement supplies ordinary functional difficulty headroom.

Run all trusted authored-fixture controls without a model:

```sh
.venv/bin/python -I -B bench/harbor/skill-workflows-v3/tasks/qa.py --stage difficulty
.venv/bin/python -I -B -m pytest bench/harbor/skill-workflows-v3/tests/test_fresh_tasks.py
```

The default QA runner uses a fresh Python process for each callable and a disposable copy for each visible check. It is intended only for these trusted authored fixtures and does not claim hostile-code containment. `run_task(..., invoke=...)` accepts the separately supervised Docker verifier for production-path containment controls. Expected values never enter a candidate invocation.

Task content can be regenerated before freezing with `author.py`, using the repository's pinned development environment (including Ruff for deterministic import ordering and formatting). Never run this generator against a frozen campaign. The task manifest and campaign registration bind the final authored bytes. Any defect discovered after a model screen must be preserved and corrected in a separately versioned study, not repaired silently inside the screen.
