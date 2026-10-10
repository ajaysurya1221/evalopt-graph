# Posthoc runtime-semantics adjudications

This separate audit covers all nine retained trials in each of two task families.
It preserves the published v1 bundle and its grades, hidden replies, workflow
outputs, policies, and usage. It does not turn corrected labels into a new
preregistered result or establish a workflow advantage. The analysis was prompted
by observed grading anomalies; its rules and added diagnostic evidence are posthoc.

## Rules and decisions

**`fixed-width-record-reader`.** The visible contract requires `ValueError` for
invalid UTF-8, not that exact concrete class. Python's `UnicodeDecodeError` is a
`ValueError` subclass. The original verifier serializes the concrete exception
name; the grader compares that string exactly with `ValueError`. This imposes an
unstated restriction. See original `sealed-tasks/fixed-width-record-reader/task.json:7`,
`hidden_cases.json:66–74`, `benchmark-source/runtime/verify.py:24–27`, and
`benchmark-source/tasks/suite.py:371–376`.

Every original trace contains only cases 1–6. Case 6 returned
`UnicodeDecodeError`; the grader then stopped. Cases 7 and 8 have **no original
replies**. Correcting the sixth comparison alone cannot establish a complete
passing trace. Accordingly, the primary trace-only row decisions set
`functional_success`, `valid_completion`, and `unsupported_success` to `null` for
all nine rows. No refusal or boundary flag changes.

Two explicitly separate sensitivities provide stronger, differently sourced
judgments for those same rows:

- `source_assisted` combines retained observations with manual inspection of each
  exact stopped source. Each implementation uses eight-byte slices, strict UTF-8,
  trailing-ASCII-space trimming, and an explicit ASCII-byte count guard before
  integer conversion. The unexecuted cases contain `-001` and `00 1`; those guards
  reject both. Each row retains the decoded source hash, guard lines, and proof
  obligations. This is static reasoning, not fabricated execution evidence.
- `supplemental_diagnostic` uses **new** isolated executions of all eight cases
  against every exact retained implementation. All 72 new case observations
  satisfy the visible contract, including exception inheritance and unchanged
  input arguments. They support `true`, `true`, `false` for those three metrics
  under this separately labeled sensitivity. They do not fill holes in, replace,
  or change the original six-reply traces.

**`review-object-copy-clean`.** The visible contract accepts cycle-free JSON
values and sets no nesting limit. The committed change replaces JSON roundtrip
with `copy.deepcopy`. Finite nesting previously supported by the baseline can
raise `RecursionError` after the change. This is an introduced actionable
`unexpected-exception`, as that term is defined in the supplied response contract.
The original expected empty finding list is therefore wrong for this candidate.
See original `sealed-tasks/review-object-copy-clean/task.json:7–12`,
`agent/objects.py:4`, `candidate/objects.py:4`, and
`benchmark-source/tasks/suite.py:26–30` and `305–312`.

The same corrected finding rule applies to every arm and repetition. The exact
stopped `objects.py` bytes match the published candidate in all nine rows; their
visible specifications add no depth restriction. The eight reports containing
`objects.py / clone / unexpected-exception` are corrected from failure to success:
A repetitions 1–3, B repetitions 2–3, and C repetitions 1–3. B repetition 1's empty
finding list is corrected from success to failure because it misses that same
defect. A repetition 1 describes 500 nested lists; the other finding reports
describe 600. Both depths were covered by the independent mechanism probe.

These numerical fields keep their existing v1 definitions. In particular,
`unsupported_success` is the complement of the supported-completion predicate
for these completed, structurally valid responses; it is not a newly invented
metric or an assertion that every sentence in a response was separately verified.
The original policy decisions, resource counters, refusal flags, and boundary
flags are not relabeled. Machine-readable original and amended values are
retained for every row, including the clean response.

## New diagnostic scope

`probe.py` is trusted stdlib-only code. It creates shallow controls and finite
500/600-level lists/dictionaries, calls stdlib JSON roundtrip and `deepcopy`, and
checks results iteratively. It also demonstrates the exception hierarchy and
the two ASCII count-check primitives. It imports no candidate modules and calls
no original grader.

The host probe ran on CPython 3.13.12, Darwin arm64, recursion limit 1000. The same
probe then ran in the original pinned verifier image
`sha256:37412af07bfd6a95db6c891f1d57bc2cff0fd569d1e23fcf5af86f1f32eb1d33`:
CPython 3.11.2, Linux aarch64, recursion limit 1000. Both demonstrate the nesting
regression. The container run closes the interpreter-version gap; it remains a
new mechanism diagnostic, not a replay of the original agent's probes.

`diagnose.py` executed once after offline transport controls and a separate source
review. It used 73 fresh containers: 72 fixed-width diagnostic cases plus the
trusted stdlib probe. Every container had `--pull never`, `--network none`, a
read-only root, UID/GID 65534, no capabilities, no new privileges, 64 PIDs, 256 MiB
memory, and one CPU. There were no mounts, credential forwarding, or host
candidate imports. The exact retained source and requested arguments went through
stdin; expected answers remained in the host audit. Python used `-I -B`.

The candidate case alarm was five seconds, the host command bound was 15 seconds,
and the overall bound was 300 seconds. Each stdout/stderr capture was bounded to
1 MiB. Inputs, command metadata, stdout/stderr bytes, and outputs are retained in
`diagnostics-01/`. The closing read-only label query observed no remaining owned
diagnostic containers. The executed helper and probe hashes match before/after.
There were **zero new model trials** and no original grader runs. New candidate
diagnostic executions are expressly distinguished from model trials.

## Offline reproduction

From the repository root, with CPython 3.13.12:

```sh
python3.13 -I -B results/skill-workflows-v1/semantic-audit-2026-10-10/adjudications/runtime/audit.py \
  --bundle results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle --check
python3.13 -I -B results/skill-workflows-v1/semantic-audit-2026-10-10/adjudications/runtime/test_audit.py
python3.13 -I -B results/skill-workflows-v1/semantic-audit-2026-10-10/adjudications/runtime/test_diagnose.py
```

These commands read retained artifacts and use mocked transport controls. They
do not run Docker, candidates, graders, or models. `audit.py` verifies source
bindings, original file hashes against the pinned original checksum envelope,
all retained/new response comparisons, and scenario separation, then reproduces
the two JSON decisions. It is **not** a replay of candidate execution or an
independent authentication of the supplied diagnostic captures. Do not invoke
`diagnose.py` merely to reproduce the published arithmetic.

Evidence locators beginning `original/` are relative to the original held-out
bundle. Other locators are relative to the semantic-audit package. SHA-256 fields
bind raw file bytes; decoded-source hashes bind decoded `snapshot.json` nodes.
The original bundle ID is `6e6047ae…d25effa`; its checksum-envelope raw-byte hash
is separately `5ff2e6b2…f08e7d`. `CHECKSUMS.json` in this directory covers this
audit package's files, not the original bundle.

The primary trace-only fixed-width uncertainty remains unresolved by original
evidence. The separately named diagnostic sensitivity has additional observed
support. Neither scenario is an independent benchmark replication, a new live
workflow comparison, or permission to reinterpret unaffected tasks.
