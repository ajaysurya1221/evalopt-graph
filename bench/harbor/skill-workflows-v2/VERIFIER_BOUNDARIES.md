# Callable grading and case isolation

Production callable grading uses `verifier_container.docker_invoker` from the
trusted host. Every baseline or candidate invocation gets a fresh Docker
container. Only the stopped snapshot, the current data request, public runner
code and a private result directory are mounted. Hidden expectations, other
case inputs and the final grade remain in the host verifier.

The container has one CPU, 2 GB RAM, 128 PIDs, no network, no automatic removal
and no restart policy. It gains no additional capabilities and retains Docker's
normal seccomp policy. Its root controller invokes the candidate as UID/GID
65534 within the prepared chroot. Expected values and the private result path
are outside that chroot.

Each invocation receives an absolute host monotonic deadline before setup,
bounded by both the remaining whole-verifier budget and the case limit. Create
and pre-start inspection use that remaining budget. The host rechecks the
deadline immediately before start; setup exhaustion records `not_run` and never
starts the created container. Started cases are terminated at the same cutoff.
A separate 30-second safety window permits only termination, stopped-result
capture and cleanup; it never extends execution or admits another case. Late
inner records remain forensic artifacts and cannot produce a passing grade.

The host records ownership before creation, checks exact container, image and
label identities, and confirms the container is stopped before reading its
retained result. A detached `setsid` descendant cannot cross into the next
case: the prior container must terminate first. Process-group killing by itself
is deliberately not claimed to establish this boundary. Containers with
uncertain termination are retained for inspection, and no later invocation is
admitted. Every remaining registered case receives an explicit `not_run`
record. Creation/start/inspection timeouts, identity contradictions and durable
capture failures also stop later invocation rather than implying no side effect.

The candidate's stdout and stderr are diagnostic bytes. The runner writes its
semantic envelope through a separate inherited descriptor after the function
returns or raises. Printing a matching JSON object followed by `os._exit(0)`
therefore lacks a runner result and fails. A premature nonzero exit fails too.
JSON parsing bounds nested semantic data at 768 levels, retaining the audited
600-level copy regression while classifying excessive output without aborting
the case roster. The published authored task domains are smaller than this
measurement bound.

**This is not arbitrary in-process semantic authentication.** Introspective
Python executing inside the same interpreter can discover or tamper with that
interpreter's objects and descriptors. A separate descriptor, prebound builtins,
producer label or digest does not prove the semantic truth of arbitrary hostile
programs. The container establishes process, filesystem and observation custody
boundaries; this finite authored callable study does not establish a general
malicious-code grading sandbox. Local `trusted_fixture=True` execution is solely
for authored offline controls and makes no descendant-containment claim.

For finite-domain review tasks, a finding outside the published input catalog
is unsupported and fails the response contract. It is not an oracle outage.
An unavailable in-domain oracle or execution remains unknown. A demonstrated
in-domain defect without a frozen obligation remains a contract dispute, keeping
the original grades and requiring separate versioned analysis.

Native JSONL framing uses literal LF only. At EOF, only a syntactically
extendable strict JSON object prefix is partial. Impossible syntax, duplicate
keys, nonfinite numbers, invalid UTF-8 and non-object roots cannot acquire
partial-evidence status merely by omitting the last LF.

## Finding locations and public witnesses

Callable obligations can map both an implementation helper and the public entry
point that exposes its defect. A mapped obligation retains `id`, `path`,
`symbol` and `kinds`, and adds both fields below:

```json
{
  "supported_locations": [
    {"path": "entry.py", "symbol": "solve", "witness_module": "entry", "witness_function": "solve"},
    {"path": "helper.py", "symbol": "compute", "witness_module": "entry", "witness_function": "solve"}
  ],
  "witness_case_ids": ["case-02", "case-05"]
}
```

Each case ID resolves to an exact request in the frozen task case roster. A
helper location is supported only by a request bound to that obligation and
public callable, plus the executable baseline-pass/candidate-fail/oracle
comparison. Location metadata by itself never demonstrates a defect. Mappings
for different obligations cannot overlap on finding location, consequence kind
and request. Duplicate supported helper/entrypoint findings cover the same
obligation neutrally; a fabricated location or a helper paired with another
defect's request fails. A demonstrated direct-call counterexample outside the
mapped obligations remains a contract dispute and grants no automatic acceptance.

Mapping fields are data only, with exact keys, valid relative paths and callable
identifiers, unique locations and case IDs, and a canonical location included.
Authored QA separately validates that mapped files/symbols exist and bound cases
are real regressions; pure replay does not execute code to rediscover those
facts. Legacy single-location obligations without these two fields retain their
original direct-call interpretation. The initial scope remains callable and
structural authored reviews, not unrestricted natural-language review judgment.
