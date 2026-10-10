# V2 development registration, round zero

**48 trials are registered; none had executed when this registration was created.** The current subscription preflight denied ordinary model usage, so no model-availability or returned-model claim is made.

The schedule covers 12 fresh development tasks, all four arms and one attempt per task/arm. It is generated with seed `20261008`. [registration.json](registration.json) contains the complete ordered schedule and the 12 frozen identities. [admission.json](admission.json) binds the passing offline controls and separate review to the frozen harness, skill and tasks. [source-manifest.json](source-manifest.json) records every frozen input; [ablation.json](ablation.json) verifies the exact C/D differences. The full upstream bundle remains pinned to `b0618bc436ad893b3c5e84e55fba86586d34a404`.

The externally retained registration identity is:

```text
4a3f1b85670651f3b52d5ec3bfa8608f41fe1d227cc2cb56df8627a5b3880ccd
```

This is the canonical registration payload digest before its self-identifying field is added. It is not the raw JSON file checksum. The controller verifies that identity and reconstructs all derived registration and frozen-input identities on every admission and replay. File checksums for this public registration are in [checksums.json](checksums.json). Digests identify bytes, not authenticated producers.

[Preflight](preflight.json) confirmed CPython 3.13.12, Harbor 0.24.0, Codex 0.154.0, the native configuration, ChatGPT authentication and both local image content IDs. It did not call a model. The controller must observe fresh subscription permission before dispatch and validate the exact `gpt-6-astra` / `ultra` identity from each retained live native stream. No billing fallback or silent substitution is permitted.

Only this development schedule is admitted. The held-out stage still requires all 48 development outcomes resolved, all controls passing, upstream completing 4–10 tasks, and both success and failure on ordinary repair/implementation tasks. At most one complete development revision is permitted. Review coverage and statistical limits are in the [offline package](../offline-package-2026-10-11/README.md) and [protocol](../../../bench/harbor/skill-workflows-v2/PROTOCOL.md).

Prepare/run/replay commands are documented in the [controller README](../../../bench/harbor/skill-workflows-v2/README.md). Recreating images from recipes does not guarantee these local image content IDs because apt/npm transitive packages may change; exact-image transfer or a separately registered environment is required for exact runtime replication.
