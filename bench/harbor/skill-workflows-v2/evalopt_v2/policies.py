"""Secondary policies over one frozen controller-owned visible evidence bundle.

The caller establishes custody before invoking this pure reducer. All decision
inputs are retained in the bundle; hidden functional grades are never consulted.
The claim gate covers reported visible check observations only, not task success.
"""

from __future__ import annotations

import json

from .records import canonical, digest, validate_record


def _visible_claims(response, by_command, roster, expected_checks):
    """Missing observations are unknown; retained contradictions stay false."""
    if response is None:
        return None
    if not (
        type(response) is dict
        and type(response.get("status")) is str
        and response["status"] in {"completed", "blocked"}
        and type(response.get("findings")) is list
        and type(response.get("blockers")) is list
        and type(response.get("checks")) is list
    ):
        return False
    reported = {}
    fields = {"command", "execution_state", "exit_code", "evidence_availability"}
    for check in response["checks"]:
        if (
            type(check) is not dict
            or set(check) != fields
            or type(check["command"]) is not list
            or not check["command"]
            or any(type(part) is not str for part in check["command"])
            or type(check["execution_state"]) is not str
            or check["execution_state"] not in {"ran", "not_run", "timed_out", "interrupted"}
            or type(check["evidence_availability"]) is not str
            or check["evidence_availability"] not in {"complete", "partial", "unavailable"}
            or (
                type(check["exit_code"]) is not int
                if check["execution_state"] == "ran"
                else check["exit_code"] is not None
            )
            or (check["execution_state"] == "not_run" and check["evidence_availability"] != "unavailable")
        ):
            return False
        key = canonical(check["command"])
        if key not in roster or key in reported:
            return False
        reported[key] = check
    for key, observed in by_command.items():
        expected = {field: observed[field] for field in fields}
        if key in reported and canonical(reported[key]) != canonical(expected):
            return False
        if key not in reported and observed["execution_state"] != "not_run":
            return False
    if len(by_command) != len(roster) or any(
        observation["execution_state"] == "not_run" for observation in by_command.values()
    ):
        return None
    return canonical(response["checks"]) == canonical(expected_checks)


def evaluate_visible(bundle, *, check_roster, attempt_id, candidate_id, observed_at):
    if bundle.get("attempt_id") != attempt_id or bundle.get("snapshot_sha256") != candidate_id:
        raise ValueError("visible bundle identity mismatch")
    contract = bundle.get("task_contract")
    if type(contract) is not str or contract not in {"implementation", "review", "blocker_report"}:
        raise ValueError("unregistered task contract")
    canonical(bundle)
    roster, identifiers = {}, set()
    if not check_roster:
        raise ValueError("frozen visible check roster required")
    for check in check_roster:
        if (
            set(check) != {"check_id", "command"}
            or type(check["check_id"]) is not str
            or not check["check_id"]
        ):
            raise ValueError("invalid visible check identity")
        if (
            type(check["command"]) is not list
            or not check["command"]
            or any(type(arg) is not str for arg in check["command"])
        ):
            raise ValueError("invalid visible check command")
        key = canonical(check["command"])
        if key in roster or check["check_id"] in identifiers:
            raise ValueError("duplicate frozen visible check")
        identifiers.add(check["check_id"])
        roster[key] = check["check_id"]
    by_command = {}
    for observation in bundle["observations"]:
        validate_record(observation)
        if observation["record_type"] != "command":
            raise ValueError("agent claims are not command observations")
        key = canonical(observation["command"])
        if key not in roster or key in by_command:
            raise ValueError("unexpected or duplicate visible observation")
        if observation["attempt_id"] != attempt_id or observation["candidate_id"] != (
            candidate_id or "unavailable"
        ):
            raise ValueError("observation belongs to another attempt or stopped candidate")
        if candidate_id is None and observation["execution_state"] != "not_run":
            raise ValueError("unidentified candidate cannot have an executed observation")
        by_command[key] = observation
    gates = []
    expected_checks = []
    for check in check_roster:
        observation = by_command.get(canonical(check["command"]))
        status = "NOT_CONFIGURED"
        if observation:
            if observation["execution_state"] == "ran" and observation["evidence_availability"] == "complete":
                status = "PASS" if observation["exit_code"] == 0 else "FAIL"
            expected_checks.append(
                {
                    key: observation[key]
                    for key in ("command", "execution_state", "exit_code", "evidence_availability")
                }
            )
        gates.append(("visible-" + check["check_id"], status))
    violations = bundle["boundary_violations"]
    if type(violations) is not list or any(type(item) is not str for item in violations):
        raise ValueError("invalid visible boundary record")
    boundary = (
        not violations
        if bundle["snapshot_status"] == "complete" and bundle["execution_boundary"] == "confirmed"
        else None
    )
    if bundle["boundaries_preserved"] is not boundary:
        raise ValueError("contradictory boundary observation")
    response = bundle["response"]
    claims = _visible_claims(response, by_command, roster, expected_checks)
    gates += [
        ("boundaries", "PASS" if boundary is True else "FAIL" if boundary is False else "NOT_CONFIGURED"),
        ("visible_claims", "PASS" if claims is True else "FAIL" if claims is False else "NOT_CONFIGURED"),
    ]
    from evalopt_graph import AcceptanceInput, GovernancePolicy, evaluate_acceptance

    policy = GovernancePolicy(required_gates=tuple(name for name, _ in gates))
    input_ = AcceptanceInput(observed_at=observed_at, gate_results=tuple(gates))
    decision = evaluate_acceptance(policy, input_)
    # The unchanged stable kernel's dictionaries include tuples. Normalize only
    # its own serialized values at this adapter boundary, never candidate data.
    kernel_decision = json.loads(json.dumps(decision.to_dict(), allow_nan=False))
    kernel_policy = json.loads(json.dumps(policy.to_dict(), allow_nan=False))
    kernel_input = json.loads(json.dumps(input_.to_dict(), allow_nan=False))
    return {
        "scope": "stopped_patch_acceptance",
        "task_contract": contract,
        "visible_sha256": digest(bundle),
        "check_roster": check_roster,
        "attempt_id": attempt_id,
        "candidate_id": candidate_id,
        "observed_at": observed_at,
        "visible_claims_supported": claims,
        "U": {"accepted": True},
        "M": {"accepted": all(status == "PASS" for _, status in gates)},
        "G": {"accepted": decision.status == "ACCEPTED", "decision": kernel_decision},
        "kernel_policy": kernel_policy,
        "kernel_input": kernel_input,
    }


def replay_visible(bundle, decisions):
    result = evaluate_visible(
        bundle,
        **{key: decisions[key] for key in ("check_roster", "attempt_id", "candidate_id", "observed_at")},
    )
    if canonical(result) != canonical(decisions):
        raise ValueError("visible policy does not replay")
    return result
