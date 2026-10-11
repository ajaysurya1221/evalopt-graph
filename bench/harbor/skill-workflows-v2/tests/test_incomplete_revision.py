"""Portable consistency controls; no live trials, private artifacts or models."""

import copy
import hashlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import test_freeze as freeze_fixture
from evalopt_v2.accounting import derive_usage
from evalopt_v2.analysis import reconcile
from evalopt_v2.descriptive import kernel_metrics, outcomes, resources
from evalopt_v2.freeze import (
    derive_identities,
    reviewed_inputs,
    tree_manifest,
    validate_admission,
    validate_stopped_incomplete,
    verify_frozen,
)
from evalopt_v2.records import canonical, digest
from evalopt_v2.registration import development_gate
from test_study import registered, tasks


def predecessor():
    original = registered(tasks("development"), "development")
    pin = original["registration_sha256"]
    schedule = original["schedule"]
    ledger, rows = [], []
    for index, row in enumerate(schedule[:4]):
        start = {
            "row": row,
            "registration_sha256": pin,
            "attempt": 1,
            "attempt_id": row["trial_id"] + "--attempt-1",
        }
        entry = {"trial_id": row["trial_id"], "start": start, "start_sha256": digest(start)}
        if index < 3:
            outcome = {
                **row,
                "valid_completion": [True, False, None][index],
                "functional_success": True,
                "contract_dispute": False,
                "unsupported_success": False,
                "incorrect_refusal": False,
                "boundary_violation": False,
                "raw_valid_completion": [True, False, None][index],
                "raw_functional_success": True,
                "runtime_identity_verified": True,
            }
            if index == 2:
                outcome["missing_reason"] = "unresolved_required_evidence"
            rows.append(outcome)
            entry.update(
                state="finalized",
                final_sha256="d" * 64,
                outcome=outcome,
                continuation={
                    "schema_version": "evalopt-workflows-v2/1",
                    "kind": "continuation",
                    "decision": "continue",
                    "reasons": [],
                    "retry_authorized": False,
                    "task_success_inferred": False,
                    "historical_delegation": "verified",
                },
            )
        else:
            failure = {
                "kind": "controller_failure",
                "error_type": "RuntimeError",
                "observed_at": "2026-10-11T05:32:51.586541+00:00",
                "automatic_retry_allowed": False,
            }
            entry.update(state="unfinalized", failure=failure, failure_sha256=digest(failure))
        ledger.append(entry)
    resolved = reconcile(original["tasks"], rows, "development")
    report = {
        "stage": "development",
        "conclusion": "development_only",
        "registration_sha256": pin,
        "scheduled_rows": resolved,
        "secondary_outcomes": outcomes(resolved),
        "gate": development_gate(original["tasks"], rows, controls_passed=True, revision=0),
        "finalized_rows": 3,
        "retained_attempts": 4,
        "unfinalized_trials": [schedule[3]["trial_id"]],
        "resources": resources(
            schedule,
            [{"trial_id": row["trial_id"], "attempt": 1, "usage": derive_usage({})} for row in schedule[:4]],
        ),
        "kernel": kernel_metrics(rows),
        "controller_time": {
            "observed_seconds": 12.5,
            "known_attempts": 3,
            "retained_attempts": 4,
            "scope": "setup_agent_capture_visible_and_hidden_verification",
        },
    }
    return {
        "status": "stopped_incomplete",
        "revision": 0,
        "registration": original,
        "registration_sha256": pin,
        "replay": report,
        "replay_sha256": digest(report),
        "replay_source": {
            "source_sha256": original["identities"]["source"],
            "controller_sha256": original["identities"]["controller"],
            "entrypoint_sha256": "b" * 64,
        },
        "preservation": {"file_count": 990, "sha256": "c" * 64},
        "partition": {
            "finalized": [row["trial_id"] for row in schedule[:3]],
            "unfinalized": [schedule[3]["trial_id"]],
            "unstarted": [row["trial_id"] for row in schedule[4:]],
        },
        "started_attempts": ledger,
        "resumptions": [],
        "correspondence": {
            "status": "PASS",
            "evidence_sha256": "e" * 64,
            "scope": "independently_reviewed_consistency_not_authentication",
        },
    }


def assign(value, path, replacement):
    for key in path[:-1]:
        value = value[key]
    value[path[-1]] = replacement


@pytest.fixture
def harness():
    # Reuse only the existing local fake-source/upstream setup, not its tests.
    fixture = freeze_fixture.FreezeTests()
    fixture.setUp()
    try:
        yield fixture
    finally:
        fixture.doCleanups()


def test_incomplete_gate_preserves_observed_rows_and_unknown_denominator():
    value = predecessor()
    before = canonical(value)
    summary = validate_stopped_incomplete(value)
    assert summary == {
        "scheduled": 48,
        "finalized": 3,
        "unfinalized": 1,
        "unstarted": 44,
        "gate": value["replay"]["gate"],
    }
    assert summary["gate"]["recorded"] == 3
    assert summary["gate"]["ready"] is False
    assert summary["gate"]["next"] == "development_revision"
    assert all(row["valid_completion"] is None for row in value["replay"]["scheduled_rows"][3:])
    assert canonical(value) == before


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("revision",), 1),
        (("revision",), False),
        (("registration_sha256",), "f" * 64),
        (("registration", "schedule", 0, "repetition"), True),
        (("registration", "runtime", "seconds"), 900),
        (("replay_source", "source_sha256"), "f" * 64),
        (("replay_source", "controller_sha256"), "f" * 64),
        (("replay_source", "entrypoint_sha256"), "unpinned"),
        (("preservation", "file_count"), True),
        (("preservation", "sha256"), None),
        (("correspondence", "status"), "PENDING"),
        (("correspondence", "scope"), "authenticated"),
        (("started_attempts", 0, "start", "attempt"), True),
        (("started_attempts", 0, "start", "attempt"), 2),
        (("started_attempts", 0, "start", "registration_sha256"), "f" * 64),
        (("started_attempts", 0, "start_sha256"), "f" * 64),
        (("started_attempts", 0, "final_sha256"), None),
        (("started_attempts", 0, "outcome", "valid_completion"), 1),
        (("started_attempts", 0, "outcome", "functional_success"), "passed"),
        (("started_attempts", 0, "continuation", "decision"), "stop"),
        (("started_attempts", 0, "continuation", "retry_authorized"), 0),
        (("started_attempts", 3, "failure", "automatic_retry_allowed"), True),
        (("started_attempts", 3, "failure", "error_type"), "private/path/error"),
        (("started_attempts", 3, "failure", "observed_at"), "2026-10-11T00:00:00"),
        (("started_attempts", 3, "failure_sha256"), "f" * 64),
        (("replay_sha256",), "f" * 64),
    ],
)
def test_malformed_or_rebound_predecessor_rejected(path, replacement):
    value = predecessor()
    assign(value, path, replacement)
    # Coherent failure envelope cannot bless a disallowed underlying failure.
    if path[:3] == ("started_attempts", 3, "failure"):
        value["started_attempts"][3]["failure_sha256"] = digest(value["started_attempts"][3]["failure"])
    with pytest.raises(ValueError):
        validate_stopped_incomplete(value)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "omit", "swap", "complete", "ledger_missing", "ledger_extra", "ledger_order"]
)
def test_partition_is_exact_disjoint_exhaustive_and_sequential(mutation):
    value = predecessor()
    partition = value["partition"]
    if mutation == "duplicate":
        partition["unstarted"][0] = partition["finalized"][0]
    elif mutation == "omit":
        partition["unstarted"].pop()
    elif mutation == "swap":
        partition["unstarted"][:2] = reversed(partition["unstarted"][:2])
    elif mutation == "complete":
        partition["finalized"] += partition["unfinalized"] + partition["unstarted"]
        partition["unfinalized"], partition["unstarted"] = [], []
    elif mutation == "ledger_missing":
        value["started_attempts"].pop()
    elif mutation == "ledger_extra":
        value["started_attempts"].append(copy.deepcopy(value["started_attempts"][0]))
    else:
        value["started_attempts"][:2] = reversed(value["started_attempts"][:2])
    with pytest.raises(ValueError):
        validate_stopped_incomplete(value)


@pytest.mark.parametrize(
    "path,replacement",
    [
        (("gate", "recorded"), 48),
        (("gate", "ready"), True),
        (("gate", "next"), "freeze_heldout"),
        (("finalized_rows",), 48),
        (("retained_attempts",), 48),
        (("stage",), "heldout"),
        (("conclusion",), "upgrade"),
        (("scheduled_rows", 4, "valid_completion"), False),
        (("scheduled_rows", 4, "reported_functional_success"), True),
        (("scheduled_rows", 0, "valid_completion"), False),
        (("scheduled_rows", 0, "functional_success"), False),
        (("secondary_outcomes", "A", "functional_success", "unknown"), 0),
        (("kernel", "U", "stopped_outputs"), 48),
        (("kernel", "U", "approval_coverage"), 1),
        (("resources", "A", "attempts"), 12),
        (("resources", "A", "efficiency_claim_allowed"), True),
        (("controller_time", "retained_attempts"), 48),
        (("controller_time", "known_attempts"), True),
    ],
)
def test_rehashing_replay_cannot_change_original_gate_or_known_missingness(path, replacement):
    value = predecessor()
    assign(value["replay"], path, replacement)
    value["replay_sha256"] = digest(value["replay"])
    with pytest.raises(ValueError):
        validate_stopped_incomplete(value)


def test_unfinished_usage_cannot_be_zero_or_exact():
    value = predecessor()
    bucket = value["replay"]["resources"][value["registration"]["schedule"][3]["arm"]]
    bucket["complete_usage_attempts"] = bucket["attempts"]
    bucket["unavailable_usage_attempts"] = 0
    bucket["observed_lower_bounds"] = dict.fromkeys(bucket["observed_lower_bounds"], 0)
    bucket["exact_totals"] = dict(bucket["observed_lower_bounds"])
    value["replay_sha256"] = digest(value["replay"])
    with pytest.raises(ValueError, match="unfinished attempt"):
        validate_stopped_incomplete(value)


@pytest.mark.parametrize("where", ["preservation", "correspondence", "replay_source", "started_attempts"])
def test_portable_projection_does_not_accept_private_manifest_or_arbitrary_fields(where):
    value = predecessor()
    target = value[where][0] if where == "started_attempts" else value[where]
    target["private_native_paths"] = ["native-id.jsonl"]
    with pytest.raises(ValueError):
        validate_stopped_incomplete(value)


def test_new_complete_revision_freezes_all_48_rows_without_importing_old_outcomes(harness):
    previous = predecessor()
    before = canonical(previous)
    harness.admission["development_round"] = {"revision": 1, "previous": previous}
    root, receipt = harness.prepare()
    store = verify_frozen(root, expected_sha256=receipt["registration_sha256"])
    assert len(store.registration["schedule"]) == 48
    assert not list((root / "attempts").glob("*/attempt-*"))
    assert canonical(previous) == before
    assert store.registration["registration_sha256"] != previous["registration_sha256"]
    retained = __import__("json").loads((root / "admission.json").read_bytes())
    assert retained["development_round"]["revision"] == 1
    assert retained["development_round"]["previous"]["replay"]["gate"]["recorded"] == 3
    for revision in (2, True):
        with pytest.raises(ValueError):
            validate_admission(
                {**retained, "development_round": {"revision": revision, "previous": previous}},
                retained["inputs"],
            )
    previous["revision"] = 1
    with pytest.raises(ValueError):
        validate_admission(harness.admission, harness.inputs)


def test_network_source_is_explicit_controller_identity_and_required_for_new_freeze(harness):
    root, _ = harness.prepare()
    frozen = root / "frozen"
    manifest = tree_manifest(frozen)
    network = frozen / "harness/evalopt_v2/network.py"
    before = derive_identities(frozen, harness.admission, manifest)
    network.write_text('"""Different nonexecuted fixture."""\n')
    after = derive_identities(frozen, harness.admission, tree_manifest(frozen))
    assert before["controller"] != after["controller"]
    network.unlink()
    legacy = derive_identities(frozen, harness.admission, tree_manifest(frozen))
    names = ["harbor_bridge.py", "observe.py", "snapshot.py", "preflight.py", "campaign.py"]
    assert legacy["controller"] == digest(
        {name: hashlib.sha256((network.parent / name).read_bytes()).hexdigest() for name in names}
    )
    (harness.harness / "evalopt_v2/network.py").unlink()
    harness.inputs = reviewed_inputs(harness.harness, harness.skill, harness.tasks)
    harness.admission["inputs"] = harness.inputs
    with pytest.raises(ValueError, match="network controller"):
        harness.prepare()


def paused_predecessor():
    value = predecessor()
    entry = value["started_attempts"][0]
    entry["continuation"].update(decision="stop", reasons=["subscription_permission_unavailable"])
    permission = {"schema_version": "evalopt-workflows-v2/1", "kind": "subscription_permission"}
    pause = {
        "registration_sha256": value["registration_sha256"],
        "stopped_trial_id": entry["trial_id"],
        "stopped_final_sha256": entry["final_sha256"],
        "permission": {**permission, "ordinary_usage_allowed": False, "state": "exhausted"},
    }
    resume = {
        "registration_sha256": value["registration_sha256"],
        "pause_sha256": digest(pause),
        "permission": {**permission, "ordinary_usage_allowed": True, "state": "allowed"},
    }
    value["resumptions"] = [
        {"pause": pause, "pause_sha256": digest(pause), "resume": resume, "resume_sha256": digest(resume)}
    ]
    return value


def test_original_subscription_stop_and_resumption_are_retained_without_normalization():
    value = paused_predecessor()
    before = canonical(value)
    assert validate_stopped_incomplete(value)["finalized"] == 3
    assert canonical(value) == before
    assert value["started_attempts"][0]["continuation"]["decision"] == "stop"


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "extra",
        "wrong_trial",
        "wrong_final",
        "wrong_registration",
        "wrong_pause_pin",
        "unavailable",
        "false_resume",
        "bool_alias",
        "other_stop",
    ],
)
def test_only_hash_bound_original_subscription_resumption_can_explain_prior_stop(mutation):
    value = paused_predecessor()
    pair = value["resumptions"][0]
    if mutation == "missing":
        value["resumptions"] = []
    elif mutation == "extra":
        value["resumptions"].append(copy.deepcopy(pair))
    elif mutation == "wrong_trial":
        pair["pause"]["stopped_trial_id"] = value["started_attempts"][1]["trial_id"]
    elif mutation == "wrong_final":
        pair["pause"]["stopped_final_sha256"] = "f" * 64
    elif mutation == "wrong_registration":
        pair["resume"]["registration_sha256"] = "f" * 64
    elif mutation == "wrong_pause_pin":
        pair["resume"]["pause_sha256"] = "f" * 64
    elif mutation == "unavailable":
        pair["pause"]["permission"]["state"] = "unavailable"
    elif mutation == "false_resume":
        pair["resume"]["permission"]["ordinary_usage_allowed"] = False
    elif mutation == "bool_alias":
        pair["resume"]["permission"]["ordinary_usage_allowed"] = 1
    else:
        value["started_attempts"][0]["continuation"]["reasons"] = ["accounting_unavailable"]
    # Even coherent local hashes cannot replace the required original contents.
    pair["pause_sha256"] = digest(pair["pause"])
    pair["resume_sha256"] = digest(pair["resume"])
    with pytest.raises(ValueError):
        validate_stopped_incomplete(value)


def test_unavailable_only_consumption_remains_null_without_changing_count_labels():
    value = predecessor()
    bucket = value["replay"]["resources"][value["registration"]["schedule"][3]["arm"]]
    bucket["observed_lower_bounds"] = dict.fromkeys(bucket["observed_lower_bounds"], 0)
    value["replay_sha256"] = digest(value["replay"])
    with pytest.raises(ValueError, match="resource counters"):
        validate_stopped_incomplete(value)


def test_unfinished_attempt_has_no_replayed_controller_timing():
    value = predecessor()
    value["replay"]["controller_time"]["known_attempts"] = 4
    value["replay_sha256"] = digest(value["replay"])
    with pytest.raises(ValueError, match="controller-time"):
        validate_stopped_incomplete(value)
