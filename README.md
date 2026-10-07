<div align="center">
  <img src="https://github.com/ajaysurya1221/evalopt-graph/raw/main/docs/assets/evalopt-hero-v1.svg" alt="evalopt: Agents propose. Policy decides. A noisy proposal signal passes through Gates, Evidence, and Bounds, then forks to Accepted or Blocked." width="100%">
</div>

<div align="center">

[![Release](https://img.shields.io/github/v/release/ajaysurya1221/evalopt-graph?display_name=tag&sort=semver)](https://github.com/ajaysurya1221/evalopt-graph/releases/latest)
[![CI](https://github.com/ajaysurya1221/evalopt-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/ajaysurya1221/evalopt-graph/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/evalopt-graph?cacheSeconds=300)](https://pypi.org/project/evalopt-graph/)
[![Python](https://img.shields.io/pypi/pyversions/evalopt-graph?cacheSeconds=300)](https://pypi.org/project/evalopt-graph/)
[![License: MIT](https://img.shields.io/badge/license-MIT-49C6B8.svg)](https://github.com/ajaysurya1221/evalopt-graph/blob/main/LICENSE)

**Agents propose. Policy decides.**

Deterministic acceptance policy for AI coding agents.

**[Run the example](https://github.com/ajaysurya1221/evalopt-graph#decide-serialize-replay)**

</div>

`evalopt-graph` evaluates gate results, declared claims and evidence records supplied by a host
against an explicit acceptance policy. It returns a deterministic, replayable decision with stable
reason codes. The host remains responsible for running checks, detecting weakened tests and
collecting trustworthy evidence.

- **What it checks.** Gate results reported by your harness (tests, lint, typecheck, build); each
  load-bearing claim against a hash-bound evidence attestation and an independent support
  assessment; and policy precedence with fail-closed defaults, so a weakened test suite blocks, a
  failed gate fails, a missing gate is unsupported, and an unbacked claim is unverified.
- **What it produces.** One content-addressed `AcceptanceDecision` with stable reason codes and
  hashes for the policy, input, evidence, and decision, which `validate()` and `replay()` can
  re-check later without trusting the process that wrote it.
- **Runtime and integration.** No LLM in the loop. The stable kernel has zero runtime dependencies. Hosts map
  observations into `AcceptanceInput`; the compatibility surfaces and Harbor example are described
  below. Python 3.10–3.14.

## Install

Install into an isolated environment, then run the example below:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install evalopt-graph==0.1.0
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## Decide, serialize, replay

```python
from evalopt_graph import AcceptanceDecision, AcceptanceInput, GovernancePolicy, evaluate_acceptance

policy = GovernancePolicy(required_gates=("tests", "lint"))

# What the harness observed: both required gates passed, nothing was skipped or deleted.
observed = AcceptanceInput(
    observed_at="2026-07-20T12:00:00+00:00",
    gate_results=(("tests", "PASS"), ("lint", "PASS")),
)
decision = evaluate_acceptance(policy, observed)
print(decision.status, decision.reasons)  # ACCEPTED ('policy_satisfied',)

# Same policy, but the test gate failed.
failed = evaluate_acceptance(
    policy,
    AcceptanceInput(
        observed_at="2026-07-20T12:00:00+00:00",
        gate_results=(("tests", "FAIL"), ("lint", "PASS")),
    ),
)
print(failed.status, failed.reasons)  # FAILED ('required_gate_failed:tests',)

# The host reports passing gates and a weakened test suite.
blocked = evaluate_acceptance(
    policy,
    AcceptanceInput(
        observed_at="2026-07-20T12:00:00+00:00",
        gate_results=(("tests", "PASS"), ("lint", "PASS")),
        tests_weakened=True,
    ),
)
print(blocked.status, blocked.reasons)  # BLOCKED ('tests_weakened',)

# Decisions are plain, content-addressed records: store them, then re-check them later.
restored = AcceptanceDecision.from_dict(decision.to_dict())
assert restored.validate()
assert restored.replay(policy, observed)
```

The evaluator is pure: the same policy and input produce the same decision. Terminal outcomes are
`ACCEPTED`, `BLOCKED`, `UNVERIFIED`, `UNSUPPORTED`, and `FAILED`, each with stable reason codes and
hashes for the policy, input, evidence records, and decision.

## Stable kernel API

The package root exports exactly ten stable symbols in `v0.1.x`:

```python
from evalopt_graph import (
    GovernancePolicy,
    ClaimRecord,
    EvidenceRequest,
    EvidenceMaterial,
    EvidenceAttestation,
    SupportAssessment,
    EvidenceAuthority,
    AcceptanceInput,
    AcceptanceDecision,
    evaluate_acceptance,
)
```

- `GovernancePolicy` declares required gates, trust, freshness, evaluator, claim, verifier, and record
  authorization requirements.
- `EvidenceAuthority` applies controller-owned adapter policy to material already retrieved by a host.
- `EvidenceAttestation` binds source policy, retrieval metadata, selected content, and hashes.
- `SupportAssessment` separately records whether selected content supports, contradicts, or is
  insufficient for a claim.
- `evaluate_acceptance` evaluates a complete immutable observation once and returns a replayable
  `AcceptanceDecision`.

See [`kernel.py`](https://github.com/ajaysurya1221/evalopt-graph/blob/main/src/evalopt_graph/kernel.py)
for the compact public contract and
[`test_kernel.py`](https://github.com/ajaysurya1221/evalopt-graph/blob/main/tests/test_kernel.py) for
complete evidence-authority examples.

## Kernel owns / host owns

| The kernel owns | Your host owns |
| --- | --- |
| Deterministic policy evaluation | Model calls, prompts, and sampling |
| Terminal decision status and reason codes | Tools, edits, retries, and orchestration |
| Content-bound evidence and support records | Retrieval and protection of controller policy |
| Record authorization and freshness checks | Sandboxes, network and filesystem controls |
| Canonical serialization, hashes, and replay | Persistence, scheduling, graders, and metrics |

This boundary is intentional. Importing `evalopt_graph` loads the kernel without importing provider
SDKs, the compatibility graph, CLI code, filesystem adapters, benchmark adapters, or optional
frameworks.

## Evidence, not a truth oracle

Evalopt keeps three questions separate:

1. **Was this exact material retrieved under an allowed adapter policy?** An attestation binds the
   retrieved bytes, selected span, source class, time, parser identity, and policy.
2. **Does the selected material support this exact claim?** A support assessment records the verifier
   and its result independently of retrieval integrity.
3. **May these exact records authorize acceptance?** Governance policy allowlists the authority policy,
   verifier, and evidence records before the decision can use them.

That structure makes evidence tampering and unsupported load-bearing claims visible. It does **not**
prove semantic truth, deployed behavior, source correctness, or model capability.

### Current evidence ladder

- **IMPLEMENTED / UNIT_PROVEN:** pure API, immutable records, distinct terminal states, authorization,
  serialization, replay, and import isolation.
- **INTEGRATION_PROVEN:** the compatibility host and optional Harbor verifier mapping terminate through
  the same kernel decision path.
- **CONFORMANCE_PROVEN:** deterministic generated and authored cases exercise a bounded evidence
  boundary mechanism.
- **What this does not claim:** external benchmark results, comparison against other tools, or
  independent reproduction. The conformance cases show the mechanism behaves as specified; they say
  nothing about model capability.

Read the
[evidence report](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_RESULTS.md) and
[prospective external protocol](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_PROTOCOL.md)
for the claims, controls, and gaps. There is no live-model governance campaign or official Docker
SWE-bench result in this release.

## Integrate it anywhere

The kernel is host-independent: adapt observations from Codex, Claude Code, OpenHands, LangGraph, CI,
or your own runtime into `AcceptanceInput`, then store the returned decision beside the policy and input
used to create it.

An optional
[Harbor 0.18 conformance task](https://github.com/ajaysurya1221/evalopt-graph/blob/main/bench/harbor/README.md)
demonstrates verifier-side mapping without importing Harbor into the kernel. It validates integration
wiring only; it is not an external benchmark.

The historical graph, standalone CLI, provider clients, Codex bridge, research loop, and filesystem
adapters remain as **deprecated compatibility surfaces for one migration cycle**. They are not stable
API or policy authorities. New integrations should depend only on the ten root exports above.

## Documentation

- [Architecture and trust boundaries](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/architecture.md)
- [Evidence results and limitations](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_RESULTS.md)
- [Prospective benchmark protocol](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_PROTOCOL.md)
- [Harbor integration](https://github.com/ajaysurya1221/evalopt-graph/blob/main/bench/harbor/README.md)
- [v0.1.0 release notes](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/releases/v0.1.0.md)
- [Changelog](https://github.com/ajaysurya1221/evalopt-graph/blob/main/CHANGELOG.md)

## Community and security

Bug reports, focused proposals, documentation improvements, and integrations are welcome. Start with
the [contribution guide](https://github.com/ajaysurya1221/evalopt-graph/blob/main/CONTRIBUTING.md) and
follow the [Code of Conduct](https://github.com/ajaysurya1221/evalopt-graph/blob/main/CODE_OF_CONDUCT.md).

Please report vulnerabilities privately using
[GitHub Security Advisories](https://github.com/ajaysurya1221/evalopt-graph/security/advisories/new), not a
public issue. See the
[security policy](https://github.com/ajaysurya1221/evalopt-graph/blob/main/SECURITY.md) for supported
versions and response expectations.

## Development

```bash
git clone https://github.com/ajaysurya1221/evalopt-graph.git
cd evalopt-graph
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"

python -m compileall -q src tests scripts
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
bash scripts/smoke_test.sh
uv build
```

## License

Released under the [MIT License](https://github.com/ajaysurya1221/evalopt-graph/blob/main/LICENSE).
Copyright © 2026 Ajay Surya Senthilrajan.
