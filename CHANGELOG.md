# Changelog

All notable changes to evalopt are documented here. The project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

No new standalone features are planned. See the maintenance and security guidance.

## [0.1.1]

Standalone feature development has ended. The repository preserves the acceptance kernel and its
research record; the README notice, the [migration map](docs/migration.md) and the
[archive decision](docs/decisions/archive-standalone.md) say where each job goes. Deprecated
compatibility surfaces receive no feature work. The entries below disclose inherited differences
between the `v0.1.0` tag and the verified main baseline `fc3045d`; there is no claim that the kernel
is byte-identical to `v0.1.0`. This wind-down adds no runtime capability and preserves that baseline
implementation except its version literal. The [final deprecation release notes](docs/releases/v0.1.1.md)
describe the target distribution; the public release record supplies publication status and date.

### Fixed

- `AcceptanceInput` now rejects scalar rows: a `gate_results` or `contradictions` value, or a row
  inside it, that is a string, bytes or not iterable raises `ValueError` with the existing
  "entries require N string fields" message. Previously a string row of the right length was split
  into characters and accepted, and a non-iterable value raised `TypeError`.
  `AcceptanceInput.from_dict` passes rows through the same validation. Contributed by Göktuğ Özkan
  ([@goktugozkanmd](https://github.com/goktugozkanmd)) in
  [#4](https://github.com/ajaysurya1221/evalopt-graph/pull/4), commit `624ed11`, with tests. This
  inherited change had no changelog entry until now.

### Changed

- Standalone development has ended. Added the STOP decision, migration map, alternatives, portfolio
  index and maintenance-scoped contribution guidance; existing implementation and research remain.
- Historical nonsecret scanner findings are excepted only by their exact commit, path, stock rule
  and captured value together. Stock rules, full-history scanning and release protections remain.
- Inherited before this wind-down: hatchling is pinned to 1.32.4; optional provider floors are
  anthropic >=1.11.0 and openai >=3.23.0; development floors are pytest >=9.1.1, ruff >=0.16.10 and
  jsonschema >=4.26.0,<5. The associated lock changes predate this run. Required runtime dependencies
  remain empty; the wind-down changes only the root package version in the lock.
- Inherited compatibility warnings point to external overnight helpers and the external Claude
  skill; the epistemic module's documentation was updated.

- The README now opens with the example's expected output, the five decision states, the host
  boundary and links to the evidence behind them. A generated evidence-card hero
  (`docs/assets/hero-{light,dark}.svg`) replaces the two-outcome banner in the README, and a
  host/kernel boundary figure (`docs/assets/where-{light,dark}.svg`) sits beside the "Kernel owns /
  host owns" table. `docs/assets/src/make_figures.py` generates both figures with the standard
  library; `tests/test_figures.py` fails if a committed figure is stale or if the evidence card no
  longer matches the README example's printed output. The previous banner files stay in place for
  pages that still link to them.
- The README opening and the package summary now describe the kernel plainly as a deterministic
  acceptance policy for AI coding agents and show the `FAILED` and `BLOCKED` paths next to
  `ACCEPTED`. The PyPI summary changes with the next release.
- The README opening now says the host supplies gate results, claims and evidence records and
  remains responsible for running checks, detecting weakened tests and collecting evidence; the
  kernel returns a deterministic, replayable decision. The README adds a "Run the example" link,
  shows an isolated `venv` install of `evalopt-graph==0.1.0`, and points to the compatibility
  surfaces and Harbor example instead of saying no runtime adapters ship. The package summary
  names all five decision states: `ACCEPTED`, `BLOCKED`, `FAILED`, `UNSUPPORTED` and `UNVERIFIED`.
- Build artifacts pin core metadata 2.4 (`core-metadata-version` on both hatch targets) so a
  hatchling upgrade cannot change the wheel or sdist metadata shape; `scripts/verify_artifacts.py`
  now asserts it.

- The detected Python test gate now runs `<sys.executable> -m pytest -q` instead of a bare
  `python`, so the gate runs in the interpreter that imported evalopt.

### Removed

- The Claude Code overnight hooks and the `~/.claude/settings.json` helper scripts moved out of the
  package into `examples/claude-code-overnight/`. They are no longer shipped in the sdist, and the
  artifact check now rejects any absolute home-directory path instead of naming a workspace.

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

[Unreleased]: https://github.com/ajaysurya1221/evalopt-graph/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/ajaysurya1221/evalopt-graph/releases/tag/v0.1.1
[0.1.0]: https://github.com/ajaysurya1221/evalopt-graph/releases/tag/v0.1.0
