# Development pilot incidents and reproduction

These are development observations, not evidence of a workflow advantage. No
held-out or transfer model outcomes were used to make these repairs.

## Harbor secret scrubbing corrupted numeric telemetry

The first development campaign ran from commit `c377118`. Its first stopped
output, visible observations, grade and policy decisions were retained. Harbor's
secret scrubber interpreted the nonsecret agent environment value `1` for
`CODEX_FORCE_AUTH_JSON` as a secret and replaced matching characters throughout
the native JSON logs. Exact resource accounting cannot be recovered from those
corrupted logs; its consumption is unavailable, not zero.

Commit `0d23c41` removed the redundant flag from the agent configuration. The host
environment still supplies the required authentication behavior. A no-model
scrubber control verified that numeric telemetry survives this configuration.
The original attempt remains retained and is reported separately from the second
development campaign. It is not silently discarded or represented as a held-out
infrastructure retry.

## Parent completion interrupted a child

The second development campaign uses frozen commit `0d23c41`. Nine of 36 trials
have terminal outcomes. On `pilot--interval-union--r1--A`, the parent completed
while a child remained active; CLI shutdown interrupted that child. The outcome
and policy inputs remain intact. The scheduler stopped at its accounting gate.

The retained owner-attributed records show the following **lower bounds**:

| Scope | Input tokens | Output tokens | Completed response records |
| --- | ---: | ---: | ---: |
| Parent | 101,790 | 1,065 | 8 |
| Interrupted child | 53,100 | 545 | 3 |
| Combined | 154,890 | 1,610 | 11 |

Codex 0.154.0 source records response usage after `ResponseEvent::Completed`.
Cancellation can occur before that event. A final `token_count` repeats retained
usage; agreement with the response records does not establish that an interrupted
request used no additional resources. An exact upper bound is unavailable.
See the pinned [response handling](https://github.com/openai/codex/blob/6b9826e3aa83b1a5947db50f4332cb9c65f1b340/codex-rs/core/src/session/turn.rs#L2364),
[usage persistence](https://github.com/openai/codex/blob/6b9826e3aa83b1a5947db50f4332cb9c65f1b340/codex-rs/core/src/session/turn.rs#L2857),
and [exec completion](https://github.com/openai/codex/blob/6b9826e3aa83b1a5947db50f4332cb9c65f1b340/codex-rs/exec/src/event_processor_with_jsonl_output.rs#L506).

No automatic child-join setting was found in the pinned configuration schema.
This is not a basis for retrying an agent outcome. Continuing with explicitly
partial accounting would change the registered accounting requirement and remains
unapproved. No existing attempt or frozen source has been rewritten.

## Offline reproduction

The local, sanitized nine-attempt candidate has bundle identity
`b76e84bbb267556b7c7a187f956bb0e31927c8ab69d9462c2ba74baab7c7a407`.
A fresh dependency-free Python 3.13.12 environment, with the ambient environment
cleared and the repository's kernel and benchmark sources on its import path,
verified all 131 files, reproduced the analysis, and replayed 27 policy decisions.
This verifies retained controller evidence; it is not independent repetition of
the agents or proof of complete resource accounting.

A separate read-only, network-disabled Docker challenge used Python 3.11. Its
verification correctly rejected byte-different resource aggregates: Python's
floating-point summation produced `404.83900000000006` instead of `404.839`, and
`273.14099999999996` instead of `273.141`. The recorded reports remain unchanged.
Python 3.13.12 is required for reproducing this development artifact. The current
controller now rejects interpreter drift before registration, dispatch and offline
report verification. The original frozen development source remains unchanged.
