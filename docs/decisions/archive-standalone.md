# ADR: Stop standalone development and preserve evalopt

Status: accepted. Recorded 2026-10-12 by the wind-down run (Task 03); revised 2026-10-12 UTC in Task 03 revision 1 after independent review.

## Decision

Standalone feature development of evalopt (`evalopt-graph`) has ended. The repository preserves the acceptance kernel and its research record. Routing, the migration map and public wording are fixed by [routing-boundary.md](routing-boundary.md), [migration-interface.md](migration-interface.md) and [winddown-positioning.md](winddown-positioning.md).

The maintainer accepted the high-confidence STOP recommendation of the private research memo `deep-research-2.md` (source inspections dated 12 October 2026 in the memo; SHA-256 `e307514fc800c2ff37c8d1a6d9a454bbf4d4addf53acd38611cbbc50b5695e81`). The memo is not published here.

No new integration, converter, predicate type, policy language, benchmark programme or shared runtime dependency is created. Actseal, Dorian, Frontier Scout and ARCI stay independent of evalopt and of each other. No partner, adoption or conformance programme runs during closure.

## Positions (Astra, Fable)

Astra (control lane) accepted STOP as preapproved and included one final `v0.1.1` deprecation release under the maintainer's explicit release authorization and memo S4; Fable's read-only planning consultation agreed that STOP permits no new product development and only a no-capability release. No disagreement arose.

## Rule that decided

The memo's recommendation was preapproved by the maintainer. Reopening is governed by the conditions below, not by architectural argument.

## Memo conclusions versus facts checked by this run

Memo conclusions, accepted as the maintainer's decision and not re-verified here:

- Overlap: portable policy decisions over attestations already exist in the [in-toto attestation framework](https://github.com/in-toto/attestation), [Witness](https://github.com/in-toto/witness) and SLSA-style [verification summaries](https://slsa.dev/spec/v1.0/verification_summary), cited at VSA v1.0; general policy evaluation is owned by engines such as [OPA](https://github.com/open-policy-agent/opa). The memo counts this against its 80-percent-overlap gate. The cited VSA v1.0 is a retired historical version and is prior art only, never a migration destination. Source status, as context only: the run's control lane checked the primary pages on 2026-10-12 UTC and found [v1.0](https://slsa.dev/spec/v1.0/verification_summary) and v1.1 marked Retired and [v1.2](https://slsa.dev/spec/v1.2/verification_summary) marked Approved; that status adds no route and does not reopen STOP.
- Demand: no dated public demand was found for evalopt's residual five-state and claim-support model as a standalone framework; no external adopter was verified.
- Portfolio cost: five adjacent decision and evidence projects impose naming and attention costs.
- Numbers: the memo states that evalopt's star, fork and commit figures were prompt-supplied and its download counts unverified; other projects' release and adoption figures are the memo's own readings. This run asserts none of them.

Facts this run checked at baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`, the verified public main:

- Exactly ten stable exports in `__all__` ([`__init__.py`](../../src/evalopt_graph/__init__.py)); `dependencies = []` in `pyproject.toml`; kernel record hashes are SHA-256 over canonical JSON ([`attestation.py`](../../src/evalopt_graph/attestation.py)). The stable kernel carries declared identifiers (the `AdapterPolicy` identity fields `adapter_id`, `adapter_version`, `retrieval_mechanism` and `parser_identity`, the `evalopt.claim-identity.v1` digest label, and adapter IDs indexed by `EvidenceAuthority` in [`kernel.py`](../../src/evalopt_graph/kernel.py)) but has no signing, key management, signature verification or cryptographic producer-authentication concept; a supplied identifier is not an authenticated producer identity ([SECURITY.md](../../SECURITY.md)).
- `AcceptanceDecision.validate()` checks schema, status and record hash; `replay()` is equality with a fresh `evaluate_acceptance(policy, input_)` ([`kernel.py`](../../src/evalopt_graph/kernel.py)). Neither reruns checks or establishes the truth of the input ([architecture.md](../architecture.md)).
- Main holds ten commits after the `v0.1.0` tag (2026-07-20). Two touch `src/`. "Reject scalar acceptance input rows" (`624ed11`) changes `kernel.py` and tests so malformed acceptance rows fail closed; it has no CHANGELOG entry yet. "build/docs: keep twine green on new hatchling, plain-words README, move personal tooling out of the package" (`fc37732`) changes three non-kernel modules: [`project_detect.py`](../../src/evalopt_graph/project_detect.py) now builds the inferred Python test-gate command from the shell-quoted running interpreter (`sys.executable`) instead of a PATH-selected `python`; [`permissions.py`](../../src/evalopt_graph/permissions.py) changes its readiness warning messages to point at the external `examples/claude-code-overnight/` helpers and the external skill, and its module docstring; [`epistemic.py`](../../src/evalopt_graph/epistemic.py) changes module docstring prose only. The interpreter change and the helper move are disclosed under CHANGELOG "Unreleased" ([CHANGELOG.md](../../CHANGELOG.md)). The other eight commits are documentation, build, CI and dependency changes, including the hatchling build backend and optional-dependency floor bumps; required runtime dependencies stay empty.
- The preservation control reports 75 protected files unchanged under `src/`, `tests/` and `bench/`; the benchmark branches are not merged into main.

## Consequences

- **Final release.** Relative to verified main `fc3045d`, the wind-down changes nothing under `src/` except the `__version__` literal and adds no capability. Approved release metadata and plumbing outside `src/` (package version metadata, this package's lock entry, workflow and verifier expected-version values, release notes) and the documentation changes owned by other tasks remain allowed within their task allowlists. Because main already differs from `v0.1.0`, release notes enumerate the inherited differences from Git, not from this prose: the scalar-row kernel fix, the interpreter selection in project detection, the readiness-message and docstring wording, and the packaging and optional-dependency floor changes; they never claim byte-identical or behaviour-identical to `v0.1.0`. Publication is a later gated step; this record does not claim it happened.
- **Archival.** A future, human-owned action that this record does not claim has occurred.
- **Preservation.** All prior results (v1 to v4 studies, pull requests 33 to 36, benchmark branches kept out of main), frozen sources, tags, release assets and attribution remain untouched.
- **Legacy surfaces.** The graph, CLI, provider, Codex bridge, research, claim-ledger, filesystem-adapter and Harbor-adapter surfaces receive no feature work; their historical source and documentation are not edited by this decision.
- **Reopening.** Only if all four hold at once: three independent organisations request the same unmet capability; the gap is real and not reasonably covered by composing in-toto, Witness or OPA with the specialised tools; at least one organisation commits to a production-grade integration or conformance deployment; and the proposed category clears the 80-percent-overlap gate. One user or an architectural preference does not reopen it.
