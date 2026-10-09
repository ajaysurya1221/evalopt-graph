# evalopt-graph

**Make acceptance policy explicit and replayable.**

Your harness runs the checks and supplies observations.
Evalopt applies the policy and returns a decision with stable reason codes.

**Expected output from the example below, using authored inputs:**
```text
ACCEPTED ('policy_satisfied',)
FAILED ('required_gate_failed:tests',)
BLOCKED ('tests_weakened',)
```
[Run the example](https://github.com/ajaysurya1221/evalopt-graph#decide-serialize-replay) · [Inspect the kernel](https://github.com/ajaysurya1221/evalopt-graph/blob/main/src/evalopt_graph/kernel.py)

Five outcomes: ACCEPTED, BLOCKED, FAILED, UNSUPPORTED and UNVERIFIED.

**Boundary:** the host runs checks, detects weakened tests and supplies trustworthy evidence.
Replay establishes consistency with that input, not the truth of the input.

**Engineering:** [Zero runtime dependencies](https://github.com/ajaysurya1221/evalopt-graph/blob/main/pyproject.toml) · [State and replay tests](https://github.com/ajaysurya1221/evalopt-graph/blob/main/tests/test_kernel.py)
[32 authored/generated conformance cases](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_RESULTS.md) · [Release checks](https://github.com/ajaysurya1221/evalopt-graph/blob/main/scripts/verify_installed_release.py)

Kernel conformance evidence only; no external capability or comparative result is claimed.
[Install](https://github.com/ajaysurya1221/evalopt-graph#install) · [Host responsibilities](https://github.com/ajaysurya1221/evalopt-graph#kernel-owns--host-owns)

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/ajaysurya1221/evalopt-graph/raw/main/docs/assets/hero-dark.svg">
  <img src="https://github.com/ajaysurya1221/evalopt-graph/raw/main/docs/assets/hero-light.svg" alt="evalopt-graph, acceptance policy kernel. Do the gates, claims and evidence satisfy the acceptance policy? Evidence card from the README example with required gates tests and lint: tests PASS and lint PASS gives ACCEPTED ('policy_satisfied',); tests FAIL gives FAILED ('required_gate_failed:tests',); passing gates with a host-reported weakened test suite give BLOCKED ('tests_weakened',)." width="100%">
</picture>

[![Release](https://img.shields.io/github/v/release/ajaysurya1221/evalopt-graph?display_name=tag&sort=semver)](https://github.com/ajaysurya1221/evalopt-graph/releases/latest) [![CI](https://github.com/ajaysurya1221/evalopt-graph/actions/workflows/ci.yml/badge.svg)](https://github.com/ajaysurya1221/evalopt-graph/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/evalopt-graph?cacheSeconds=300)](https://pypi.org/project/evalopt-graph/) [![Python](https://img.shields.io/pypi/pyversions/evalopt-graph?cacheSeconds=300)](https://pypi.org/project/evalopt-graph/) [![License: MIT](https://img.shields.io/badge/license-MIT-49C6B8.svg)](https://github.com/ajaysurya1221/evalopt-graph/blob/main/LICENSE)

> **Apply acceptance policy to your CI observations**
>
> Have the host report its test and lint results through `AcceptanceInput`. Evaluate them against `GovernancePolicy`, save the decision with its policy and input, then deserialize and replay it later. The example shows passing gates, a failed test gate, and a host-reported weakened test suite producing different outcomes.
>
> This workflow is exercised with authored inputs. Evalopt neither runs those checks nor discovers weakened tests itself.

## Install

Install into an isolated environment (Python 3.10–3.14), then run the example below:

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

The evaluator is pure, with no LLM in the loop: the same policy and input produce the same decision,
with stable reason codes and hashes for the policy, input, evidence records, and decision. Its
[precedence](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/architecture.md#acceptance-precedence) is fail-closed: malformed or tampered input
`FAILED`, policy or contradiction block `BLOCKED`, observed gate failure `FAILED`, unavailable required
mechanism `UNSUPPORTED`, incomplete required evidence `UNVERIFIED`, otherwise `ACCEPTED`.

## Stable kernel API

The package root exports exactly ten stable symbols in `v0.1.x`: `GovernancePolicy`, `ClaimRecord`,
`EvidenceRequest`, `EvidenceMaterial`, `EvidenceAttestation`, `SupportAssessment`, `EvidenceAuthority`,
`AcceptanceInput`, `AcceptanceDecision` and `evaluate_acceptance`.

- `GovernancePolicy` declares required gates, trust, freshness, evaluator, claim, verifier, and record
  authorization requirements.
- `EvidenceAuthority` applies controller-owned adapter policy to material already retrieved by a host.
- `EvidenceAttestation` binds source policy, retrieval metadata, selected content, and hashes.
- `SupportAssessment` separately records whether selected content supports, contradicts, or is
  insufficient for a claim.
- `evaluate_acceptance` evaluates a complete immutable observation once and returns a replayable
  `AcceptanceDecision`.

See [`kernel.py`](https://github.com/ajaysurya1221/evalopt-graph/blob/main/src/evalopt_graph/kernel.py) for the compact public contract and
[`test_kernel.py`](https://github.com/ajaysurya1221/evalopt-graph/blob/main/tests/test_kernel.py) for complete evidence-authority examples.

## Kernel owns / host owns

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://github.com/ajaysurya1221/evalopt-graph/raw/main/docs/assets/where-dark.svg">
  <img src="https://github.com/ajaysurya1221/evalopt-graph/raw/main/docs/assets/where-light.svg" alt="Two lanes. Host lane: your host runs the checks, detects weakened tests, collects evidence, holds the GovernancePolicy and builds an AcceptanceInput. Kernel lane: evaluate_acceptance returns an AcceptanceDecision in one of five states: ACCEPTED, BLOCKED, FAILED, UNSUPPORTED or UNVERIFIED. The host stores policy, input and decision; replay later recomputes the decision and is true only for an identical record." width="100%">
</picture>

In words: your host runs the checks, detects weakened tests, collects evidence and builds an `AcceptanceInput`.
`evaluate_acceptance(policy, input)` returns an `AcceptanceDecision`. The host stores policy, input and decision;
`replay()` later recomputes the decision and compares the record.

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

Read the [evidence report](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_RESULTS.md) and
[prospective external protocol](https://github.com/ajaysurya1221/evalopt-graph/blob/main/docs/BENCHMARK_PROTOCOL.md) for the claims, controls, and gaps.
The v0.1.0 kernel package release contains no live-model governance campaign or official Docker SWE-bench result.

### Workflow skill and measured comparison

The portable [eval-opt skill](skills/eval-opt/SKILL.md) and
[workflow benchmark](bench/harbor/skill-workflows-v1/README.md) are separate
development artifacts. The benchmark compares a baseline, Matt Pocock's pinned
workflow bundle, and eval-opt under the same task and runtime conditions. Hidden
outcome grading is separate from the kernel's stopped-output policy comparison.

The [432-trial held-out comparison](results/skill-workflows-v1/heldout-comparison-2026-10-10/README.md)
found **no demonstrated workflow upgrade**: upstream and eval-opt each achieved
132/144 valid completions (91.67%). The registered paired C-minus-B difference
is 0.00 percentage points, with a 95% interval of −2.08 to +2.08 points. This
observed tie does not establish equivalence. All final outcomes are retained;
one controller interruption and its permitted retry leave 433 attempts.
The package releases all 48 authored task assets and replays 432 supplied-reply
grades plus 1,296 policy decisions without executing candidate code.

In the secondary policy comparison, M and G each accepted 378/432 outputs,
including 19/37 graded-invalid outputs, while not accepting 36/395 valid outputs.
G's nine abstentions overlap that non-acceptance count. These descriptive results
do not establish a kernel advantage over M. All-attempt accounting contains
417 complete and 16 partial records; partial counters are lower bounds, with no
efficiency comparison or invented dollar costs.

The [36-trial development pilot](results/skill-workflows-v1/development-pilot-2026-10-09/README.md)
recorded 12/12 valid completions for each arm. Its separate isolated corrected-grader
reexecution changed none of the 36 grades and added no agent trials. The pilot has
[a fresh public-clone reproduction receipt](results/skill-workflows-v1/validation-f515456/README.md).
The [claim-to-evidence table](results/skill-workflows-v1/CLAIMS.md) keeps pilot,
held-out, policy, transfer and replication scope distinct.

The [72-trial Terminal-Bench transfer registration](results/skill-workflows-v1/transfer-registration-2026-10-10/README.md)
is frozen after primary completion and report replay. It is a feasibility subset,
not an official leaderboard score; no transfer result is established by the
held-out report. The prior [12-image setup checks](results/skill-workflows-v1/transfer-readiness-2026-10-09/README.md)
were infrastructure controls, not task outcomes.

The [protocol](bench/harbor/skill-workflows-v1/PROTOCOL.md) and
[frozen implementation notes](bench/harbor/skill-workflows-v1/STATUS.md) retain their
original prospective wording; completed result packages supersede historical
pending statuses. This is a maintainer-run study, not independent human validation
or independent agent replication. Hashes identify bytes, not authenticated
producers. The stable kernel API and wheel dependencies remain unchanged.

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
public issue. See the [security policy](https://github.com/ajaysurya1221/evalopt-graph/blob/main/SECURITY.md) for supported versions and response expectations.

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

Maintained by Ajay Surya Senthilrajan, with AI pair-programming recorded in commit trailers.
See the tests, design records and release evidence linked here.

## License

Released under the [MIT License](https://github.com/ajaysurya1221/evalopt-graph/blob/main/LICENSE).
Copyright © 2026 Ajay Surya Senthilrajan.
