# Independent analysis review

**Verdict: ACCEPT** for the exact source and evidence identities in
[the review receipt](analysis-review.json). This is separate maintainer-agent
review, not independent human adjudication or replication of agent execution.

The reviewed aggregation retains all 432 original trial rows and changes only
the 45 explicitly adjudicated rows. The other 387 rows, original policy
decisions, task status and resource observations remain unchanged.

- Trace-only valid counts are A 141 plus 3 unresolved, B 140 plus 1 failure and
  3 unresolved, and C 141 plus 3 unresolved. The full-schedule identification
  bounds are −1.39 to +2.78 percentage points; they are not confidence intervals.
- The separately supported diagnostic projection is A 144/144, B 143/144 and
  C 144/144. C minus B is exactly 1/144, with descriptive bootstrap endpoints
  0 and 3/144. This post hoc result does not establish an upgrade.
- Excluding all five audited tasks leaves 43 tasks and 129 valid outcomes per
  arm. Its degenerate bootstrap is not proof of equivalence.
- Unchanged U/M/G cross-tabs match the README. The diagnostic projection has
  only one invalid output, which every policy accepted; that does not establish
  robust false-acceptance performance.

The final source passed 26 author tests and 24 additional independent
assertions. The latter check actual in-memory registration and arithmetic,
generated output bytes, unresolved denominators, task/cluster treatment,
unchanged rows and policy/resource boundaries, and six coherently rewritten
diagnostic provenance cases. The receipt retains their Python source.
Ruff, formatting and a local directory Gitleaks scan also passed.

Two earlier issues were resolved before acceptance: substring arm membership,
and incomplete diagnostic execution provenance. Final replay binds the exact
helper/probe bytes, inertly parsed child-program literal, complete container
command, source/arguments, all 72 case replies, start/end records and closure.
It never executes those diagnostic programs. Altering these records coherently
does not bypass the final support gate.

The reviewed README, protocol, v2 plan, repository claim qualifications and
additive CI commands preserve the distinction between frozen v1 and this
failure-informed audit. Typed evidence/dispute handling and harness fixes are
development proposals, not demonstrated skill improvements. Hashes establish
byte identity, not producer authentication.

No model, Docker, candidate or original-verifier execution occurred during
this review. Final outer-manifest sealing, public-checkout replay and hosted CI
are separate integration steps; this receipt does not claim they have passed.
