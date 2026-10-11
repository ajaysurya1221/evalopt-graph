"""Full-row, no-model Harbor controls with real frozen-source/report replay.

The agent implementation and native events are explicitly synthetic. Docker,
Harbor environment setup, stopped capture, visible policy, isolated cases, store
sealing, and semantic replay are real. No subscription or model is contacted.
"""

import inspect
import os
import subprocess
from pathlib import Path

import pytest


def _positive_replay_control(directory, include_native_end):
    import asyncio
    import hashlib
    import importlib.util
    import json
    import runpy
    import shlex
    import shutil
    from unittest.mock import patch

    from evalopt_v2 import campaign, harbor_bridge, preflight
    from evalopt_v2.capture import DockerController
    from evalopt_v2.freeze import prepare, reviewed_inputs, verify_frozen
    from evalopt_v2.lifecycle import write_once
    from evalopt_v2.policies import evaluate_visible
    from evalopt_v2.records import canonical, digest
    from evalopt_v2.registration import CATEGORIES, schedule
    from evalopt_v2.store import exclusive_json, read_json

    directory = Path(directory).resolve()
    benchmark = Path(__file__).resolve().parents[1]
    repository = benchmark.parents[2]
    agent_image = os.environ["EVALOPT_V2_AGENT_CONTROL_IMAGE"]
    verifier_image = os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"]
    upstream = Path(os.environ["EVALOPT_V2_UPSTREAM_CONTROL"]).resolve()
    harness = directory / "input-harness"
    harness.mkdir()
    shutil.copytree(
        benchmark / "evalopt_v2",
        harness / "evalopt_v2",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    shutil.copytree(benchmark / "runtime", harness / "runtime")
    task_root = directory / "input-tasks"
    task_root.mkdir()
    # Only one row executes. The other eleven task identities are explicit
    # fixture-only schedule placeholders, not authored difficulty evidence.
    catalog = [
        {
            "id": f"fixture-{category}-{index}",
            "category": category,
            "split": "development",
            "source_cluster": f"fixture-{category}-{index}",
            "evidence_opportunity": index == 0,
        }
        for category in CATEGORIES
        for index in range(2)
    ]
    first = schedule(catalog, "development")[0]
    first_metadata = next(item for item in catalog if item["id"] == first["task_id"])
    source_task = benchmark / "tasks/development/bounded-run-expansion"
    authored = json.loads((source_task / "task.json").read_text())
    task = dict(authored, **first_metadata, task_id=first["task_id"])
    frozen_input = task_root / "development" / first["task_id"]
    frozen_input.parent.mkdir()
    shutil.copytree(source_task, frozen_input)
    (frozen_input / "task.json").write_bytes(canonical(task))
    (task_root / "catalog.json").write_bytes(canonical(catalog))
    skill_c = repository / "skills/eval-opt-v2"
    fixture_evidence = digest({"scope": "synthetic offline integration; not live admission"})
    admission = {
        "schema_version": "evalopt-workflows-v2/1",
        "development_round": {"revision": 0, "previous": None},
        "inputs": reviewed_inputs(harness, skill_c, task_root),
        "controls": {
            name: {"status": "PASS", "skipped": 0, "evidence_sha256": fixture_evidence}
            for name in (
                "audited_regressions",
                "semantic",
                "framing_accounting",
                "lifecycle",
                "compatibility_reproduction",
            )
        },
        "reviews": {
            name: {"verdict": "ACCEPT", "evidence_sha256": fixture_evidence}
            for name in ("skill", "tasks", "grading_capture", "integration_analysis")
        },
    }
    root = directory / "campaign"
    freeze = prepare(
        root,
        harness=harness,
        skill_c=skill_c,
        task_root=task_root,
        upstream=upstream,
        agent_image=agent_image,
        verifier_image=verifier_image,
        admission=admission,
        kernel=repository / "src/evalopt_graph",
    )
    store = verify_frozen(root, expected_sha256=freeze["registration_sha256"])
    assert store.next_row() == first
    attempt = store.start(first["trial_id"])
    start = read_json(attempt / "start.json")
    row = dict(first, attempt_id=start["attempt_id"])
    task_directory = root / "frozen/tasks/development" / row["task_id"]
    permission = {
        "schema_version": "evalopt-workflows-v2/1",
        "kind": "subscription_permission",
        "ordinary_usage_allowed": True,
        "state": "allowed",
    }
    auth = directory / "synthetic-auth.json"
    auth.write_text("{}")
    native = harbor_bridge.retained_codex_class()

    class SyntheticCodex(native):
        async def run(self, instruction, environment, context):
            # Trusted authored oracle copied as a fixture mutation. No model.
            await environment.upload_file(task_directory / "oracle/expand.py", "/workspace/expand.py")
            checked = await environment.exec(command="python3 -B verify.py", timeout_sec=10)
            assert checked.return_code == 0
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

            def event(kind, payload, second):
                return {"type": kind, "payload": payload, "timestamp": f"2026-10-11T00:00:0{second}Z"}

            events = [
                event(
                    "session_meta", {"id": "fixture-parent", "source": "exec", "cli_version": "0.154.0"}, 0
                ),
                event(
                    "turn_context", {"turn_id": "fixture-turn", "model": "gpt-6-astra", "effort": "ultra"}, 1
                ),
                event("event_msg", {"type": "task_started", "turn_id": "fixture-turn"}, 1),
                event(
                    "token_usage_record",
                    {
                        "thread_id": "fixture-parent",
                        "turn_id": "fixture-turn",
                        "response_id": "fixture-response",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    },
                    2,
                ),
                event(
                    "response_item",
                    {
                        "type": "message",
                        "role": "assistant",
                        "phase": "final_answer",
                        "content": [{"type": "output_text", "text": json.dumps(response)}],
                    },
                    3,
                ),
            ]
            if include_native_end:
                events.append(event("event_msg", {"type": "task_complete", "turn_id": "fixture-turn"}, 4))
            text = "".join(json.dumps(event) + "\n" for event in events)
            script = (
                "from pathlib import Path;p=Path('/tmp/codex-home/sessions');p.mkdir(parents=True,exist_ok=True);(p/'fixture.jsonl').write_text("
                + repr(text)
                + ")"
            )
            written = await environment.exec(command="python3 -B -c " + shlex.quote(script), timeout_sec=10)
            assert written.return_code == 0

    async def freeze_visible(bundle):
        assert not (attempt / "runtime/verifier").exists()
        policies = evaluate_visible(
            bundle,
            check_roster=[{"check_id": "required", "command": task["visible_command"]}],
            attempt_id=start["attempt_id"],
            candidate_id=bundle["snapshot_sha256"],
            observed_at="2026-10-11T00:00:05Z",
        )
        return store.record_visible(first["trial_id"], bundle, policies)

    runtime = attempt / "runtime"
    try:
        with (
            patch.object(harbor_bridge, "auth_path", return_value=auth),
            patch.object(
                harbor_bridge, "require_versions", return_value={"scope": "offline synthetic control"}
            ),
            patch.object(harbor_bridge, "subscription_permission", return_value=permission),
            patch.object(harbor_bridge, "retained_codex_class", return_value=SyntheticCodex),
            patch.object(
                preflight, "subscription_permission", side_effect=AssertionError("auth not permitted")
            ),
        ):
            result = asyncio.run(
                harbor_bridge.execute_one(
                    row,
                    task_directory,
                    runtime,
                    root / "frozen/upstream",
                    root / "frozen/skill-c",
                    root / "frozen/skill-d",
                    agent_image,
                    verifier_image,
                    freeze_visible=freeze_visible,
                )
            )
        exclusive_json(attempt / "post-permission.json", permission)
        grade, continuation = campaign.project_result(
            dict(task, attempt_id=start["attempt_id"]), result, permission
        )
        exclusive_json(attempt / "usage.json", result["usage"])
        store.record_grade(first["trial_id"], grade)
        store.finalize(first["trial_id"], grade["outcome"], continuation)
        assert grade["outcome"]["functional_success"] is True
        assert grade["outcome"]["valid_completion"] is (True if include_native_end else None)
        assert result["case_boundary_confirmed"] is True
        assert len(result["verification"]["case_records"]) == len(task["cases"]) == 9
        assert result["usage"]["accounting_status"] == ("complete" if include_native_end else "partial")
        # External cutoff plus valid partial accounting permits continuation;
        # it does not establish missing native completion or a successful grade.
        assert continuation["decision"] == "continue"
        before = {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }
        # Replay may invoke read-only git for pinned upstream provenance. Every
        # process command besides that, and every candidate adapter, is denied.
        original_popen = subprocess.Popen

        def no_candidate_process(argv, *args, **kwargs):
            assert isinstance(argv, (list, tuple)) and argv[0] == "git", "replay launched candidate process"
            return original_popen(argv, *args, **kwargs)

        from evalopt_v2 import case_runner, verifier, verifier_container

        with (
            patch.object(subprocess, "Popen", side_effect=no_candidate_process),
            patch.object(
                importlib.util, "spec_from_file_location", side_effect=AssertionError("candidate import")
            ),
            patch.object(runpy, "run_path", side_effect=AssertionError("candidate run_path")),
            patch.object(harbor_bridge, "execute_one", side_effect=AssertionError("agent replay")),
            patch.object(case_runner, "run_case", side_effect=AssertionError("candidate replay")),
            patch.object(verifier, "verify_task", side_effect=AssertionError("live verifier replay")),
            patch.object(verifier_container, "docker_invoker", side_effect=AssertionError("Docker replay")),
        ):
            store.verify_trial(first["trial_id"])
            campaign.validate_retained_grade(store, first["trial_id"], grade)
            report = campaign.replay(root, expected_sha256=freeze["registration_sha256"])
            assert report == campaign.replay(root, expected_sha256=freeze["registration_sha256"])
        assert before == {
            str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*")
            if path.is_file()
        }
        assert report["finalized_rows"] == report["retained_attempts"] == 1
        assert len(report["scheduled_rows"]) == 48 and report["unfinalized_trials"] == []
        selected = next(item for item in report["scheduled_rows"] if item["trial_id"] == first["trial_id"])
        assert selected["reported_valid_completion"] is (True if include_native_end else None)
        assert selected["reported_functional_success"] is True
        assert (
            sum(
                item["missing_reason"] == "unstarted_or_missing"
                for item in report["scheduled_rows"]
                if item["trial_id"] != first["trial_id"]
            )
            == 47
        )
        assert all(report["kernel"][policy]["stopped_outputs"] == 1 for policy in ("U", "M", "G"))
        resource = report["resources"][first["arm"]]
        assert resource["attempts"] == 1
        assert resource["observed_lower_bounds"]["input_tokens"] == 1
        assert (
            resource["exact_totals"] is not None if include_native_end else resource["exact_totals"] is None
        )
        # Two independent tamper checks: the sealed store catches changed bytes,
        # and the semantic validator rejects a missing retained case without
        # relying on the store-manifest failure.
        case = sorted((runtime / "verifier").glob("case-*.json"))[0]
        original = case.read_bytes()
        case.write_bytes(original + b" ")
        try:
            store.verify_trial(first["trial_id"])
        except ValueError:
            pass
        else:
            raise AssertionError("changed retained case passed store verification")
        case.write_bytes(original)
        moved = directory / "removed-case.json"
        case.rename(moved)
        try:
            campaign.validate_retained_grade(store, first["trial_id"], grade)
        except ValueError:
            pass
        else:
            raise AssertionError("missing retained case passed semantic replay")
        finally:
            moved.rename(case)
        store.verify_trial(first["trial_id"])
        write_once(
            directory / "control-receipt.json",
            {
                "scope": "offline synthetic native events; real Harbor/Docker/capture/grading/store/replay",
                "source_scope": "working controller with verified frozen inputs; not frozen-entry dispatch",
                "model_calls": 0,
                "include_native_end": include_native_end,
                "registration_sha256": freeze["registration_sha256"],
                "report_sha256": digest(report),
                "case_records": 9,
                "finalized_rows": 1,
                "scheduled_rows": 48,
                "grade_valid_completion": grade["outcome"]["valid_completion"],
                "candidate_execution_during_replay": False,
                "tamper_controls": 2,
            },
        )
    finally:
        # Stop/remove only exact owned identities captured by this fixture.
        seen = set()
        for path in list(runtime.glob("**/identity.json")) + list(runtime.glob("**/end.json")):
            value = json.loads(path.read_text())
            identity = value if "container_id" in value else value.get("identity")
            if not isinstance(identity, dict) or identity.get("container_id") in seen:
                continue
            seen.add(identity["container_id"])
            controller = DockerController()
            observed = controller.inspect_owned(identity)
            if not observed["stopped"]:
                controller.terminate(identity)
            subprocess.run(
                ["docker", "rm", identity["container_id"]], capture_output=True, timeout=20, check=True
            )


@pytest.mark.skipif(
    not all(
        os.environ.get(name)
        for name in (
            "EVALOPT_V2_AGENT_CONTROL_IMAGE",
            "EVALOPT_V2_DOCKER_CONTROL_IMAGE",
            "EVALOPT_V2_UPSTREAM_CONTROL",
        )
    ),
    reason="explicit local images and pinned upstream checkout required",
)
@pytest.mark.parametrize("include_native_end", [True, False])
def test_positive_campaign_store_semantic_and_report_replay(tmp_path, include_native_end):
    """Use locked Harbor runtime without installing pytest into that environment."""
    benchmark = Path(__file__).resolve().parents[1]
    repository = benchmark.parents[2]
    prefix = "import os,sys,subprocess\nfrom pathlib import Path\n"
    prefix += f"sys.path.insert(0,{str(repository / 'src')!r});sys.path.insert(0,{str(benchmark)!r})\n"
    prefix += f"__file__={str(Path(__file__).resolve())!r}\n"
    launcher = tmp_path / "trusted-campaign-control.py"
    launcher.write_text(
        prefix
        + inspect.getsource(_positive_replay_control)
        + f"\n_positive_replay_control(Path({str(tmp_path.resolve())!r}),{include_native_end!r})\n"
    )
    result = subprocess.run(
        [str(repository / ".venv-harbor/bin/python"), "-I", "-B", str(launcher)],
        capture_output=True,
        timeout=240,
        env=os.environ.copy(),
    )
    (tmp_path / "launcher.stdout").write_bytes(result.stdout)
    (tmp_path / "launcher.stderr").write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode()
