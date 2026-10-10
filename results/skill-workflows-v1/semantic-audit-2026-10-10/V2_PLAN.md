# Eval-opt v2: development priorities after the semantic audit

These are implementation hypotheses and acceptance criteria, not measured v2
improvements. Do not tune a candidate against these exposed tasks and call them
held out again. The frozen portable v1 skill and kernel remain unchanged.

## 1. Fix the measurement contract before expanding the skill

Owner: benchmark/task maintainer with a separate semantic reviewer.

Create a new grader version outside `skill-workflows-v1`. Encode exception
subclass compatibility when the visible contract specifies a base class, reject
unrelated exceptions, and retain results for every case even after a mismatch.
For reviews, grade supported introduced behaviors rather than an exact number
of finding records. Validate negative controls against baseline and candidate,
including finite boundary inputs within the stated domain.

Acceptance: the audited five tasks become development regression controls;
wrong exceptions, missed defects, fabricated extra findings and false blockers
still fail. A clean-review control must have independent evidence supporting
its claimed input domain. Retained evidence and the reference grader must have
separate versions; a changed grader never overwrites original results.

## 2. Add a typed evidence record and explicit dispute handling

Owner: portable skill maintainer and host-adapter maintainer, with separate paths.

Use a compact record with candidate identity, command, exit code, execution
state (`ran`, `not_run`, `timed_out`), evidence availability, asserted claim,
and supporting artifact. Keep requested task outcome separate: implementing a
patch and accurately reporting an unavailable prerequisite are different
contracts. Adapt these observations outside the stable kernel API.

Add one short conditional skill instruction: when a check conflicts with the
visible contract, retain the failure, show the smallest counterexample, and
report the disagreement. Do not edit the test, waive a required check, or
self-certify completion. For reviews, attach a trigger and baseline/candidate
behavior to a finding; group related symptoms when useful without suppressing
supported consequences.

Acceptance: a return-code-3 probe can be recorded as executed unsuccessfully
while its required evidence is unavailable; neither implies the suite passed.
A supported blocker satisfies only a blocker-reporting task, never a solvable
implementation task. New contract-dispute controls cover both a wrong grader
and a wrong agent; disagreement alone never earns success. Keep an optional
adapter distinct from what a prompt-only skill actually enforces.

## 3. Repair evidence capture before another live campaign

Owner: harness maintainer, outside the frozen v1 source.

Use literal newline framing for JSONL, preserve non-ASCII characters inside
records, retain completed child lifecycle/accounting evidence, and make
timeout handling produce explicit missing-artifact records. Keep command
termination, process absence and output capture as separate facts. Preserve
strict stop rules for unverifiable boundaries.

Acceptance: fault-injection controls cover U+0085 inside JSON strings, partial
records, terminated children, missing child ends, interrupted capture and
unknown usage. No missing accounting is silently treated as zero, no failure
is retried as a new task success, and uncertain process absence blocks further
admission. The v1 transfer evidence is not repaired by these new controls.

## 4. Test one added mechanism at a time on fresh tasks

Owner: evaluation designer plus independent task authors/reviewers.

Calibrate difficulty on new development tasks before freezing a new held-out
set. Include meaningful successes and failures for evidence disputes, review
coverage, constraints and bounded recovery. Compare the same baseline and
upstream bundle with portable v2; use a small preregistered ablation to isolate
the typed evidence/dispute mechanism before attempting another large study.

Acceptance: contracts and oracle controls are reviewed before candidate scores;
positive-result thresholds are compatible with the observed development
ceiling; all settings, exclusions and missing-outcome rules freeze before held-out
execution. Repetitions remain clustered within tasks. Report neutral and negative
results, and measure resource usage completely before making efficiency claims.

## What this audit does not justify

It does not justify more agents, longer prompts, model changes, relaxed gates,
or a new kernel policy as a proven improvement. Task/measurement defects are
not automatically skill defects. New independent evidence is required to
attribute gains to any v2 mechanism or to claim superiority over upstream.
