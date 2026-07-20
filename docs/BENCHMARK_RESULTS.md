# Evidence status and reproducible checks

This document reports only evidence that can be reproduced from the public `v0.1.0` source tree.

No live-model governance benchmark, official Docker SWE-bench result, externally authored governance
comparison, or independent reproduction is included. The release does not establish task-distribution
performance or comparative superiority.

## Release validation

The release gate checks:

- Python 3.10–3.14 on Ubuntu, plus Python 3.14 on macOS and Windows;
- compilation, the full test suite, Ruff lint and format checks, deterministic demos, and smoke tests;
- the exact ten-symbol stable API, version identity, serialization, and replay;
- a clean-wheel install with no required runtime dependencies; and
- wheel/source-distribution contents, checksums, an SPDX SBOM, and provenance attestations.

The GitHub Actions run attached to the release tag is the durable record of those checks. To run the
main offline validation locally from a clean clone:

```bash
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

On Windows, activate with `.venv\Scripts\Activate.ps1`; the Windows release job validates the installed
wheel rather than running the Bash compatibility smoke.

## Deterministic evidence-boundary conformance

The repository includes a fixed, seeded `12 + 12 + 8` regression corpus:

| Stratum | Expected result | What it exercises |
| --- | ---: | --- |
| Producer-controlled legacy packets | 12/12 rejected | Producer metadata cannot mint trusted evidence |
| Invalid or adversarial adapter cases | 12/12 expected outcomes | Selector, hash, locator, time, polarity, traversal, and mutation handling |
| Valid adapter controls | 8/8 accepted | Exact text, JSON pointer, local, deterministic, Unicode, and multiline cases |

Run it without writing into the repository:

```bash
conformance_dir="$(mktemp -d)"
python scripts/provenance_benchmark.py \
  --out "$conformance_dir/summary.json"
cat "$conformance_dir/summary.json"
```

The utility runs in process and writes one summary. It has no external task authors, sealed holdout,
model calls, container isolation, trial sampling, or comparative baseline. These cases overlap
development and therefore provide mechanism conformance only. Repeating the fixed corpus does not
create independent samples.

## Harbor integration conformance

The repository-authored Harbor task checks the verifier-side mapping for three policies applied to the
same stopped deterministic output:

- `U`: an ungoverned policy that always accepts;
- `M`: a small independently implemented policy shape; and
- `G`: the evalopt kernel policy.

The observation builder binds the source version, wheel, policy source, and canonical visible
observation. The policy-verifier image contains no grader. A separate public oracle grades the
deterministic task only after the policy artifact is frozen.

Unit and integration tests exercise the builder, all three policy paths, tamper cases, artifact schema,
and the separate grader. [`bench/harbor/README.md`](../bench/harbor/README.md) contains the optional
Harbor 0.18 configuration and Docker smoke. Passing it demonstrates adapter wiring; it is not evidence
of agent capability or an external governance advantage.

## Evidence ladder

| Level | v0.1.0 status | Meaning |
| --- | --- | --- |
| `IMPLEMENTED` | Yes | The kernel and records exist as a stable, zero-dependency API |
| `UNIT_PROVEN` | Yes | Focused tests cover terminal states, authorization, mutation, serialization, and replay |
| `INTEGRATION_PROVEN` | Yes | Compatibility and Harbor mappings terminate through the kernel path |
| `CONFORMANCE_PROVEN` | Yes | Authored/generated cases exercise a bounded evidence mechanism |
| `BENCHMARK_PROVEN` | No | No representative external task-distribution result exists |
| `EXTERNALLY_COMPARED` | No | No completed comparison against serious external policies exists |
| `INDEPENDENTLY_REPRODUCED` | No | No independent team has reproduced an external result |

## Interpretation limits

- An attestation demonstrates content binding under declared controller policy, not semantic truth.
- The lexical verifier is deliberately exact and is not calibrated natural-language entailment.
- A visible gate can differ from a hidden grader; policy acceptance and task correctness must remain
  separate outcomes.
- The compatibility loop is not a durable or isolated production runtime.
- No model-quality, cost, latency, safety-rate, or coding-capability conclusion follows from the fixed
  conformance corpus.

The [prospective external protocol](BENCHMARK_PROTOCOL.md) defines the additional independence,
isolation, task, artifact, and analysis requirements for a comparative result.
