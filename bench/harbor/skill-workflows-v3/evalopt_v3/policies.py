"""Secondary policies over one frozen controller-owned visible evidence bundle.

The caller establishes custody before invoking this pure reducer. All decision
inputs are retained in the bundle; hidden functional grades are never consulted.
The claim gate covers reported visible check observations only, not task success.
"""

from __future__ import annotations

import json

from .records import canonical, digest
from .reporting import check_claims, validate_ledger


def evaluate_visible(bundle, *, check_roster, attempt_id, candidate_id, observed_at):
    if bundle.get("attempt_id") != attempt_id or bundle.get("snapshot_sha256") != candidate_id:
        raise ValueError("visible bundle identity mismatch")
    contract = bundle.get("task_contract")
    if type(contract) is not str or contract not in {"implementation", "review", "blocker_report"}:
        raise ValueError("unregistered task contract")
    canonical(bundle)
    ledger = validate_ledger(
        bundle["observations"],
        attempt_id=attempt_id,
        check_roster=check_roster,
        supplied_observation_ids=bundle["supplied_observation_ids"],
        initial_candidate_id=bundle["initial_snapshot_sha256"],
        post_stop_candidate_id=candidate_id,
    )
    gates = []
    for check in check_roster:
        observation = ledger["post_stop"].get(check["check_id"])
        status = "NOT_CONFIGURED"
        if (
            observation
            and observation["execution_state"] == "ran"
            and observation["evidence_availability"] == "complete"
        ):
            status = "PASS" if observation["exit_code"] == 0 else "FAIL"
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
    claims = check_claims(
        response,
        observations=bundle["observations"],
        supplied_observation_ids=bundle["supplied_observation_ids"],
        attempt_id=attempt_id,
        check_roster=check_roster,
    )
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
