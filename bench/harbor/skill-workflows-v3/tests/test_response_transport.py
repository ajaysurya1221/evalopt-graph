"""Transport bounds survive capture, visible policy and durable store envelopes."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v3.materialize import materialize
from evalopt_v3.policies import evaluate_visible
from evalopt_v3.records import canonical, seal_observation, task_outcome
from evalopt_v3.reporting import check_claim
from evalopt_v3.snapshot import (
    RESPONSE_MAX_BYTES,
    RESPONSE_MAX_DEPTH,
    RESPONSE_MAX_NODES,
    final_response,
    response_transport_contract,
)
from evalopt_v3.store import CampaignStore, exclusive_json, read_json
from test_snapshot import native
from test_study import registered, tasks


def response_text(kind, limit, check):
    response = {
        "status": "completed",
        "findings": [],
        "blockers": [],
        "checks": [check],
        "padding": None,
    }
    if kind == "depth":
        nested = None
        for _ in range(limit - 1):
            nested = [nested]
        response["padding"] = nested
    elif kind == "nodes":
        # This six-field phase-bound check response has 25 nodes before
        # padding children, counting object keys and every value.
        response["padding"] = [None] * (limit - 25)
    else:
        response["padding"] = ""
        overhead = len(json.dumps(response, separators=(",", ":")).encode())
        response["padding"] = "x" * (limit - overhead)
    return json.dumps(response, separators=(",", ":"))


@pytest.mark.parametrize(
    "kind,limit,parsed",
    [
        ("depth", 602, True),
        ("depth", RESPONSE_MAX_DEPTH, True),
        ("depth", RESPONSE_MAX_DEPTH + 1, False),
        ("depth", 768, False),
        ("nodes", RESPONSE_MAX_NODES, True),
        ("nodes", RESPONSE_MAX_NODES + 1, False),
        ("bytes", RESPONSE_MAX_BYTES, True),
        ("bytes", RESPONSE_MAX_BYTES + 1, False),
    ],
)
def test_response_thresholds_remain_retainable_through_policy_and_store(tmp_path, kind, limit, parsed):
    registration = registered(tasks())
    root = tmp_path.resolve() / "campaign"
    store = CampaignStore.create(root, registration)
    trial_id = registration["schedule"][0]["trial_id"]
    path = store.start(trial_id)
    attempt_id = read_json(path / "start.json")["attempt_id"]
    observation = seal_observation(
        {
            "schema_version": "evalopt-workflows-v3/1",
            "record_type": "command",
            "attempt_id": attempt_id,
            "candidate_id": "snapshot",
            "check_id": "required",
            "phase": "initial",
            "command": ["verify"],
            "execution_state": "ran",
            "exit_code": 0,
            "evidence_availability": "complete",
            "artifact_refs": ["stdout.bin"],
            "artifact_sha256": {"stdout.bin": hashlib.sha256(b"").hexdigest()},
            "asserted_claim": None,
        }
    )
    post_stop = seal_observation(
        {
            key: ("post_stop" if key == "phase" else value)
            for key, value in observation.items()
            if key != "observation_id"
        }
    )
    text = response_text(kind, limit, check_claim(observation))
    raw = native(text=text)
    capture = final_response({"parent": raw})
    assert capture["status"] == ("parsed" if parsed else "malformed")
    assert capture["response_sha256"] == hashlib.sha256(text.encode()).hexdigest()
    visible = {
        "attempt_id": attempt_id,
        "snapshot_sha256": "snapshot",
        "initial_snapshot_sha256": "snapshot",
        "supplied_observation_ids": [observation["observation_id"]],
        "task_contract": "implementation",
        "observations": [observation, post_stop],
        "boundary_violations": [],
        "boundaries_preserved": True,
        "snapshot_status": "complete",
        "execution_boundary": "confirmed",
        "response": capture["response"],
        "response_capture": capture,
    }
    decisions = evaluate_visible(
        visible,
        check_roster=[{"check_id": "required", "command": ["verify"]}],
        attempt_id=attempt_id,
        candidate_id="snapshot",
        observed_at="2026-10-11T00:00:00Z",
    )
    assert decisions["G"]["accepted"] is parsed
    store.record_visible(trial_id, visible, decisions)
    # Match the live result's duplicated response-bearing envelopes. Their depth
    # and aggregate node count must retain headroom beyond the response itself.
    exclusive_json(path / "runtime-result.json", {"visible_bundle": visible, "response_capture": capture})
    (path / "parent.jsonl").write_bytes(raw)
    outcome = task_outcome(
        attempt_id,
        "implementation",
        functional_success=True,
        boundary_preserved=True,
        claims_supported=parsed,
        lifecycle_verified=True,
    )
    store.record_grade(trial_id, {"outcome": outcome})
    store.finalize(trial_id, outcome, {"decision": "continue"})
    reopened = CampaignStore(root, expected_sha256=registration["registration_sha256"])
    assert reopened.verify_trial(trial_id)["outcome"] == outcome
    retained = read_json(path / "visible-policy.json")
    assert canonical(retained["visible"]) == canonical(visible)
    assert (path / "parent.jsonl").read_bytes() == raw


def test_all_arms_publish_identical_transport_bounds_and_task_finding_limit(tmp_path):
    task_dir = (
        Path(__file__).resolve().parents[2] / "skill-workflows-v2/tasks/development/review-template-values"
    )
    task = json.loads((task_dir / "task.json").read_text())
    contract = response_transport_contract(task.get("max_findings", 16))
    instructions = []
    for arm in "ABCD":
        record = materialize(task_dir, tmp_path.resolve() / arm, arm=arm)
        assert record["instruction"].count(contract) == 1
        instructions.append(record["instruction"])
    assert instructions[2] == instructions[3]
    assert f"at most {task['max_findings']} entries" in contract
