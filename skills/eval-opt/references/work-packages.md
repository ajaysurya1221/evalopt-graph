# Work packages

For a small fix, keep one plan item. For larger work, give each package an
observable behavior rather than a disconnected implementation layer. A command
line task need not invent a user interface or database. Keep inseparable changes
together, or make their compatibility and integration dependencies explicit.

Use this compact contract where applicable:

```text
Package: identifier and observable behavior
Owner: one worker or the main agent
Allowed paths: specific files or narrow directories
Excluded paths: frozen inputs and unrelated changes
Dependencies: verified outputs needed before starting
Acceptance: input or trigger -> expected observable result
Verify: command or inspection procedure and working directory
Evidence: observation or artifact location
Cut line: work intentionally outside this package
State: pending, in progress, verified, or blocked with reason
```

Every requested criterion needs an owner and a verification path. Dependencies
must be acyclic. Parallel editing requires disjoint ownership; shared writes
need one owner or an explicit sequence. Give workers enough current context to
start without inventing requirements, and warn them about concurrent work.

Check dependency artifacts before starting dependent work. A completion message
does not establish that a dependency passes. Preserve each repository's own
environment and history. A blocked package need not prevent unrelated authorized
work from progressing.

Verify integration against the actual combined candidate before completion.
Package success does not establish hosted CI, release, or publication success.
All packages consume the same overall budget. This reference neither configures
an issue tracker nor authorizes publishing tickets.

Behavior-first slicing and explicit dependencies adapt upstream ideas identified
in [ATTRIBUTION.md](../ATTRIBUTION.md).
