# Development revision 1: network and admission repair controls

**586 tests and 268 subtests passed, with zero failures or skips.**

This package supports the one permitted complete development revision after
[round 0 stopped during setup](../development-round-zero-stopped-2026-10-11/README.md).
It does not establish workflow performance or authorize bypassing a live gate.

The prospective controller allocates one explicitly owned bridge network per
trial from `/28` subnets in `10.254.0.0/16`. It checks existing allocations and
configured automatic pools, durably records intent before creation, and validates
exact container attachment before authentication upload. After confirmed stop
and durable capture it releases only that new network, preserving the stopped
container and captured evidence. Ambiguous identity, endpoint or release state
stops admission. The verifier remains networkless; historical networks and
containers are untouched.

Allowlisted runtime diagnostics now retain the failed phase and classified
Docker cause without raw credential-bearing output. A typed `stopped_incomplete`
predecessor receipt preserves round 0's original registration, report and
finalized/unfinalized/unstarted partition. It keeps the original gate's recorded
count at three. Reconciling 48 scheduled rows is not reported as 48 executions.
Revision 1 runs all 48 rows under a separate registration and consumes the sole
revision allowance. The original campaign cannot resume or retry its fourth row.

The skill, tasks, semantic grading, parser, accounting, statistical analysis,
model/effort, images and resource limits are unchanged. The development gate
still requires all 48 revised outcomes resolved, all controls passing, B completing
4–10 tasks, and ordinary repair/implementation successes and failures. A second
nonready round ends the study without held-out execution.

## Evidence and reproduction

- [Source-bound controls](controls.json) give each test identity and outcome.
- [Separate AI review](review.json) names the exact reviewed source hashes.
- [Authored task controls](task-controls.json) retain the unchanged 12-task checks.
- [Stopped-round publication review](round-zero-review.json) independently checks
  the original report, ledger, preservation and public privacy boundaries.

From this exact repository revision:

```sh
python3 -I -B results/skill-workflows-v2/development-revision-1-offline-2026-10-11/reproduce.py
```

This standard-library check verifies receipt checksums, source identities and
reported control outcomes. It executes no candidate code or models. Docker and
Harbor are real in opted-in integration controls, while model output is synthetic.
Digests establish consistency, not producer authentication or independent live
replication. Raw local logs and native session histories remain private.

The original offline package and registration remain unchanged at
`c015a4cd9215f1925663dfdee9447d5b4866d244`. V1 artifacts and the stable kernel also
remain unchanged. New live execution needs a source-bound revision admission,
published external registration digest and fresh native gates.
