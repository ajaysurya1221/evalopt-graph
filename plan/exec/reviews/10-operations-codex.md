REVIEW 10-operations — Reviewer Astra (independent Codex verification agent) | Verdict ACCEPT

## Target and scope

Review of the operational working-tree amendment over control HEAD `29da14b2805d33dac184dc75ca1fc9ed2d5a96a0`, identified by these exact file SHA-256 values:

- `plan/exec/supervise.py`: `045c4b0fa27c88f26ad66671dcb2019e336740e8d65a5c85d27b6ff9934d9d4d`.
- `plan/exec/DECISIONS.md`: `97ca324e5f3e6a6cf62ea345f3fc1fb6a78a931b14dacc8652e3cf07453e0aff`.

This accepts the bounded tool-roster amendment and its operational disclosure. It does not accept the failed integration review, approve product changes or establish a publication decision. The patch was not yet part of the inspected publication candidate; fresh Fable review remains a separate merge gate.

## Findings by severity

No defect requiring revision found within this amendment. Required changes: none.

## Verification

The code diff is exactly one argument pair: `--tools Bash,Read,Write,Edit,Glob,Grep`. Removing that single inserted line reproduces the previous supervisor bytes exactly. Classifier, expected model/provider, requested turn flag, external timeout, process-group cleanup, scope checks, admission deadlines and immutable-record checks are unchanged. The executed command, including the new flag, is retained in each native start receipt.

I checked installed `claude --help`: its `--tools` option explicitly selects names from the built-in tool set and documents the same comma-separated syntax. The chosen roster excludes Agent/Task/WebFetch, while keeping the existing `--safe-mode` setting. As the new decision text correctly states, Bash still permits broad execution; this is neither a security sandbox nor proof that all possible auxiliary model use is prevented.

I reran `python3 -B -m unittest discover -s plan/exec/tests`: 11 tests passed, no skips. A separate in-memory negative control reused the first failed attempt's mixed modelUsage, supplied otherwise successful native status and an accepted REVIEW header, and verified the classifier still returns PARTIAL with model_identity as its sole reason. No classifier or test-source change was made.

## First failed review, preserved

The original `10-integration-review` start receipt requested Fable selector `claude-fable-5-1[1m]`, high effort and max-turns 20. Native output reports `error_max_turns`, is_error true and num_turns 21; the process exited 1 after 216.179 seconds. Its modelUsage contains both first-party `claude-fable-5-1` and `claude-haiku-4-5-20251001`. The finish receipt correctly classifies PARTIAL for nonzero_exit, native_failure, model_identity and missing_or_nonaccepted_report. Termination was confirmed with no surviving process-group children.

The terminal JSON does not establish why the auxiliary model entry appeared, and I infer no Agent, WebFetch, compaction or routing cause. Requested CLI max-turns and observed num_turns remain separate native counters; their difference is not independently treated as a proven supervisor cap violation. No successful review or approved model substitution is inferred.

Original native receipt SHA-256: `7d6055caf9714c0e2da1e1f8a465918e060b81eac1f071927857a30a9e950757`. Original finish receipt SHA-256: `99d13fbd58c894b3565d797e5a927b32f1f4ee6b3d23b1a389771201221c913c`.

## Exact-roster probe, observed

The later `10-tool-roster-probe` start receipt includes the exact new tools argument and unchanged model/safe-mode/provider approach; it requests high effort and max-turns 3. Native output records subtype success, is_error false, num_turns 3 and only canonical first-party `claude-fable-5-1`. Exit is 0, no timeout, termination confirmed, no leftover children, 17.389 seconds elapsed; the supervisor returns DONE with no reasons. The required REPORT exists and limits its claim to the directory-read probe. Effective effort is not exposed in terminal JSON; only the high request is observable here.

Probe native receipt SHA-256: `875d4da37444cb0eefcd625348764df2edc6a7f5697075ad754ed9e091b655ee`. Probe finish receipt SHA-256: `1446d7028ccb5dee31d956a16c54ddfb450aa3e4ca4954c917143dc33765b236`. This finite invocation demonstrates that the actual flag is accepted and this probe stayed within the required native model identity. It does not guarantee future calls will lack auxiliary usage; strict per-attempt classification must continue.

## Limits and follow-ups

The original failure remains retained and unaccepted. Split follow-up source and artifact reviews must each produce their own accepted record and pass unchanged native gates; this review cannot substitute for them. No source/code/ref edit, model call, credential read or network mutation was performed. The review used only local help, receipts, source inspection and offline controls; an initial read-only test-file lookup used a nonexistent filename before the actual test files were located, without changing any evidence.
