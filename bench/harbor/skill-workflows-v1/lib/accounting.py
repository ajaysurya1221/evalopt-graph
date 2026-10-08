"""Whole-trial usage with explicit telemetry semantics; never infer missing child usage."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .common import exact, safe_name


def summarize_usage(events: list[dict]) -> dict:
    """Sum final per-agent-exclusive counters OR one documented inclusive whole-trial total.

    Every row is a final total (not a streaming delta). A single inclusive parent summary
    may coexist with child rows for audit, but children are not summed a second time.
    Per-agent mode requires an explicit complete roster supplied by the runtime adapter.
    """
    fields = {
        "agent_id",
        "parent_id",
        "scope",
        "input_tokens",
        "output_tokens",
        "model_calls",
        "tool_calls",
        "wall_seconds",
        "roster",
        "complete",
    }
    if not events:
        raise ValueError("usage evidence missing")
    seen = set()
    for event in events:
        exact(event, fields, "usage event")
        safe_name(event["agent_id"])
        if event["agent_id"] in seen:
            raise ValueError("duplicate agent final usage")
        seen.add(event["agent_id"])
        if event["scope"] not in {"agent_exclusive", "trial_inclusive"} or event["complete"] is not True:
            raise ValueError("unknown or incomplete usage semantics")
        for name in ("input_tokens", "output_tokens", "model_calls", "tool_calls"):
            if type(event[name]) is not int or event[name] < 0:
                raise ValueError("missing or invalid resource counter")
        if (
            isinstance(event["wall_seconds"], bool)
            or not isinstance(event["wall_seconds"], int | float)
            or not 0 <= event["wall_seconds"] < float("inf")
        ):
            raise ValueError("invalid wall time")
        if not isinstance(event["roster"], list) or len(set(event["roster"])) != len(event["roster"]):
            raise ValueError("invalid agent roster")
    parents = [event for event in events if event["parent_id"] is None]
    if len(parents) != 1:
        raise ValueError("usage requires one parent")
    parent = parents[0]
    if not set(parent["roster"]) >= seen or parent["agent_id"] not in parent["roster"]:
        raise ValueError("unaccounted agent identity")
    if any(event["parent_id"] not in (None, parent["agent_id"]) for event in events):
        raise ValueError("delegation depth exceeds one")
    inclusive = [event for event in events if event["scope"] == "trial_inclusive"]
    if inclusive:
        if len(inclusive) != 1 or inclusive[0] is not parent:
            raise ValueError("overlapping inclusive usage totals")
        selected = [parent]
    else:
        if set(parent["roster"]) != seen:
            raise ValueError("missing child usage")
        selected = events
    totals = {
        name: sum(event[name] for event in selected)
        for name in ("input_tokens", "output_tokens", "model_calls", "tool_calls")
    }
    return {
        "schema_version": "evalopt.workflow-usage.v1",
        **totals,
        "wall_seconds": parent["wall_seconds"],
        "agent_count": len(parent["roster"]),
        "aggregation": "trial_inclusive" if inclusive else "agent_exclusive",
        "child_usage_complete": True,
    }


def parse_native_usage(session_directory: Path | str) -> list[dict]:
    """Parse pinned Codex 0.154 native logs without retaining prompt, auth or quota data.

    Child logs contain copied parent history. Only the first session metadata owns a
    file; usage records explicitly identify their thread, and tool calls are restricted
    to that thread's metered turns. token_count summaries are deliberately ignored.
    Unknown/incomplete telemetry fails closed instead of reporting zero child cost.
    """
    sessions = {}
    all_response_ids = set()
    spawned_paths = set()
    actual_paths = set()
    child_intervals = []
    native_sessions = {}
    for path in sorted(Path(session_directory).rglob("*.jsonl")):
        records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        metadata = next((item["payload"] for item in records if item.get("type") == "session_meta"), None)
        if metadata is None or metadata["id"] in native_sessions:
            raise ValueError("missing or duplicate native session identity")
        native_sessions[metadata["id"]] = (metadata, records)

    def observed_turns(records):
        return {
            item["payload"]["turn_id"]
            for item in records
            if (
                item.get("type") == "turn_context"
                or (
                    item.get("type") == "event_msg"
                    and item.get("payload", {}).get("type") in {"task_started", "task_complete"}
                )
            )
            and isinstance(item.get("payload", {}).get("turn_id"), str)
        }

    for metadata, records in native_sessions.values():
        agent_id = metadata["id"]
        source = metadata.get("source")
        spawn = source.get("subagent", {}).get("thread_spawn") if isinstance(source, dict) else None
        parent_id = spawn.get("parent_thread_id") if spawn else None
        if spawn:
            if spawn.get("depth") != 1:
                raise ValueError("native delegation depth exceeds one")
            actual_paths.add(spawn["agent_path"])
        owned = [
            item["payload"]
            for item in records
            if item.get("type") == "token_usage_record" and item["payload"].get("thread_id") == agent_id
        ]
        if not owned:
            raise ValueError("native session has no attributable response usage")
        turns = observed_turns(records)
        if parent_id is not None:
            if parent_id not in native_sessions:
                raise ValueError("native child lacks its parent session")
            # Parent history copied at spawn time is not another child turn. The
            # parent's complete turn roster, including unmetered turns, is excluded.
            turns -= observed_turns(native_sessions[parent_id][1])
        if turns != {item["turn_id"] for item in owned}:
            raise ValueError("native owned turn roster has missing or unattributable usage")
        totals = {"input_tokens": 0, "output_tokens": 0}
        local_responses = set()
        for item in owned:
            response_id = item["response_id"]
            if response_id in local_responses or response_id in all_response_ids:
                raise ValueError("duplicate native response usage")
            local_responses.add(response_id)
            all_response_ids.add(response_id)
            for key in totals:
                count = item["usage"].get(key)
                if type(count) is not int or count < 0:
                    raise ValueError("invalid native token counter")
                totals[key] += count
        current_turn = None
        tool_ids = set()
        spawn_call_ids = set()
        started = []
        finished = []
        finished_turns = set()
        for item in records:
            payload = item.get("payload", {})
            if item.get("type") == "event_msg" and payload.get("type") == "task_started":
                current_turn = payload.get("turn_id")
                if current_turn in turns:
                    started.append(datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")))
            if item.get("type") == "turn_context":
                current_turn = payload.get("turn_id")
            if (
                item.get("type") == "event_msg"
                and payload.get("type") == "task_complete"
                and payload.get("turn_id") in turns
            ):
                finished_turns.add(payload["turn_id"])
                finished.append(datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00")))
            if current_turn not in turns or item.get("type") != "response_item":
                continue
            if payload.get("type") in {"function_call", "custom_tool_call"}:
                call_id = payload.get("call_id")
                if not isinstance(call_id, str) or call_id in tool_ids:
                    raise ValueError("missing or duplicate native tool call")
                tool_ids.add(call_id)
                if payload.get("name", "").split(".")[-1] == "spawn_agent":
                    spawn_call_ids.add(call_id)
            if payload.get("type") == "function_call_output" and payload.get("call_id") in spawn_call_ids:
                try:
                    output = json.loads(payload.get("output", ""))
                except (TypeError, json.JSONDecodeError) as exc:
                    raise ValueError("unknown native spawn result") from exc
                if "task_name" in output:
                    spawned_paths.add(output["task_name"])
        if finished_turns != turns or not started or not finished:
            raise ValueError("native session is incomplete; retain raw logs and mark accounting unavailable")
        if parent_id is not None:
            child_intervals.extend(((min(started), 1), (max(finished), -1)))
        sessions[agent_id] = {
            "agent_id": agent_id,
            "parent_id": parent_id,
            "scope": "agent_exclusive",
            **totals,
            "model_calls": len(local_responses),
            "tool_calls": len(tool_ids),
            "wall_seconds": (max(finished) - min(started)).total_seconds(),
            "roster": [],
            "complete": True,
        }
    if spawned_paths != actual_paths:
        raise ValueError("native child roster is incomplete or contains an unregistered child")
    active_children = 0
    for _, delta in sorted(child_intervals):
        active_children += delta
        if active_children > 2:
            raise ValueError("native child concurrency exceeds two")
    if not sessions:
        raise ValueError("native session logs missing")
    roster = sorted(sessions)
    for event in sessions.values():
        event["roster"] = roster if event["parent_id"] is None else [event["agent_id"]]
    events = list(sessions.values())
    summarize_usage(events)  # Validate the roster and depth together, not file by file.
    return events
