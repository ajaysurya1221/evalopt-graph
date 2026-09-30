# Changelog

All notable changes to evalopt are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Build artifacts pin core metadata 2.4 (`core-metadata-version` on both hatch targets) so a
  hatchling upgrade cannot change the wheel or sdist metadata shape; `scripts/verify_artifacts.py`
  now asserts it.

## [0.1.0] - 2026-07-20

### Added

- A zero-dependency governance and evidence-integrity kernel for Python 3.10–3.14.
- An exact ten-symbol stable package API for policy, evidence, acceptance, serialization, and replay.
- Five distinct terminal decisions: `ACCEPTED`, `BLOCKED`, `UNVERIFIED`, `UNSUPPORTED`, and `FAILED`.
- Controller-owned evidence authority policies, content-bound attestations, independent support
  assessments, freshness checks, and exact-record authorization.
- Optional verifier-side Harbor integration conformance without a Harbor runtime dependency.
- Reproducible evidence documentation, a prospective external evaluation protocol, and public
  contribution and security processes.

### Compatibility

- Historical graph, CLI, provider, research, filesystem-adapter, and package-root surfaces remain lazy
  or standalone for one migration cycle. They are deprecated, host-owned, and outside the stable API.

### Evidence status

- The bounded evidence mechanism is implemented, unit-proven, integration-proven, and
  conformance-proven.
- This release does not claim benchmark superiority, external comparison, independent reproduction,
  or SOTA performance.

[Unreleased]: https://github.com/ajaysurya1221/evalopt-graph/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ajaysurya1221/evalopt-graph/releases/tag/v0.1.0
