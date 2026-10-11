"""Bounded public evidence projection; no filesystem reads or candidate execution.

Call only after independent endpoint QA and frozen native replay. Digests and
cross-record checks establish correspondence, not authenticated producers.
"""

from __future__ import annotations

import hashlib
import json
import re

SCHEMA = "evalopt.v3-public-trial-evidence.v1"
RAW_PATHS = {
    "start": "start.json",
    "grade": "grade.json",
    "usage": "usage.json",
    "visible_policy": "visible-policy.json",
    "result": "runtime/result.json",
    "initial_observation": "runtime/initial-visible/observation.json",
    "post_stop_observation": "runtime/post-stop-observation.json",
    "prompt_receipt": "runtime/prompt-receipt.json",
    "prompt": "runtime/prompt.txt",
    "verification": "runtime/verifier/verification.json",
    "controller_failure": "controller-failure.json",
    "infrastructure": "infrastructure.json",
}
INVOCATION_STATES = {"returned", "raised", "timeout", "malformed", "error", "not_run"}
SKIP_REASONS = {
    "prior_case_boundary_unconfirmed",
    "verifier_budget_exhausted",
    "case_boundary_unconfirmed",
    "invoker_evidence_unavailable",
    "case_setup_deadline",
    "case_runner_evidence_unavailable",
    "required_evidence_unavailable",
    "docker_inspection_before_container_creation",
    "unresolved_required_evidence",
}
CASE_REASONS = SKIP_REASONS | {
    "not_run",
    "candidate_timeout",
    "candidate_malformed",
    "candidate_error",
    "arguments_mutated",
    "contract_satisfied",
    "contract_mismatch",
}
WITNESS_REASONS = {
    "malformed_finding",
    "malformed_witness",
    "witness_outside_published_domain",
    "verifier_budget_exhausted",
    "witness_oracle_or_execution_unavailable",
    "case_boundary_unconfirmed",
    "prior_case_boundary_unconfirmed",
    "wrong_finding_location",
    "incomplete_witness_execution",
    "introduced_violation",
    "witness_does_not_demonstrate_claim",
}


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def same(a, b):
    return canonical(a) == canonical(b)


def parse(raw):
    need(type(raw) is bytes and len(raw) <= 64 * 1024**2, "bounded raw JSON bytes required")

    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate JSON key")
            out[key] = value
        return out

    def reject(_):
        raise ValueError("nonfinite JSON")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject)
    canonical(value)
    return value


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def token(value):
    need(
        type(value) is str and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}", value),
        "nonpublic registered token",
    )
    return value


def enum(value, choices, message):
    need(type(value) is str and value in choices, message)
    return value


def tri(value):
    need(type(value) is bool or value is None, "boolean or null required")
    return value


def invocation_projection(actual):
    """Raw invocation presence and semantic usability are different facts."""
    if actual is None:
        return {
            "execution_state": None,
            "semantic_result": None,
            "semantic_evidence_availability": "unavailable",
            "container_boundary": "unavailable",
            "stdout_stderr_truncated": None,
            "semantic_output_truncated": None,
        }
    need(type(actual) is dict, "invalid invocation")
    state = enum(actual.get("state"), INVOCATION_STATES, "unknown invocation state")
    boundary = actual.get("container_boundary")
    boundary_state = (
        "unavailable"
        if boundary is None
        else enum(
            boundary.get("status"), {"confirmed", "not_started", "unconfirmed"}, "invalid case boundary"
        )
    )
    return {
        "execution_state": "not_run" if state == "not_run" else "timed_out" if state == "timeout" else "ran",
        "semantic_result": state,
        "semantic_evidence_availability": "complete" if state in {"returned", "raised"} else "unavailable",
        "container_boundary": boundary_state,
        "stdout_stderr_truncated": tri(actual.get("output_truncated")),
        "semantic_output_truncated": tri(actual.get("semantic_truncated")),
    }


def _case(case_id, role, status, source, actual=None, evaluation=None, raw_hash=None):
    if evaluation is not None:
        need(
            type(evaluation) is dict and set(evaluation) == {"verdict", "reason"},
            "invalid retained case evaluation",
        )
        verdict = enum(evaluation["verdict"], {"pass", "fail", "unknown"}, "unknown case verdict")
        reason = enum(evaluation["reason"], CASE_REASONS, "nonpublic case reason")
    else:
        verdict, reason = None, None
    return {
        "case_id": case_id,
        "role": role,
        "projection_status": status,
        "source": source,
        "raw_record_sha256": raw_hash,
        "record_availability": "retained"
        if raw_hash
        else "not_applicable"
        if status == "not_executed_by_review_contract"
        else "unavailable",
        **invocation_projection(actual),
        "verdict": verdict,
        "reason_code": reason,
    }


def is_digest(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def claim_projection(response, command, raw_hash):
    """Project claimed fields, including malformed entries, without judging truth."""
    base = {"source": "agent_claim", "raw_source_sha256": raw_hash}
    if response is None:
        return {
            **base,
            "response_status_state": "unavailable",
            "response_status": None,
            "status": "unavailable",
            "checks_count": None,
            "checks": [],
        }
    if type(response) is not dict:
        return {
            **base,
            "response_status_state": "malformed",
            "response_status": None,
            "status": "malformed",
            "checks_count": None,
            "checks": [],
        }
    value = response.get("status")
    status_typed = type(value) is str and value in {"completed", "blocked"}
    base.update(
        response_status=value if status_typed else None,
        response_status_state="typed"
        if status_typed
        else "missing"
        if "status" not in response
        else "malformed",
    )
    if "checks" not in response:
        return {**base, "status": "unavailable", "checks_count": None, "checks": []}
    checks = response["checks"]
    if type(checks) is not list or len(checks) > 4096:
        return {
            **base,
            "status": "malformed",
            "checks_count": len(checks) if type(checks) is list else None,
            "checks": [],
        }
    projected = []
    fields = {"observation_id", "phase", "command", "execution_state", "exit_code", "evidence_availability"}
    for index, check in enumerate(checks):
        valid = (
            type(check) is dict
            and set(check) == fields
            and is_digest(check["observation_id"])
            and type(check["phase"]) is str
            and check["phase"] in {"initial", "post_stop"}
            and type(check["command"]) is list
            and bool(check["command"])
            and all(type(part) is str for part in check["command"])
            and type(check["execution_state"]) is str
            and check["execution_state"] in {"ran", "not_run", "timed_out", "interrupted"}
            and type(check["evidence_availability"]) is str
            and check["evidence_availability"] in {"complete", "partial", "unavailable"}
            and (
                type(check["exit_code"]) is int
                if check["execution_state"] == "ran"
                else check["exit_code"] is None
            )
            and (check["execution_state"] != "not_run" or check["evidence_availability"] == "unavailable")
        )
        projected.append(
            {
                "ordinal": index + 1,
                "shape_status": "typed" if valid else "malformed",
                "observation_id": check["observation_id"] if valid else None,
                "phase": check["phase"] if valid else None,
                "registered_command": same(check["command"], command) if valid else None,
                "execution_state": check["execution_state"] if valid else None,
                "exit_code": check["exit_code"] if valid else None,
                "evidence_availability": check["evidence_availability"] if valid else None,
            }
        )
    return {
        **base,
        "status": "typed" if all(c["shape_status"] == "typed" for c in projected) else "malformed",
        "checks_count": len(checks),
        "checks": projected,
    }


def prompt_projection(visible, data, refs, raw, aid, ledger):
    """Check retained prompt/phase correspondence; never expose prompt contents."""
    prompt = visible.get("prompt_receipt")
    if prompt is None:
        need(data.get("result") is None, "executed runtime requires retained prompt")
        need(
            not visible["supplied_observation_ids"] and not ledger["initial"],
            "missing supplied prompt receipt",
        )
        need(
            not ({"prompt", "prompt_receipt", "initial_observation"} & set(raw)),
            "unexpected pre-dispatch sources",
        )
        return {
            "status": "unavailable",
            "prompt_sha256": None,
            "prompt_bytes": None,
            "initial_observation_sha256": None,
            "raw_record_sha256": None,
        }
    from evalopt_v3.records import digest

    fields = {
        "schema_version",
        "kind",
        "attempt_id",
        "arm",
        "initial_snapshot_sha256",
        "supplied_observation_ids",
        "initial_observation_sha256",
        "prompt_sha256",
        "prompt_bytes",
    }
    need(type(prompt) is dict and set(prompt) == fields, "unexpected prompt receipt fields")
    need(
        {"prompt", "prompt_receipt", "initial_observation", "post_stop_observation"} <= set(raw),
        "runtime phase sources missing",
    )
    need(
        prompt["schema_version"] == "evalopt-workflows-v3/1"
        and prompt["kind"] == "predispatch_prompt"
        and prompt["attempt_id"] == aid
        and prompt["arm"] == "B",
        "foreign prompt receipt",
    )
    need(
        set(ledger["initial"]) == {"required"} and set(ledger["post_stop"]) == {"required"},
        "runtime phase roster incomplete",
    )
    initial = ledger["initial"]["required"]
    need(
        same(prompt, data["prompt_receipt"])
        and same(initial, data["initial_observation"])
        and same(ledger["post_stop"]["required"], data["post_stop_observation"]),
        "separate phase receipt differs",
    )
    need(
        is_digest(prompt["initial_snapshot_sha256"])
        and prompt["initial_snapshot_sha256"] == initial["candidate_id"]
        and same(prompt["supplied_observation_ids"], visible["supplied_observation_ids"])
        and prompt["initial_observation_sha256"] == digest(initial),
        "prompt initial binding differs",
    )
    need(
        type(prompt["prompt_bytes"]) is int
        and 0 < prompt["prompt_bytes"] <= 4 * 1024**2
        and prompt["prompt_bytes"] == len(raw["prompt"])
        and prompt["prompt_sha256"] == sha(raw["prompt"]),
        "prompt bytes differ",
    )
    return {
        "status": "retained",
        "prompt_sha256": prompt["prompt_sha256"],
        "prompt_bytes": prompt["prompt_bytes"],
        "initial_observation_sha256": prompt["initial_observation_sha256"],
        "raw_record_sha256": refs["prompt_receipt"],
    }


def report_projection(grade, verification):
    """Same runtime-eligibility projection as the frozen report, not a new grade."""
    names = (
        "valid_completion",
        "functional_success",
        "contract_dispute",
        "unsupported_success",
        "incorrect_refusal",
        "boundary_violation",
        "raw_valid_completion",
        "raw_functional_success",
        "runtime_identity_verified",
        "boundary_preserved",
        "claims_supported",
        "lifecycle_verified",
        "timed_out",
        "verifier_status",
        "missing_reason",
        "response_valid",
    )
    if grade is None:
        return {name: None for name in names}
    outcome = grade["outcome"]
    native_grade = {} if verification is None else verification["grade"]
    tri(grade.get("runtime_identity_verified"))
    eligible = grade.get("runtime_identity_verified") is True
    valid = outcome["valid_completion"] if eligible or outcome["timed_out"] else None
    reason = (
        None
        if valid is not None
        else enum(
            grade.get("reason") or "unresolved_required_evidence", SKIP_REASONS, "nonpublic missing reason"
        )
    )
    return {
        "valid_completion": valid,
        "functional_success": outcome["functional_success"] if eligible else None,
        "contract_dispute": outcome["contract_dispute"],
        "unsupported_success": tri(native_grade.get("unsupported_success")) if eligible else None,
        "incorrect_refusal": tri(native_grade.get("incorrect_refusal")) if eligible else None,
        "boundary_violation": None
        if outcome["boundary_preserved"] is None
        else not outcome["boundary_preserved"],
        "raw_valid_completion": outcome["valid_completion"],
        "raw_functional_success": outcome["functional_success"],
        "runtime_identity_verified": eligible,
        "boundary_preserved": outcome["boundary_preserved"],
        "claims_supported": outcome["claims_supported"],
        "lifecycle_verified": outcome["lifecycle_verified"],
        "timed_out": outcome["timed_out"],
        "verifier_status": outcome["verifier_status"],
        "missing_reason": reason,
        "response_valid": tri(native_grade.get("response_valid")),
    }


def project_trial(registration, scheduled, *, attempt, state, raw, retained_records=()):
    """Project one registered row from explicitly provided retained raw bytes.

    `task` is the frozen task.json; other named blobs use RAW_PATHS. Individual
    verifier records are passed in their original case-NNNN order. Callers may
    not mix campaigns, retries or substitute semantic equality for raw seals.
    """
    from evalopt_v3.accounting import derive_usage, validate_usage
    from evalopt_v3.records import validate_record
    from evalopt_v3.reporting import validate_ledger

    need(type(raw) is dict and set(raw) <= set(RAW_PATHS) | {"task", "final"}, "unknown raw artifact role")
    need("task" in raw, "frozen task required")
    need(type(state) is str and state in {"finalized", "unfinalized", "unstarted"}, "invalid row state")
    pin = registration["registration_sha256"]
    need(type(pin) is str and re.fullmatch(r"[0-9a-f]{64}", pin), "invalid registration digest")
    need(any(same(scheduled, row) for row in registration["schedule"]), "unregistered scheduled row")
    token(scheduled["task_id"])
    need(
        type(scheduled["trial_id"]) is str
        and re.fullmatch(r"difficulty--[a-z0-9-]+--r[12]--B", scheduled["trial_id"]),
        "nonpublic trial identity",
    )
    need(
        (attempt is None) if state == "unstarted" else (type(attempt) is int and attempt in (1, 2)),
        "invalid attempt",
    )
    if "prompt" in raw:
        need(
            type(raw["prompt"]) is bytes and len(raw["prompt"]) <= 4 * 1024**2, "bounded raw prompt required"
        )
    data = {key: parse(value) for key, value in raw.items() if key != "prompt"}
    refs = {key: sha(value) for key, value in raw.items()}
    task = data["task"]
    need(task["task_id"] == scheduled["task_id"], "wrong frozen task")
    contract = enum(
        task["task_contract"], {"implementation", "review", "blocker_report"}, "unknown task contract"
    )
    cases = task.get("cases", [])
    need(type(cases) is list, "case roster required")
    ids = [token(case["case_id"]) for case in cases]
    need(len(set(ids)) == len(ids), "duplicate registered case")
    obligations = [token(o["id"]) for o in task.get("defect_obligations", [])]
    if state == "unstarted":
        need(set(raw) == {"task"} and not retained_records, "unstarted trial cannot carry observed artifacts")
    else:
        need("start" in data, "started trial missing start")
        start = data["start"]
        need(
            same(
                start,
                {
                    "row": scheduled,
                    "registration_sha256": pin,
                    "attempt": attempt,
                    "attempt_id": scheduled["trial_id"] + f"--attempt-{attempt}",
                },
            ),
            "attempt start does not bind registration",
        )
    aid = scheduled["trial_id"] + f"--attempt-{attempt}" if attempt is not None else None
    if state == "finalized":
        need(
            {"start", "final", "grade", "usage", "visible_policy"} <= set(data),
            "finalized trial missing required projection sources",
        )
        final = data["final"]
        need(final["registration_sha256"] == pin and same(final["row"], scheduled), "foreign final")
        for key in set(raw) & set(RAW_PATHS):
            need(
                final["files"].get(RAW_PATHS[key]) == refs[key],
                "provided source bytes differ from final seal",
            )
        need(same(final["outcome"], data["grade"]["outcome"]), "grade/final outcome mismatch")
        validate_record(data["grade"]["outcome"])
        need(data["grade"]["outcome"]["attempt_id"] == aid, "foreign grade")
        visible = data["visible_policy"]["visible"]
        need(visible["attempt_id"] == aid, "foreign visible observations")
        usage = validate_usage(data["usage"])
        result = data.get("result")
        if result is not None:
            need(result["attempt_id"] == aid and same(result["usage"], usage), "foreign result or usage")
            verification = result["verification"]
            need(same(verification, data["grade"]["raw_verification"]), "result/grade verification mismatch")
            if verification is not None:
                need(
                    "verification" in data and same(verification, data["verification"]),
                    "separate verifier record missing or differs",
                )
        else:
            need(
                "infrastructure" in data
                and data["infrastructure"]["classification"] == "docker_inspection_before_container_creation",
                "final missing runtime is not classified pre-dispatch failure",
            )
            verification = None
        case_records = [] if verification is None else verification["case_records"]
        witnesses = [] if verification is None else verification["review_witnesses"]
        records = list(retained_records)
        need(len(records) == len(case_records) + len(witnesses), "retained verifier record roster differs")
        record_hashes = []
        for index, (blob, expected) in enumerate(zip(records, case_records + witnesses, strict=True)):
            need(same(parse(blob), expected), "retained verifier record content differs")
            digest = sha(blob)
            need(
                final["files"].get(f"runtime/verifier/case-{index:04d}.json") == digest,
                "individual verifier record seal differs",
            )
            record_hashes.append(digest)
    else:
        need(
            "final" not in data and not retained_records,
            "unfinalized row cannot publish sealed verifier evidence",
        )
        usage, result, verification, case_records, witnesses, record_hashes, visible = (
            derive_usage({}),
            None,
            None,
            [],
            [],
            [],
            None,
        )
    projected_cases = []
    case_map = {}
    for index, record in enumerate(case_records):
        cid = record["case_id"]
        need(cid in ids and cid not in case_map, "unregistered or duplicate case result")
        need(record.get("record_type") == "case_evidence", "wrong case record type")
        case_map[cid] = (record, record_hashes[index])
    unrun = (
        {}
        if state != "finalized"
        else {item["case_id"]: item for item in data["grade"].get("unrun_case_roster", [])}
    )
    need(
        len(unrun) == (0 if state != "finalized" else len(data["grade"].get("unrun_case_roster", []))),
        "duplicate explicit unrun case",
    )
    need(set(unrun) <= set(ids) and not (set(unrun) & set(case_map)), "unrun roster disagrees with cases")
    for cid in ids:
        role = "review_oracle_reference" if contract == "review" else "callable_case"
        if cid in case_map:
            record, digest = case_map[cid]
            projected_cases.append(
                _case(
                    cid,
                    role,
                    "recorded_case",
                    "retained_case_record",
                    record["invocation"],
                    record["evaluation"],
                    digest,
                )
            )
        elif cid in unrun:
            reason = enum(unrun[cid]["reason"], SKIP_REASONS, "nonpublic unrun reason")
            need(unrun[cid]["execution_state"] == "not_run", "invalid explicit unrun state")
            projected_cases.append(
                _case(
                    cid,
                    role,
                    "controller_recorded_not_run",
                    "retained_grade_record",
                    {"state": "not_run"},
                    {"verdict": "unknown", "reason": reason},
                    refs["grade"],
                )
            )
        elif contract == "review" and verification is not None:
            projected_cases.append(_case(cid, role, "not_executed_by_review_contract", "derived_roster_join"))
        else:
            projected_cases.append(
                _case(
                    cid,
                    role,
                    "trial_unstarted" if state == "unstarted" else "required_case_record_missing",
                    "derived_roster_join",
                )
            )
    projected_witnesses = []
    for index, witness in enumerate(witnesses):
        need(witness.get("record_type") == "review_witness", "wrong witness type")
        reason = enum(witness["reason"], WITNESS_REASONS, "nonpublic witness reason")
        covered = witness["obligation_ids"]
        need(
            type(covered) is list and len(set(covered)) == len(covered) and set(covered) <= set(obligations),
            "unknown witness obligation",
        )
        projected_witnesses.append(
            {
                "witness_ordinal": index + 1,
                "supported": tri(witness["supported"]),
                "obligation_ids": covered,
                "reason_code": reason,
                "raw_record_sha256": record_hashes[len(case_records) + index],
                "baseline": invocation_projection(witness.get("baseline")),
                "candidate": invocation_projection(witness.get("candidate")),
                "structural_manifest_evidence": "baseline_manifest" in witness
                and "candidate_manifest" in witness,
            }
        )
    observations = []
    prompt = {
        "status": "unavailable",
        "prompt_sha256": None,
        "prompt_bytes": None,
        "initial_observation_sha256": None,
        "raw_record_sha256": None,
    }
    supplied_ids = []
    if visible is not None:
        ledger = validate_ledger(
            visible["observations"],
            attempt_id=aid,
            check_roster=[{"check_id": "required", "command": task["visible_command"]}],
            supplied_observation_ids=visible["supplied_observation_ids"],
            initial_candidate_id=visible["initial_snapshot_sha256"],
            post_stop_candidate_id=visible["snapshot_sha256"],
        )
        supplied_ids = list(visible["supplied_observation_ids"])
        prompt = prompt_projection(visible, data, refs, raw, aid, ledger)
        for index, observed in enumerate(visible["observations"]):
            observations.append(
                {
                    "source": "controller_observation",
                    "ordinal": index + 1,
                    "check_id": "required",
                    "phase": observed["phase"],
                    "observation_id": observed["observation_id"],
                    "supplied_to_agent": observed["observation_id"] in supplied_ids,
                    "execution_state": observed["execution_state"],
                    "exit_code": observed["exit_code"],
                    "evidence_availability": observed["evidence_availability"],
                    "artifact_hashes": [
                        {"ordinal": i + 1, "sha256": observed["artifact_sha256"][name]}
                        for i, name in enumerate(observed["artifact_refs"])
                    ],
                    "raw_source_sha256": refs["visible_policy"],
                }
            )
    outcome = None if state != "finalized" else data["grade"]["outcome"]
    outcome_fields = [
        "functional_success",
        "valid_completion",
        "contract_dispute",
        "boundary_preserved",
        "claims_supported",
        "lifecycle_verified",
        "timed_out",
    ]
    completion = {name: None if outcome is None else tri(outcome[name]) for name in outcome_fields}
    completion["verifier_status"] = None if outcome is None else outcome["verifier_status"]
    closure = None if result is None else result["closure"]
    native = None if result is None else result["native_lifecycle"]
    typed = {
        "execution_status": None
        if result is None
        else enum(result["status"], {"completed", "timeout", "agent_failure"}, "unknown runtime status"),
        "runtime_identity_verified": None if result is None else tri(result["runtime_identity"]["verified"]),
        "cutoff": {
            "reason": None
            if closure is None
            else enum(
                closure["reason"], {"agent_end", "deadline", "worker_interrupted"}, "invalid cutoff reason"
            ),
            "execution_boundary": "unavailable"
            if closure is None
            else enum(
                closure["execution_boundary"], {"confirmed", "unconfirmed"}, "invalid execution boundary"
            ),
            "native_end_inferred": None if closure is None else tri(closure["native_end_inferred"]),
        },
        "capture": {
            "archive_status": "unavailable"
            if closure is None
            else enum(closure["snapshot"], {"complete", "partial", "missing"}, "invalid capture state"),
            "workspace_snapshot": "unavailable"
            if visible is None
            else enum(visible["snapshot_status"], {"complete", "unavailable"}, "invalid workspace capture"),
            "response_status": "unavailable"
            if result is None
            else enum(
                result["response_capture"]["status"],
                {"parsed", "malformed", "missing"},
                "invalid response capture",
            ),
        },
        "native_lifecycle": {
            "parent_native_completion": None if native is None else tri(native["parent_native_completion"]),
            "delegation_status": "unverified"
            if native is None
            else enum(
                native["delegation_status"], {"verified", "unverified", "violated"}, "invalid delegation"
            ),
            "lifecycle_verified": None if native is None else tri(native["lifecycle_verified"]),
        },
        "verifier_boundary_confirmed": None if result is None else tri(result["case_boundary_confirmed"]),
        "accounting": {
            name: usage[name]
            for name in (
                "accounting_status",
                "provenance_status",
                "delegation_status",
                "exact_totals",
                "lower_bounds",
            )
        },
        "completion": completion,
    }
    typed["accounting"].update(
        agent_records=len(usage["agents"]),
        complete_agent_records=sum(a["complete"] is True for a in usage["agents"]),
        partial_agent_records=sum(a["complete"] is False for a in usage["agents"]),
    )
    return {
        "schema_version": SCHEMA,
        "registration_sha256": pin,
        "trial_id": scheduled["trial_id"],
        "task_id": scheduled["task_id"],
        "task_contract": contract,
        "attempt": attempt,
        "state": state,
        "source_status": "sealed_attempt_projection"
        if state == "finalized"
        else "unstarted_roster_projection"
        if state == "unstarted"
        else "unsealed_attempt_no_outcome_projection",
        "source_record_sha256": refs,
        "registered_case_roster": ids,
        "registered_defect_obligations": obligations,
        "cases": projected_cases,
        "review_witnesses": projected_witnesses,
        "visible_commands": observations,
        "supplied_observation_ids": supplied_ids,
        "prompt": prompt,
        "structured_check_claims": claim_projection(
            None if visible is None else visible.get("response"),
            task["visible_command"],
            refs.get("visible_policy"),
        ),
        "report_metrics": report_projection(None if state != "finalized" else data["grade"], verification),
        "stopped_output_policies": None
        if state != "finalized"
        else {
            "source": "retained_visible_policy",
            "raw_source_sha256": refs["visible_policy"],
            "acceptance": {
                name: tri(data["visible_policy"]["decisions"][name]["accepted"]) for name in ("U", "M", "G")
            },
            "visible_claims_supported": tri(data["visible_policy"]["decisions"]["visible_claims_supported"]),
        },
        "typed": typed,
    }
