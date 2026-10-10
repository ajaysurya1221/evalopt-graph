"""Pure, typed prospective predicate. No repair, execution, imports of candidate code."""

import hashlib
import json
import math
from datetime import datetime

REASON = "execution_boundary_requires_remediation"
ERROR = "outstanding candidate work prevents original-verifier scoring"
IDENTITY = ("pid", "started", "ppid", "pgid", "sid")


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def number(value, *, minimum=0):
    require(
        type(value) in (int, float) and math.isfinite(value) and value >= minimum, "invalid finite number"
    )
    return value


def instant(value):
    require(type(value) is str, "timestamp is not text")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(result.tzinfo is not None, "timestamp is not timezone aware")
    return result


def process(row):
    for key in ("pid", "ppid", "pgid", "sid"):
        require(
            type(row.get(key)) is int and row[key] >= (0 if key == "ppid" else 1), "invalid process identity"
        )
    require(
        type(row.get("started")) is str and row["started"].isdigit() and int(row["started"]) > 0,
        "invalid process start ticks",
    )
    return row["pid"], row["started"]


def classify(data, *, validate_accounting):
    """Return quarantine only for the complete exact predicate, otherwise raise.

    The collector owns file/hash/native correspondence. validate_accounting is the
    unchanged frozen validator bound by the trusted collector; it must return the
    exact validated derived accounting object. This pure seam performs no IO.
    """
    require(
        set(data)
        == {
            "row",
            "finish",
            "summary",
            "harbor",
            "stop",
            "stop_failure",
            "identity",
            "exposure",
            "native_end",
            "child_result",
            "child_returncode",
            "strict_reason",
            "raw_nodes",
            "services",
            "collected_at",
        },
        "wrong predicate input roster",
    )
    row, finish, summary = data["row"], data["finish"], data["summary"]
    require(
        type(row.get("ordinal")) is int and 56 <= row["ordinal"] <= 71, "row outside approved pending scope"
    )
    require(
        type(finish.get("attempt")) is int and finish["attempt"] == 1, "attempt is not exact first attempt"
    )
    require(
        finish.get("trial_id") == row["trial_id"]
        and finish.get("status") == "timeout"
        and finish["error_code"] is None,
        "not eligible finalized timeout",
    )
    require(digest({k: summary.get(k) for k in row}) == digest(row), "summary row differs")
    require(summary.get("status") == "timeout" and summary["error_code"] is None, "summary timeout differs")
    for key in (
        "execution_boundary_complete",
        "artifact_capture_complete",
        "runtime_evidence_complete",
        "raw_artifacts_publication_ready",
    ):
        require(summary.get(key) is False, "unexpected boundary/capture completeness")
    require(
        summary["upstream_reward"] is None and summary["functional_success"] is None,
        "quarantine must remain unscored",
    )
    usage = summary["usage"]
    require(digest(finish.get("usage")) == digest(usage), "finish/summary usage differs")
    for key in (
        "runtime_valid",
        "agent_started",
        "native_agent_stopped",
        "agent_deadline_expired",
        "workflow_exposure_verified",
        "entrypoint_load_observed",
    ):
        require(usage.get(key) is True, "required native observation missing: " + key)
    require(usage.get("execution_boundary_complete") is False, "usage boundary differs")
    for key, expected in {
        "returned_models": ["gpt-6-astra"],
        "returned_efforts": ["ultra"],
        "cli_versions": ["0.154.0"],
    }.items():
        require(digest(usage.get(key)) == digest(expected), "native runtime identity differs")
    derived = validate_accounting(finish)
    require(
        derived is not None and digest(derived) == digest(usage["accounting"]["derived"]),
        "frozen derived accounting differs",
    )
    require(
        derived["accounting_status"] in ("complete", "partial")
        and derived["provenance_status"] == "valid"
        and derived["delegation_boundary_status"] == "verified",
        "invalid accounting or delegation",
    )
    require(data["strict_reason"] == REASON, "original strict gate was not exact boundary failure")
    end, child = data["native_end"], data["child_result"]
    require(
        type(data["child_returncode"]) is int and data["child_returncode"] == 0,
        "child did not return normally",
    )
    require(digest(child["scheduler"]) == digest(end), "child/native ending differs")
    require(
        end.get("schema_version") == "evalopt.scheduler-stop.v1"
        and end.get("status") == "paused"
        and end.get("reason") == REASON
        and end.get("trial_id") == row["trial_id"]
        and end.get("dispatched") == [row["trial_id"]],
        "genuine strict paused end required",
    )
    stop = data["stop"]
    expected_stop_keys = {
        "agent_deadline_seconds",
        "agent_end_hook_at",
        "agent_phase_elapsed_seconds",
        "agent_phase_started_at",
        "boundary_confirmed",
        "confirmed",
        "controller_wall_seconds",
        "frozen_processes",
        "issues",
        "producer",
        "reason",
        "services_preserved",
        "signaled",
        "termination_finished_at",
        "termination_started_at",
        "wall_seconds",
    }
    require(set(stop) == expected_stop_keys, "unexpected stop fields")
    require(
        stop["producer"] == "controller"
        and stop["reason"] == "original_agent_deadline"
        and stop["confirmed"] is True
        and stop["boundary_confirmed"] is False,
        "native stop not confirmed exact deadline failure",
    )
    require(
        stop["services_preserved"] == []
        and data["services"] == []
        and data["identity"].get("service_contracts") == [],
        "service contract not eligible",
    )
    deadline = number(row["agent_seconds"], minimum=1)
    require(
        number(stop["agent_deadline_seconds"], minimum=1) == deadline
        and number(stop["agent_phase_elapsed_seconds"]) >= deadline,
        "deadline not expired",
    )
    number(stop["wall_seconds"])
    number(stop["controller_wall_seconds"])
    started, terminated, finished, hook, ended, collected = (
        instant(v)
        for v in (
            stop["agent_phase_started_at"],
            stop["termination_started_at"],
            stop["termination_finished_at"],
            stop["agent_end_hook_at"],
            end["ended_at"],
            data["collected_at"],
        )
    )
    require(started <= terminated <= hook <= finished <= ended <= collected, "stop/native chronology differs")
    require((terminated - started).total_seconds() >= deadline, "observed deadline not elapsed")
    frozen = {}
    for item in stop["frozen_processes"]:
        require(set(item) == set(IDENTITY) | {"native", "tool"}, "unexpected census fields")
        key = process(item)
        require(
            key not in frozen and type(item["native"]) is bool and type(item["tool"]) is bool,
            "duplicate/invalid census",
        )
        frozen[key] = item
    unclassified = {k: v for k, v in frozen.items() if v["native"] is False and v["tool"] is False}
    issues = {}
    require(type(stop["issues"]) is list and bool(stop["issues"]), "empty stop issue list")
    for item in stop["issues"]:
        require(
            set(item) == set(IDENTITY) | {"kind"} and item["kind"] == "unclassified_new_process",
            "different stop issue",
        )
        key = process(item)
        require(key not in issues and key in unclassified, "duplicate/unmatched stop issue")
        require(
            digest({k: item[k] for k in IDENTITY}) == digest({k: unclassified[key][k] for k in IDENTITY}),
            "census/issue metadata differs",
        )
        issues[key] = item
    require(set(issues) == set(unclassified), "unclassified issue roster differs")
    signals = {}
    for item in stop["signaled"]:
        require(set(item) == {"pid", "started", "kind"}, "unexpected signal fields")
        require(
            type(item["pid"]) is int
            and item["pid"] > 0
            and type(item["started"]) is str
            and item["started"].isdigit()
            and int(item["started"]) > 0,
            "invalid signal identity",
        )
        key = item["pid"], item["started"]
        require(key not in signals and key in frozen, "duplicate/unmatched signal")
        expected_kind = "native" if frozen[key]["native"] else "tool_or_unclassified"
        require(item["kind"] == expected_kind, "wrong signal kind")
        signals[key] = item
    require(set(issues) <= set(signals), "unsignaled unclassified process")
    failure = data["stop_failure"]
    require(
        digest(failure)
        == digest(
            {
                "agent_end_hook_at": stop["agent_end_hook_at"],
                "error_type": "ExecutionBoundaryError",
                "termination_started_at": stop["termination_started_at"],
            }
        ),
        "unexpected end-hook failure",
    )
    harbor = data["harbor"]
    require(
        harbor["verifier_result"] is None and harbor["verifier"] is None, "verifier ran or produced output"
    )
    error = harbor.get("exception_info") or {}
    require(
        error.get("exception_type") == "ExecutionBoundaryError" and error.get("exception_message") == ERROR,
        "different Harbor exception",
    )
    trace = error.get("exception_traceback", "")
    require(
        type(trace) is str
        and "in on_stop" in trace
        and "await self._emit(TrialEvent.AGENT_END)" in trace
        and trace.rstrip().endswith("runtime.transfer.ExecutionBoundaryError: " + ERROR),
        "exception not expected agent-end guard",
    )
    require(
        started <= instant(harbor["agent_execution"]["started_at"]) <= terminated
        and terminated <= instant(harbor["agent_execution"]["finished_at"]) <= hook
        and finished <= instant(harbor["finished_at"]) <= ended,
        "Harbor execution chronology differs",
    )
    exposure = data["exposure"]
    require(
        exposure.get("producer") == "controller"
        and exposure.get("verified_before_agent") is True
        and exposure.get("arm") == row["arm"]
        and bool(exposure.get("source_files")),
        "workflow exposure missing",
    )
    require(
        type(data["raw_nodes"]) is list and len(set(data["raw_nodes"])) == len(data["raw_nodes"]),
        "raw roster invalid",
    )
    for path in data["raw_nodes"]:
        parts = path.split("/")
        require(
            not path.startswith("/") and ".." not in parts and "." not in parts and "" not in parts,
            "unsafe raw node",
        )
        require(
            "stopped" not in parts
            and "verifier" not in parts
            and not path.endswith((".tar", ".tar.gz", ".tgz")),
            "unexpected capture/verifier artifact",
        )
    return {
        "schema_version": "evalopt.transfer-policy-v2.classification.v1",
        "classification": "quarantine",
        "trial_id": row["trial_id"],
        "attempt": 1,
        "row_sha256": digest(row),
        "predicate_version": "unclassified-process-deadline.v1",
        "original_strict_reason": REASON,
        "reward": None,
        "execution_boundary_restored": False,
        "accounting_status": derived["accounting_status"],
        "eligible_for_later_admission_only": True,
        "input_sha256": digest(data),
    }
