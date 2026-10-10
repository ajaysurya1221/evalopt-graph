"""Synthetic native-log controls; no live requests or retained pilot payloads."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
from lib.accounting import parse_native_usage, summarize_usage  # noqa: E402
from runtime import partial_accounting as accounting  # noqa: E402


def lifecycle(kind, turn, second):
    return {
        "timestamp": f"2026-10-08T00:00:{second:02d}Z",
        "type": "event_msg",
        "payload": {"type": kind, "turn_id": turn},
    }


def response(owner, turn=None, response_id=None, inputs=10):
    return {
        "type": "token_usage_record",
        "payload": {
            "thread_id": owner,
            "turn_id": turn or owner,
            "response_id": response_id or f"response-{owner}",
            "usage": {"input_tokens": inputs, "output_tokens": 2},
        },
    }


def native_session(owner, *, parent=None, copied=(), children=(), ending="task_complete", metered=True):
    source = (
        "exec"
        if parent is None
        else {
            "subagent": {
                "thread_spawn": {"parent_thread_id": parent, "depth": 1, "agent_path": f"/root/{owner}"}
            }
        }
    )
    records = [
        {
            "type": "session_meta",
            "payload": {"id": owner, "source": source, "cli_version": "0.154.0"},
        }
    ]
    records.extend(copy.deepcopy(copied))
    records.append(lifecycle("task_started", owner, 0))
    for child in children:
        records.extend(
            [
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call",
                        "name": "spawn_agent",
                        "call_id": f"spawn-{child}",
                    },
                },
                {
                    "type": "response_item",
                    "payload": {
                        "type": "function_call_output",
                        "call_id": f"spawn-{child}",
                        "output": json.dumps({"task_name": f"/root/{child}"}),
                    },
                },
            ]
        )
    if metered:
        records.append(response(owner))
    if ending:
        records.append(lifecycle(ending, owner, 4))
    return records


def write_sessions(root, *sessions):
    root.mkdir(exist_ok=True)
    for index, records in enumerate(sessions):
        (root / f"synthetic-{index}.jsonl").write_text("\n".join(json.dumps(row) for row in records))


def assert_invalid(result, reason):
    assert result["accounting_status"] == "unavailable"
    assert result["provenance_status"] == "invalid"
    assert result["delegation_boundary_status"] == "invalid"
    assert result["lower_bounds"] == dict.fromkeys(accounting.COUNTERS)
    assert result["complete_usage"] is None
    assert result["agents"] == []
    assert not result["child_usage_complete"]
    assert not result["efficiency_eligible"]
    assert reason in result["completeness_reasons"]


def test_complete_matches_strict_parser_and_excludes_copied_history(tmp_path):
    root = native_session("native-private-root", children=["native-private-child"])
    child = native_session("native-private-child", parent="native-private-root", copied=root)
    write_sessions(tmp_path, root, child)
    before = {p: p.read_bytes() for p in tmp_path.iterdir()}
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "complete"
    assert result["provenance_status"] == "valid"
    assert result["delegation_boundary_status"] == "verified"
    assert result["complete_usage"] == summarize_usage(parse_native_usage(tmp_path))
    assert result["lower_bounds"] == {
        "input_tokens": 20,
        "output_tokens": 4,
        "model_calls": 2,
        "tool_calls": 1,
    }
    assert result["child_usage_complete"] and result["efficiency_eligible"]
    assert result["completeness_reasons"] == []
    assert result["source_log_sha256"] == sorted(hashlib.sha256(raw).hexdigest() for raw in before.values())
    assert {p: p.read_bytes() for p in tmp_path.iterdir()} == before
    rendered = json.dumps(result)
    assert "native-private" not in rendered
    assert str(tmp_path) not in rendered
    assert [a["agent_id"] for a in result["agents"]] == ["agent-0", "agent-1"]


def test_interrupted_child_keeps_owned_response_lower_bounds_only(tmp_path):
    root = native_session("root", children=["child"])
    child = native_session("child", parent="root", copied=root, ending="turn_aborted")
    child.insert(-1, response("child", response_id="second-child-response", inputs=7))
    child.insert(
        -1,
        {
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {
                    "total_token_usage": {"input_tokens": 99999999, "output_tokens": 99999999},
                },
            },
        },
    )
    write_sessions(tmp_path, root, child)
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "partial"
    assert result["provenance_status"] == "valid"
    assert result["delegation_boundary_status"] == "verified"
    assert result["lower_bounds"] == {
        "input_tokens": 27,
        "output_tokens": 6,
        "model_calls": 3,
        "tool_calls": 1,
    }
    assert result["completeness_reasons"] == ["owned_turn_aborted"]
    assert result["complete_usage"] is None
    assert result["agents"][0]["complete"]
    assert not result["agents"][1]["complete"]
    assert not result["efficiency_eligible"] and not result["child_usage_complete"]


def test_aborted_child_without_response_records_has_zero_lower_bound_not_zero_exact(tmp_path):
    root = native_session("root", children=["child"])
    child = native_session("child", parent="root", copied=root, ending="turn_aborted", metered=False)
    write_sessions(tmp_path, root, child)
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "partial"
    assert result["lower_bounds"]["input_tokens"] == 10
    assert result["agents"][1]["lower_bounds"] == dict.fromkeys(accounting.COUNTERS, 0)
    assert "owned_response_usage_missing" in result["completeness_reasons"]
    assert "owned_turn_usage_missing" in result["completeness_reasons"]
    assert result["complete_usage"] is None
    assert not result["efficiency_eligible"]


def test_unknown_child_end_does_not_assert_concurrency_compliance(tmp_path):
    root = native_session("root", children=["child"])
    child = native_session("child", parent="root", copied=root, ending=None)
    write_sessions(tmp_path, root, child)
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "partial"
    assert result["provenance_status"] == "valid"
    assert result["delegation_boundary_status"] == "unverified"
    assert "child_concurrency_unverified" in result["completeness_reasons"]
    assert result["complete_usage"] is None


def test_unmetered_followup_tool_is_counted_but_usage_remains_partial(tmp_path):
    root = native_session("root")
    root.extend(
        [
            lifecycle("task_started", "followup", 5),
            {"type": "turn_context", "payload": {"turn_id": "followup"}},
            {
                "type": "response_item",
                "payload": {"type": "custom_tool_call", "name": "exec", "call_id": "tool-2"},
            },
            lifecycle("task_complete", "followup", 6),
        ]
    )
    write_sessions(tmp_path, root)
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "partial"
    assert result["lower_bounds"] == {
        "input_tokens": 10,
        "output_tokens": 2,
        "model_calls": 1,
        "tool_calls": 1,
    }
    assert result["completeness_reasons"] == ["owned_turn_usage_missing"]


@pytest.mark.parametrize("value", [None, -1, True, 1.5, "10"])
def test_invalid_counter_is_not_an_ordinary_partial_record(tmp_path, value):
    root = native_session("root", ending="turn_aborted")
    root[-2]["payload"]["usage"]["input_tokens"] = value
    write_sessions(tmp_path, root)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "invalid_native_token_counter")


def test_unknown_counter_semantics_are_invalid(tmp_path):
    root = native_session("root")
    root[-2]["payload"]["usage"]["mystery_tokens"] = 2
    write_sessions(tmp_path, root)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "unknown_native_token_counter")


@pytest.mark.parametrize("cross_owner", [False, True])
def test_duplicate_owned_response_is_rejected_instead_of_double_counted(tmp_path, cross_owner):
    root = native_session("root", children=["child"])
    child = native_session("child", parent="root", ending="turn_aborted")
    if cross_owner:
        child[-2]["payload"]["response_id"] = root[-2]["payload"]["response_id"]
    else:
        child.insert(-1, copy.deepcopy(child[-2]))
    write_sessions(tmp_path, root, child)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "duplicate_native_response_usage")


def test_copied_usage_must_match_known_parent_record(tmp_path):
    root = native_session("root", children=["child"])
    child = native_session("child", parent="root", copied=root, ending="turn_aborted")
    next(item for item in child if item["type"] == "token_usage_record")["payload"]["usage"][
        "input_tokens"
    ] += 1
    write_sessions(tmp_path, root, child)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "unattributable_copied_response_usage")


def test_foreign_usage_is_not_silently_dropped(tmp_path):
    root = native_session("root")
    root.insert(-1, response("unknown-owner"))
    write_sessions(tmp_path, root)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "unattributable_copied_response_usage")


@pytest.mark.parametrize("kind", ["missing", "unregistered", "depth", "duplicate-owner", "duplicate-path"])
def test_invalid_agent_roster_is_not_ordinary_missing_completion(tmp_path, kind):
    root = native_session("root", children=["child"])
    child = native_session("child", parent="root", ending="turn_aborted")
    sessions = [root, child]
    expected = "native_child_roster_mismatch"
    if kind == "missing":
        sessions.pop()
    elif kind == "unregistered":
        root[2:4] = []
    elif kind == "depth":
        child[0]["payload"]["source"]["subagent"]["thread_spawn"]["depth"] = 2
        expected = "delegation_depth_exceeded"
    elif kind == "duplicate-owner":
        sessions.append(copy.deepcopy(child))
        expected = "duplicate_or_missing_native_owner"
    else:
        second = native_session("child-2", parent="root")
        second[0]["payload"]["source"]["subagent"]["thread_spawn"]["agent_path"] = "/root/child"
        sessions.append(second)
        expected = "duplicate_native_child_path"
    write_sessions(tmp_path, *sessions)
    assert_invalid(accounting.derive_partial_usage(tmp_path), expected)


def test_three_observably_concurrent_children_are_invalid(tmp_path):
    children = ["one", "two", "three"]
    write_sessions(
        tmp_path,
        native_session("root", children=children),
        *[native_session(child, parent="root", ending="turn_aborted") for child in children],
    )
    assert_invalid(accounting.derive_partial_usage(tmp_path), "native_child_concurrency_exceeded")


def test_sequential_children_do_not_exceed_concurrency(tmp_path):
    children = ["one", "two", "three"]
    sessions = [native_session("root", children=children)]
    for index, child in enumerate(children):
        records = native_session(child, parent="root", ending="turn_aborted")
        records[1] = lifecycle("task_started", child, index * 5)
        records[-1] = lifecycle("turn_aborted", child, index * 5 + 4)
        sessions.append(records)
    write_sessions(tmp_path, *sessions)
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "partial"
    assert result["delegation_boundary_status"] == "verified"
    assert result["lower_bounds"]["model_calls"] == 4


def test_duplicate_tool_call_is_invalid_even_when_turn_is_interrupted(tmp_path):
    root = native_session("root", ending="turn_aborted")
    call = {"type": "response_item", "payload": {"type": "function_call", "name": "exec", "call_id": "same"}}
    root[2:2] = [call, copy.deepcopy(call)]
    write_sessions(tmp_path, root)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "duplicate_or_missing_native_tool_call")


def test_missing_logs_are_unavailable_not_zero(tmp_path):
    result = accounting.derive_partial_usage(tmp_path)
    assert result["accounting_status"] == "unavailable"
    assert result["provenance_status"] == "unavailable"
    assert result["lower_bounds"] == dict.fromkeys(accounting.COUNTERS)


@pytest.mark.parametrize(
    "content",
    ['{"private-sentinel":', '{"type":"session_meta","type":"ignored","payload":{}}', '{"payload":NaN}'],
)
def test_malformed_logs_do_not_leak_exception_payload(tmp_path, content):
    (tmp_path / "synthetic.jsonl").write_text(content)
    result = accounting.derive_partial_usage(tmp_path)
    assert result["provenance_status"] == "invalid"
    assert content not in json.dumps(result)


def test_cli_drift_is_invalid(tmp_path):
    root = native_session("root")
    root[0]["payload"]["cli_version"] = "different-version"
    write_sessions(tmp_path, root)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "unsupported_native_cli_version")


def test_source_change_during_strict_parse_invalidates_derived_accounting(tmp_path, monkeypatch):
    write_sessions(tmp_path, native_session("root"))
    real = accounting.parse_native_usage

    def mutate(directory):
        result = real(directory)
        with next(directory.glob("*.jsonl")).open("a") as stream:
            stream.write("\n")
        return result

    monkeypatch.setattr(accounting, "parse_native_usage", mutate)
    assert_invalid(accounting.derive_partial_usage(tmp_path), "native_logs_changed_during_derivation")


def test_log_names_do_not_affect_sanitized_hash_bag_or_result(tmp_path):
    write_sessions(tmp_path, native_session("root"))
    first = accounting.derive_partial_usage(tmp_path)
    next(tmp_path.glob("*.jsonl")).rename(tmp_path / "renamed-private-identifier.jsonl")
    assert accounting.derive_partial_usage(tmp_path) == first
