# Development pilot: 36 trials

All three arms recorded **12 valid completions out of 12** under the original
frozen grader. These are descriptive results from 12 development tasks with one
attempt per arm. They do not establish a workflow advantage. The 432-trial
held-out comparison and 72-trial transfer stage have no results in this package.

| Arm | Workflow | Original valid completion |
| --- | --- | --- |
| A | Common tools, no workflow bundle | 12/12 |
| B | Pinned Matt Pocock workflow bundle | 12/12 |
| C | Frozen eval-opt workflow bundle | 12/12 |

The [original outcome records](pilot/pilot/reports/outcomes.json) and
[analysis](pilot/pilot/reports/analysis.json) preserve every scheduled pilot trial.
The [acceptance-policy report](pilot/pilot/reports/kernel.json) replays 108 U/M/G
decisions on the same 36 stopped outputs. All outputs received valid grades under
the original verifier, so this pilot has no graded-incorrect outputs with which
to estimate incorrect acceptance. Kernel decisions
are separate from workflow outcomes.

A parser change in the current grader is a **scoring change**. It rejects
nonfinite JSON that the original parser could accept when duplicate keys replaced
the nonfinite value. See the [grading amendment](../../../bench/harbor/skill-workflows-v1/GRADING_AMENDMENT.md).
The isolated regrade of all **36 stopped outputs completed with zero changed
grades**. Original grades and policy decisions remain unchanged. The
[regrade evidence](regrade/evidence.json) and [receipt](regrade-receipt.json)
report current-grader results separately. Each stopped output ran in a fresh,
network-disabled verifier container using the pinned image; no additional model
calls or agent trials were made. Public replay checks retained verifier replies
without executing candidate code.

[Amended accounting](pilot/resource-report.json) retains 34 complete attempts and
two partial attempts, both in arm A. Partial values are observed lower bounds.
Complete totals and partial-only components are shown separately; combined lower
bounds already include both. No efficiency comparison or dollar cost is claimed.
The [accounting claims](pilot/CLAIMS.md) explain the limits of public counter replay.

[Development overhead](overhead/overhead-ledger.json) is separate: three complete
capability probes record 223,938 input tokens, 1,017 output tokens, 17 completed
response records, 10 tool calls, and 73.168 summed parent wall seconds. Probe 04's
readiness mirror is counted once. Probe 02 has unknown dispatch and consumption;
one [earlier pilot attempt](original-pilot-overhead/README.md) has unavailable
consumption. That archived attempt is the same event described in the overhead
ledger and is not added again. Unknown usage is not zero. Engineering-assistant
usage and unmeasured setup or verification work are outside these figures.

From the repository root, using **CPython 3.13.12** and the trusted checkout whose
benchmark and kernel hashes match the retained registrations:

```sh
python3.13 -I -B results/skill-workflows-v1/development-pilot-2026-10-09/reproduce.py --source .
```

This standard-library replay checks `CHECKSUMS.json`, all outer file identities,
the original/amended pilot bundles, overhead
arithmetic without duplicate events, and the regrade receipt and supplied hidden
replies. It imports only the explicitly selected repository code with a fresh
bytecode cache. It makes no network or model calls and executes no stopped
candidate code or Docker containers.

The records establish supplied maintainer-run evidence and deterministic replay.
Hashes identify retained bytes; they do not authenticate the producer. Public
replay does not recover missing native telemetry or establish independent agent
replication. No upload is performed by the replay command.
