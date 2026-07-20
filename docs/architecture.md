# Architecture — one policy boundary, many possible hosts

Evalopt is a small, pure-Python governance and evidence-integrity kernel. It is not an agent runtime,
tool router, retrieval engine, sandbox, scheduler, benchmark harness, or durable workflow system.

```text
host runtime
  model · tools · edits · retrieval · retries · isolation · persistence
       |
       | immutable observations and retrieved material
       v
evalopt kernel
  evidence authority -> acceptance policy -> deterministic decision
       |
       | status · reason codes · content hashes · replay
       v
host lifecycle / verifier / CI
```

## Ownership boundary

The kernel owns:

- immutable policy, claim, evidence, input, and decision records;
- controller-policy-derived evidence attestations and support assessments;
- deterministic acceptance with explicit terminal outcomes; and
- record validation, content hashes, serialization, and replay.

The host owns:

- model inference, prompting, tools, repository changes, and retries;
- retrieval and the protection of controller policy and authorized records;
- sandboxes, credentials, network and filesystem controls;
- scheduling, checkpoints, persistence, graders, and metrics; and
- the decision about what operational action follows an evalopt result.

The kernel never infers that a source is trustworthy merely because a producer labels it trusted.
Likewise, it never treats a passing visible gate as proof of hidden correctness.

## Pure transitions

There are two core transitions:

```text
EvidenceRequest + EvidenceMaterial + controller adapter policy
    -> EvidenceAttestation + SupportAssessment

GovernancePolicy + AcceptanceInput
    -> AcceptanceDecision
```

`EvidenceRequest` contains proposal fields such as an adapter identifier, locator, selector, and
optional expected hashes. `EvidenceAuthority` supplies the trusted adapter policy. It validates the
material supplied by the host and derives source class, trust tier, retrieval metadata, selected
content, and record hashes.

Retrieval integrity and claim support remain separate:

- an `EvidenceAttestation` says what material was processed and how it was bound; and
- a `SupportAssessment` says how a named verifier relates that selected material to one exact claim.

Neither record is a semantic truth oracle. Acceptance can use a record only when the governance policy
allows its authority policy and verifier and authorizes the exact attestation and assessment hashes.

## Acceptance precedence

`evaluate_acceptance` is the only stable acceptance authority. It applies fail-closed precedence:

```text
malformed or tampered input       -> FAILED
explicit policy/contradiction block -> BLOCKED
observed gate or score failure    -> FAILED
required mechanism unavailable   -> UNSUPPORTED
required evidence incomplete     -> UNVERIFIED
all policy conditions satisfied  -> ACCEPTED
```

The result includes stable reason codes plus hashes of the policy, input, evidence records used, and
decision. `AcceptanceDecision.validate()` verifies the decision record, while
`AcceptanceDecision.replay(policy, input_)` recomputes and compares the complete decision.

## Stable surface

The `v0.1.x` package root exposes ten stable symbols:

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

Importing `evalopt_graph` does not import a model provider, graph runtime, CLI, repository helper,
filesystem adapter, Harbor adapter, or benchmark dependency. The distribution has no required runtime
dependencies.

Historical graph, CLI, provider, research, and filesystem-adapter surfaces remain lazy or standalone
for one migration cycle. They are deprecated host adapters, absent from `__all__`, and cannot define a
second stable acceptance path.

## Host integration pattern

1. Protect the policy and evidence-adapter configuration from the untrusted producer.
2. Run the agent or other producer in the host's chosen isolation boundary.
3. Retrieve material through host-controlled adapters and preserve retrieval metadata.
4. Convert visible gate results, claims, contradictions, attestations, and assessments into one
   `AcceptanceInput`.
5. Call `evaluate_acceptance` once and store the policy, input, and decision together.
6. Validate or replay the decision before taking an acceptance-dependent action.

The optional [`harbor_adapter.py`](../src/evalopt_graph/harbor_adapter.py) maps this pattern into a
verifier artifact without importing Harbor into the kernel. The repository's
[Harbor task](../bench/harbor/README.md) is integration conformance, not an external benchmark.

## Known limits

- In-process evaluation is not an isolation or authentication boundary.
- Exact lexical support is intentionally narrow; broader entailment requires a separately calibrated
  verifier and evidence.
- Attestation binds bytes and declared processing, not source correctness or deployed behavior.
- The compatibility host is process-local and has no durable checkpoint guarantee.
- No externally authored governance benchmark or independent reproduction is included in `v0.1.0`.
