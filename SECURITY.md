# Security policy

Evalopt sits on an acceptance boundary. Security reports are welcome, especially when they concern
decision integrity, record authorization, replay divergence, parser ambiguity, evidence substitution,
or ways untrusted host state can influence a kernel decision.

## Supported versions

| Version | Supported |
| --- | --- |
| `0.1.x` | Yes |
| `< 0.1` | No |

Only the latest patch release receives security fixes.

## Report a vulnerability

Use [GitHub's private vulnerability reporting](https://github.com/ajaysurya1221/evalopt-graph/security/advisories/new).
Please do not open a public issue, discussion, or pull request for an undisclosed vulnerability.

Include, when possible:

- the affected version or commit;
- the violated security or trust-boundary assumption;
- a minimal reproducer and the observed decision or record;
- expected impact and required attacker capabilities; and
- any suggested mitigation or disclosure constraints.

Do not include real credentials, private repository contents, personal data, or third-party secrets.
Use synthetic evidence and scrubbed traces in reproductions.

## What to expect

- Acknowledgement within three business days.
- An initial assessment and next-step update within seven business days.
- Coordinated disclosure after a fix is available, with credit if requested.

These are targets, not a service-level agreement. Complex reports may take longer, but material status
changes will be communicated through the private advisory.

## Security boundary

The stable kernel performs deterministic in-process evaluation. It is **not** a sandbox, retrieval
engine, secret store, signature system, model monitor, or semantic truth oracle. Hosts must isolate
untrusted producers, authenticate observations where needed, and protect controller policy and
authorized-record lists. Reports that demonstrate a kernel invariant violation are in scope; general
prompt injection or host-runtime compromise without a kernel bypass may belong with the affected host.
