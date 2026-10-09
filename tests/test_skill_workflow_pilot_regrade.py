"""Offline regrade controls with synthetic36 outcomes and no candidate execution."""

from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import pilot_regrade as regrade  # noqa: E402
from lib.common import bytes_digest, canonical_bytes, digest, read_json, write_once  # noqa: E402
from lib.manifest import build_schedule  # noqa: E402
from lib.store import CampaignStore  # noqa: E402
from runtime import harbor_campaign  # noqa: E402
from runtime.snapshot import encode_snapshot  # noqa: E402
from runtime.verify import collect_grade, strict_json  # noqa: E402
from tasks import suite  # noqa: E402


def oracle_grade(root, row):
    context = read_json(root / "inputs" / row["trial_id"] / "context.json")
    task = suite.load_task(row["task_id"])
    snapshot = read_json(root / "inputs" / row["trial_id"] / "agent/snapshot.json")
    node = snapshot["nodes"].get("response.json")
    try:
        response = None if context["unsafe_snapshot"] else strict_json(base64.b64decode(node["data"]))
    except (ValueError, KeyError, TypeError):
        response = None
    cases = iter(read_json(suite.task_path(task) / "hidden_cases.json"))

    def invoke(request):
        case = next(cases)
        assert request == {key: case[key] for key in ("module", "function", "args")}
        key = "error" if "raises" in case else "result"
        return {key: case.get("raises") if key == "error" else case["result"], "args": request["args"]}

    return collect_grade(task, context, context["stopped_manifest"], response, invoke)


def fake_execute(root, registration, row):
    return oracle_grade(root, row), {
        "mode": "isolated_docker_chroot",
        "exit_code": 0,
        "verifier_image": registration["runtime"]["verifier_image"],
        "stdout_sha256": bytes_digest(b""),
        "stderr_sha256": bytes_digest(b""),
        "agent_trials": 0,
    }


@pytest.fixture
def regrade_source(tmp_path, monkeypatch):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    frozen = tmp_path / "frozen-benchmark"
    frozen.mkdir()
    tasks = []
    for task_id in suite.task_ids():
        task = suite.load_task(task_id)
        tasks.append(
            {
                "task_id": task_id,
                "stage": "pilot",
                "category": task["category"].replace("-", "_"),
                "cluster_id": task["source_family"],
                "agent_seconds": 600,
                "task_sha256": regrade.source_identity(suite.task_path(task)),
                "grader_sha256": digest("original-suite"),
            }
        )
    schedule = build_schedule(tasks, "pilot")
    store = CampaignStore(pilot / "evidence", schedule)
    runtime = {"agent_image": "sha256:" + digest("agent"), "verifier_image": "sha256:" + digest("verifier")}
    monkeypatch.setattr(regrade, "image_identity", lambda value: value)
    monkeypatch.setattr(harbor_campaign, "local_image_reference", lambda value: value)
    baseline = {}
    for index, row in enumerate(schedule):
        task = suite.load_task(row["task_id"])
        task_dir = pilot / "private-harbor" / row["trial_id"] / "attempt-1/task"
        initial = harbor_campaign.materialize(task, task_dir, arm=row["arm"], **runtime)
        baseline[(row["task_id"], row["arm"])] = initial
        workspace = task_dir / "environment/workspace"
        response = read_json(suite.task_path(task) / "controls.json")["positive_response"]
        raw = json.dumps(response)
        if row["task_id"] == "duration-parser":
            raw = '{"summary":NaN,' + raw[1:]
        (workspace / "response.json").write_text(raw)
        stopped = suite.file_manifest(workspace)
        observation = {
            "command": task["visible_check"],
            "outcome": task["expected"]["visible_outcome"],
            "source": "controller",
        }
        context = {
            "task_id": row["task_id"],
            "initial_manifest": initial,
            "stopped_manifest": stopped,
            "observations": [observation],
            "unsafe_snapshot": False,
        }
        (task_dir / "tests/grading.json").write_bytes(canonical_bytes(context))
        attempt = store.start_attempt(row["trial_id"])
        stopped_sha = store.capture_stopped(
            row["trial_id"],
            attempt,
            {
                "snapshot.json": encode_snapshot(workspace),
                "node-manifest.json": canonical_bytes(stopped),
                "workflow-exposure.json": canonical_bytes(
                    {"arm": row["arm"], "source_files": {}, "verified_before_agent": True}
                ),
            },
        )
        log = canonical_bytes(observation)
        visible = {
            "schema_version": "evalopt.workflow-visible.v1",
            "trial_id": row["trial_id"],
            "stopped_sha256": stopped_sha,
            "observed_at": "2026-10-09T00:00:00Z",
            "required_gates": ["visible_check"],
            "gates": [
                {
                    "name": "visible_check",
                    "status": {"passed": "PASS", "failed": "FAIL", "unavailable": "NOT_CONFIGURED"}[
                        observation["outcome"]
                    ],
                    "producer": "controller",
                    "evidence_sha256": bytes_digest(log),
                }
            ],
            "tests_weakened": False,
            "boundary_violations": [],
            "unsupported_claims": [],
        }
        store.record_visible(row["trial_id"], attempt, visible, {"visible-check.json": log})
        store.decide(row["trial_id"], attempt)
        grade = suite.grade_snapshot(
            task, initial, stopped, json.loads(raw), [observation], hidden_test_passed=True
        )
        status = "timeout" if index == 0 else "completed"
        if status == "timeout":
            grade["valid_completion"] = False
        grade["boundary_violation"] = not grade["boundaries_preserved"]
        store.record_grade(row["trial_id"], attempt, grade)
        store.finish_attempt(
            row["trial_id"], attempt, status, usage={"child_usage_complete": True, "runtime_valid": True}
        )
    write_once(pilot / "runtime.json", runtime)
    write_once(pilot / "manifest.json", {"tasks": tasks})
    controls = tmp_path / "controls"
    write_once(
        controls / "results.json",
        {"tasks_sha256": digest("original-suite"), "verify_sha256": digest("original-verifier")},
    )
    write_once(pilot / "readiness-sources.json", {"controls": str(controls)})
    rows, _, attempts = regrade.campaign._report_rows(store, schedule)
    payloads = {"outcomes.json": rows, "attempts.json": attempts}
    export_id = digest(payloads)
    for name, value in payloads.items():
        write_once(pilot / "exports" / export_id / name, value)
    write_once(
        pilot / "exports" / export_id / "checksums.json",
        {
            "files": {
                name: bytes_digest((pilot / "exports" / export_id / name).read_bytes()) for name in payloads
            }
        },
    )
    info = {
        "states": store.statuses(),
        "schedule": schedule,
        "registration_sha256": digest("pilot"),
        "schedule_sha256": digest(schedule),
        "source_lock": {"campaign_sha256": digest("frozen")},
    }
    monkeypatch.setattr(
        regrade.amended_pilot,
        "verify",
        lambda *_: {"info": copy.deepcopy(info), "local": {"frozen_source": str(frozen)}},
    )
    return SimpleNamespace(
        pilot=pilot,
        schedule=schedule,
        store=store,
        runtime=runtime,
        info=info,
        export_id=export_id,
        amendment=digest("amendment"),
        baseline=baseline,
        tmp=tmp_path,
    )


def prepared(source):
    result = regrade.prepare(
        source.pilot,
        source.tmp / "staging",
        amendment_sha256=source.amendment,
        pilot_export_id=source.export_id,
        verifier_image=source.runtime["verifier_image"],
        bridge=lambda request: source.baseline[(request["task_id"], request["arm"])],
    )
    return Path(result["registration_path"]).parent, result["registration_sha256"]


def test_full36_regrade_preserves_originals_and_reports_scoring_change(regrade_source):
    source = regrade_source
    before = {
        str(path.relative_to(source.store.root)): bytes_digest(path.read_bytes())
        for path in source.store.root.rglob("*")
        if path.is_file()
    }
    root, identity = prepared(source)
    receipt = regrade.execute(root, registration_sha256=identity, runner=fake_execute)
    assert receipt["regraded_attempts"] == 36 and receipt["agent_trials"] == 0
    assert receipt["changed_trial_count"] == 3
    assert receipt["metric_changes"]["functional_success"] == 3
    assert receipt["original_policy_decisions_changed"] is False
    after = {
        str(path.relative_to(source.store.root)): bytes_digest(path.read_bytes())
        for path in source.store.root.rglob("*")
        if path.is_file()
    }
    assert before == after
    for row in source.schedule:
        record = read_json(root / "results" / (row["trial_id"] + ".json"))
        if record["original_status"] == "timeout":
            assert record["current_effective_grade"]["valid_completion"] is False
    public = source.tmp / "public"
    assert (
        regrade.export_evidence(
            root / "registration.json",
            public,
            registration_sha256=identity,
            evidence_sha256=receipt["evidence_sha256"],
        )
        == receipt
    )
    assert not (public / "local-sources.json").exists()
    assert not (public / "private-execution").exists()
    assert (
        regrade.verify_evidence(
            public / "registration.json",
            registration_sha256=identity,
            evidence_sha256=receipt["evidence_sha256"],
        )
        == receipt
    )


def test_prepare_requires_every_terminal_outcome_before_any_output(regrade_source):
    regrade_source.info["states"][0]["status"] = "pending"
    with pytest.raises(ValueError, match="all36"):
        prepared(regrade_source)
    assert not (regrade_source.tmp / "staging").exists()


def test_original_initial_context_cannot_substitute_for_reconstructed_baseline(regrade_source):
    row = regrade_source.schedule[0]
    regrade_source.baseline[(row["task_id"], row["arm"])] = {"invented": "file:420:invalid"}
    with pytest.raises(ValueError, match="reconstructed"):
        prepared(regrade_source)


@pytest.mark.parametrize("name", ["../outside", "/absolute", "a//b", "a/./b", "a/../b", "a\\b"])
def test_decoder_rejects_aliases_and_traversal_before_creating_files(tmp_path, name):
    snapshot = {
        "schema_version": "evalopt.stopped-nodes.v1",
        "nodes": {name: {"type": "file", "mode": 0o644, "data": ""}},
    }
    with pytest.raises(ValueError):
        regrade._decode(snapshot, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()


@pytest.mark.parametrize(
    "kind,extra", [("symlink", {"target": "/outside"}), ("special", {"device": 0, "file_type": 0o010000})]
)
def test_unsafe_nodes_are_never_constructed_on_host(tmp_path, kind, extra):
    snapshot = {
        "schema_version": "evalopt.stopped-nodes.v1",
        "nodes": {"node": {"type": kind, "mode": 0o644, **extra}},
    }
    assert regrade._snapshot(snapshot)
    with pytest.raises(ValueError):
        regrade._decode(snapshot, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()


def test_decoder_preserves_file_and_directory_modes(tmp_path):
    snapshot = {
        "schema_version": "evalopt.stopped-nodes.v1",
        "nodes": {
            "dir": {"type": "directory", "mode": 0o750},
            "dir/file": {"type": "file", "mode": 0o640, "data": base64.b64encode(b"data").decode()},
        },
    }
    regrade._decode(snapshot, tmp_path / "snapshot")
    assert (tmp_path / "snapshot/dir").stat().st_mode & 0o777 == 0o750
    assert (tmp_path / "snapshot/dir/file").stat().st_mode & 0o777 == 0o640


def test_pure_replay_rejects_missing_hidden_input_and_original_mutation(regrade_source):
    root, identity = prepared(regrade_source)
    receipt = regrade.execute(root, registration_sha256=identity, runner=fake_execute)
    row = next(row for row in regrade_source.schedule if row["task_id"] == "duration-parser")
    target = root / "results" / (row["trial_id"] + ".json")
    record = read_json(target)
    record["current_verifier_grade"]["reproduction_inputs"]["hidden_case_records"] = []
    target.write_bytes(canonical_bytes(record))
    with pytest.raises(RuntimeError, match="reply missing"):
        regrade.verify_evidence(
            root / "registration.json",
            registration_sha256=identity,
            evidence_sha256=receipt["evidence_sha256"],
        )


def test_executor_command_is_pinned_offline_and_receives_only_trusted_tests(regrade_source, monkeypatch):
    root, identity = prepared(regrade_source)
    registration = regrade.verify_registration(root / "registration.json", identity)
    row = registration["attempts"][0]
    calls = []

    def run(argv, **options):
        calls.append(argv)
        if argv[:2] == ["docker", "run"]:
            assert argv[argv.index("--pull") + 1] == "never"
            assert argv[argv.index("--network") + 1] == "none"
            assert argv[argv.index("--cpus") + 1] == "1"
            assert argv[argv.index("--memory") + 1] == "2g"
            assert options["timeout"] == 120
            assert registration["runtime"]["verifier_image"] in argv
            assert "--privileged" not in argv and "-e" not in argv
            mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "--mount"]
            assert len(mounts) == 2 and mounts[0].endswith("dst=/tests,readonly")
            assert mounts[1].endswith("dst=/logs/verifier")
            write_once(
                root / "private-execution" / row["trial_id"] / "output/grade.json", oracle_grade(root, row)
            )
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(regrade.subprocess, "run", run)
    grade, execution = regrade._execute_one(root, registration, row)
    assert grade["reproduction_inputs"]["task_id"] == row["task_id"]
    assert execution["mode"] == "isolated_docker_chroot" and execution["agent_trials"] == 0
    assert calls[-1][:3] == ["docker", "rm", "-f"]


def executor_control(tmp_path, kind):
    """Standalone synthetic duration-parser snapshot for the actual cached verifier."""
    import shutil

    root = tmp_path / "control"
    root.mkdir()
    task = suite.load_task("duration-parser")
    workspace = tmp_path / "workspace"
    suite.materialize_agent(task, workspace)
    initial = suite.file_manifest(workspace)
    shutil.copytree(suite.task_path(task) / "oracle", workspace, dirs_exist_ok=True)
    response = read_json(suite.task_path(task) / "controls.json")["positive_response"]
    raw = json.dumps(response)
    if kind == "incorrect_candidate":
        (workspace / "duration.py").write_text("def parse(text):\n    return -1\n")
    if kind == "duplicate_nonfinite_response":
        raw = '{"summary":NaN,' + raw[1:]
    encoding = {"utf8_bom_response": "utf-8-sig", "utf16_response": "utf-16"}.get(kind, "utf-8")
    (workspace / "response.json").write_bytes(raw.encode(encoding))
    context = {
        "task_id": task["id"],
        "split": "development",
        "initial_manifest": initial,
        "stopped_manifest": suite.file_manifest(workspace),
        "observations": [{"command": task["visible_check"], "outcome": "passed", "source": "controller"}],
        "unsafe_snapshot": False,
    }
    trial_id = "pilot--duration-parser--r1--A"
    target = root / "inputs" / trial_id
    write_once(target / "context.json", context)
    (target / "agent").mkdir()
    (target / "agent/snapshot.json").write_bytes(encode_snapshot(workspace))
    for name, path in regrade._grader_files().items():
        regrade._copy(path, root / "grader" / name)
    return root, {"trial_id": trial_id, "task_id": task["id"]}


@pytest.mark.skipif(
    not __import__("os").environ.get("EVALOPT_REGRADE_DOCKER_CONTROL_IMAGE"),
    reason="explicit cached verifier digest required; this control never runs a model",
)
@pytest.mark.parametrize(
    "kind,expected",
    [
        ("oracle", True),
        ("incorrect_candidate", False),
        ("duplicate_nonfinite_response", False),
        ("utf8_bom_response", False),
        ("utf16_response", False),
    ],
)
def test_real_isolated_regrade_executor_with_cached_image(tmp_path, kind, expected):
    import os

    image = os.environ["EVALOPT_REGRADE_DOCKER_CONTROL_IMAGE"]
    assert image.startswith("sha256:") and len(image) == 71
    root, row = executor_control(tmp_path, kind)
    grade, execution = regrade._execute_one(root, {"runtime": {"verifier_image": image}}, row)
    assert grade["valid_completion"] is expected
    assert grade["functional_success"] is expected
    assert execution["exit_code"] == 0 and execution["agent_trials"] == 0
    assert grade["reproduction_inputs"]["hidden_case_records"]
    assert regrade._replay(root, row, grade) == {
        key: value for key, value in grade.items() if key != "reproduction_inputs"
    }


def test_standalone_export_scans_all_payloads_before_writing(regrade_source, monkeypatch):
    root, identity = prepared(regrade_source)
    receipt = regrade.execute(root, registration_sha256=identity, runner=fake_execute)
    original = regrade.public_payloads

    def injected(path):
        values = original(path)
        values["context-with-secret.json"] = canonical_bytes({"access_token": "SYNTHETIC_PRIVATE_CREDENTIAL"})
        return values

    monkeypatch.setattr(regrade, "public_payloads", injected)
    destination = regrade_source.tmp / "rejected-public"
    with pytest.raises(ValueError):
        regrade.export_evidence(
            root / "registration.json",
            destination,
            registration_sha256=identity,
            evidence_sha256=receipt["evidence_sha256"],
        )
    assert not destination.exists()
