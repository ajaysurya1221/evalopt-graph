# Kernel boundary diagrams

The graph loop is a deprecated host adapter. The stable architecture is the smaller policy boundary:

```mermaid
flowchart LR
    H[Host runtime<br/>model · tools · edits · retries] --> O[Immutable observations]
    R[Trusted retrieval adapter] --> M[Evidence material]
    P[Controller policy] --> A[EvidenceAuthority]
    M --> A
    A --> E[Attestation + support record]
    O --> I[AcceptanceInput]
    E --> I
    P --> G[evaluate_acceptance]
    I --> G
    G --> D{AcceptanceDecision}
    D -->|ACCEPTED| OK[Host may accept]
    D -->|BLOCKED| B[Policy block]
    D -->|UNVERIFIED| U[Evidence incomplete]
    D -->|UNSUPPORTED| N[Required mechanism absent]
    D -->|FAILED| F[Observed or malformed failure]
```

Harbor integration keeps experiment ownership outside the kernel:

```mermaid
flowchart LR
    T[Harbor task] --> C[Harbor coding agent]
    C --> W[Stopped workspace + ATIF]
    W --> V[Separate Harbor verifier]
    V --> U[U: no policy]
    V --> M[M: one-screen minimum]
    V --> G[G: evalopt kernel]
    U --> P[Policy artifact + reward.json]
    M --> P
    G --> P
    W -->|after Harbor freezes output| H[Separately sealed grader]
    H --> Q[Grade artifact]
    P --> J[Preregistered analysis join]
    Q --> J
```

The grader runs after generation and policy-artifact freezing. Its result is separate and is never input
to the agent, observation builder, or kernel.
