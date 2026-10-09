# Development pilot grading repair

The current verifier rejects nonfinite JSON values that the original pilot
verifier could accept. This is a **scoring change**, not unchanged semantics.
Before held-out registration, all 36 stopped pilot outputs require a separate,
source-bound regrade. The live pilot continues to use its original frozen grader.

## Reason and scope

The original JSON parser accepts `NaN` and allows a later duplicate field to
replace it. For example, a discarded nonfinite summary followed by an otherwise
valid response can pass the original parser. The current parser rejects the
nonfinite value before that replacement. The same difference affects hidden
function replies. This repair enforces the visible JSON contract; it adds no
task requirement.

A separate role reviewed parser behavior without inspecting live candidate
scores or sealed held-out task contents. Development task payloads and their
modes remained identical. The public regression controls in
`tests/test_skill_workflow_pilot_regrade.py` cover malformed JSON and preserve
the original grades when producing separate regrade evidence. These controls
are not additional benchmark trials or evidence of a workflow advantage.

| Grading identity | Original pilot | Current implementation |
| --- | --- | --- |
| Task suite tree | `a9c77b49e7fb0e425b644b9dbf8e19dc70ecaf37e91895765a1b3d248d24b94f` | `5e6321baf59c82ebe91508d8c52a8ebe72780ecb1201363e34cec5514dab546d` |
| Verifier source | `e9977f6b7073d818501427a8997aa0a6933d473c3f364bc65546f8b490e9c379` | `856fd980d1a9d662c20e3567870d337ca775fc7c48e86f036d50b9735a35a712` |

## Required evidence

The regrade must bind the original registration, complete outcome export,
accounting amendment, all stopped artifacts, reconstructed initial context,
both grading identities, executor source and pinned verifier image. Initial
context is reconstructed from the trusted original materializer and checked
against retained context. An unbound private grading file is insufficient.

Candidate execution takes place in a fresh network-disabled Docker verifier,
with candidate code confined to an unprivileged chroot. The host does not import
candidate files. The regrade retains hidden-case replies and explicit metric
differences for every original trial, including unchanged grades. It preserves
original status handling and reports any verifier failure rather than treating it
as a new coding-agent attempt.

The original grade, finish, accounting, visible evidence and U/M/G decisions stay
unchanged. New hidden results never enter an acceptance-policy input. The regrade
uses no additional model trials and does not authorize retrying a failed task.

Held-out progression requires the explicit compatibility verdict
`regraded_stopped_outputs`, bound to the complete regrade registration and evidence.
An `unchanged_semantics` receipt cannot describe this repair. The held-out freeze
must retain and verify the safe regrade package and its identities.

## Reproduction limits

Public replay checks grade calculations against retained hidden replies and
checks the original artifact bindings. It is distinct from the recorded isolated
candidate execution. Neither establishes independent authentication or independent
replication. Original pilot grades predate hidden-reply retention, so their public
bundle supports report arithmetic and policy replay, not reconstruction of those
original hidden replies.

Execution and grade differences remain pending until the complete regrade
evidence is retained and reviewed. The development pilot cannot establish the
held-out comparison's positive, neutral or negative headline.
