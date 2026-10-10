"""No-model controls for an append-only continuation of nine retained pilot attempts."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import amended_pilot as controller  # noqa: E402


def native_bytes(*, partial=False, inputs=10):
    records = [
        {
            "type": "session_meta",
            "payload": {"id": "native-private-owner", "source": "exec", "cli_version": "0.154.0"},
        },
        {
            "type": "event_msg",
            "timestamp": "2026-10-08T00:00:00Z",
            "payload": {"type": "task_started", "turn_id": "turn"},
        },
        {
            "type": "token_usage_record",
            "payload": {
                "thread_id": "native-private-owner",
                "turn_id": "turn",
                "response_id": "response",
                "usage": {"input_tokens": inputs, "output_tokens": 2},
            },
        },
        {
            "type": "event_msg",
            "timestamp": "2026-10-08T00:00:04Z",
            "payload": {"type": "turn_aborted" if partial else "task_complete", "turn_id": "turn"},
        },
    ]
    return b"\n".join(controller.canonical_bytes(row) for row in records)


class SyntheticBridge:
    def __init__(self, root):
        self.root = root
        self.schedule = [
            {"trial_id": f"trial-{i:02d}-{arm}", "arm": arm, "stage": "pilot"}
            for i in range(12)
            for arm in "ABC"
        ]
        self.source_lock = {"campaign_sha256": "a" * 64, "kernel_source_sha256": "b" * 64}
        self.modes = []
        self.dispatched = []
        for row in self.schedule[:9]:
            self.complete(row, partial=row is self.schedule[8])

    def complete(self, row, *, partial=False, status="completed", runtime_valid=True, logs=True):
        trial = row["trial_id"]
        path = self.root / "evidence/trials" / trial / "attempt-1"
        path.mkdir(parents=True)
        sessions = self.root / "private-harbor" / trial / "attempt-1/harbor-synthetic/agent/sessions"
        if logs:
            sessions.mkdir(parents=True)
            (sessions / "native.jsonl").write_bytes(native_bytes(partial=partial))
        derived = controller.derive_partial_usage(sessions)
        usage = dict(
            derived["complete_usage"] or {"child_usage_complete": False, "accounting_status": "unavailable"}
        )
        usage["runtime_valid"] = runtime_valid
        controller.write_once(
            path / "finish.json",
            {
                "status": status,
                "error_code": "container_start" if status == "infra_failure" else None,
                "usage": usage,
            },
        )
        controller.write_once(path / "manifest.json", {"fixture": trial})

    def info(self):
        states, attempts = [], []
        for row in self.schedule:
            path = self.root / "evidence/trials" / row["trial_id"] / "attempt-1"
            if not path.exists():
                states.append({"trial_id": row["trial_id"], "attempts": 0, "status": "pending"})
                continue
            finish = controller.read_json(path / "finish.json")
            states.append({"trial_id": row["trial_id"], "attempts": 1, "status": finish["status"]})
            attempts.append(
                {
                    "trial_id": row["trial_id"],
                    "attempt": 1,
                    **finish,
                    "finish_sha256": controller.bytes_digest((path / "finish.json").read_bytes()),
                    "manifest_sha256": controller.bytes_digest((path / "manifest.json").read_bytes()),
                }
            )
        return {
            "registration_sha256": controller.digest(
                controller.read_json(self.root / "registration-lock.json")
            ),
            "source_lock": self.source_lock,
            "schedule": self.schedule,
            "schedule_sha256": controller.digest(self.schedule),
            "states": states,
            "attempts": attempts,
        }

    def __call__(self, action, request):
        if action == "report":
            return {"export_id": controller.digest(self.info())}
        if action in {"inspect", "verify"}:
            return self.info()
        assert action == "execute"
        mode = self.modes.pop(0) if self.modes else "complete"
        permission = Path(request["permission_receipt"])
        controller.write_once(
            permission,
            {
                "state": "exhausted" if mode == "quota" else "allowed",
                "ordinary_usage_allowed": mode != "quota",
            },
        )
        if mode == "quota":
            return {"dispatched": False, "reason": "subscription_exhausted"}
        row = next(row for row in self.schedule if row["trial_id"] == request["trial_id"])
        assert (
            next(s for s in self.info()["states"] if s["trial_id"] == row["trial_id"])["status"] == "pending"
        )
        self.complete(
            row,
            partial=mode == "partial",
            runtime_valid=mode != "runtime",
            status="infra_failure" if mode == "infra" else "completed",
            logs=mode != "infra",
        )
        self.dispatched.append(row["trial_id"])
        return {
            "dispatched": True,
            "trial_id": row["trial_id"],
            "status": "infra_failure" if mode == "infra" else "completed",
        }


@pytest.fixture
def pilot(tmp_path):
    root = tmp_path / "pilot"
    root.mkdir()
    controller.write_once(root / "registration-lock.json", {"fixture": "registration"})
    controller.write_once(
        root / "runs/run-0002/end.json",
        {"status": "paused", "reason": "usage_accounting_requires_remediation"},
    )
    bridge = SyntheticBridge(root)
    registration = controller.register(
        root, tmp_path / "frozen", tmp_path / "upstream", authorization="partial accounting", bridge=bridge
    )
    return root, bridge, registration["amendment_sha256"]


def test_register_preserves_nine_attempts_and_binds_partial_source(pilot):
    root, bridge, identity = pilot
    verified = controller.verify(root, identity, bridge=bridge)
    amendment = verified["amendment"]
    assert len(amendment["baseline_attempts"]) == len(amendment["baseline_usage"]) == 9
    assert len(amendment["pending_trial_ids"]) == 27
    assert not bridge.dispatched
    saved = list((root / controller.AMENDMENT / "usage").glob("*/attempt-1.json"))
    assert len(saved) == 9
    partial = next(
        controller.read_json(path) for path in saved if path.parent.name == bridge.schedule[8]["trial_id"]
    )
    assert partial["derived_usage"]["accounting_status"] == "partial"
    assert partial["derived_usage"]["child_usage_complete"] is False
    assert partial["continuation_admissible"] is True
    assert "native-private-owner" not in json.dumps(amendment)
    assert str(root) not in json.dumps(amendment)


def test_resume_pending_only_keeps_original_bytes_and_reports_lower_bounds(pilot):
    root, bridge, identity = pilot
    before = {p: p.read_bytes() for p in (root / "evidence").rglob("*") if p.is_file()}
    bridge.modes = ["partial", "complete"]
    result = controller.run(root, identity, limit=2, bridge=bridge)
    assert result["status"] == "limited" and result["pending_trials"] == 25
    assert result["dispatched"] == [row["trial_id"] for row in bridge.schedule[9:11]]
    assert all(path.read_bytes() == raw for path, raw in before.items())
    resource = result["accounting_report"]["resource_report"]
    assert resource["retained_attempts"] == 11
    assert sum(arm["observed_lower_bounds"]["input_tokens"] for arm in resource["arms"].values()) == 110
    assert (
        sum(arm["partial_attempts_lower_bounds"]["input_tokens"] for arm in resource["arms"].values()) == 20
    )
    assert (
        sum(arm["complete_attempts_exact_totals"]["input_tokens"] for arm in resource["arms"].values()) == 90
    )
    assert resource["efficiency_comparison_eligible"] is False
    assert controller.report(root, identity, bridge=bridge) == result["accounting_report"]


@pytest.mark.parametrize("mutation", ["finish", "manifest", "sidecar_missing", "logs", "controller", "local"])
def test_changed_frozen_inputs_block_resume(pilot, monkeypatch, mutation):
    root, bridge, identity = pilot
    row = bridge.schedule[8]
    if mutation in {"finish", "manifest"}:
        path = root / "evidence/trials" / row["trial_id"] / "attempt-1" / (mutation + ".json")
        path.write_bytes(path.read_bytes() + b"\n")
    elif mutation == "sidecar_missing":
        (root / controller.AMENDMENT / "usage" / row["trial_id"] / "attempt-1.json").unlink()
    elif mutation == "logs":
        path = (
            root
            / "private-harbor"
            / row["trial_id"]
            / "attempt-1/harbor-synthetic/agent/sessions/native.jsonl"
        )
        path.write_bytes(native_bytes(partial=True, inputs=99))
    elif mutation == "controller":
        monkeypatch.setattr(controller, "code_identity", lambda: {"changed": "0" * 64})
    else:
        path = root / controller.AMENDMENT / "local-sources.json"
        data = controller.read_json(path)
        data["upstream"] += "-changed"
        path.write_bytes(controller.canonical_bytes(data))
    with pytest.raises(ValueError):
        controller.run(root, identity, limit=1, bridge=bridge)
    assert not bridge.dispatched


def test_quota_pause_consumes_no_attempt_and_explicit_later_run_can_continue(pilot):
    root, bridge, identity = pilot
    bridge.modes = ["quota"]
    stopped = controller.run(root, identity, limit=1, bridge=bridge)
    assert stopped["reason"] == "subscription_exhausted"
    assert stopped["pending_trials"] == 27 and not bridge.dispatched
    resumed = controller.run(root, identity, limit=1, bridge=bridge)
    assert len(resumed["dispatched"]) == 1


def test_fresh_infrastructure_without_logs_pauses_and_never_retries(pilot):
    root, bridge, identity = pilot
    bridge.modes = ["infra"]
    stopped = controller.run(root, identity, limit=2, bridge=bridge)
    assert stopped["reason"] == "infrastructure_failure_requires_inspection"
    assert len(bridge.dispatched) == 1
    resource = stopped["accounting_report"]["resource_report"]
    assert sum(row["unavailable_accounting_attempts"] for row in resource["arms"].values()) == 1
    again = controller.run(root, identity, limit=1, bridge=bridge)
    assert again["reason"] == stopped["reason"] and len(bridge.dispatched) == 1


def test_runtime_failure_blocks_but_retains_known_consumption(pilot):
    root, bridge, identity = pilot
    bridge.modes = ["runtime"]
    result = controller.run(root, identity, limit=2, bridge=bridge)
    assert result["reason"] == "runtime_identity_requires_remediation"
    arms = result["accounting_report"]["resource_report"]["arms"]
    assert sum(row["runtime_invalid_attempts"] for row in arms.values()) == 1
    assert sum(row["observed_lower_bounds"]["input_tokens"] for row in arms.values()) == 100


@pytest.mark.parametrize(
    "key,value",
    [
        ("provenance_status", "invalid"),
        ("delegation_boundary_status", "unverified"),
        ("efficiency_eligible", True),
        ("child_usage_complete", True),
    ],
)
def test_partial_admission_does_not_relax_structural_or_completeness_gates(pilot, key, value):
    root, bridge, identity = pilot
    record = bridge.info()["attempts"][-1]
    sidecar = controller.derive_attempt(root, identity, record["trial_id"], bridge=bridge)
    derived = copy.deepcopy(sidecar["derived_usage"])
    derived[key] = value
    assert controller.admit(record["usage"], derived)[0] is False


def test_duplicate_resource_attempt_cannot_double_count(pilot):
    root, bridge, identity = pilot
    info = bridge.info()
    sidecars = controller._all_sidecars(root, identity, info)
    with pytest.raises(ValueError, match="duplicate"):
        controller.summarize_resources(
            identity,
            info["registration_sha256"],
            info["schedule"],
            info["states"],
            sidecars + sidecars[:1],
            "e" * 64,
        )
