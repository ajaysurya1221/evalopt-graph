# Fixed upstream difficulty screen registration

Prospective registration: **8 fresh development tasks × 2 attempts = 16 trials**, arm B only. No live outcomes were observed when this freeze was created. The prior v1/v2 studies are preserved; no old attempt enters this schedule.

External registration pin:

```
f19253f9e47586e6568c37b112a584a1479ecdff4b8e69d1aafa54208d17b569
```

The [frozen protocol](../../../bench/harbor/skill-workflows-v3/PROTOCOL.md) requires 4–12 functional/boundary successes, at least two consistently successful tasks and two consistently unsuccessful tasks, and both patterns among ordinary repair/implementation tasks. A consistent failure must come from completed executions with genuine functional failure, preserved boundaries and verified runtime/lifecycle; reporting errors, refusals and timeouts cannot supply it. All 16 outcomes must resolve, with no disputed task or measurement defect. Passing means finite difficulty variation, not measured eval-opt efficacy or permission to launch a larger study. Either result ends with a report.

The complete upstream workflow bundle is pinned to `b0618bc436ad893b3c5e84e55fba86586d34a404`. Native conditions remain `gpt-6-astra`/`ultra`, Codex 0.154.0, Harbor 0.24.0, CPython 3.13.12, subscription authentication, 600 seconds per trial, one CPU, 2 GiB, one parent and at most two concurrent children at depth one. Dispatch is sequential. No API-billing fallback or silent model substitution is permitted.

The agent and verifier image identities, randomized original schedule, task/source/grader/parser/analysis identities, continuation rules and admission receipt are frozen in the adjacent JSON files. The admission evidence binds the current 559-test/236-subtest zero-skip run, semantic controls and unchanged legacy report reproduction. Synthetic controls are not live model outcomes. Independent here means separated AI implementation/review roles in a maintainer-run study.

Run from a fresh checkout, without model access:

```sh
python3 -I -B results/skill-workflows-v3/difficulty-registration-2026-10-11/reproduce.py
```

This checks exact local source correspondence, registration/task allocation and retained admission hashes. Upstream and image identities remain declared freeze provenance; the command neither executes candidate code nor performs a new live replication. The adjacent checksums detect changes relative to the retained packet, not malicious replacement of the packet and all its checksums together.
