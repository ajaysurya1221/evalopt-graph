"""Conservative native ownership/lifecycle accounting; no model or provider calls."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from .framing import SCHEMA, FramingError, decode_jsonl, strict_json

COUNTERS = ("input_tokens", "output_tokens", "model_calls", "tool_calls")
TOKEN_FIELDS = {
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "reasoning_output_tokens",
    "total_tokens",
}
ENDS = {"task_complete", "turn_aborted"}


class EvidenceError(ValueError):
    pass


def require(value, reason):
    if not value:
        raise EvidenceError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identifier(value):
    return isinstance(value, str) and bool(value)


def timestamp(record):
    value = datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))
    require(value.utcoffset() is not None, "timestamp_without_timezone")
    return value


def snapshot(directory):
    root = Path(directory)
    require(root.is_dir() and not root.is_symlink(), "native_logs_missing")
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "native_log_symlink")
        if path.suffix == ".jsonl":
            require(path.is_file(), "native_log_not_regular")
            require(path.stat().st_size <= 64 * 1024**2, "native_log_size_limit")
            with path.open("rb") as stream:
                raw = stream.read(64 * 1024**2 + 1)
            require(len(raw) <= 64 * 1024**2, "native_log_size_limit")
            result[path.relative_to(root).as_posix()] = raw
            require(
                len(result) <= 256 and sum(map(len, result.values())) <= 256 * 1024**2,
                "native_log_roster_size_limit",
            )
    return result


def observed_turns(records):
    result = set()
    for record in records:
        payload = record["payload"]
        if record["type"] == "turn_context" or (
            record["type"] == "event_msg" and payload.get("type") in ENDS | {"task_started"}
        ):
            require(identifier(payload.get("turn_id")), "missing_turn_identity")
            result.add(payload["turn_id"])
    return result


def _derive(files, expected_cli_version, max_children):
    require(bool(files), "native_logs_missing")
    sessions, framing_partial = {}, False
    for raw in files.values():
        decoded = decode_jsonl(raw)
        framing_partial |= decoded["status"] == "partial"
        records = [row["value"] for row in decoded["records"]]
        require(bool(records), "owner_metadata_missing")
        for row in records:
            require(
                isinstance(row.get("type"), str) and isinstance(row.get("payload"), dict),
                "invalid_native_record",
            )
        require(records[0]["type"] == "session_meta", "owner_metadata_missing")
        meta = records[0]["payload"]
        owner = meta.get("id")
        require(identifier(owner) and owner not in sessions, "duplicate_or_missing_owner")
        require(meta.get("cli_version") == expected_cli_version, "unsupported_native_version")
        source = meta.get("source")
        if source == "exec":
            parent, path = None, None
        else:
            require(isinstance(source, dict), "unknown_session_source")
            spawn = source.get("subagent", {}).get("thread_spawn", {})
            require(type(spawn.get("depth")) is int and spawn["depth"] == 1, "delegation_depth_exceeded")
            parent, path = spawn.get("parent_thread_id"), spawn.get("agent_path")
            require(identifier(parent) and identifier(path), "invalid_child_identity")
        sessions[owner] = {
            "records": records,
            "meta": meta,
            "parent": parent,
            "path": path,
            "observed": observed_turns(records),
            "framing_partial": decoded["status"] == "partial",
        }
    parents = [key for key, session in sessions.items() if session["parent"] is None]
    require(len(parents) == 1, "parent_roster_invalid")
    parent = parents[0]
    paths = [session["path"] for session in sessions.values() if session["parent"] is not None]
    require(len(paths) == len(set(paths)), "duplicate_child_path")
    seen_turns = set()
    for owner, session in sessions.items():
        require(session["parent"] in (None, parent), "parent_or_depth_invalid")
        session["turns"] = session["observed"] - (sessions[parent]["observed"] if owner != parent else set())
        require(not (seen_turns & session["turns"]), "ambiguous_turn_ownership")
        seen_turns |= session["turns"]
        for record in session["records"][1:]:
            if record["type"] == "session_meta":
                require(
                    owner != parent and canonical(record["payload"]) == canonical(sessions[parent]["meta"]),
                    "foreign_owner_metadata",
                )
    responses, by_owner = {}, {owner: [] for owner in sessions}
    for owner, session in sessions.items():
        for record in session["records"]:
            payload = record["payload"]
            if record["type"] != "token_usage_record" or payload.get("thread_id") != owner:
                continue
            response_id = payload.get("response_id")
            require(identifier(response_id) and response_id not in responses, "duplicate_or_missing_response")
            require(payload.get("turn_id") in session["turns"], "unowned_response_turn")
            usage = payload.get("usage")
            require(
                isinstance(usage, dict) and {"input_tokens", "output_tokens"} <= set(usage) <= TOKEN_FIELDS,
                "unknown_or_missing_counter",
            )
            require(all(type(n) is int and n >= 0 for n in usage.values()), "invalid_counter")
            responses[response_id] = payload
            by_owner[owner].append(payload)
    for owner, session in sessions.items():
        for record in session["records"]:
            payload = record["payload"]
            if record["type"] == "token_usage_record" and payload.get("thread_id") != owner:
                require(
                    session["parent"] is not None
                    and payload.get("thread_id") == parent
                    and canonical(responses.get(payload.get("response_id"))) == canonical(payload),
                    "foreign_or_changed_copied_response",
                )
    agents, all_spawned, intervals, overall_reasons = [], set(), [], set()
    delegation = "verified"
    owners = [parent, *sorted(set(sessions) - {parent})]
    for index, owner in enumerate(owners):
        session, current = sessions[owner], None
        starts, ends, tools, spawn_calls, spawn_results, times = {}, {}, set(), set(), set(), []
        reasons = {"partial_native_record"} if session["framing_partial"] else set()
        for record in session["records"]:
            payload, kind = record["payload"], record["type"]
            event = payload.get("type") if kind == "event_msg" else None
            if kind == "turn_context" or event == "task_started":
                current = payload["turn_id"]
            turn = payload.get("turn_id", current)
            if event in ENDS | {"task_started"} and turn in session["turns"]:
                when = timestamp(record)
                times.append(when)
                if event == "task_started":
                    require(turn not in starts and turn not in ends, "duplicate_or_unordered_start")
                    starts[turn] = when
                else:
                    require(turn not in ends, "duplicate_turn_end")
                    ends[turn] = (when, event)
            if current not in session["turns"]:
                if kind == "response_item" and payload.get("type") in {"function_call", "custom_tool_call"}:
                    require(current in session["observed"], "unowned_tool_call")
                continue
            if "timestamp" in record:
                times.append(timestamp(record))
            if kind != "response_item":
                continue
            if payload.get("type") in {"function_call", "custom_tool_call"}:
                call = payload.get("call_id")
                require(
                    current not in ends and identifier(call) and call not in tools,
                    "duplicate_or_unordered_tool",
                )
                tools.add(call)
                if payload.get("name", "").split(".")[-1] == "spawn_agent":
                    spawn_calls.add(call)
            if payload.get("type") == "function_call_output" and payload.get("call_id") in spawn_calls:
                call = payload["call_id"]
                require(call not in spawn_results, "duplicate_spawn_result")
                spawn_results.add(call)
                output = strict_json(payload.get("output", ""))
                require(isinstance(output, dict), "invalid_spawn_result")
                if "task_name" in output:
                    require(owner == parent, "delegation_depth_exceeded")
                    require(
                        identifier(output["task_name"]) and output["task_name"] not in all_spawned,
                        "duplicate_spawned_child",
                    )
                    all_spawned.add(output["task_name"])
                else:
                    require("error" in output, "invalid_spawn_result")
        require(spawn_calls == spawn_results, "unresolved_child_roster")
        for turn in session["turns"]:
            if turn not in starts:
                reasons.add("owned_turn_start_missing")
            if turn not in ends:
                reasons.add("owned_turn_end_missing")
            elif ends[turn][1] == "turn_aborted":
                reasons.add("owned_turn_aborted")
            if turn in starts and turn in ends:
                require(ends[turn][0] >= starts[turn], "end_precedes_start")
        if not session["turns"]:
            reasons.add("owned_turns_missing")
        metered = {row["turn_id"] for row in by_owner[owner]}
        if metered != session["turns"]:
            reasons.add("owned_turn_usage_missing")
        if not by_owner[owner]:
            reasons.add("owned_response_usage_missing")
        if owner != parent:
            if set(starts) != session["turns"] or set(ends) != session["turns"] or not session["turns"]:
                delegation = "unverified"
            if starts and times:
                intervals.extend(((min(starts.values()), 1), (max(times), -1)))
        bounds = {
            "input_tokens": sum(row["usage"]["input_tokens"] for row in by_owner[owner]),
            "output_tokens": sum(row["usage"]["output_tokens"] for row in by_owner[owner]),
            "model_calls": len(by_owner[owner]),
            "tool_calls": len(tools),
        }
        agents.append(
            {
                "agent": f"agent-{index}",
                "parent": None if owner == parent else "agent-0",
                "lower_bounds": bounds,
                "complete": not reasons,
                "reasons": sorted(reasons),
            }
        )
        overall_reasons |= reasons
    require(all_spawned == set(paths), "child_roster_mismatch")
    active = 0
    for _, delta in sorted(intervals):
        active += delta
        if active > max_children:
            delegation = "violated"
    if delegation != "verified":
        overall_reasons.add("child_concurrency_" + delegation)
    if framing_partial:
        overall_reasons.add("partial_native_record")
        if delegation != "violated":
            delegation = "unverified"
    return agents, overall_reasons, delegation


def derive_usage(
    source: Path | str | dict[str, bytes], *, expected_cli_version="0.154.0", max_children=2
) -> dict:
    """Only observed owned responses are summed; missing usage is never estimated.

    A valid empty response roster gives zero *observed lower bounds*, not zero
    consumption. Invalid provenance returns null counters. Native identifiers and
    source filenames do not leave this reducer.
    """
    result = {
        "schema_version": SCHEMA,
        "kind": "usage",
        "accounting_status": "unavailable",
        "provenance_status": "unavailable",
        "delegation_status": "unverified",
        "exact_totals": None,
        "lower_bounds": dict.fromkeys(COUNTERS),
        "agents": [],
        "reasons": [],
        "source_hashes": [],
        "efficiency_eligible": False,
    }
    try:
        require(type(max_children) is int and max_children > 0, "invalid_delegation_limit")
        files = dict(source) if isinstance(source, dict) else snapshot(source)
        require(all(isinstance(raw, bytes) for raw in files.values()), "invalid_source_bytes")
        result["source_hashes"] = sorted(hashlib.sha256(raw).hexdigest() for raw in files.values())
        agents, reasons, delegation = _derive(files, expected_cli_version, max_children)
        if not isinstance(source, dict):
            require(files == snapshot(source), "native_logs_changed")
        totals = {key: sum(agent["lower_bounds"][key] for agent in agents) for key in COUNTERS}
        complete = not reasons
        result.update(
            accounting_status="complete" if complete else "partial",
            provenance_status="valid",
            delegation_status=delegation,
            exact_totals=totals if complete else None,
            lower_bounds=totals,
            agents=agents,
            reasons=sorted(reasons),
            efficiency_eligible=complete,
        )
    except (EvidenceError, FramingError) as exc:
        reason = str(exc)
        result["reasons"] = [reason]
        if reason != "native_logs_missing":
            result["provenance_status"] = "invalid"
        if reason in {"delegation_depth_exceeded", "parent_or_depth_invalid"}:
            result["delegation_status"] = "violated"
    except OSError:
        result["reasons"] = ["native_logs_unreadable"]
    except (ValueError, KeyError, TypeError, AttributeError, RecursionError):
        result.update(provenance_status="invalid", reasons=["invalid_native_record"])
    return result


def validate_usage(value):
    """Check a sanitized projection's types/arithmetic, never authenticate its source."""
    require(
        isinstance(value, dict)
        and set(value)
        == {
            "schema_version",
            "kind",
            "accounting_status",
            "provenance_status",
            "delegation_status",
            "exact_totals",
            "lower_bounds",
            "agents",
            "reasons",
            "source_hashes",
            "efficiency_eligible",
        },
        "invalid_usage_schema",
    )
    require(value["schema_version"] == SCHEMA and value["kind"] == "usage", "invalid_usage_schema")
    require(
        value["accounting_status"] in {"complete", "partial", "unavailable"}
        and value["provenance_status"] in {"valid", "invalid", "unavailable"}
        and value["delegation_status"] in {"verified", "unverified", "violated"},
        "invalid_usage_status",
    )
    require(type(value["efficiency_eligible"]) is bool, "invalid_usage_completeness")
    require(
        isinstance(value["reasons"], list)
        and value["reasons"] == sorted(set(value["reasons"]))
        and all(isinstance(reason, str) and re.fullmatch(r"[a-z_]+", reason) for reason in value["reasons"]),
        "invalid_usage_reasons",
    )
    require(
        isinstance(value["source_hashes"], list)
        and all(
            isinstance(item, str) and re.fullmatch(r"[0-9a-f]{64}", item) for item in value["source_hashes"]
        ),
        "invalid_usage_sources",
    )
    require(
        isinstance(value["lower_bounds"], dict)
        and set(value["lower_bounds"]) == set(COUNTERS)
        and isinstance(value["agents"], list),
        "invalid_usage_counters",
    )
    if value["provenance_status"] != "valid":
        require(
            value["accounting_status"] == "unavailable"
            and value["exact_totals"] is None
            and value["agents"] == []
            and not value["efficiency_eligible"]
            and all(item is None for item in value["lower_bounds"].values()),
            "unavailable_usage_fabricates_counters",
        )
        return value
    require(bool(value["agents"]) and bool(value["source_hashes"]), "usage_owner_evidence_missing")
    sums = dict.fromkeys(COUNTERS, 0)
    for index, agent in enumerate(value["agents"]):
        require(
            isinstance(agent, dict)
            and set(agent) == {"agent", "parent", "lower_bounds", "complete", "reasons"},
            "invalid_usage_agent",
        )
        require(
            agent["agent"] == f"agent-{index}"
            and agent["parent"] == (None if index == 0 else "agent-0")
            and type(agent["complete"]) is bool,
            "invalid_usage_agent",
        )
        require(
            isinstance(agent["lower_bounds"], dict)
            and set(agent["lower_bounds"]) == set(COUNTERS)
            and all(type(n) is int and n >= 0 for n in agent["lower_bounds"].values()),
            "invalid_usage_counter",
        )
        require(
            isinstance(agent["reasons"], list)
            and all(isinstance(reason, str) for reason in agent["reasons"])
            and agent["complete"] is (not agent["reasons"]),
            "invalid_usage_agent_completeness",
        )
        for key in COUNTERS:
            sums[key] += agent["lower_bounds"][key]
    require(
        all(
            type(value["lower_bounds"][key]) is int and value["lower_bounds"][key] == sums[key]
            for key in COUNTERS
        ),
        "usage_arithmetic_mismatch",
    )
    complete = value["accounting_status"] == "complete"
    require(
        value["accounting_status"] in {"complete", "partial"} and value["efficiency_eligible"] is complete,
        "usage_completeness_mismatch",
    )
    if complete:
        require(
            value["reasons"] == []
            and all(agent["complete"] for agent in value["agents"])
            and value["delegation_status"] == "verified"
            and canonical(value["exact_totals"]) == canonical(sums),
            "false_complete_usage",
        )
    else:
        require(value["exact_totals"] is None and bool(value["reasons"]), "false_partial_usage")
    return value
