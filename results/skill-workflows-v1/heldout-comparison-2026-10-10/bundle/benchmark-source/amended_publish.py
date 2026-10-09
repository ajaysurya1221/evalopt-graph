#!/usr/bin/env python3
"""Export an offline accounting-amendment wrapper around unchanged pilot evidence."""

from __future__ import annotations

import argparse
import json
import math
import re
import stat
from pathlib import Path

import amended_pilot as amendment
import publish_bundle as legacy
from lib.common import bytes_digest, canonical_bytes, digest, exact, is_digest
from runtime.controller import require_controller
from runtime.verify import strict_json

HERE = Path(__file__).resolve().parent
COUNTERS = amendment.COUNTERS
ROOT_FILES = {"amendment.json", "resource-report.json", "PUBLICATION.json", "CLAIMS.md", "README.md"}
SIDECAR_SCOPE = "controller-derived usage from hash-bound retained native logs; hashes are content identity, not authentication"
SCOPE = "arithmetic replay from sanitized, source-bound controller counters; no raw-log replay, independent authentication, recovered missing usage, or independent agent replication"
REASONS = {
    "duplicate_json_field",
    "invalid_native_json",
    "native_log_directory_missing",
    "native_log_symlink",
    "native_log_not_regular",
    "missing_lifecycle_timestamp",
    "invalid_lifecycle_timestamp",
    "empty_native_log",
    "invalid_native_record",
    "invalid_native_turn_identity",
    "native_owner_metadata_missing",
    "duplicate_or_missing_native_owner",
    "unsupported_native_cli_version",
    "unknown_native_session_source",
    "delegation_depth_exceeded",
    "invalid_native_child_identity",
    "native_session_logs_missing",
    "native_parent_roster_invalid",
    "duplicate_native_child_path",
    "native_parent_or_depth_invalid",
    "ambiguous_native_turn_ownership",
    "unknown_copied_session_owner",
    "missing_native_response_identity",
    "duplicate_native_response_usage",
    "unattributable_native_response_turn",
    "invalid_native_token_counter",
    "unknown_native_token_counter",
    "missing_native_token_counter",
    "unattributable_copied_response_usage",
    "duplicate_or_unordered_native_start",
    "duplicate_native_turn_end",
    "unattributable_native_tool_call",
    "native_tool_after_turn_end",
    "duplicate_or_missing_native_tool_call",
    "duplicate_native_spawn_result",
    "unknown_native_spawn_result",
    "duplicate_or_invalid_spawned_child",
    "unresolved_native_spawn_roster",
    "owned_turn_start_missing",
    "owned_turn_end_missing",
    "owned_turn_aborted",
    "native_end_precedes_start",
    "owned_turns_missing",
    "native_child_roster_mismatch",
    "native_child_concurrency_exceeded",
    "owned_turn_usage_missing",
    "owned_response_usage_missing",
    "child_concurrency_unverified",
    "strict_parser_rejected_complete_evidence",
    "strict_parser_counter_mismatch",
    "native_logs_changed_during_derivation",
    "native_logs_unreadable",
}
INCOMPLETE_REASONS = {
    "owned_turn_start_missing",
    "owned_turn_end_missing",
    "owned_turn_aborted",
    "owned_turns_missing",
    "owned_turn_usage_missing",
    "owned_response_usage_missing",
}
STOP_REASONS = {
    "runtime_identity_requires_remediation",
    "accounting_provenance_requires_remediation",
    "delegation_boundary_requires_remediation",
    "usage_accounting_requires_remediation",
    "contradictory_partial_accounting",
    "contradictory_complete_accounting",
    "original_complete_accounting_changed",
    "subscription_exhausted",
    "subscription_permission_unavailable",
    "infrastructure_failure_requires_inspection",
    "interrupted_controller_requires_recovery",
    "dispatch_requires_inspection",
}


def _require(condition, message):
    if not condition:
        raise legacy.PublicationError(message)


def _read(path):
    return strict_json(legacy._read_regular(path))


def _counter_map(value, *, nullable=False):
    exact(value, set(COUNTERS), "derived resource counters")
    _require(
        all(item is None for item in value.values())
        if nullable
        else all(type(item) is int and item >= 0 for item in value.values()),
        "derived resource counters have invalid semantics",
    )


def _reasons(value, allowed):
    _require(
        isinstance(value, list) and all(isinstance(item, str) for item in value), "invalid accounting reasons"
    )
    _require(value == sorted(set(value)) and set(value) <= allowed, "unknown or duplicate accounting reason")


def validate_derived(value):
    """Validate a supplied sanitized projection; never imply raw-log re-derivation."""
    exact(
        value,
        {
            "schema_version",
            "accounting_status",
            "provenance_status",
            "child_usage_complete",
            "lower_bounds",
            "completeness_reasons",
            "efficiency_eligible",
            "delegation_boundary_status",
            "agents",
            "complete_usage",
            "source_log_sha256",
        },
        "derived usage",
    )
    _require(
        value["schema_version"] == "evalopt.partial-workflow-usage.v1", "unsupported derived usage schema"
    )
    _require(
        value["accounting_status"] in {"complete", "partial", "unavailable"}, "unknown accounting status"
    )
    _require(value["provenance_status"] in {"valid", "invalid", "unavailable"}, "unknown provenance status")
    _require(
        value["delegation_boundary_status"] in {"verified", "unverified", "invalid"},
        "unknown delegation status",
    )
    _require(
        type(value["child_usage_complete"]) is bool and type(value["efficiency_eligible"]) is bool,
        "invalid completeness flags",
    )
    _reasons(value["completeness_reasons"], REASONS)
    hashes = value["source_log_sha256"]
    _require(
        isinstance(hashes, list) and all(is_digest(item) for item in hashes) and hashes == sorted(hashes),
        "invalid native-source hash bag",
    )
    if value["accounting_status"] == "unavailable":
        _counter_map(value["lower_bounds"], nullable=True)
        _require(
            value["provenance_status"] != "valid"
            and not value["child_usage_complete"]
            and not value["efficiency_eligible"]
            and value["complete_usage"] is None
            and value["agents"] == []
            and bool(value["completeness_reasons"])
            and value["delegation_boundary_status"]
            == ("invalid" if value["provenance_status"] == "invalid" else "unverified"),
            "unavailable accounting contradicts its evidence",
        )
        return
    _require(
        value["provenance_status"] == "valid" and bool(hashes) and len(hashes) == len(set(hashes)),
        "usable accounting lacks distinct source identities",
    )
    _counter_map(value["lower_bounds"])
    agents = value["agents"]
    _require(
        isinstance(agents, list) and bool(agents) and len(agents) == len(hashes),
        "invalid sanitized agent roster",
    )
    combined_reasons = set()
    for index, agent in enumerate(agents):
        exact(
            agent,
            {"agent_id", "parent_id", "lower_bounds", "complete", "completeness_reasons"},
            "sanitized agent",
        )
        _require(
            agent["agent_id"] == f"agent-{index}"
            and agent["parent_id"] == (None if index == 0 else "agent-0"),
            "invalid sanitized ownership",
        )
        _counter_map(agent["lower_bounds"])
        _reasons(agent["completeness_reasons"], INCOMPLETE_REASONS)
        _require(
            type(agent["complete"]) is bool and agent["complete"] == (not agent["completeness_reasons"]),
            "agent completeness contradicts its reasons",
        )
        _require(
            not agent["complete"] or agent["lower_bounds"]["model_calls"] > 0,
            "complete agent lacks a response record",
        )
        no_response = agent["lower_bounds"]["model_calls"] == 0
        _require(
            no_response == ("owned_response_usage_missing" in agent["completeness_reasons"])
            and (
                not no_response
                or all(agent["lower_bounds"][key] == 0 for key in ("input_tokens", "output_tokens"))
            ),
            "response-count projection contradicts token lower bounds or reasons",
        )
        combined_reasons.update(agent["completeness_reasons"])
    _require(
        value["lower_bounds"]
        == {key: sum(agent["lower_bounds"][key] for agent in agents) for key in COUNTERS},
        "per-agent lower bounds do not sum to the trial",
    )
    unclosed_child = any(
        set(agent["completeness_reasons"])
        & {"owned_turn_start_missing", "owned_turn_end_missing", "owned_turns_missing"}
        for agent in agents[1:]
    )
    _require(
        (value["delegation_boundary_status"] == "unverified") == unclosed_child,
        "delegation completeness contradicts child lifecycle projection",
    )
    if value["delegation_boundary_status"] == "unverified":
        combined_reasons.add("child_concurrency_unverified")
    _require(
        value["delegation_boundary_status"] != "invalid", "valid accounting has invalid delegation provenance"
    )
    _require(
        value["completeness_reasons"] == sorted(combined_reasons),
        "trial completeness differs from owned evidence",
    )
    if value["accounting_status"] == "partial":
        _require(
            bool(combined_reasons)
            and value["child_usage_complete"] is False
            and value["efficiency_eligible"] is False
            and value["complete_usage"] is None,
            "partial accounting cannot become exact or efficiency eligible",
        )
        return
    complete = value["complete_usage"]
    exact(
        complete,
        {"schema_version", *COUNTERS, "wall_seconds", "agent_count", "aggregation", "child_usage_complete"},
        "strict complete usage",
    )
    _require(
        not combined_reasons
        and value["child_usage_complete"] is True
        and value["efficiency_eligible"] is True
        and value["delegation_boundary_status"] == "verified"
        and complete["schema_version"] == "evalopt.workflow-usage.v1"
        and complete["child_usage_complete"] is True
        and type(complete["agent_count"]) is int
        and complete["agent_count"] == len(agents)
        and complete["aggregation"] == "agent_exclusive"
        and all(
            type(complete[key]) is int and complete[key] == value["lower_bounds"][key] for key in COUNTERS
        )
        and type(complete["wall_seconds"]) in (int, float)
        and math.isfinite(complete["wall_seconds"])
        and complete["wall_seconds"] >= 0,
        "strict complete accounting differs from its derived projection",
    )


def _attempt_key(record):
    _require(
        type(record.get("attempt")) is int and record["attempt"] == 1, "amendment cannot publish a retry"
    )
    legacy._safe_relative(record["trial_id"])
    _require("/" not in record["trial_id"], "invalid amendment trial identity")
    return record["trial_id"] + "/attempt-1"


def _validate_amendment(record, pilot, schedule, identity):
    exact(
        record,
        {
            "schema_version",
            "authorization",
            "controller",
            "controller_sources",
            "policy",
            "pilot_registration_sha256",
            "source_lock",
            "schedule_sha256",
            "baseline_attempts",
            "pending_trial_ids",
            "baseline_usage",
            "pause_receipt",
            "local_sources_sha256",
        },
        "accounting amendment",
    )
    _require(digest(record) == identity and is_digest(identity), "amendment differs from explicit identity")
    _require(
        record["schema_version"] == "evalopt.partial-accounting-amendment.v1", "unsupported amendment schema"
    )
    _require(
        record["authorization"]
        == {"decision": "allow_partial_accounting", "statement": "partial accounting"},
        "unsupported amendment authorization",
    )
    _require(record["policy"] == amendment.POLICY, "amendment policy changed")
    _require(
        record["controller"] == require_controller()
        and record["controller_sources"] == amendment.code_identity(),
        "amendment controller source or interpreter differs",
    )
    _require(
        record["pilot_registration_sha256"] == digest(_read(pilot / "registration-lock.json")),
        "amendment registration differs from pilot",
    )
    _require(
        record["source_lock"] == _read(pilot / "source-lock.json"),
        "amendment frozen conditions differ from pilot",
    )
    _require(record["schedule_sha256"] == digest(schedule), "amendment schedule differs from pilot")
    _require(is_digest(record["local_sources_sha256"]), "invalid private-source identity")
    baseline, pending = record["baseline_attempts"], record["pending_trial_ids"]
    _require(
        isinstance(baseline, list) and len(baseline) == 9, "amendment must preserve nine baseline attempts"
    )
    for row in baseline:
        exact(row, {"trial_id", "attempt", "finish_sha256", "manifest_sha256"}, "amendment baseline attempt")
        _attempt_key(row)
        _require(
            is_digest(row["finish_sha256"]) and is_digest(row["manifest_sha256"]),
            "invalid baseline artifact identity",
        )
    base_ids = [row["trial_id"] for row in baseline]
    _require(
        len(set(base_ids)) == 9
        and isinstance(pending, list)
        and len(pending) == len(set(pending)) == 27
        and all(isinstance(item, str) for item in pending)
        and not set(base_ids) & set(pending)
        and set(base_ids) | set(pending) == {row["trial_id"] for row in schedule}
        and pending == [row["trial_id"] for row in schedule if row["trial_id"] not in base_ids],
        "amendment baseline and pending roster differ from the 36-trial pilot",
    )
    _require(
        isinstance(record["baseline_usage"], dict)
        and set(record["baseline_usage"]) == {_attempt_key(row) for row in baseline},
        "baseline usage identity roster differs",
    )
    _require(
        all(is_digest(value) for value in record["baseline_usage"].values()),
        "invalid baseline usage identity",
    )
    pause = record["pause_receipt"]
    exact(pause, {"path", "sha256"}, "accounting pause binding")
    _require(
        isinstance(pause["path"], str) and re.fullmatch(r"runs/run-[0-9]{4}/end\.json", pause["path"]),
        "invalid original pause path",
    )
    runs = _read(pilot / "reports/scheduler-runs.json")
    matching = [run for run in runs if run["run"] == Path(pause["path"]).parts[1]]
    _require(
        len(matching) == 1 and matching[0]["end"].get("reason") == "usage_accounting_requires_remediation",
        "accounting amendment lacks its original pause",
    )
    _require(
        bytes_digest(canonical_bytes(matching[0]["end"]) + b"\n") == pause["sha256"],
        "original pause differs from its canonical retained report",
    )


def _validate_sidecars(directory, record, schedule, store, identity):
    expected = {}
    for state in store.statuses():
        _require(state["attempts"] in (0, 1), "amendment cannot publish retried attempts")
        if state["attempts"]:
            expected[state["trial_id"] + "/attempt-1"] = state
    paths = sorted((directory / "usage").glob("*/attempt-1.json"))
    _require(
        {str(path.relative_to(directory / "usage"))[:-5] for path in paths} == set(expected),
        "usage sidecar coverage differs from retained attempts",
    )
    baseline = {_attempt_key(row): row for row in record["baseline_attempts"]}
    sidecars = []
    for path in paths:
        value = _read(path)
        exact(
            value,
            {
                "schema_version",
                "amendment_sha256",
                "trial_id",
                "attempt",
                "finish_sha256",
                "manifest_sha256",
                "derived_usage",
                "continuation_admissible",
                "continuation_blocker",
                "scope",
            },
            "amended attempt usage",
        )
        key = _attempt_key(value)
        _require(
            key in expected and path.relative_to(directory / "usage").as_posix() == key + ".json",
            "usage sidecar path differs from its trial",
        )
        _require(
            value["schema_version"] == "evalopt.amended-attempt-usage.v1"
            and value["amendment_sha256"] == identity
            and value["scope"] == SIDECAR_SCOPE,
            "sidecar amendment or scope differs",
        )
        attempt = directory / "pilot/evidence/trials" / key
        for name in ("finish", "manifest"):
            _require(
                value[name + "_sha256"] == bytes_digest(legacy._read_regular(attempt / (name + ".json"))),
                "sidecar original artifact binding changed",
            )
        finish = _read(attempt / "finish.json")
        validate_derived(value["derived_usage"])
        allowed, reason = amendment.admit(finish.get("usage") or {}, value["derived_usage"])
        _require(
            type(value["continuation_admissible"]) is bool
            and value["continuation_admissible"] == allowed
            and value["continuation_blocker"] == reason,
            "sidecar continuation admission does not reproduce",
        )
        if key in baseline:
            _require(
                finish["status"] == "completed" and allowed,
                "baseline attempt differs from approved continuation",
            )
            _require(
                {field: value[field] for field in baseline[key]} == baseline[key],
                "original baseline attempt changed",
            )
            _require(
                digest(value["derived_usage"]) == record["baseline_usage"][key],
                "baseline derived usage changed",
            )
        sidecars.append(value)
    _require(set(baseline) <= set(expected), "original baseline attempt is missing")
    # Preserve schedule order when calling the controller's pure report helper.
    order = {row["trial_id"]: index for index, row in enumerate(schedule)}
    return sorted(sidecars, key=lambda row: order[row["trial_id"]])


def _validate_runs(directory, record, sidecars, identity):
    seen = set()
    by_trial = {row["trial_id"]: row for row in sidecars}
    baseline = {row["trial_id"] for row in record["baseline_attempts"]}
    finishes = {
        trial: _read(directory / "pilot/evidence/trials" / trial / "attempt-1/finish.json")
        for trial in by_trial
    }

    def pause(retained):
        selected = [row for row in sidecars if row["trial_id"] in retained]
        attempts = [
            {
                "trial_id": row["trial_id"],
                "status": finishes[row["trial_id"]]["status"],
                "error_code": finishes[row["trial_id"]].get("error_code"),
            }
            for row in selected
        ]
        # Reuse the frozen controller's stop priority, including infrastructure
        # failures and quota pauses. Public evidence contains only terminal attempts.
        return amendment._pause({"attempts": attempts, "states": []}, selected)

    root = directory / "runs"
    for run in sorted(root.iterdir()) if root.exists() else []:
        _require(run.is_dir() and re.fullmatch(r"run-[0-9]{4}", run.name), "invalid amendment run directory")
        start, end = _read(run / "start.json"), _read(run / "end.json")
        exact(start, {"schema_version", "amendment_sha256", "pending_at_start"}, "amended run start")
        queue = start["pending_at_start"]
        remaining = [trial for trial in record["pending_trial_ids"] if trial not in seen]
        _require(
            start["schema_version"] == "evalopt.amended-run.v1"
            and start["amendment_sha256"] == identity
            and isinstance(queue, list)
            and queue == remaining[: len(queue)]
            and (bool(queue) or not remaining),
            "amendment run queue differs from pending first attempts",
        )
        if end.get("status") == "interrupted":
            exact(end, {"schema_version", "status", "reason", "dispatched"}, "interrupted amendment run")
            _require(
                isinstance(end["reason"], str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", end["reason"]),
                "invalid sanitized exception type",
            )
        else:
            exact(
                end,
                {"schema_version", "status", "reason", "trial_id", "dispatched", "pending_trials"},
                "amendment run end",
            )
            _require(
                end["status"] in {"paused", "limited", "finished"} and end["reason"] in STOP_REASONS | {None},
                "invalid amendment stop status",
            )
            _require(
                (end["status"] == "paused") == (end["reason"] is not None),
                "amendment stop reason contradicts status",
            )
            _require(
                end["trial_id"] is None
                or end["trial_id"] in {row["trial_id"] for row in sidecars} | set(queue),
                "amendment stop refers to unknown trial",
            )
        dispatched = end["dispatched"]
        _require(
            end["schema_version"] == "evalopt.amended-stop.v1"
            and isinstance(dispatched, list)
            and dispatched == queue[: len(dispatched)]
            and not set(dispatched) & seen,
            "amendment dispatch is not a pending first-attempt prefix",
        )
        permissions = {}
        for path in sorted(run.glob("*/permission.json")):
            permission = _read(path)
            exact(
                permission,
                {"schema_version", "trial_id", "amendment_sha256", "ordinary_usage_allowed", "state"},
                "amended subscription permission",
            )
            trial = permission["trial_id"]
            _require(
                trial == path.parent.name and trial in queue and trial not in permissions,
                "permission receipt has an unregistered trial",
            )
            _require(
                permission["schema_version"] == "evalopt.amended-permission.v1"
                and permission["amendment_sha256"] == identity
                and type(permission["ordinary_usage_allowed"]) is bool
                and permission["state"] in {"allowed", "exhausted", "unavailable"}
                and permission["ordinary_usage_allowed"] == (permission["state"] == "allowed"),
                "invalid subscription permission receipt",
            )
            permissions[trial] = permission
        _require(
            all(permissions.get(trial, {}).get("ordinary_usage_allowed") is True for trial in dispatched),
            "dispatched amendment attempt lacks allowed subscription receipt",
        )
        _require(
            set(permissions) <= set(queue[: len(dispatched) + 1]),
            "permission receipt lies beyond the dispatched prefix",
        )
        completed = set()
        for path in sorted(run.glob("*/completed.json")):
            receipt = _read(path)
            exact(
                receipt,
                {
                    "schema_version",
                    "amendment_sha256",
                    "trial_id",
                    "attempt",
                    "finish_sha256",
                    "manifest_sha256",
                    "sidecar_sha256",
                },
                "amended completion receipt",
            )
            _attempt_key(receipt)
            trial = receipt["trial_id"]
            _require(
                receipt["schema_version"] == "evalopt.amended-completion.v1"
                and receipt["amendment_sha256"] == identity
                and trial == path.parent.name
                and trial in dispatched
                and trial in by_trial
                and trial not in completed,
                "invalid amended completion roster",
            )
            source = by_trial[trial]
            _require(
                receipt["sidecar_sha256"] == digest(source)
                and all(
                    receipt[key] == source[key] for key in ("finish_sha256", "manifest_sha256", "attempt")
                ),
                "amended completion differs from bound sidecar or attempt",
            )
            completed.add(trial)
        _require(completed == set(dispatched), "dispatched amendment attempt lacks completion binding")
        reason, blocked = pause(baseline | seen)
        for trial in dispatched:
            _require(reason is None, "amendment dispatched after a retained continuation blocker")
            seen.add(trial)
            reason, blocked = pause(baseline | seen)
        if end["status"] != "interrupted":
            extra = set(permissions) - set(dispatched)
            if reason is not None:
                _require(not extra, "amendment checked another dispatch after a retained blocker")
            elif extra:
                _require(len(extra) == 1, "ambiguous nondispatched permission receipt")
                blocked = next(iter(extra))
                permission = permissions[blocked]
                _require(
                    permission["ordinary_usage_allowed"] is False,
                    "allowed permission lacks a retained dispatch",
                )
                reason = (
                    "subscription_exhausted"
                    if permission["state"] == "exhausted"
                    else "subscription_permission_unavailable"
                )
            _require(
                end["reason"] == reason and end["trial_id"] == blocked,
                "amendment stop reason does not reproduce retained continuation gates",
            )
            _require(
                reason is not None or dispatched == queue,
                "unblocked amendment stopped before its queued limit",
            )
            _require(
                type(end["pending_trials"]) is int and end["pending_trials"] == 27 - len(seen),
                "amendment run pending count differs",
            )
            _require(
                (end["status"] == "finished") == (not end["reason"] and end["pending_trials"] == 0),
                "amendment finished status differs from coverage",
            )
    later = {row["trial_id"] for row in sidecars} - {row["trial_id"] for row in record["baseline_attempts"]}
    _require(seen == later, "amended attempt coverage differs from dispatch receipts")


def _claims(report):
    partial = sum(row["partial_attempts"] for row in report["arms"].values())
    unavailable = sum(row["unavailable_accounting_attempts"] for row in report["arms"].values())
    return (
        "# Claim-to-evidence limits\n\n"
        "| Claim | Retained evidence and limit |\n| --- | --- |\n"
        "| Original outcomes | pilot/ retains original finish, grade, policy and report bytes; partial accounting does not rescore or remove outcomes. |\n"
        f"| Accounting coverage | {report['retained_attempts']} retained attempts out of 36 scheduled; {partial} partial and {unavailable} unavailable. See resource-report.json and usage/. |\n"
        "| Resource arithmetic | Replayed from sanitized, source-bound controller counters. Native logs remain private; public replay does not independently derive or authenticate these counters. |\n"
        "| Missing usage | Partial counters are lower bounds with unknown upper bounds. They are not recovered exact totals. Complete-attempt subtotals must not be added to observed lower bounds. |\n"
        "| Efficiency | No efficiency comparison is supported while any selected attempt is partial, unavailable, blocked or unexecuted. |\n"
        "| Continuation | amendment.json binds the prospective authorization, unchanged nine-attempt baseline and 27 pending first attempts; runs/ retains bounded permission and dispatch receipts. |\n"
        "| Workflow advantage and independent replication | Neither is established by this development pilot or arithmetic replay. This is maintainer-run evidence. |\n"
    ).encode()


def _readme():
    return (
        b"# Offline amended pilot evidence candidate\n\n"
        b"This local candidate wraps unchanged pilot evidence with an explicit partial-accounting amendment. The exporter does not upload files.\n\n"
        b"Use the registered controller source and CPython 3.13.12:\n\n"
        b"```sh\npython bench/harbor/skill-workflows-v1/amended_publish.py verify /path/to/bundle\n```\n\n"
        b"[Resource report](resource-report.json), [amendment](amendment.json), [claim limits](CLAIMS.md), and [original pilot evidence](pilot/README.md). Public checks replay policy decisions, original outcome analysis and resource arithmetic. Raw native logs, local source paths and authentication data are excluded. Hashes establish content identity, not authentication or independent raw-log replay. The bounded sensitive-content scan is not proof that every possible secret was recognized.\n"
    )


def _allowed(name):
    parts = legacy._safe_relative(name).parts
    return (
        name in ROOT_FILES
        or parts[0] == "pilot"
        or (len(parts) == 3 and parts[0] == "usage" and parts[2] == "attempt-1.json")
        or (
            len(parts) in {3, 4}
            and parts[0] == "runs"
            and re.fullmatch(r"run-[0-9]{4}", parts[1])
            and (
                (len(parts) == 3 and parts[2] in {"start.json", "end.json"})
                or (len(parts) == 4 and parts[3] in {"permission.json", "completed.json"})
            )
        )
    )


def _payloads(directory):
    result = {}
    directories = set()
    for path in sorted(directory.rglob("*")):
        _require(not path.is_symlink(), "symlink in amended public candidate")
        _require(
            path.is_dir() or stat.S_ISREG(path.lstat().st_mode), "nonregular node in amended public candidate"
        )
        if path.is_dir():
            directories.add(path.relative_to(directory).as_posix())
        elif path.is_file():
            name = path.relative_to(directory).as_posix()
            if name != "CHECKSUMS.json":
                _require(_allowed(name), "non-whitelisted amendment artifact")
                result[name] = legacy._read_regular(path)
    expected_directories = {
        parent.as_posix() for name in result for parent in Path(name).parents if parent.as_posix() != "."
    }
    _require(directories == expected_directories, "unexpected empty directory in amended public candidate")
    return result


def _checksums(payloads, identity):
    files = {name: {"sha256": bytes_digest(raw), "size": len(raw)} for name, raw in sorted(payloads.items())}
    return {
        "schema_version": "evalopt.amended-public-checksums.v1",
        "amendment_sha256": identity,
        "bundle_id": digest(files),
        "files": files,
    }


def verify_public_bundle(directory, *, amendment_sha256=None, bundle_id=None):
    require_controller()
    directory = legacy._safe_root(directory)
    checksum_raw = legacy._read_regular(directory / "CHECKSUMS.json")
    legacy.scan_public_file("CHECKSUMS.json", checksum_raw)
    checksum = strict_json(checksum_raw)
    exact(checksum, {"schema_version", "amendment_sha256", "bundle_id", "files"}, "amended public checksums")
    payloads = _payloads(directory)
    identity = checksum["amendment_sha256"]
    _require(
        checksum == _checksums(payloads, identity), "amended public checksums differ from retained bytes"
    )
    _require(
        amendment_sha256 is None or identity == amendment_sha256,
        "public amendment differs from requested identity",
    )
    _require(
        bundle_id is None or checksum["bundle_id"] == bundle_id,
        "public bundle differs from requested identity",
    )
    for name, raw in payloads.items():
        legacy.scan_public_file(name, raw)
    base = legacy.verify_public_bundle(directory / "pilot")
    _, schedule = legacy._public_registration(directory / "pilot")
    _require(
        len(schedule) == 36 and all(row["stage"] == "pilot" for row in schedule),
        "amendment requires the 36-trial pilot",
    )
    record = _read(directory / "amendment.json")
    _validate_amendment(record, directory / "pilot", schedule, identity)
    store = legacy._read_only_store(directory / "pilot/evidence", schedule)
    sidecars = _validate_sidecars(directory, record, schedule, store, identity)
    _validate_runs(directory, record, sidecars, identity)
    base_publication = _read(directory / "pilot/PUBLICATION.json")
    report = amendment.summarize_resources(
        identity,
        record["pilot_registration_sha256"],
        schedule,
        store.statuses(),
        sidecars,
        base_publication["report_export_id"],
    )
    _require(
        legacy._read_regular(directory / "resource-report.json") == canonical_bytes(report) + b"\n",
        "amended resource arithmetic does not reproduce",
    )
    expected = {
        "schema_version": "evalopt.amended-public-evidence.v1",
        "amendment_sha256": identity,
        "pilot_bundle_id": base["bundle_id"],
        "resource_report_sha256": digest(report),
        "exporter_sha256": bytes_digest(Path(__file__).read_bytes()),
        "scope": SCOPE,
        "raw_native_log_replay": False,
        "independent_authentication": False,
        "independent_replication": False,
        "original_outcomes_changed": False,
        "network_publication_performed": False,
    }
    _require(
        _read(directory / "PUBLICATION.json") == expected, "amended publication identity or scope differs"
    )
    _require(
        payloads["CLAIMS.md"] == _claims(report) and payloads["README.md"] == _readme(),
        "amended public claims differ from retained evidence",
    )
    return {
        "schema_version": "evalopt.amended-public-verification.v1",
        "bundle_id": checksum["bundle_id"],
        "amendment_sha256": identity,
        "resource_report_sha256": digest(report),
        "files": len(payloads),
        "pilot_attempts_verified": base["attempts_verified"],
        "policy_decisions_replayed": base["policy_decisions_replayed"],
        "resource_arithmetic_reproduced": True,
        "source_bound_counter_projection": True,
        "raw_native_log_replay": False,
        "independent_authentication": False,
        "independent_replication": False,
        "efficiency_comparison_eligible": report["efficiency_comparison_eligible"],
        "network_publication_performed": False,
    }


def export_public_bundle(campaign_directory, destination, *, amendment_sha256, bridge=None):
    require_controller()
    campaign, destination = map(legacy._safe_root, (campaign_directory, destination))
    _require(
        not destination.exists()
        and not destination.is_relative_to(campaign)
        and not campaign.is_relative_to(destination),
        "amended export requires a fresh destination outside the campaign",
    )
    report = amendment.report(campaign, amendment_sha256, bridge=bridge)
    verified = amendment.verify(campaign, amendment_sha256, bridge=bridge)
    base = legacy.export_public_bundle(
        campaign,
        destination / "pilot",
        frozen_source=verified["local"]["frozen_source"],
        export_id=report["frozen_export_id"],
    )
    source = campaign / amendment.AMENDMENT
    payloads = {
        "amendment.json": legacy._read_regular(source / "amendment.json"),
        "resource-report.json": canonical_bytes(report["resource_report"]) + b"\n",
    }
    for folder in ("usage", "runs"):
        if (source / folder).exists():
            for path in sorted((source / folder).rglob("*")):
                _require(
                    not path.is_symlink() and (path.is_dir() or stat.S_ISREG(path.lstat().st_mode)),
                    "invalid private amendment artifact node",
                )
                if path.is_file():
                    name = path.relative_to(source).as_posix()
                    _require(_allowed(name), "non-whitelisted amendment receipt")
                    payloads[name] = legacy._read_regular(path)
    payloads["PUBLICATION.json"] = (
        canonical_bytes(
            {
                "schema_version": "evalopt.amended-public-evidence.v1",
                "amendment_sha256": amendment_sha256,
                "pilot_bundle_id": base["bundle_id"],
                "resource_report_sha256": report["report_sha256"],
                "exporter_sha256": bytes_digest(Path(__file__).read_bytes()),
                "scope": SCOPE,
                "raw_native_log_replay": False,
                "independent_authentication": False,
                "independent_replication": False,
                "original_outcomes_changed": False,
                "network_publication_performed": False,
            }
        )
        + b"\n"
    )
    payloads["CLAIMS.md"], payloads["README.md"] = _claims(report["resource_report"]), _readme()
    # Detect concurrent dispatch or source mutation between the report and base export.
    after = amendment.verify(campaign, amendment_sha256, bridge=bridge)
    _require(
        after["amendment"] == verified["amendment"] and after["info"] == verified["info"],
        "campaign changed during amended publication",
    )
    for name, raw in payloads.items():
        legacy.scan_public_file(name, raw)
        target = destination / legacy._safe_relative(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
    checksum = canonical_bytes(_checksums(_payloads(destination), amendment_sha256)) + b"\n"
    legacy.scan_public_file("CHECKSUMS.json", checksum)
    with (destination / "CHECKSUMS.json").open("xb") as stream:
        stream.write(checksum)
    return verify_public_bundle(destination, amendment_sha256=amendment_sha256)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--campaign", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    export.add_argument("--amendment-sha256", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    verify.add_argument("--amendment-sha256")
    verify.add_argument("--bundle-id")
    args = parser.parse_args(argv)
    result = (
        export_public_bundle(args.campaign, args.destination, amendment_sha256=args.amendment_sha256)
        if args.command == "export"
        else verify_public_bundle(
            args.directory, amendment_sha256=args.amendment_sha256, bundle_id=args.bundle_id
        )
    )
    print(json.dumps(result, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
