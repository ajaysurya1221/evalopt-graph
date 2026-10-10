"""Independent adversarial controls for approved partial accounting and resume.

All native logs are synthetic; no private trial content or model execution.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import marshal
import py_compile
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))


def partial_module():
    """Load the current controller module without importing frozen pilot code."""
    spec = importlib.util.spec_from_file_location(
        "amendment_review_partial", BENCH / "runtime/partial_accounting.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stamp(second):
    return f"2026-10-08T00:00:{second:02d}Z"


def record(kind, payload, second=None):
    value = {"type": kind, "payload": payload}
    if second is not None:
        value["timestamp"] = stamp(second)
    return value


def session(owner, *, parent=None, start=0, end=9, aborted=False, metered=True, children=(), copied=()):
    source = "exec"
    if parent is not None:
        source = {
            "subagent": {
                "thread_spawn": {
                    "parent_thread_id": parent,
                    "agent_path": f"/root/{owner}",
                    "depth": 1,
                }
            }
        }
    rows = [record("session_meta", {"id": owner, "source": source, "cli_version": "0.154.0"}, start)]
    rows += copy.deepcopy(list(copied))
    rows += [
        record("event_msg", {"type": "task_started", "turn_id": owner}, start),
        record("turn_context", {"turn_id": owner, "model": "gpt-6-astra", "effort": "ultra"}, start),
    ]
    for child in children:
        call_id = f"spawn-{child}"
        rows += [
            record(
                "response_item",
                {"type": "function_call", "name": "spawn_agent", "call_id": call_id},
                start + 1,
            ),
            record(
                "response_item",
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps({"task_name": f"/root/{child}"}),
                },
                start + 1,
            ),
        ]
    if metered:
        rows.append(
            record(
                "token_usage_record",
                {
                    "thread_id": owner,
                    "turn_id": owner,
                    "response_id": f"response-{owner}",
                    "usage": {"input_tokens": 10, "output_tokens": 2},
                },
                start + 1,
            )
        )
    rows.append(
        record(
            "event_msg",
            {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 999999}}},
            start + 1,
        )
    )
    if end is not None:
        rows.append(
            record(
                "event_msg",
                {"type": "turn_aborted" if aborted else "task_complete", "turn_id": owner},
                end,
            )
        )
    return rows


def write_sessions(root, logs):
    root.mkdir(exist_ok=True)
    for name, rows in logs.items():
        (root / f"{name}.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return root


def derive(root, logs):
    return partial_module().derive_partial_usage(write_sessions(root, logs))


def native_response(rows):
    return next(row["payload"] for row in rows if row["type"] == "token_usage_record")


def assert_unavailable(value, reason):
    assert value["accounting_status"] == "unavailable"
    assert value["provenance_status"] == "invalid"
    assert value["delegation_boundary_status"] == "invalid"
    assert value["completeness_reasons"] == [reason]
    assert value["lower_bounds"] == dict.fromkeys(
        ("input_tokens", "output_tokens", "model_calls", "tool_calls")
    )
    assert value["complete_usage"] is None
    assert value["efficiency_eligible"] is False


def test_review_partial_aborted_child_retains_only_owner_response_lower_bounds(tmp_path):
    parent = session("parent", children=("child",))
    child = session("child", parent="parent", start=2, end=8, aborted=True, copied=parent)
    result = derive(tmp_path, {"parent": parent, "child": child})
    assert result["accounting_status"] == "partial"
    assert result["provenance_status"] == "valid"
    assert result["delegation_boundary_status"] == "verified"
    assert result["child_usage_complete"] is False
    assert result["lower_bounds"] == {
        "input_tokens": 20,
        "output_tokens": 4,
        "model_calls": 2,
        "tool_calls": 1,
    }
    assert result["complete_usage"] is None
    assert result["efficiency_eligible"] is False
    assert "owned_turn_aborted" in result["completeness_reasons"]
    # Accumulated token_count and copied parent usage do not contribute again.
    assert all(agent["agent_id"].startswith("agent-") for agent in result["agents"])
    assert "parent" not in json.dumps(result["agents"]).replace("parent_id", "")


def test_review_unmetered_aborted_child_is_unknown_cost_not_complete_zero(tmp_path):
    result = derive(
        tmp_path,
        {
            "parent": session("parent", children=("child",)),
            "child": session("child", parent="parent", start=2, end=8, aborted=True, metered=False),
        },
    )
    assert result["accounting_status"] == "partial"
    assert result["delegation_boundary_status"] == "verified"
    assert result["lower_bounds"]["model_calls"] == 1
    assert result["agents"][1]["lower_bounds"]["model_calls"] == 0
    assert result["agents"][1]["complete"] is False
    assert "owned_response_usage_missing" in result["completeness_reasons"]
    assert result["complete_usage"] is None


@pytest.mark.parametrize("change", ["counter", "response_id", "thread_id", "turn_id"])
def test_review_forged_parent_copies_are_not_accepted_as_partial(tmp_path, change):
    parent = session("parent", children=("child",))
    child = session("child", parent="parent", start=2, end=8, aborted=True, copied=parent)
    copied = native_response(child)
    if change == "counter":
        copied["usage"]["input_tokens"] += 1
    else:
        copied[change] = "unknown-private-identifier"
    result = derive(tmp_path, {"parent": parent, "child": child})
    assert_unavailable(result, "unattributable_copied_response_usage")
    assert "unknown-private-identifier" not in json.dumps(result)


@pytest.mark.parametrize("across_owners", [False, True])
def test_review_duplicate_owned_responses_cannot_become_partial_bounds(tmp_path, across_owners):
    parent = session("parent", children=("child",))
    child = session("child", parent="parent", start=2, end=8, aborted=True)
    if across_owners:
        native_response(child)["response_id"] = native_response(parent)["response_id"]
    else:
        child.insert(-1, copy.deepcopy(next(row for row in child if row["type"] == "token_usage_record")))
    assert_unavailable(
        derive(tmp_path, {"parent": parent, "child": child}), "duplicate_native_response_usage"
    )


@pytest.mark.parametrize("missing", ["transcript", "spawn_result", "successful_spawn"])
def test_review_child_roster_uncertainty_is_not_a_resource_exception(tmp_path, missing):
    parent = session("parent", children=("child",))
    logs = {"parent": parent, "child": session("child", parent="parent", start=2, end=8, aborted=True)}
    reason = "native_child_roster_mismatch"
    if missing == "transcript":
        logs.pop("child")
    elif missing == "spawn_result":
        parent[:] = [row for row in parent if row["payload"].get("type") != "function_call_output"]
        reason = "unresolved_native_spawn_roster"
    else:
        parent[:] = [row for row in parent if row["type"] != "response_item"]
    assert_unavailable(derive(tmp_path, logs), reason)


@pytest.mark.parametrize("depth", [2, True])
def test_review_child_depth_must_remain_exactly_one(tmp_path, depth):
    parent = session("parent", children=("child",))
    child = session("child", parent="parent", start=2, end=8, aborted=True)
    child[0]["payload"]["source"]["subagent"]["thread_spawn"]["depth"] = depth
    assert_unavailable(derive(tmp_path, {"parent": parent, "child": child}), "delegation_depth_exceeded")


def test_review_three_overlapping_aborted_children_remain_invalid(tmp_path):
    logs = {"parent": session("parent", children=("one", "two", "three"))}
    logs.update(
        {
            name: session(name, parent="parent", start=2, end=8, aborted=True)
            for name in ("one", "two", "three")
        }
    )
    assert_unavailable(derive(tmp_path, logs), "native_child_concurrency_exceeded")


def test_review_absent_child_end_does_not_prove_a_released_concurrency_slot(tmp_path):
    logs = {
        "parent": session("parent", children=("one", "two", "three")),
        "one": session("one", parent="parent", start=2, end=None),
        "two": session("two", parent="parent", start=4, end=8, aborted=True),
        "three": session("three", parent="parent", start=4, end=8, aborted=True),
    }
    result = derive(tmp_path, logs)
    assert result["accounting_status"] == "partial"
    assert result["delegation_boundary_status"] == "unverified"
    assert "child_concurrency_unverified" in result["completeness_reasons"]
    assert result["efficiency_eligible"] is False


@pytest.mark.parametrize("counter", [True, -1, 1.5, float("inf")])
def test_review_invalid_response_counters_are_not_partial_observations(tmp_path, counter):
    parent = session("parent", aborted=True)
    native_response(parent)["usage"]["input_tokens"] = counter
    result = derive(tmp_path, {"parent": parent})
    assert result["provenance_status"] == "invalid"
    assert result["accounting_status"] == "unavailable"
    assert result["lower_bounds"]["input_tokens"] is None


def test_review_partial_derivation_does_not_modify_retained_bytes(tmp_path):
    write_sessions(tmp_path, {"parent": session("parent", aborted=True)})
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    result = partial_module().derive_partial_usage(tmp_path)
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert result["source_log_sha256"] == sorted(hashlib.sha256(raw).hexdigest() for raw in before.values())


def test_review_complete_logs_must_agree_with_original_strict_parser(tmp_path):
    result = derive(tmp_path, {"parent": session("parent")})
    assert result["accounting_status"] == "complete"
    assert result["child_usage_complete"] is True
    assert all(result["complete_usage"][key] == value for key, value in result["lower_bounds"].items())


def test_review_symlinked_native_log_is_invalid_not_missing_usage(tmp_path):
    source = tmp_path / "outside"
    source.write_text("private source must not be followed")
    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "parent.jsonl").symlink_to(source)
    assert_unavailable(partial_module().derive_partial_usage(logs), "native_log_symlink")


def test_review_frozen_bridge_ignores_unchecked_existing_bytecode(tmp_path, monkeypatch):
    import amended_pilot

    controller = tmp_path / "controller"
    source = tmp_path / "frozen"
    campaign = tmp_path / "campaign"
    for directory in (controller, source, campaign):
        directory.mkdir()
    module = source / "campaign.py"
    module.write_text("value = 'registered-source'\n")
    cache = Path(py_compile.compile(str(module), doraise=True))
    header = cache.read_bytes()[:16]
    poisoned = compile("value = 'unregistered-cached-code'\n", str(module), "exec")
    cache.write_bytes(header + marshal.dumps(poisoned))
    # A narrow transport probe imports a module just as the frozen bridge does.
    # The real FrozenBridge subprocess must not read a matching unchecked .pyc.
    (controller / "frozen_pilot_bridge.py").write_text(
        "import json,sys\n"
        "from pathlib import Path\n"
        "request=json.loads(sys.stdin.read())\n"
        "sys.path.insert(0,request['frozen_source'])\n"
        "import campaign\n"
        "Path(sys.argv[sys.argv.index('--result')+1]).write_text(json.dumps({'value':campaign.value}))\n"
    )
    monkeypatch.setattr(amended_pilot, "HERE", controller)
    result = amended_pilot.FrozenBridge(sys.executable)(
        "inspect", {"campaign": str(campaign), "frozen_source": str(source)}
    )
    assert result == {"value": "registered-source"}


class SyntheticFrozenBridge:
    """Controller transport fixture with actual immutable attempt/log files."""

    def __init__(self, root):
        from lib.common import digest

        self.root = root
        self.executed = []
        self.next_status = "completed"
        self.next_runtime_valid = True
        self.next_no_logs = False
        self.quota_allowed = True
        self.schedule = [
            {
                "trial_id": f"pilot--problem-{i // 3}--r1--{'ABC'[i % 3]}",
                "arm": "ABC"[i % 3],
                "stage": "pilot",
            }
            for i in range(36)
        ]
        self.states = {
            row["trial_id"]: {"trial_id": row["trial_id"], "status": "pending", "attempts": 0}
            for row in self.schedule
        }
        self.source_lock = {
            "campaign_sha256": digest("frozen source"),
            "skill_sha256": digest("frozen skill"),
        }
        (root / "registration-lock.json").write_text(json.dumps({"registered": "synthetic-pilot"}))
        pause = root / "runs/run-0001/end.json"
        pause.parent.mkdir(parents=True)
        pause.write_text(json.dumps({"reason": "usage_accounting_requires_remediation"}))
        for i, row in enumerate(self.schedule[:9]):
            self.finish(row["trial_id"], partial=i == 8)

    def attempt_path(self, trial_id):
        return self.root / "evidence/trials" / trial_id / "attempt-1"

    def sessions_path(self, trial_id):
        return self.root / "private-harbor" / trial_id / "attempt-1/harbor-fixture/agent/sessions"

    def finish(self, trial_id, *, partial=False, status="completed", runtime_valid=True, no_logs=False):
        logs = self.sessions_path(trial_id)
        if not no_logs:
            logs.mkdir(parents=True)
            write_sessions(logs, {"parent": session("parent", aborted=partial)})
            derived = partial_module().derive_partial_usage(logs)
            usage = derived["complete_usage"] or {
                "child_usage_complete": False,
                "accounting_status": "unavailable",
            }
        else:
            usage = {"child_usage_complete": False, "accounting_status": "unavailable"}
        usage = {**usage, "runtime_valid": runtime_valid}
        path = self.attempt_path(trial_id)
        path.mkdir(parents=True)
        value = {
            "status": status,
            "error_code": "docker_start_failed" if status == "infra_failure" else None,
            "usage": usage,
        }
        (path / "finish.json").write_text(json.dumps(value))
        (path / "manifest.json").write_text(json.dumps({"artifacts": [], "synthetic": trial_id}))
        self.states[trial_id].update(status=status, attempts=1)

    def inspect(self):
        from lib.common import bytes_digest, digest

        attempts = []
        for row in self.schedule:
            if not self.states[row["trial_id"]]["attempts"]:
                continue
            path = self.attempt_path(row["trial_id"])
            finish = json.loads((path / "finish.json").read_bytes())
            attempts.append(
                {
                    "trial_id": row["trial_id"],
                    "attempt": 1,
                    **finish,
                    "finish_sha256": bytes_digest((path / "finish.json").read_bytes()),
                    "manifest_sha256": bytes_digest((path / "manifest.json").read_bytes()),
                }
            )
        return {
            "registration_sha256": digest(json.loads((self.root / "registration-lock.json").read_bytes())),
            "source_lock": copy.deepcopy(self.source_lock),
            "schedule": copy.deepcopy(self.schedule),
            "schedule_sha256": digest(self.schedule),
            "states": copy.deepcopy(list(self.states.values())),
            "attempts": attempts,
        }

    def __call__(self, action, request):
        from lib.common import digest

        if action in {"inspect", "verify"}:
            return self.inspect()
        if action == "report":
            return {"export_id": digest(self.inspect())}
        assert action == "execute"
        if not self.quota_allowed:
            return {"dispatched": False, "reason": "subscription_exhausted"}
        trial_id = request["trial_id"]
        assert self.states[trial_id] == {"trial_id": trial_id, "status": "pending", "attempts": 0}
        self.executed.append(trial_id)
        self.finish(
            trial_id,
            status=self.next_status,
            runtime_valid=self.next_runtime_valid,
            no_logs=self.next_no_logs,
            partial=self.next_status == "timeout",
        )
        return {"dispatched": True, "trial_id": trial_id, "status": self.next_status}


@pytest.fixture
def amended_fixture(tmp_path):
    import amended_pilot

    root = tmp_path / "campaign"
    root.mkdir()
    bridge = SyntheticFrozenBridge(root)
    registration = amended_pilot.register(
        root,
        tmp_path / "frozen",
        tmp_path / "upstream",
        authorization="partial accounting",
        bridge=bridge,
    )
    return amended_pilot, root, bridge, registration["amendment_sha256"]


@pytest.mark.parametrize("runtime_valid", [None, False, 1, "true"])
def test_review_partial_permission_does_not_waive_positive_runtime_identity(tmp_path, runtime_valid):
    import amended_pilot

    derived = derive(tmp_path, {"parent": session("parent", aborted=True)})
    assert amended_pilot.admit({"runtime_valid": runtime_valid}, derived) == (
        False,
        "runtime_identity_requires_remediation",
    )


def test_review_unverified_child_concurrency_cannot_resume_despite_valid_provenance(tmp_path):
    import amended_pilot

    derived = derive(
        tmp_path,
        {
            "parent": session("parent", children=("child",)),
            "child": session("child", parent="parent", start=2, end=None),
        },
    )
    assert derived["provenance_status"] == "valid"
    assert amended_pilot.admit({"runtime_valid": True}, derived) == (
        False,
        "delegation_boundary_requires_remediation",
    )


def test_review_resume_only_pending_rows_without_rewriting_ninth_attempt(amended_fixture):
    module, root, bridge, identity = amended_fixture
    original = {p: p.read_bytes() for p in (root / "evidence").rglob("*") if p.is_file()}
    result = module.run(root, identity, limit=2, bridge=bridge)
    assert result["dispatched"] == [row["trial_id"] for row in bridge.schedule[9:11]]
    assert result["pending_trials"] == 25
    assert all(path.read_bytes() == raw for path, raw in original.items())
    assert bridge.schedule[8]["trial_id"] not in bridge.executed
    report = result["accounting_report"]["resource_report"]
    assert report["scheduled_trials"] == 36
    assert report["retained_attempts"] == 11
    assert report["efficiency_comparison_eligible"] is False
    assert sum(arm["partial_attempts"] for arm in report["arms"].values()) == 1
    assert sum(arm["scheduled_trials"] for arm in report["arms"].values()) == 36
    assert sum(arm["pending_trials"] for arm in report["arms"].values()) == 25
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in report["arms"].values()) == 110
    assert sum(arm["partial_attempts_lower_bounds"]["input_tokens"] for arm in report["arms"].values()) == 10
    assert (
        sum(arm["complete_attempts_exact_totals"]["input_tokens"] for arm in report["arms"].values()) == 100
    )


@pytest.mark.parametrize("status", ["timeout", "agent_failure", "budget_exhausted"])
def test_review_terminal_task_failures_never_get_a_second_attempt(amended_fixture, status):
    module, root, bridge, identity = amended_fixture
    bridge.next_status = status
    first = module.run(root, identity, limit=1, bridge=bridge)
    first_trial = first["dispatched"][0]
    second = module.run(root, identity, limit=1, bridge=bridge)
    assert second["dispatched"] == [bridge.schedule[10]["trial_id"]]
    assert bridge.executed.count(first_trial) == 1
    assert bridge.states[first_trial]["attempts"] == 1


def test_review_quota_exhaustion_does_not_dispatch_or_create_attempt(amended_fixture):
    module, root, bridge, identity = amended_fixture
    bridge.quota_allowed = False
    result = module.run(root, identity, limit=1, bridge=bridge)
    assert result["status"] == "paused"
    assert result["reason"] == "subscription_exhausted"
    assert result["dispatched"] == []
    assert len(bridge.inspect()["attempts"]) == 9


def test_review_new_runtime_uncertainty_pauses_but_keeps_observed_consumption(amended_fixture):
    module, root, bridge, identity = amended_fixture
    bridge.next_runtime_valid = None
    result = module.run(root, identity, limit=2, bridge=bridge)
    assert result["dispatched"] == [bridge.schedule[9]["trial_id"]]
    assert result["reason"] == "runtime_identity_requires_remediation"
    report = result["accounting_report"]["resource_report"]
    assert sum(arm["runtime_invalid_attempts"] for arm in report["arms"].values()) == 1
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in report["arms"].values()) == 100
    assert report["efficiency_comparison_eligible"] is False


def test_review_infrastructure_failure_without_native_logs_is_visible_and_not_retried(amended_fixture):
    module, root, bridge, identity = amended_fixture
    bridge.next_status = "infra_failure"
    bridge.next_no_logs = True
    bridge.next_runtime_valid = None
    result = module.run(root, identity, limit=2, bridge=bridge)
    assert result["status"] == "paused"
    assert result["reason"] == "infrastructure_failure_requires_inspection"
    assert result["dispatched"] == [bridge.schedule[9]["trial_id"]]
    report = result["accounting_report"]["resource_report"]
    assert report["retained_attempts"] == 10
    assert sum(arm["unavailable_accounting_attempts"] for arm in report["arms"].values()) == 1
    assert sum(arm["continuation_blocked_attempts"] for arm in report["arms"].values()) == 1
    again = module.run(root, identity, limit=1, bridge=bridge)
    assert again["dispatched"] == []
    assert len(bridge.executed) == 1


@pytest.mark.parametrize(
    "target", ["finish", "manifest", "source", "schedule", "pause", "local_sources", "amendment"]
)
def test_review_modified_registration_or_retained_evidence_blocks_dispatch(amended_fixture, target):
    module, root, bridge, identity = amended_fixture
    if target in {"finish", "manifest"}:
        path = bridge.attempt_path(bridge.schedule[0]["trial_id"]) / f"{target}.json"
        value = json.loads(path.read_bytes())
        value["unregistered"] = True
        path.write_text(json.dumps(value))
    elif target == "source":
        bridge.source_lock["skill_sha256"] = "f" * 64
    elif target == "schedule":
        bridge.schedule[9]["arm"] = "A" if bridge.schedule[9]["arm"] != "A" else "B"
    else:
        path = {
            "pause": root / "runs/run-0001/end.json",
            "local_sources": root / module.AMENDMENT / "local-sources.json",
            "amendment": root / module.AMENDMENT / "amendment.json",
        }[target]
        value = json.loads(path.read_bytes())
        value["unregistered"] = True
        path.write_text(json.dumps(value))
    with pytest.raises((ValueError, KeyError)):
        module.run(root, identity, limit=1, bridge=bridge)
    assert bridge.executed == []


@pytest.mark.parametrize("rewrite_sidecar", [False, True])
def test_review_baseline_native_bytes_are_bound_to_amendment_not_only_replaceable_sidecar(
    amended_fixture, rewrite_sidecar
):
    module, root, bridge, identity = amended_fixture
    trial_id = bridge.schedule[8]["trial_id"]
    path = bridge.sessions_path(trial_id) / "parent.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    native_response(rows)["usage"]["input_tokens"] += 1000
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    if rewrite_sidecar:
        sidecar = root / module.AMENDMENT / "usage" / trial_id / "attempt-1.json"
        value = json.loads(sidecar.read_bytes())
        value["derived_usage"] = partial_module().derive_partial_usage(path.parent)
        sidecar.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        module.verify(root, identity, bridge=bridge)


def test_review_deleting_baseline_sidecar_cannot_silently_regenerate_it(amended_fixture):
    module, root, bridge, identity = amended_fixture
    trial_id = bridge.schedule[8]["trial_id"]
    sidecar = root / module.AMENDMENT / "usage" / trial_id / "attempt-1.json"
    sidecar.unlink()
    with pytest.raises(ValueError):
        module.run(root, identity, limit=1, bridge=bridge)
    assert bridge.executed == []


def test_review_new_attempt_remains_bound_after_its_completed_run(amended_fixture):
    module, root, bridge, identity = amended_fixture
    bridge.next_status = "timeout"
    result = module.run(root, identity, limit=1, bridge=bridge)
    trial_id = result["dispatched"][0]
    path = bridge.sessions_path(trial_id) / "parent.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    native_response(rows)["usage"]["input_tokens"] += 1000
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    sidecar = root / module.AMENDMENT / "usage" / trial_id / "attempt-1.json"
    value = json.loads(sidecar.read_bytes())
    value["derived_usage"] = partial_module().derive_partial_usage(path.parent)
    sidecar.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        module.verify(root, identity, bridge=bridge)


@pytest.mark.parametrize("missing", ["dispatch_receipt", "run_end", "new_sidecar"])
def test_review_deleted_new_evidence_cannot_be_silently_regenerated_on_resume(amended_fixture, missing):
    module, root, bridge, identity = amended_fixture
    result = module.run(root, identity, limit=1, bridge=bridge)
    trial_id = result["dispatched"][0]
    amendment = root / module.AMENDMENT
    if missing == "dispatch_receipt":
        receipts = list((amendment / "runs").rglob("completed.json"))
        assert len(receipts) == 1
        path = receipts[0]
    elif missing == "run_end":
        path = amendment / "runs/run-0001/end.json"
    else:
        path = amendment / "usage" / trial_id / "attempt-1.json"
    path.unlink()
    with pytest.raises(ValueError):
        module.run(root, identity, limit=1, bridge=bridge)
    assert bridge.executed == [trial_id]
