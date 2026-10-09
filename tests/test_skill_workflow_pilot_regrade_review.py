"""Independent stopped-output regrading controls; no models or live pilot inputs."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import test_skill_workflow_pilot_regrade as support

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import heldout_campaign as heldout  # noqa: E402
import pilot_regrade as subject  # noqa: E402

regrade_source = support.regrade_source


def file_node(data=b"raise RuntimeError('candidate must never be imported on host')\n", mode=0o444):
    return {"type": "file", "mode": mode, "data": base64.b64encode(data).decode()}


def snapshot(nodes):
    return {"schema_version": "evalopt.stopped-nodes.v1", "nodes": nodes}


@pytest.mark.parametrize("name", ["../escape", "/outside", "a/../outside", "./alias", "a//b", "a\\b"])
def test_review_snapshot_alias_or_traversal_never_creates_files(tmp_path, name):
    target = tmp_path / "snapshot"
    with pytest.raises(ValueError):
        subject._decode(snapshot({name: file_node()}), target)
    assert not target.exists()


@pytest.mark.parametrize("ancestor", [None, file_node(), {"type": "symlink", "mode": 0o777, "target": "/"}])
def test_review_every_snapshot_ancestor_must_be_an_explicit_directory(tmp_path, ancestor):
    nodes = {"a/b": file_node()}
    if ancestor is not None:
        nodes["a"] = ancestor
    with pytest.raises(ValueError):
        subject._decode(snapshot(nodes), tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()


@pytest.mark.parametrize(
    "node",
    [
        {"type": "symlink", "mode": 0o777, "target": "/private"},
        {"type": "special", "mode": 0o600, "device": 0, "file_type": stat.S_IFIFO},
        {"type": "special", "mode": 0o666, "device": 0, "file_type": stat.S_IFCHR},
    ],
)
def test_review_unsafe_nodes_are_classified_without_reconstruction(tmp_path, node):
    data = snapshot({"unsafe": node})
    assert subject._snapshot(data) is True
    with pytest.raises(ValueError, match="must not be materialized"):
        subject._decode(data, tmp_path / "snapshot")
    assert not (tmp_path / "snapshot").exists()


@pytest.mark.parametrize("mode", [True, -1, 0o10000, "0444"])
def test_review_snapshot_modes_require_exact_bounded_integers(tmp_path, mode):
    with pytest.raises(ValueError, match="mode"):
        subject._decode(snapshot({"candidate.py": file_node(mode=mode)}), tmp_path / "snapshot")


def test_review_safe_decode_preserves_bytes_and_modes_without_candidate_import(tmp_path):
    marker = tmp_path / "host-imported"
    payload = f"from pathlib import Path\nPath({str(marker)!r}).write_text('bad')\n".encode()
    target = tmp_path / "snapshot"
    subject._decode(
        snapshot(
            {
                "module": {"type": "directory", "mode": 0o555},
                "module/candidate.py": file_node(payload, 0o440),
                "response.json": file_node(b'{"fixture":true}\n', 0o644),
            }
        ),
        target,
    )
    assert not marker.exists()
    assert (target / "module/candidate.py").read_bytes() == payload
    assert stat.S_IMODE((target / "module").stat().st_mode) == 0o555
    assert stat.S_IMODE((target / "module/candidate.py").stat().st_mode) == 0o440
    assert stat.S_IMODE((target / "response.json").stat().st_mode) == 0o644


def test_review_baseline_bridge_rejects_changed_frozen_source_before_import(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "regrade_bridge_review", BENCH / "runtime/regrade_bridge.py"
    )
    assert spec and spec.loader
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    source = tmp_path / "untrusted-source"
    source.mkdir()
    (source / "runtime.py").write_text("raise AssertionError('never import altered source')\n")
    import io
    import json

    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"frozen_source": str(source), "frozen_source_sha256": "f" * 64})),
    )
    with pytest.raises(ValueError, match="source changed"):
        bridge.main()


@pytest.mark.parametrize("status", ["completed", "agent_failure", "timeout", "budget_exhausted"])
def test_review_effective_grade_preserves_exact_original_timeout_only_override(status):
    grade = {
        "functional_success": True,
        "boundaries_preserved": True,
        "claims_supported": True,
        "unsupported_success": False,
        "incorrect_refusal": False,
        "valid_completion": True,
        "response_valid": True,
        "boundary_violations": [],
    }
    before = copy.deepcopy(grade)
    result = subject._effective(grade, status)
    assert result["valid_completion"] is (status != "timeout")
    assert result["functional_success"] is True
    assert result["boundary_violation"] is False
    assert grade == before


def test_review_original_finalization_record_is_part_of_preserved_inputs():
    assert "finalize.json" in subject.INPUT_FILES


@pytest.mark.parametrize("encoding", ["utf-8-sig", "utf-16"])
def test_review_response_replay_matches_actual_verifier_text_decoding(tmp_path, encoding):
    from runtime.verify import collect_grade, strict_json

    task = subject.suite.load_task("review-pagination-clean")
    positive = json.loads((subject.suite.task_path(task) / "controls.json").read_text())["positive_response"]
    raw = json.dumps(positive).encode(encoding)
    response_path = tmp_path / "response.json"
    response_path.write_bytes(raw)
    # This is the actual verifier's read_text/strict_json boundary. Passing bytes
    # directly instead lets json.loads auto-detect BOM/UTF-16 and changes grades.
    try:
        response = strict_json(response_path.read_text())
    except (OSError, ValueError):
        response = None
    assert response is None
    context = {
        "task_id": task["id"],
        "split": "development",
        "initial_manifest": {},
        "stopped_manifest": {},
        "observations": [{"source": "controller", "command": task["visible_check"], "outcome": "passed"}],
        "unsafe_snapshot": False,
    }
    root = tmp_path / "regrade"
    subject.write_once(root / "inputs/fixture/context.json", context)
    subject.write_once(
        root / "inputs/fixture/agent/snapshot.json", snapshot({"response.json": file_node(raw)})
    )
    grade = collect_grade(task, context, {}, response, lambda request: None)
    assert grade["response_valid"] is False and grade["valid_completion"] is False
    assert subject._replay(root, {"trial_id": "fixture", "task_id": task["id"]}, grade) == {
        key: value for key, value in grade.items() if key != "reproduction_inputs"
    }


@pytest.mark.parametrize("unsafe", [False, True])
def test_review_real_execution_command_is_offline_and_never_imports_candidate_on_host(
    tmp_path, monkeypatch, unsafe
):
    root = tmp_path / "regrade"
    (root / "grader").mkdir(parents=True)
    (root / "grader/verify.py").write_text("raise AssertionError('must run only in Docker')\n")
    trial = "pilot--review-pagination-clean--r1--A"
    original = root / "inputs" / trial
    nodes = {"forbidden": {"type": "symlink", "mode": 0o777, "target": "/private"}} if unsafe else {}
    subject.write_once(original / "context.json", {"unsafe_snapshot": unsafe, "stopped_manifest": {}})
    subject.write_once(original / "agent/snapshot.json", snapshot(nodes))
    calls = []

    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        if argv[:2] == ["docker", "run"]:
            observed = root / "private-execution" / trial
            assert list((observed / "tests/snapshot").iterdir()) == []
            subject.write_once(observed / "output/grade.json", {"fixture": "controlled Docker reply"})
        return SimpleNamespace(returncode=0, stdout=b"controlled stdout", stderr=b"")

    monkeypatch.setattr(subject.subprocess, "run", run)
    image = "sha256:" + "a" * 64
    grade, receipt = subject._execute_one(root, {"runtime": {"verifier_image": image}}, {"trial_id": trial})
    argv, kwargs = calls[0]
    assert argv[:2] == ["docker", "run"] and argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--pull") + 1] == "never"
    assert argv[argv.index("--cpus") + 1] == "1" and argv[argv.index("--memory") + 1] == "2g"
    assert "no-new-privileges" in argv and image in argv
    mounts = [argv[index + 1] for index, value in enumerate(argv) if value == "--mount"]
    assert len(mounts) == 2 and sum(value.endswith("dst=/tests,readonly") for value in mounts) == 1
    assert kwargs["timeout"] == 120
    assert calls[1][0][:3] == ["docker", "rm", "-f"]
    assert grade == {"fixture": "controlled Docker reply"} and receipt["agent_trials"] == 0


def test_review_unbound_private_context_cannot_change_trusted_original_baseline(regrade_source):
    source = regrade_source
    trial = source.schedule[0]["trial_id"]
    path = source.pilot / "private-harbor" / trial / "attempt-1/task/tests/grading.json"
    value = subject._json(path)
    value["initial_manifest"]["forged-baseline.py"] = "file:420:forged"
    path.write_bytes(subject.canonical_bytes(value))
    with pytest.raises(ValueError, match="reconstructed frozen inputs"):
        support.prepared(source)
    assert not list((source.pilot / "qa-regrades").glob("*/registration.json"))


@pytest.mark.parametrize("name", ["grade.json", "policies.json", "finish.json", "finalize.json"])
def test_review_any_original_attempt_change_stops_before_reexecution(regrade_source, name):
    source = regrade_source
    root, identity = support.prepared(source)
    path = source.store.root / "trials" / source.schedule[0]["trial_id"] / "attempt-1" / name
    path.write_bytes(path.read_bytes() + b"\n")
    calls = []

    def forbidden(*args):
        calls.append(args)
        raise AssertionError("changed original must be rejected before Docker execution")

    with pytest.raises(ValueError, match="original pilot attempt changed"):
        subject.execute(root, registration_sha256=identity, runner=forbidden)
    assert calls == [] and not (root / "evidence.json").exists()


@pytest.mark.parametrize("mutation", ["missing", "request", "extra"])
def test_review_hidden_reply_coverage_is_required_before_complete_regrade_receipt(regrade_source, mutation):
    source = regrade_source
    root, identity = support.prepared(source)
    poisoned = False

    def altered(root, registration, row):
        nonlocal poisoned
        grade, execution = support.fake_execute(root, registration, row)
        records = grade["reproduction_inputs"]["hidden_case_records"]
        if records and not poisoned:
            poisoned = True
            if mutation == "missing":
                records.pop()
            elif mutation == "request":
                records[0]["request"]["args"].append("unregistered input")
            else:
                records.append(copy.deepcopy(records[0]))
        return grade, execution

    with pytest.raises((ValueError, RuntimeError), match="hidden"):
        subject.execute(root, registration_sha256=identity, runner=altered)
    assert poisoned and not (root / "evidence.json").exists()


@pytest.mark.parametrize("mutation", ["missing-attempt", "arm", "ordering"])
def test_review_count36_cannot_substitute_for_exact_seeded_task_arm_roster(regrade_source, mutation):
    root, _ = support.prepared(regrade_source)
    registration = subject._json(root / "registration.json")
    if mutation == "missing-attempt":
        registration["attempts"].pop()
    elif mutation == "arm":
        registration["schedule"][0]["arm"] = "unregistered"
        registration["attempts"][0]["arm"] = "unregistered"
        registration["schedule_sha256"] = subject.digest(registration["schedule"])
    else:
        registration["schedule"].reverse()
        registration["attempts"].reverse()
        registration["schedule_sha256"] = subject.digest(registration["schedule"])
    (root / "registration.json").write_bytes(subject.canonical_bytes(registration))
    with pytest.raises(ValueError):
        subject.verify_registration(root / "registration.json", subject.digest(registration))


def test_review_all36_receipt_preserves_original_bytes_and_separates_scoring_deltas(regrade_source):
    source = regrade_source
    before = {
        path.relative_to(source.store.root).as_posix(): path.read_bytes()
        for path in source.store.root.rglob("*")
        if path.is_file()
    }
    root, identity = support.prepared(source)
    receipt = subject.execute(root, registration_sha256=identity, runner=support.fake_execute)
    assert receipt["scheduled_trials"] == receipt["regraded_attempts"] == 36
    assert receipt["schedule_sha256"] == subject.digest(source.schedule)
    assert receipt["changed_trial_count"] == 3 and receipt["agent_trials"] == 0
    assert receipt["original_policy_decisions_changed"] is False
    assert "not independent execution or authentication" in receipt["scope"]
    assert all((source.store.root / name).read_bytes() == raw for name, raw in before.items())
    for row in source.schedule:
        result = subject._json(root / "results" / (row["trial_id"] + ".json"))
        old = subject._json(root / "inputs" / row["trial_id"] / "grade.json")["grade"]
        assert result["original_effective_grade"] == old
        assert result["original_policies_sha256"] == subject.bytes_digest(
            (root / "inputs" / row["trial_id"] / "policies.json").read_bytes()
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("registration_sha256", "f" * 64),
        ("evidence_sha256", "f" * 64),
        ("pilot_registration_sha256", "f" * 64),
        ("pilot_export_id", "f" * 64),
        ("accounting_amendment_sha256", "f" * 64),
        ("schedule_sha256", "f" * 64),
        ("grading", {"pilot": {}, "current": {}}),
        ("scheduled_trials", 35),
        ("regraded_attempts", 35),
        ("original_policy_decisions_changed", True),
        ("agent_trials", False),
    ],
)
def test_review_heldout_regrade_receipt_binds_all_independent_scope_identities(field, value):
    previous = {"suite": "a" * 64, "verifier": "b" * 64}
    current = {"suite": "c" * 64, "verifier": "d" * 64}
    review = {
        "schema_version": "evalopt.pilot-review.v2",
        "pilot_registration_sha256": subject.digest("pilot registration"),
        "pilot_export_id": subject.digest("pilot export"),
        "accounting": {"amendment_sha256": subject.digest("accounting amendment")},
        "grading_compatibility": {
            "pilot": previous,
            "current": current,
            "verdict": "regraded_stopped_outputs",
            "reason": "Explicit parser semantic change reviewed through isolated regrade.",
            "regrade_registration_sha256": subject.digest("regrade registration"),
            "regrade_evidence_sha256": subject.digest("regrade evidence"),
        },
    }
    schedule_sha = subject.digest("schedule")
    receipt = {
        "registration_sha256": review["grading_compatibility"]["regrade_registration_sha256"],
        "evidence_sha256": review["grading_compatibility"]["regrade_evidence_sha256"],
        "pilot_registration_sha256": review["pilot_registration_sha256"],
        "pilot_export_id": review["pilot_export_id"],
        "accounting_amendment_sha256": review["accounting"]["amendment_sha256"],
        "schedule_sha256": schedule_sha,
        "grading": {"pilot": previous, "current": current},
        "scheduled_trials": 36,
        "regraded_attempts": 36,
        "original_policy_decisions_changed": False,
        "agent_trials": 0,
    }
    assert heldout._match_regrade_receipt(receipt, review, previous, current, schedule_sha) == receipt
    receipt[field] = value
    with pytest.raises(ValueError, match="reviewed identities"):
        heldout._match_regrade_receipt(receipt, review, previous, current, schedule_sha)


@pytest.mark.parametrize("missing", ["regrade_registration_sha256", "regrade_evidence_sha256"])
def test_review_regrade_declaration_requires_both_explicit_content_pins(missing):
    compatibility = {
        "pilot": {"suite": "a" * 64, "verifier": "b" * 64},
        "current": {"suite": "c" * 64, "verifier": "d" * 64},
        "verdict": "regraded_stopped_outputs",
        "reason": "Known semantic change requires inspected stopped outputs.",
        "regrade_registration_sha256": "e" * 64,
        "regrade_evidence_sha256": "f" * 64,
    }
    compatibility.pop(missing)
    with pytest.raises(ValueError):
        heldout._grading_review(compatibility, compatibility["pilot"], compatibility["current"])
