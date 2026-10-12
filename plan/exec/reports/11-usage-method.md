REPORT 11-usage-method — Status DONE | Timestamped incomplete usage inventory

## Snapshot and scope

Snapshot window: 2026-10-12 22:32:22.751095–22:32:22.772124 UTC. This is a bounded inventory of retained run receipts, not final run usage or a billing statement. Calls were still in progress; totals must be recomputed after closeout. All files read were stable across this short capture; no new supervisor start receipt appeared during the capture.

The snapshot identifies 47 attempted native invocations: 41 supervised attempts plus six early direct calls. It contains 46 unique complete terminal results. `10-candidate-review` has a start receipt but no finish receipt and a zero-byte native output at this endpoint; its usage is unavailable and is excluded, not assigned zero. An open receipt does not by itself prove the process was still running.

Among the 40 finished supervised attempts, the recorded classifier states are 34 DONE and six PARTIAL. Across all 46 complete native outputs, 44 have native subtype success and two have error_max_turns. Native success does not imply a task or review was accepted: five PARTIAL supervised attempts have native success, but fail scope or report acceptance. The early direct calls do not acquire fabricated supervisor classifications.

## Counting method

1. Enumerate every `plan/logs/**/start.json`; pair it only with sibling `native.json` and `finish.json`. Count each start as one attempted invocation, regardless of final status. Include usage from failed/rejected attempts whenever a complete native result exists.
2. Include these known early direct result files once each: `00-review.json`, `00-01-review-r2.json`, `02-review-r1.json`, `01-high.json`, `01-xhigh.json`, and `01-turnlimit.json`. The first three were direct review calls; the last three were the Task 01 probes. Do not infer that result files prove process exit status where no independent exit receipt exists.
3. Hash each raw input and retain its relative path, size and SHA-256 privately. A candidate usage source must be a complete native JSON object with type result and a modelUsage mapping. An empty, incomplete or malformed native output remains unaccounted for.
4. Deduplicate byte-identical raw results and compare the native `(session_id, uuid, result_index)` identity. Conflicting bytes under one identity or repeated sessions require explicit reconciliation before cumulative totals can be trusted. This snapshot found zero duplicate result files, zero identity conflicts and zero repeated sessions.
5. Sum each complete result's `modelUsage` fields once, grouped by canonicalModel while retaining original model keys, provider and costBasis. Never sum copied modelUsage from finish receipts, summary files or reports. Do not add top-level usage, usage.iterations, thinkingTokens or total_cost_usd to the per-model token sums: these are overlapping or independently reported fields, not additional usage.
6. Retain requested CLI caps/effort from start receipts separately from native num_turns and observability. For direct high/xhigh Task 01 calls, use their summary solely as request/exit evidence, not as another usage source. Missing request records remain unavailable; do not reconstruct them from native counters.
7. Reconcile the sum of per-model costUSD against terminal total_cost_usd with a 1e-9 USD tolerance for binary-decimal serialization. No material discrepancy was found. These native amounts all state costBasis=list; they are list-price estimates, never demonstrated subscription charges or API invoices.
8. Re-read every captured input after aggregation to detect concurrent changes. This snapshot found none. Final closeout must make a new inventory in a fresh directory after every relevant call has ended, include any newly added direct calls explicitly, and report any remaining missing usage.

## Provisional native totals

| Field | Canonical Fable 5.1 | Rejected auxiliary Haiku 4.5 entry |
|---|---:|---:|
| Complete result entries | 46 | 1 |
| Input tokens, as modelUsage inputTokens | 15,420 | 1,670 |
| Output tokens | 934,517 | 63 |
| Cache-read input tokens | 24,181,851 | 0 |
| Cache-creation input tokens | 2,972,487 | 0 |
| Thinking tokens, separately reported; not added again | 383,729 | 0 |
| Native webSearchRequests | 0 | 0 |
| Native USD list-price estimate, rounded to six decimals | $112.375253 | $0.001985 |

The combined native list-price estimate is $112.377238. Actual subscription charges attributable to this run are unknown. Native per-model fields contain no missing token/cost field among the included entries. All included modelUsage entries report provider firstParty and costBasis list; those observations do not establish every transport, billing or account property beyond the receipts.

The sole auxiliary entry is raw key `claude-haiku-4-5-20251001`, canonicalModel `claude-haiku-4-5`, in rejected attempt `10-integration-review`. That attempt remains PARTIAL for native failure, nonzero exit, model identity and missing accepted review. Its tokens and estimated list cost are counted honestly, not silently removed because the attempt was rejected. Terminal output does not establish the origin of auxiliary use, so no routing, tool or compaction cause is inferred.

Native num_turns sum to 818 across the 46 complete outputs. This is a native counter total, not an API-request count, assistant-turn count or completed-task count. Among the 41 supervised starts, requested caps are: 3×1, 12×1, 15×2, 20×25, 25×7, 30×3, 35×1 and 45×1 (cap × attempts). Requested efforts are high for 28 and xhigh for 13 supervised attempts; direct probe summaries additionally record one high and one xhigh request. Effective effort is not exposed by terminal JSON. Fifteen complete supervised results numerically exceed their requested CLI cap in native num_turns; the counters have no established equivalence, so this alone does not prove enforcement failure. The supervisor independently enforces its external wall-clock/process limits and records the requested CLI cap.

Summed native duration_ms is 13,697,983 ms; summed duration_api_ms is 12,333,869 ms. These are overlapping per-invocation elapsed counters across parallel calls, not the run's wall-clock duration or a billing measure.

## Retention, reproducibility and unknowns

A private, read-only inventory helper and this endpoint's numeric records are retained under `plan/artifacts/11-usage-inventory/`. For recomputation, run its `inventory.py` with a fresh output-directory argument; it refuses to overwrite an existing snapshot. Extend the explicit direct-result roster if new non-supervised calls occur. Current hashes:

- `snapshot-01/summary.json`: `84b43e6191381171edeb29e0881a288b1134a63235605f85550942f17a325fbc`.
- `snapshot-01/receipt-manifest.json`: `3bf5b6c9c86ba934b4de62060eab776c7674cec74615acb0cac65d48c587494a`.
- `snapshot-01/attempts.json`: `aa8f8a77d644e111fa75e450c80c78f0d94c5b313958066d7a70985caf966d96`.

The private manifest enumerates each inspected raw receipt path/hash. The active empty file is recorded as an incomplete-output parse failure, not discarded or declared a failed model call. Later output must be counted from a new endpoint, never added as a delta to this snapshot without recomputing deduplication.

Astra orchestrator and Codex verification-subagent token/cost totals are unavailable from these Fable receipts. Account-wide usage-limit percentages cannot supply run-attributable totals and were not used. Pre-run planning consultations, activity outside the retained control-log scope and unrecorded external sessions are not included. This report asserts a complete count only of its explicit stable input roster, not complete vendor billing coverage. No credentials, model calls, product/settings/ref changes or existing evidence modifications were involved.
