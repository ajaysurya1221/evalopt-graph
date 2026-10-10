import asyncio
import inspect
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import harbor_bridge as bridge


def test_capture_roster_never_includes_auth_or_home():
    assert bridge.CAPTURE_PATHS == ["/workspace", "/tmp/codex-home/sessions"]
    assert not any("auth" in name or name in {"/root", "/tmp/codex-home"} for name in bridge.CAPTURE_PATHS)


def test_retained_agent_has_no_finally_candidate_commands():
    text = inspect.getsource(bridge.retained_codex_class)
    run = text[text.index("async def run") :]
    assert "finally:" not in run and "rm -rf" not in run
    assert "self.exec_as_agent" in run
    assert "os.environ" not in text


def test_stopped_missing_capture_freezes_before_return_without_hidden(tmp_path, monkeypatch):
    observed = []

    async def freeze(bundle):
        assert not (tmp_path / "result.json").exists()
        assert bundle["observations"][0]["candidate_id"] == "unavailable"
        assert bundle["observations"][0]["execution_state"] == "not_run"
        observed.append(bundle)
        return {"frozen_visible_sha": "fixture"}

    closure = {"execution_boundary": "unconfirmed", "snapshot": "missing", "reason": "deadline"}
    result = asyncio.run(
        bridge.finish_stopped(
            {"trial_id": "x", "task_id": "t", "attempt_id": "x-1"},
            tmp_path,
            tmp_path,
            {
                "task": {
                    "task_id": "t",
                    "task_contract": "implementation",
                    "visible_command": ["python3", "verify.py"],
                },
                "initial_sha256": "a" * 64,
                "initial_manifest": {},
            },
            closure,
            verifier_image="sha256:" + "a" * 64,
            freeze_visible=freeze,
        )
    )
    assert len(observed) == 1 and result["verification"] is None
    assert result["status"] == "timeout" and result["usage"]["accounting_status"] == "unavailable"
    assert (tmp_path / "policy-receipt.json").exists()


def test_bad_or_sync_freeze_receipt_blocks_hidden(tmp_path):
    closure = {"execution_boundary": "unconfirmed", "snapshot": "missing", "reason": "agent_end"}
    task = {
        "task": {"task_contract": "implementation", "visible_command": ["x"]},
        "initial_sha256": "a",
        "initial_manifest": {},
    }
    with pytest.raises(ValueError, match="awaitable"):
        asyncio.run(
            bridge.finish_stopped(
                {"trial_id": "x"},
                tmp_path,
                tmp_path,
                task,
                closure,
                verifier_image="sha256:" + "a" * 64,
                freeze_visible=lambda _: {},
            )
        )


def test_fresh_attempt_required_before_any_auth_or_model(tmp_path):
    with pytest.raises(ValueError, match="fresh_attempt"):
        asyncio.run(
            bridge.execute_one(
                {}, tmp_path, tmp_path, None, None, None, "x", "x", freeze_visible=lambda _: {}
            )
        )


def test_missing_supervisor_ready_prevents_agent_dispatch(tmp_path, monkeypatch):
    class Agent:
        async def run(self, *args):
            pytest.fail("agent ran without supervisor ready")

    monkeypatch.setattr(
        bridge, "spawn_supervisor", lambda *a, **k: ({"spec_sha256": "x"}, SimpleNamespace(poll=lambda: 2))
    )
    with pytest.raises(ValueError, match="supervisor_exited"):
        asyncio.run(bridge.run_supervised(Agent(), None, "", None, identity={}, directory=tmp_path))


def test_supervisor_stops_then_recovers_same_closure(tmp_path, monkeypatch):
    events = []
    closure = {"test": "closure"}
    from evalopt_v2.lifecycle import digest

    prepared = {"spec_sha256": "s", "spec": "spec"}

    class Agent:
        async def run(self, *args):
            events.append("agent")

    monkeypatch.setattr(
        bridge, "spawn_supervisor", lambda *a, **k: (prepared, SimpleNamespace(poll=lambda: None))
    )

    async def wait(path, process, seconds):
        if path.name == "ready.json":
            return {"kind": "supervisor_ready", "spec_sha256": "s"}
        while "signal" not in events:
            await asyncio.sleep(0)
        events.append("end")
        return {"closure_sha256": digest(closure)}

    monkeypatch.setattr(bridge, "wait_record", wait)
    monkeypatch.setattr(bridge, "signal_agent_complete", lambda *a: events.append("signal"))
    monkeypatch.setattr(bridge, "recover_closure", lambda *a: closure)
    result, error = asyncio.run(
        bridge.run_supervised(Agent(), None, "", None, identity={}, directory=tmp_path)
    )
    assert events == ["agent", "signal", "end"] and result == closure and error is None


def _actual_harbor_smoke(tmp_path, monkeypatch, include_native_end=True):
    """Real Harbor/container/supervisor/grader; substituted native writer, zero models."""
    import os
    import shlex
    import subprocess

    from evalopt_v2.capture import DockerController
    from evalopt_v2.framing import SCHEMA
    from evalopt_v2.policies import evaluate_visible

    image = os.environ["EVALOPT_V2_AGENT_CONTROL_IMAGE"]
    verifier_image = os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"]
    auth = tmp_path / "synthetic-auth.json"
    auth.write_text("{}")
    monkeypatch.setattr(bridge, "auth_path", lambda: auth)
    monkeypatch.setattr(
        bridge,
        "require_versions",
        lambda: {
            "controller": "CPython 3.13.12",
            "harbor": "0.24.0",
            "codex": "0.154.0",
            "scope": "offline-synthetic",
        },
    )
    monkeypatch.setattr(
        bridge,
        "subscription_permission",
        lambda: {
            "schema_version": SCHEMA,
            "ordinary_usage_allowed": True,
            "state": "allowed",
            "scope": "offline-synthetic",
        },
    )
    native = bridge.retained_codex_class()

    class Synthetic(native):
        async def run(self, instruction, environment, context):
            await environment.upload_file(task / "oracle/expand.py", "/workspace/expand.py")
            check = await environment.exec(command="python3 -B verify.py", timeout_sec=10)
            assert check.return_code == 0
            response = {
                "status": "completed",
                "findings": [],
                "blockers": [],
                "checks": [
                    {
                        "command": ["python3", "-B", "verify.py"],
                        "execution_state": "ran",
                        "exit_code": 0,
                        "evidence_availability": "complete",
                    }
                ],
            }
            rows = []

            def event(kind, payload, n):
                rows.append({"type": kind, "payload": payload, "timestamp": f"2026-10-11T00:00:{n:02d}Z"})

            event("session_meta", {"id": "fixture-parent", "source": "exec", "cli_version": "0.154.0"}, 0)
            event("turn_context", {"turn_id": "fixture-turn", "model": "gpt-6-astra", "effort": "ultra"}, 1)
            event("event_msg", {"type": "task_started", "turn_id": "fixture-turn"}, 1)
            event(
                "token_usage_record",
                {
                    "thread_id": "fixture-parent",
                    "turn_id": "fixture-turn",
                    "response_id": "fixture-response",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
                2,
            )
            event(
                "response_item",
                {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final_answer",
                    "content": [{"type": "output_text", "text": json.dumps(response)}],
                },
                3,
            )
            if include_native_end:
                event("event_msg", {"type": "task_complete", "turn_id": "fixture-turn"}, 4)
            text = "".join(json.dumps(row) + "\n" for row in rows)
            command = shlex.join(
                [
                    "python3",
                    "-I",
                    "-B",
                    "-c",
                    "from pathlib import Path;Path('/tmp/codex-home/sessions/fixture.jsonl').write_text("
                    + repr(text)
                    + ")",
                ]
            )
            result = await environment.exec(command=command, timeout_sec=10)
            assert result.return_code == 0

    monkeypatch.setattr(bridge, "retained_codex_class", lambda: Synthetic)
    order = []

    async def freeze(bundle):
        assert not (tmp_path / "attempt/verifier").exists()
        order.append("freeze")
        decision = evaluate_visible(
            bundle,
            check_roster=[{"check_id": "task-check", "command": ["python3", "-B", "verify.py"]}],
            attempt_id=bundle["attempt_id"],
            candidate_id=bundle["snapshot_sha256"],
            observed_at="2026-10-11T00:00:00Z",
        )
        from evalopt_v2.lifecycle import write_once

        write_once(tmp_path / "actual-policy-freeze.json", {"visible": bundle, "decisions": decision})
        return decision

    task = Path(__file__).resolve().parents[1] / "tasks/development/bounded-run-expansion"
    root = tmp_path / "attempt"
    try:
        result = asyncio.run(
            bridge.execute_one(
                {
                    "trial_id": "offline-harbor",
                    "attempt_id": "offline-harbor-1",
                    "task_id": task.name,
                    "arm": "A",
                },
                task,
                root,
                None,
                None,
                None,
                image,
                verifier_image,
                freeze_visible=freeze,
            )
        )
        assert result["closure"]["execution_boundary"] == "confirmed"
        assert result["closure"]["snapshot"] == "complete"
        assert result["runtime_identity"]["verified"]
        assert result["usage"]["accounting_status"] == ("complete" if include_native_end else "partial")
        assert result["response_capture"]["status"] == "parsed"
        assert order == ["freeze"] and result["verification"] is not None
        assert len(result["verification"]["case_records"]) == len(
            json.loads((task / "task.json").read_text())["cases"]
        )
        assert not (root / "native-sessions/auth.json").exists()
        assert result["verification"]["grade"]["functional_success"] is True
        assert result["verification"]["grade"]["valid_completion"] is (True if include_native_end else None)
        assert result["native_lifecycle"]["parent_native_completion"] is (
            True if include_native_end else None
        )
    finally:
        # Only exact identities created by this fixture; no broad prune/cleanup.
        paths = list(root.glob("**/identity.json")) + list(root.glob("**/end.json"))
        seen = set()
        for path in paths:
            value = json.loads(path.read_text())
            identity = value if "container_id" in value else value.get("identity")
            if not isinstance(identity, dict) or identity.get("container_id") in seen:
                continue
            seen.add(identity["container_id"])
            controller = DockerController()
            observation = controller.inspect_owned(identity)
            if not observation["stopped"]:
                controller.terminate(identity)
            subprocess.run(
                ["docker", "rm", identity["container_id"]], capture_output=True, timeout=20, check=True
            )


@pytest.mark.skipif(
    not __import__("os").environ.get("EVALOPT_V2_AGENT_CONTROL_IMAGE"),
    reason="explicit local agent and verifier images required",
)
@pytest.mark.parametrize("include_native_end", [True, False])
def test_actual_harbor_synthetic_session_end_to_end(tmp_path, include_native_end):
    import os
    import subprocess

    helper = inspect.getsource(_actual_harbor_smoke)
    repository = Path(__file__).resolve().parents[4]
    prefix = "import asyncio,json,sys\nfrom pathlib import Path\nfrom contextlib import ExitStack\nfrom unittest.mock import patch\n"
    prefix += (
        "sys.path.insert(0,"
        + repr(str(repository / "src"))
        + ");sys.path.insert(0,"
        + repr(str(Path(__file__).resolve().parents[1]))
        + ")\nfrom evalopt_v2 import harbor_bridge as bridge\n"
    )
    prefix += "__file__=" + repr(str(Path(__file__).resolve())) + "\n"
    suffix = (
        "\nclass PatchSet:\n def setattr(self,owner,name,value): stack.enter_context(patch.object(owner,name,value))\nwith ExitStack() as stack: _actual_harbor_smoke(Path("
        + repr(str(tmp_path.resolve()))
        + "),PatchSet(),include_native_end="
        + repr(include_native_end)
        + ")\n"
    )
    launcher = tmp_path / "trusted-offline-launcher.py"
    launcher.write_text(prefix + helper + suffix)
    result = subprocess.run(
        [str(repository / ".venv-harbor/bin/python"), "-I", "-B", str(launcher)],
        capture_output=True,
        timeout=180,
        env=os.environ.copy(),
    )
    (tmp_path / "launcher.stdout").write_bytes(result.stdout)
    (tmp_path / "launcher.stderr").write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode()


def test_mutating_freeze_callback_cannot_change_hidden_inputs(tmp_path):
    async def mutate(bundle):
        bundle["response"] = {"status": "completed"}
        return {"receipt": "invalid"}

    closure = {"execution_boundary": "unconfirmed", "snapshot": "missing", "reason": "agent_end"}
    with pytest.raises(ValueError, match="mutated_visible"):
        asyncio.run(
            bridge.finish_stopped(
                {"trial_id": "x"},
                tmp_path,
                tmp_path,
                {
                    "task": {"task_contract": "implementation", "visible_command": ["x"]},
                    "initial_sha256": "a",
                    "initial_manifest": {},
                },
                closure,
                verifier_image="sha256:" + "a" * 64,
                freeze_visible=mutate,
            )
        )
    assert not (tmp_path / "verifier").exists()


@pytest.mark.parametrize(
    "reasons,delegation,expected",
    [
        ([], "verified", True),
        (["owned_turn_end_missing"], "verified", None),
        (["owned_turn_start_missing"], "verified", None),
        (["owned_turns_missing"], "verified", None),
        (["partial_native_record"], "verified", None),
        (["owned_response_usage_missing"], "verified", True),
        (["owned_turn_aborted"], "verified", False),
        ([], "unverified", None),
        (["owned_turn_end_missing"], "violated", False),
    ],
)
def test_native_parent_completion_is_not_inferred_from_delegation(reasons, delegation, expected):
    usage = {
        "provenance_status": "valid",
        "delegation_status": delegation,
        "agents": [{"agent": "agent-0", "parent": None, "reasons": reasons}],
    }
    result = bridge.lifecycle_observation(usage)
    assert result["lifecycle_verified"] is expected
    if "owned_turn_end_missing" in reasons:
        assert result["parent_native_completion"] is None


def test_external_cutoff_does_not_turn_unknown_native_completion_into_success():
    from evalopt_v2.records import task_outcome

    usage = {
        "provenance_status": "valid",
        "delegation_status": "verified",
        "agents": [{"agent": "agent-0", "parent": None, "reasons": ["owned_turn_end_missing"]}],
    }
    lifecycle = bridge.lifecycle_observation(usage)["lifecycle_verified"]
    for timed_out, expected in ((False, None), (True, False)):
        result = task_outcome(
            "a",
            "implementation",
            functional_success=True,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=lifecycle,
            timed_out=timed_out,
        )
        assert result["functional_success"] is True
        assert result["lifecycle_verified"] is None
        assert result["valid_completion"] is expected
