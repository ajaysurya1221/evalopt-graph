"""Synthetic amendment publication controls; never live benchmark outcomes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

import test_skill_workflow_partial_accounting as native
import test_skill_workflow_publication as support

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import amended_pilot as controller  # noqa: E402
import amended_publish as publication  # noqa: E402
from lib.common import bytes_digest, canonical_bytes, digest, read_json  # noqa: E402


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value) + b"\n")


def hashes(path):
    return {
        item.relative_to(path).as_posix(): bytes_digest(item.read_bytes())
        for item in path.rglob("*")
        if item.is_file()
    }


@pytest.fixture
def amended(tmp_path):
    source, frozen, store, first = support.recorded_campaign.__wrapped__(tmp_path)()
    schedule = read_json(source / "evidence/schedule.json")["schedule"]
    reporter = support._load_reporter(frozen)

    def finish(index, *, runtime_valid=True):
        row = schedule[index]
        attempt = store.start_attempt(row["trial_id"])
        base = source / "evidence/trials" / first / "attempt-1"
        artifacts = {p.name: p.read_bytes() for p in (base / "agent").iterdir()}
        artifacts["workflow-exposure.json"] = canonical_bytes(
            {"arm": row["arm"], "source_files": {}, "verified_before_agent": True}
        )
        stopped = store.capture_stopped(row["trial_id"], attempt, artifacts)
        observation = b'{"outcome":"passed"}'
        store.record_visible(
            row["trial_id"],
            attempt,
            {
                "schema_version": "evalopt.workflow-visible.v1",
                "trial_id": row["trial_id"],
                "stopped_sha256": stopped,
                "observed_at": "2026-10-08T00:00:00+00:00",
                "required_gates": ["visible_check"],
                "gates": [
                    {
                        "name": "visible_check",
                        "status": "PASS",
                        "producer": "controller",
                        "evidence_sha256": bytes_digest(observation),
                    }
                ],
                "tests_weakened": False,
                "boundary_violations": [],
                "unsupported_claims": [],
            },
            {"visible-check.json": observation},
        )
        store.decide(row["trial_id"], attempt)
        store.record_grade(
            row["trial_id"],
            attempt,
            {
                "valid_completion": True,
                "functional_success": True,
                "unsupported_success": False,
                "incorrect_refusal": False,
                "boundary_violation": False,
            },
        )
        usage = {
            "child_usage_complete": True,
            "runtime_valid": runtime_valid,
            "input_tokens": 10,
            "output_tokens": 2,
            "model_calls": 1,
            "tool_calls": 1,
            "wall_seconds": 3,
            "agent_count": 1,
            "aggregation": "agent_exclusive",
        }
        if index == 8:
            usage = {"child_usage_complete": False, "runtime_valid": True, "accounting_status": "unavailable"}
        store.finish_attempt(row["trial_id"], attempt, "completed", usage=usage)

    def logs(index):
        session = (
            source
            / "private-harbor"
            / schedule[index]["trial_id"]
            / "attempt-1/harbor-synthetic/agent/sessions"
        )
        session.mkdir(parents=True)
        parent = native.native_session("synthetic-parent", children=["synthetic-child"] if index == 8 else [])
        parent[-1] = native.lifecycle("task_complete", "synthetic-parent", 3)
        if index != 8:
            parent.insert(
                2,
                {
                    "type": "response_item",
                    "payload": {"type": "function_call", "name": "exec", "call_id": "synthetic-tool"},
                },
            )
        sessions = [parent]
        if index == 8:
            child = native.native_session(
                "synthetic-child", parent="synthetic-parent", copied=parent, ending="turn_aborted"
            )
            sessions.append(child)
        native.write_sessions(session, *sessions)

    for index in range(9):
        if index:
            finish(index)
        logs(index)
    write_json(source / "runs/run-0001/start.json", {"schema_version": "synthetic.original-start.v1"})
    write_json(
        source / "runs/run-0001/end.json",
        {
            "schema_version": "synthetic.original-stop.v1",
            "status": "paused",
            "reason": "usage_accounting_requires_remediation",
        },
    )

    def bridge(action, request):
        assert action in {"verify", "inspect", "report"}
        if action == "report":
            return {"export_id": reporter.report(source)["export_id"]}
        attempts = []
        for state in store.statuses():
            if not state["attempts"]:
                continue
            path = source / "evidence/trials" / state["trial_id"] / "attempt-1"
            record = read_json(path / "finish.json")
            attempts.append(
                {
                    "trial_id": state["trial_id"],
                    "attempt": 1,
                    "status": record["status"],
                    "error_code": record.get("error_code"),
                    "usage": record["usage"],
                    "finish_sha256": bytes_digest((path / "finish.json").read_bytes()),
                    "manifest_sha256": bytes_digest((path / "manifest.json").read_bytes()),
                }
            )
        return {
            "registration_sha256": digest(read_json(source / "registration-lock.json")),
            "source_lock": read_json(source / "source-lock.json"),
            "schedule": schedule,
            "schedule_sha256": digest(schedule),
            "states": store.statuses(),
            "attempts": attempts,
        }

    registered = controller.register(
        source, frozen, tmp_path / "synthetic-upstream", authorization="partial accounting", bridge=bridge
    )
    identity = registered["amendment_sha256"]

    def later_blocked():
        finish(9, runtime_valid=False)
        logs(9)
        root = source / controller.AMENDMENT / "runs/run-0001"
        pending = [row["trial_id"] for row in schedule[9:]]
        write_json(
            root / "start.json",
            {
                "schema_version": "evalopt.amended-run.v1",
                "amendment_sha256": identity,
                "pending_at_start": pending,
            },
        )
        write_json(
            root / pending[0] / "permission.json",
            {
                "schema_version": "evalopt.amended-permission.v1",
                "trial_id": pending[0],
                "amendment_sha256": identity,
                "ordinary_usage_allowed": True,
                "state": "allowed",
            },
        )
        record = bridge("inspect", {})["attempts"][-1]
        captured = controller._derive(source, record, identity)
        write_json(source / controller.AMENDMENT / "usage" / pending[0] / "attempt-1.json", captured)
        write_json(
            root / pending[0] / "completed.json",
            {
                "schema_version": "evalopt.amended-completion.v1",
                "amendment_sha256": identity,
                **controller._bound_attempt(record),
                "sidecar_sha256": digest(captured),
            },
        )
        write_json(
            root / "end.json",
            {
                "schema_version": "evalopt.amended-stop.v1",
                "status": "paused",
                "reason": "runtime_identity_requires_remediation",
                "trial_id": pending[0],
                "dispatched": pending[:1],
                "pending_trials": 26,
            },
        )

    return {
        "source": source,
        "frozen": frozen,
        "store": store,
        "schedule": schedule,
        "bridge": bridge,
        "identity": identity,
        "later_blocked": later_blocked,
    }


def export(record, destination):
    return publication.export_public_bundle(
        record["source"], destination, amendment_sha256=record["identity"], bridge=record["bridge"]
    )


def rechecksum(destination):
    value = read_json(destination / "CHECKSUMS.json")
    write_json(
        destination / "CHECKSUMS.json",
        publication._checksums(publication._payloads(destination), value["amendment_sha256"]),
    )


def sidecar(destination, record, index=8):
    return destination / "usage" / record["schedule"][index]["trial_id"] / "attempt-1.json"


def test_partial_publication_reproduces_and_preserves_original_evidence(amended, tmp_path):
    before = hashes(amended["source"] / "evidence")
    destination = tmp_path / "public"
    result = export(amended, destination)
    assert result["pilot_attempts_verified"] == 9
    assert result["policy_decisions_replayed"] == 27
    assert result["resource_arithmetic_reproduced"]
    assert not result["efficiency_comparison_eligible"]
    assert not result["raw_native_log_replay"] and not result["independent_authentication"]
    assert not result["independent_replication"] and not result["network_publication_performed"]
    assert hashes(amended["source"] / "evidence") == before
    for name, value in before.items():
        assert bytes_digest((destination / "pilot/evidence" / name).read_bytes()) == value
    assert not list(destination.rglob("local-sources.json"))
    assert not list(destination.rglob("*.jsonl"))
    assert "synthetic-parent" not in "\n".join(
        path.read_text() for path in destination.rglob("*") if path.is_file()
    )
    assert (
        publication.verify_public_bundle(
            destination, amendment_sha256=result["amendment_sha256"], bundle_id=result["bundle_id"]
        )
        == result
    )
    assert export(amended, tmp_path / "public-copy") == result


def test_blocked_attempt_keeps_known_usage_in_resource_coverage(amended, tmp_path):
    amended["later_blocked"]()
    destination = tmp_path / "public"
    export(amended, destination)
    report = read_json(destination / "resource-report.json")
    arm = amended["schedule"][9]["arm"]
    assert report["retained_attempts"] == 10 and report["pending_trials"] == 26
    assert report["arms"][arm]["continuation_blocked_attempts"] == 1
    assert report["arms"][arm]["runtime_invalid_attempts"] == 1
    assert report["arms"][arm]["complete_attempts_exact_totals"]["input_tokens"] >= 10
    assert not report["efficiency_comparison_eligible"]


@pytest.mark.parametrize(
    "mutation", ["count", "complete", "admission", "private-field", "agent-sum", "hash-bag"]
)
def test_rehashed_sidecar_tampering_fails(amended, tmp_path, mutation):
    destination = tmp_path / "public"
    export(amended, destination)
    path = sidecar(destination, amended)
    value = read_json(path)
    if mutation == "count":
        value["derived_usage"]["lower_bounds"]["input_tokens"] += 1
        value["derived_usage"]["agents"][0]["lower_bounds"]["input_tokens"] += 1
    elif mutation == "complete":
        value["derived_usage"]["accounting_status"] = "complete"
        value["derived_usage"]["child_usage_complete"] = True
        value["derived_usage"]["efficiency_eligible"] = True
    elif mutation == "admission":
        value["continuation_admissible"] = False
        value["continuation_blocker"] = "runtime_identity_requires_remediation"
    elif mutation == "private-field":
        value["derived_usage"]["access_token"] = "synthetic-private-token"
    elif mutation == "agent-sum":
        value["derived_usage"]["agents"][0]["lower_bounds"]["model_calls"] += 1
    else:
        value["derived_usage"]["source_log_sha256"][0] = "f" * 64
        value["derived_usage"]["source_log_sha256"].sort()
    write_json(path, value)
    rechecksum(destination)
    with pytest.raises(ValueError):
        publication.verify_public_bundle(destination)


def test_deleted_partial_sidecar_is_rejected_even_with_new_checksums(amended, tmp_path):
    destination = tmp_path / "public"
    export(amended, destination)
    path = sidecar(destination, amended)
    path.unlink()
    path.parent.rmdir()
    rechecksum(destination)
    with pytest.raises(ValueError, match="sidecar coverage"):
        publication.verify_public_bundle(destination)


@pytest.mark.parametrize("mutation", ["schedule", "policy", "controller", "pause"])
def test_rehashed_amendment_mutations_are_rejected(amended, tmp_path, mutation):
    destination = tmp_path / "public"
    export(amended, destination)
    path = destination / "amendment.json"
    value = read_json(path)
    if mutation == "schedule":
        value["pending_trial_ids"][:2] = list(reversed(value["pending_trial_ids"][:2]))
    elif mutation == "policy":
        value["policy"]["partial_efficiency_comparisons"] = True
    elif mutation == "controller":
        value["controller_sources"]["runtime/partial_accounting.py"] = "f" * 64
    else:
        value["pause_receipt"]["sha256"] = "f" * 64
    write_json(path, value)
    # Even if the checksum wrapper follows the altered amendment, the semantic
    # bindings must reject it before trusting the derived resources.
    write_json(
        destination / "CHECKSUMS.json",
        publication._checksums(publication._payloads(destination), digest(value)),
    )
    with pytest.raises(ValueError):
        publication.verify_public_bundle(destination)


def test_rehashed_resource_report_cannot_enable_efficiency(amended, tmp_path):
    destination = tmp_path / "public"
    export(amended, destination)
    path = destination / "resource-report.json"
    value = read_json(path)
    value["efficiency_comparison_eligible"] = True
    write_json(path, value)
    rechecksum(destination)
    with pytest.raises(ValueError, match="arithmetic"):
        publication.verify_public_bundle(destination)


def test_changed_original_grade_is_not_rescored_by_amendment(amended, tmp_path):
    destination = tmp_path / "public"
    export(amended, destination)
    path = destination / "pilot/evidence/trials" / amended["schedule"][0]["trial_id"] / "attempt-1/grade.json"
    value = read_json(path)
    value["grade"]["valid_completion"] = False
    write_json(path, value)
    rechecksum(destination)
    with pytest.raises(ValueError):
        publication.verify_public_bundle(destination)


@pytest.mark.parametrize(
    "mutation", ["permission", "permission-amendment", "missing-amendment", "dispatched", "extra-run-field"]
)
def test_rehashed_amendment_run_receipts_are_checked(amended, tmp_path, mutation):
    amended["later_blocked"]()
    destination = tmp_path / "public"
    export(amended, destination)
    run = destination / "runs/run-0001"
    if mutation in {"permission", "permission-amendment", "missing-amendment"}:
        path = run / amended["schedule"][9]["trial_id"] / "permission.json"
        value = read_json(path)
        if mutation == "permission":
            value.update(ordinary_usage_allowed=False, state="exhausted")
        elif mutation == "permission-amendment":
            value["amendment_sha256"] = "0" * 64
        else:
            value.pop("amendment_sha256")
    else:
        path = run / "end.json"
        value = read_json(path)
        if mutation == "dispatched":
            value["dispatched"] = []
        else:
            value["unreviewed_note"] = "not in the controller schema"
    write_json(path, value)
    rechecksum(destination)
    with pytest.raises(ValueError):
        publication.verify_public_bundle(destination)


@pytest.mark.parametrize("kind", ["extra", "empty-directory", "symlink", "fifo"])
def test_extra_or_nonregular_nodes_are_rejected(amended, tmp_path, kind):
    destination = tmp_path / "public"
    export(amended, destination)
    if kind == "extra":
        (destination / "private-log.txt").write_text("unregistered content")
    elif kind == "empty-directory":
        (destination / "unexpected-empty").mkdir()
    elif kind == "symlink":
        (destination / "leak").symlink_to(tmp_path)
    else:
        os.mkfifo(destination / "pipe")
    with pytest.raises(ValueError):
        publication.verify_public_bundle(destination)


def test_outer_checksum_envelope_is_scanned(amended, tmp_path):
    destination = tmp_path / "public"
    export(amended, destination)
    value = read_json(destination / "CHECKSUMS.json")
    value["access_token"] = "synthetic-sensitive-envelope"
    write_json(destination / "CHECKSUMS.json", value)
    with pytest.raises(ValueError, match="sensitive"):
        publication.verify_public_bundle(destination)


def test_fresh_destination_required_and_cli_verify_matches(amended, tmp_path, capsys):
    destination = tmp_path / "public"
    result = export(amended, destination)
    assert (
        publication.main(["verify", str(destination), "--amendment-sha256", result["amendment_sha256"]]) == 0
    )
    assert json.loads(capsys.readouterr().out) == result
    with pytest.raises(ValueError, match="fresh destination"):
        export(amended, destination)


@pytest.mark.parametrize("mutation", ["zero-response-tokens", "invented-open-child"])
def test_projection_cannot_claim_impossible_owned_response_or_lifecycle_semantics(amended, mutation):
    path = (
        amended["source"]
        / controller.AMENDMENT
        / "usage"
        / amended["schedule"][8]["trial_id"]
        / "attempt-1.json"
    )
    value = read_json(path)["derived_usage"]
    if mutation == "zero-response-tokens":
        value["agents"][1]["lower_bounds"]["model_calls"] = 0
        value["lower_bounds"]["model_calls"] -= 1
        expected = "response-count"
    else:
        value["delegation_boundary_status"] = "unverified"
        value["completeness_reasons"].append("child_concurrency_unverified")
        value["completeness_reasons"].sort()
        expected = "delegation completeness"
    with pytest.raises(ValueError, match=expected):
        publication.validate_derived(value)
