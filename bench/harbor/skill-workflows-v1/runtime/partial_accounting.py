"""Conservative, sanitized accounting from retained Codex 0.154.0 native logs.

Only owner-attributed response records and observed tool calls contribute lower
bounds. Missing completion never makes those bounds exact. This module does not
authenticate logs or authorize continuation; the controller must bind these bytes
to its immutable trial capture. It deliberately leaves the strict parser intact.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from lib.accounting import parse_native_usage, summarize_usage

COUNTERS = ("input_tokens", "output_tokens", "model_calls", "tool_calls")
TOKEN_COUNTERS = {
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}
LIFECYCLE = {"task_started", "task_complete", "turn_aborted"}


class _Invalid(ValueError):
    """Contains only a static public reason code, never a native payload."""


def _require(condition, reason):
    if not condition:
        raise _Invalid(reason)


def _identifier(value):
    return isinstance(value, str) and bool(value)


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "duplicate_json_field")
            result[key] = value
        return result

    def nonfinite(_):
        raise _Invalid("invalid_native_json")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    # Also reject an overflowing exponent, which parse_constant does not see.
    json.dumps(value, allow_nan=False)
    return value


def _snapshot(directory):
    root = Path(directory)
    _require(root.is_dir() and not root.is_symlink(), "native_log_directory_missing")
    files = {}
    for path in sorted(root.rglob("*")):
        _require(not path.is_symlink(), "native_log_symlink")
        if path.suffix == ".jsonl":
            _require(path.is_file(), "native_log_not_regular")
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _timestamp(record):
    value = record.get("timestamp")
    _require(isinstance(value, str), "missing_lifecycle_timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _Invalid("invalid_lifecycle_timestamp") from exc
    _require(parsed.utcoffset() is not None, "invalid_lifecycle_timestamp")
    return parsed


def _turns(records):
    return {
        item["payload"]["turn_id"]
        for item in records
        if item["type"] == "turn_context"
        or (item["type"] == "event_msg" and item["payload"].get("type") in LIFECYCLE)
    }


def _load(files):
    sessions = {}
    for raw in files.values():
        records = [_json(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
        _require(bool(records), "empty_native_log")
        for record in records:
            _require(isinstance(record, dict), "invalid_native_record")
            _require(isinstance(record.get("type"), str), "invalid_native_record")
            _require(isinstance(record.get("payload"), dict), "invalid_native_record")
            if record["type"] == "turn_context" or (
                record["type"] == "event_msg" and record["payload"].get("type") in LIFECYCLE
            ):
                _require(_identifier(record["payload"].get("turn_id")), "invalid_native_turn_identity")
        _require(records[0]["type"] == "session_meta", "native_owner_metadata_missing")
        meta = records[0]["payload"]
        agent_id = meta.get("id")
        _require(_identifier(agent_id) and agent_id not in sessions, "duplicate_or_missing_native_owner")
        _require(meta.get("cli_version") == "0.154.0", "unsupported_native_cli_version")
        source = meta.get("source")
        if source == "exec":
            parent, agent_path = None, None
        else:
            _require(isinstance(source, dict), "unknown_native_session_source")
            subagent = source.get("subagent")
            _require(isinstance(subagent, dict), "unknown_native_session_source")
            spawn = subagent.get("thread_spawn")
            _require(isinstance(spawn, dict), "unknown_native_session_source")
            _require(type(spawn.get("depth")) is int and spawn["depth"] == 1, "delegation_depth_exceeded")
            parent, agent_path = spawn.get("parent_thread_id"), spawn.get("agent_path")
            _require(_identifier(parent) and _identifier(agent_path), "invalid_native_child_identity")
        sessions[agent_id] = {
            "records": records,
            "parent": parent,
            "path": agent_path,
            "observed": _turns(records),
        }
    _require(bool(sessions), "native_session_logs_missing")
    parents = [key for key, value in sessions.items() if value["parent"] is None]
    _require(len(parents) == 1, "native_parent_roster_invalid")
    parent = parents[0]
    paths = [value["path"] for value in sessions.values() if value["parent"] is not None]
    _require(len(paths) == len(set(paths)), "duplicate_native_child_path")
    all_turns = set()
    for key, session in sessions.items():
        _require(session["parent"] in (None, parent), "native_parent_or_depth_invalid")
        session["turns"] = session["observed"] - (sessions[parent]["observed"] if key != parent else set())
        _require(not (session["turns"] & all_turns), "ambiguous_native_turn_ownership")
        all_turns.update(session["turns"])
        for item in session["records"][1:]:
            if item["type"] == "session_meta":
                # A child's copied parent metadata does not create another owner.
                _require(
                    key != parent and item["payload"].get("id") == parent, "unknown_copied_session_owner"
                )
    return sessions, parent


def _responses(sessions):
    responses, by_owner = {}, {owner: [] for owner in sessions}
    for owner, session in sessions.items():
        for item in session["records"]:
            if item["type"] != "token_usage_record":
                continue
            payload = item["payload"]
            if payload.get("thread_id") != owner:
                continue
            response_id = payload.get("response_id")
            _require(_identifier(response_id), "missing_native_response_identity")
            _require(response_id not in responses, "duplicate_native_response_usage")
            _require(payload.get("turn_id") in session["turns"], "unattributable_native_response_turn")
            usage = payload.get("usage")
            _require(isinstance(usage, dict), "invalid_native_token_counter")
            _require(set(usage) <= TOKEN_COUNTERS, "unknown_native_token_counter")
            _require({"input_tokens", "output_tokens"} <= set(usage), "missing_native_token_counter")
            _require(all(type(n) is int and n >= 0 for n in usage.values()), "invalid_native_token_counter")
            responses[response_id] = payload
            by_owner[owner].append(payload)
    for owner, session in sessions.items():
        for item in session["records"]:
            if item["type"] != "token_usage_record" or item["payload"].get("thread_id") == owner:
                continue
            payload = item["payload"]
            _require(
                session["parent"] is not None
                and payload.get("thread_id") == session["parent"]
                and responses.get(payload.get("response_id")) == payload,
                "unattributable_copied_response_usage",
            )
    return by_owner


def _activity(session):
    turns = session["turns"]
    current = None
    tools, starts, ends, end_kinds, times = set(), {}, {}, {}, []
    spawn_calls, spawn_outputs, spawned = set(), set(), set()
    reasons = set()
    for item in session["records"]:
        kind, payload = item["type"], item["payload"]
        event = payload.get("type") if kind == "event_msg" else None
        if kind == "turn_context" or event == "task_started":
            current = payload["turn_id"]
        turn = payload.get("turn_id", current)
        if event in LIFECYCLE and turn in turns:
            timestamp = _timestamp(item)
            times.append(timestamp)
            if event == "task_started":
                _require(turn not in starts and turn not in ends, "duplicate_or_unordered_native_start")
                starts[turn] = timestamp
            else:
                _require(turn not in ends, "duplicate_native_turn_end")
                ends[turn], end_kinds[turn] = timestamp, event
        if current not in turns:
            if kind == "response_item" and payload.get("type") in {"function_call", "custom_tool_call"}:
                _require(current in session["observed"], "unattributable_native_tool_call")
            continue
        if item.get("timestamp") is not None:
            times.append(_timestamp(item))
        if kind != "response_item":
            continue
        if payload.get("type") in {"function_call", "custom_tool_call"}:
            _require(current not in ends, "native_tool_after_turn_end")
            call = payload.get("call_id")
            _require(_identifier(call) and call not in tools, "duplicate_or_missing_native_tool_call")
            tools.add(call)
            if payload.get("name", "").split(".")[-1] == "spawn_agent":
                spawn_calls.add(call)
        if payload.get("type") == "function_call_output" and payload.get("call_id") in spawn_calls:
            call = payload["call_id"]
            _require(call not in spawn_outputs, "duplicate_native_spawn_result")
            spawn_outputs.add(call)
            output = _json(payload.get("output", ""))
            _require(isinstance(output, dict), "unknown_native_spawn_result")
            if "task_name" in output:
                path = output["task_name"]
                _require(_identifier(path) and path not in spawned, "duplicate_or_invalid_spawned_child")
                spawned.add(path)
            else:
                _require("error" in output, "unknown_native_spawn_result")
    _require(spawn_calls == spawn_outputs, "unresolved_native_spawn_roster")
    for turn in turns:
        if turn not in starts:
            reasons.add("owned_turn_start_missing")
        if turn not in ends:
            reasons.add("owned_turn_end_missing")
        elif end_kinds[turn] == "turn_aborted":
            reasons.add("owned_turn_aborted")
        if turn in starts and turn in ends:
            _require(ends[turn] >= starts[turn], "native_end_precedes_start")
    if not turns:
        reasons.add("owned_turns_missing")
    return {
        "tools": tools,
        "starts": starts,
        "ends": ends,
        "times": times,
        "spawned": spawned,
        "reasons": reasons,
    }


def _derive(files):
    sessions, parent = _load(files)
    responses = _responses(sessions)
    activity = {owner: _activity(session) for owner, session in sessions.items()}
    spawned = set().union(*(item["spawned"] for item in activity.values()))
    actual = {session["path"] for session in sessions.values() if session["parent"] is not None}
    _require(spawned == actual, "native_child_roster_mismatch")
    # Children cannot create native children under the registered depth-one policy.
    _require(
        not any(activity[key]["spawned"] for key in sessions if key != parent), "delegation_depth_exceeded"
    )
    boundary, intervals = "verified", []
    for owner, session in sessions.items():
        if owner == parent:
            continue
        item = activity[owner]
        if (
            set(item["starts"]) != session["turns"]
            or set(item["ends"]) != session["turns"]
            or not session["turns"]
        ):
            boundary = "unverified"
        if item["starts"] and item["times"]:
            # The last observed activity proves a minimum lifetime. An absent end
            # is not silently treated as a release of the concurrency slot.
            intervals += [(min(item["starts"].values()), 1), (max(item["times"]), -1)]
    active = 0
    for _, delta in sorted(intervals):
        active += delta
        _require(active <= 2, "native_child_concurrency_exceeded")
    aliases = {owner: f"agent-{i}" for i, owner in enumerate([parent, *sorted(set(sessions) - {parent})])}
    agents, reasons = [], set()
    for owner in aliases:
        item = activity[owner]
        missing = set(item["reasons"])
        metered = {record["turn_id"] for record in responses[owner]}
        if metered != sessions[owner]["turns"]:
            missing.add("owned_turn_usage_missing")
        if not responses[owner]:
            missing.add("owned_response_usage_missing")
        bounds = {
            "input_tokens": sum(record["usage"]["input_tokens"] for record in responses[owner]),
            "output_tokens": sum(record["usage"]["output_tokens"] for record in responses[owner]),
            "model_calls": len(responses[owner]),
            "tool_calls": len(item["tools"]),
        }
        agents.append(
            {
                "agent_id": aliases[owner],
                "parent_id": None if owner == parent else aliases[parent],
                "lower_bounds": bounds,
                "complete": not missing,
                "completeness_reasons": sorted(missing),
            }
        )
        reasons.update(missing)
    if boundary == "unverified":
        reasons.add("child_concurrency_unverified")
    return agents, reasons, boundary


def derive_partial_usage(session_directory: Path | str) -> dict:
    """Return lower bounds without native identifiers, paths, prompts or secrets.

    Invalid provenance yields null counters, distinct from valid but incomplete
    lifecycle evidence. Zero observed responses establishes only a zero lower bound.
    Complete results must also pass, and exactly agree with, the existing parser.
    """
    result = {
        "schema_version": "evalopt.partial-workflow-usage.v1",
        "accounting_status": "unavailable",
        "provenance_status": "unavailable",
        "child_usage_complete": False,
        "lower_bounds": dict.fromkeys(COUNTERS),
        "completeness_reasons": [],
        "efficiency_eligible": False,
        "delegation_boundary_status": "unverified",
        "agents": [],
        "complete_usage": None,
        "source_log_sha256": [],
    }
    try:
        files = _snapshot(session_directory)
        result["source_log_sha256"] = sorted(hashlib.sha256(raw).hexdigest() for raw in files.values())
        agents, reasons, boundary = _derive(files)
        bounds = {name: sum(agent["lower_bounds"][name] for agent in agents) for name in COUNTERS}
        complete = None
        if not reasons:
            try:
                complete = summarize_usage(parse_native_usage(session_directory))
            except (ValueError, KeyError, TypeError) as exc:
                raise _Invalid("strict_parser_rejected_complete_evidence") from exc
            _require(
                all(complete[name] == bounds[name] for name in COUNTERS), "strict_parser_counter_mismatch"
            )
        _require(files == _snapshot(session_directory), "native_logs_changed_during_derivation")
        result.update(
            {
                "accounting_status": "complete" if complete is not None else "partial",
                "provenance_status": "valid",
                "child_usage_complete": complete is not None,
                "lower_bounds": bounds,
                "completeness_reasons": sorted(reasons),
                "efficiency_eligible": complete is not None,
                "delegation_boundary_status": boundary,
                "agents": agents,
                "complete_usage": complete,
            }
        )
    except _Invalid as exc:
        reason = str(exc)
        result["completeness_reasons"] = [reason]
        if reason not in {"native_log_directory_missing", "native_session_logs_missing"}:
            result["provenance_status"] = "invalid"
            result["delegation_boundary_status"] = "invalid"
    except (OSError, UnicodeError):
        result["completeness_reasons"] = ["native_logs_unreadable"]
    except (ValueError, KeyError, TypeError, AttributeError):
        result["completeness_reasons"] = ["invalid_native_record"]
        result["provenance_status"] = "invalid"
        result["delegation_boundary_status"] = "invalid"
    return result
