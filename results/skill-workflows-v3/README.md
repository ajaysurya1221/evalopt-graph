# Phase-bound reporting: completed screen and measurement diagnosis

The fixed screen completed **16/16 upstream trials**, but **difficulty was not validated**: all eight ordinary repair and implementation attempts passed the retained functional checks. A separate audit found that the prompt omitted response fields required by the grader, invalidating the interpretation of all reporting failures and four review failures. All v1/v2 artifacts and original v3 grades remain unchanged. **No larger benchmark was started or authorized.**

Read the [completed report](difficulty-2026-10-11/README.md), [separate measurement diagnosis](reporting-diagnosis-2026-10-11/README.md), and [prospective offline correction](response-contract-correction-2026-10-11/README.md). The correction does not regrade or rerun this screen.

## What the reporting correction means

The controller now retains distinct, content-bound `initial` and `post_stop` observations. Before dispatch it seals the initial observation and exact prompt supplied to the agent. Structured agent checks describe only those supplied observations. A truthful report of an initial pass remains truthful when the stopped candidate later fails. The stopped check still fails, and M/G acceptance still uses the applicable stopped evidence.

Functional correctness, reporting support, boundary preservation, lifecycle confirmation and resource completeness have separate fields. The new code separated malformed checks from review evaluation, but a different undeclared top-level response requirement still gated four reviews. That defect is disclosed in the diagnosis rather than hidden by the earlier offline controls. All 16 actual responses accurately quoted the supplied initial check. This finite phase-correspondence result does not establish valid completion or workflow efficacy.

## Evidence and scope

- [Reviewed offline package](offline-package-2026-10-11/README.md): controls, source identities, preserved-file inventory and pure reproduction.
- [Fixed screen registration](difficulty-registration-2026-10-11/README.md): eight tasks, two attempts each, the complete pinned upstream workflow, and fixed runtime conditions.
- [Prospective protocol](../../bench/harbor/skill-workflows-v3/PROTOCOL.md): readiness rules, missingness, continuation and publication limits.
- [Fresh task contracts and controls](../../bench/harbor/skill-workflows-v3/tasks/README.md): two repairs, two implementations and four review/constraint/evidence problems.

The portable v3 skill remains an offline deliverable; it was not injected into this upstream-only screen. The completed screen ends as `difficulty_not_validated`. It provides no comparative efficacy or upgrade evidence.

This is a maintainer-run study with separated AI authoring and review roles. Public reproduction checks retained evidence and analysis consistency; it is not independent human authorship or a fresh live replication.
