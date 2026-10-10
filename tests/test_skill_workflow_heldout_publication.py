"""Synthetic held-out publication controls; no model outcomes or candidate execution."""

from __future__ import annotations

import copy
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import test_skill_workflow_heldout as support

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
import heldout_publish as publication  # noqa: E402
from runtime import verify as verifier  # noqa: E402
from runtime.snapshot import encode_snapshot  # noqa: E402
from tasks import suite  # noqa: E402


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(publication.canonical_bytes(value) + b"\n")


def hashes(root):
    return {
        p.relative_to(root).as_posix(): publication.bytes_digest(p.read_bytes())
        for p in root.rglob("*")
        if p.is_file()
    }


@pytest.fixture
def sealed(tmp_path):
    root, _ = support.sealed.__wrapped__(tmp_path)
    manifest = publication.read_json(root / "candidate-manifest.json")
    task = manifest["tasks"][0]
    oracle = root / task["id"] / "oracle/app.py"
    oracle.parent.mkdir()
    oracle.write_text("def run(): return 'HIDDEN_EXPECTED_SENTINEL'\n")
    task["files"]["oracle/app.py"] = publication.bytes_digest(oracle.read_bytes())
    write_json(root / "candidate-manifest.json", manifest)
    return root, publication.bytes_digest((root / "candidate-manifest.json").read_bytes())


@pytest.fixture
def reviewed_pilot(tmp_path):
    return support.reviewed_pilot.__wrapped__(tmp_path)


@pytest.fixture
def frozen(sealed, reviewed_pilot, tmp_path, monkeypatch):
    return support.frozen.__wrapped__(sealed, reviewed_pilot, tmp_path, monkeypatch)


@pytest.fixture
def recorded(frozen, tmp_path, monkeypatch):
    root, _, registration = frozen
    frozen_source = tmp_path / "registered-source"
    shutil.copytree(BENCH, frozen_source, ignore=shutil.ignore_patterns("__pycache__"))
    schedule = publication.read_json(root / "evidence/schedule.json")["schedule"]
    store = publication.authored._read_only_store(root / "evidence", schedule)
    row = next(item for item in schedule if item["arm"] == "A")
    task_root = root / "sealed-tasks"
    task = suite.load_task(row["task_id"], task_root=task_root, split="heldout")

    def create(*, grade_change=None, status="completed", secret=False, raw_response=None):
        workspace = tmp_path / "stopped-workspace"
        suite.materialize_agent(task, workspace, task_root=task_root)
        initial = suite.file_manifest(workspace)
        # Deliberately unexecutable candidate: publication must replay retained
        # replies, never import these bytes as a new independent verification.
        (workspace / "app.py").write_text("raise RuntimeError('candidate execution forbidden in replay')\n")
        response = {
            "status": "completed",
            "summary": json.dumps({"access_token": "synthetic-private-only"})
            if secret
            else "Synthetic result",
            "findings": [],
            "blockers": [],
            "checks": [{"command": task["visible_check"], "outcome": "passed"}],
        }
        if raw_response is None:
            write_json(workspace / "response.json", response)
        else:
            (workspace / "response.json").write_bytes(raw_response)
            with pytest.raises(ValueError):
                verifier.strict_json(raw_response)
            response = None
        stopped_manifest = suite.file_manifest(workspace)
        observation = {"command": task["visible_check"], "outcome": "passed", "source": "controller"}
        attempt = store.start_attempt(row["trial_id"])
        stopped = store.capture_stopped(
            row["trial_id"],
            attempt,
            {
                "snapshot.json": encode_snapshot(workspace),
                "node-manifest.json": publication.canonical_bytes(stopped_manifest),
                "workflow-exposure.json": publication.canonical_bytes(
                    {"arm": "A", "source_files": {}, "verified_before_agent": True}
                ),
            },
        )
        log = publication.canonical_bytes(observation)
        store.record_visible(
            row["trial_id"],
            attempt,
            {
                "schema_version": "evalopt.workflow-visible.v1",
                "trial_id": row["trial_id"],
                "stopped_sha256": stopped,
                "observed_at": "2026-10-08T00:00:00+00:00",
                "required_gates": ["visible_check"],
                "gates": [
                    {
                        "name": "visible_check",
                        "status": "PASS",
                        "producer": "controller",
                        "evidence_sha256": publication.bytes_digest(log),
                    }
                ],
                "tests_weakened": False,
                "boundary_violations": [],
                "unsupported_claims": ["missing_or_malformed_response"] if raw_response is not None else [],
            },
            {"visible-check.json": log},
        )
        store.decide(row["trial_id"], attempt)
        monkeypatch.setattr(
            verifier,
            "evaluate_cases",
            lambda task, invoke: suite.evaluate_cases(task, invoke, task_root=task_root),
        )
        grade = verifier.collect_grade(
            task,
            {"initial_manifest": initial, "observations": [observation], "unsafe_snapshot": False},
            stopped_manifest,
            response,
            lambda request: {"result": "HIDDEN_EXPECTED_SENTINEL", "args": request["args"]},
        )
        assert grade["valid_completion"] is (raw_response is None)
        if status == "timeout":
            grade["valid_completion"] = False
        grade["boundary_violation"] = not grade["boundaries_preserved"]
        if grade_change:
            grade_change(grade)
        store.record_grade(row["trial_id"], attempt, grade)
        store.finish_attempt(
            row["trial_id"],
            attempt,
            status,
            usage={
                "child_usage_complete": True,
                "runtime_valid": True,
                "input_tokens": 10,
                "output_tokens": 2,
                "model_calls": 1,
                "tool_calls": 1,
                "wall_seconds": 3,
                "agent_count": 1,
                "aggregation": "agent_exclusive",
            },
        )
        receipt = tmp_path / "unavailable.json"
        write_json(
            receipt,
            {
                "schema_version": "evalopt.heldout-unavailable.v1",
                "heldout_registration_sha256": registration,
                "trials": [
                    {"trial_id": item["trial_id"], "reason": "Synthetic trial deliberately not executed"}
                    for item in schedule
                    if item["trial_id"] != row["trial_id"]
                ],
            },
        )
        # This intentionally private material must stay outside the published allowlist.
        write_json(root / "private-harbor/auth.json", {"access_token": "synthetic-private-only"})
        return SimpleNamespace(
            root=root,
            source=frozen_source,
            registration=registration,
            receipt=receipt,
            trial=row,
            store=store,
            task=task,
        )

    return create


def export(record, destination, **overrides):
    arguments = {
        "registration_sha256": record.registration,
        "frozen_source": record.source,
        "unavailable_receipt": record.receipt,
    }
    arguments.update(overrides)
    return publication.export_public_bundle(record.root, destination, **arguments)


def test_release_replays_grades_and_reports_without_executing_candidates(recorded, tmp_path):
    record = recorded()
    before = hashes(record.root)
    first = export(record, tmp_path / "public-a")
    second = export(record, tmp_path / "public-b")
    assert first == second
    assert first["scheduled_trials"] == 432
    assert first["declared_unavailable_trials"] == 431
    assert first["released_tasks"] == 48
    assert first["grade_records_replayed"] == 1
    assert first["policy_analysis_reproduced"] is True
    assert first["candidate_execution_performed"] is False
    assert first["independent_replication"] is False
    assert first["network_publication_performed"] is False
    assert hashes(record.root) == before
    public = tmp_path / "public-a"
    assert not (public / "private-harbor").exists()
    assert not (public / "sealed-tasks/_qa").exists()
    assert len(list((public / "sealed-tasks").glob("*/hidden_cases.json"))) == 48
    assert len(list((public / "sealed-tasks").glob("*/controls.json"))) == 48
    assert list((public / "sealed-tasks").glob("*/oracle/app.py"))
    assert (public / "benchmark-source/runtime/verify.py").is_file()
    assert suite.file_manifest(public / "sealed-tasks") == suite.file_manifest(record.root / "sealed-tasks")
    assert hashes(public) == hashes(tmp_path / "public-b")
    analysis = publication.read_json(public / "reports/analysis.json")
    assert analysis["scoped_positive_headline_permitted"] is False
    assert "not independent candidate execution" in (public / "CLAIMS.md").read_text()


def test_missing_unavailable_receipt_rejects_incomplete_study_before_writing(recorded, tmp_path):
    record = recorded()
    with pytest.raises(ValueError, match="432 outcomes"):
        export(record, tmp_path / "public", unavailable_receipt=None)
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("change", ["missing", "duplicate", "blank", "wrong_registration", "extra"])
def test_unavailable_receipt_must_cover_exact_missing_trials(recorded, tmp_path, change):
    record = recorded()
    receipt = publication.read_json(record.receipt)
    if change == "missing":
        receipt["trials"].pop()
    elif change == "duplicate":
        receipt["trials"].append(receipt["trials"][0])
    elif change == "blank":
        receipt["trials"][0]["reason"] = " "
    elif change == "wrong_registration":
        receipt["heldout_registration_sha256"] = "0" * 64
    else:
        receipt["trials"].append(
            {"trial_id": record.trial["trial_id"], "reason": "Cannot hide a complete outcome"}
        )
    write_json(record.receipt, receipt)
    with pytest.raises(ValueError):
        export(record, tmp_path / "public")
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("change", ["missing_inputs", "wrong_actual", "wrong_request", "missing_reply"])
def test_unreplayable_grade_requires_explicit_unavailability(recorded, tmp_path, change):
    def mutate(grade):
        if change == "missing_inputs":
            grade.pop("reproduction_inputs")
            return
        records = grade["reproduction_inputs"]["hidden_case_records"]
        if change == "wrong_actual":
            records[0]["actual"]["result"] = "wrong"
        elif change == "wrong_request":
            records[0]["request"]["function"] = "different_function"
        else:
            records.clear()

    record = recorded(grade_change=mutate)
    with pytest.raises(ValueError, match="432 outcomes"):
        export(record, tmp_path / "rejected")
    receipt = publication.read_json(record.receipt)
    receipt["trials"].append(
        {"trial_id": record.trial["trial_id"], "reason": "Grade reply replay unavailable"}
    )
    write_json(record.receipt, receipt)
    result = export(record, tmp_path / "explicit-unavailable")
    assert result["declared_unavailable_trials"] == 432
    assert result["grade_records_replayed"] == 0
    rows = publication.read_json(tmp_path / "explicit-unavailable/reports/outcomes.json")
    assert all(row["valid_completion"] is None for row in rows)


def test_timeout_replays_functional_grade_and_preserves_timeout_completion_rule(recorded, tmp_path):
    record = recorded(status="timeout")
    result = export(record, tmp_path / "public")
    assert result["grade_records_replayed"] == 1
    rows = publication.read_json(tmp_path / "public/reports/outcomes.json")
    actual = next(row for row in rows if row["trial_id"] == record.trial["trial_id"])
    assert actual["status"] == "timeout"
    assert actual["functional_success"] is True
    assert actual["valid_completion"] is False


@pytest.mark.parametrize("change", ["registration", "task_bytes", "task_mode", "source"])
def test_changed_frozen_inputs_reject_publication_before_writing(recorded, tmp_path, change):
    record = recorded()
    options = {}
    if change == "registration":
        options["registration_sha256"] = "0" * 64
    elif change == "source":
        (record.source / "runtime/verify.py").write_text("raise RuntimeError('changed source')\n")
    else:
        path = record.root / "sealed-tasks" / record.task["id"] / "agent/app.py"
        if change == "task_bytes":
            path.write_text("changed")
        else:
            path.chmod(0o755)
    with pytest.raises(ValueError):
        export(record, tmp_path / "public", **options)
    assert not (tmp_path / "public").exists()


@pytest.mark.parametrize("change", ["hidden_bytes", "mode", "missing_oracle", "claim"])
def test_released_bundle_rejects_asset_and_claim_tampering(recorded, tmp_path, change):
    record = recorded()
    public = tmp_path / "public"
    export(record, public)
    if change == "hidden_bytes":
        next((public / "sealed-tasks").glob("*/hidden_cases.json")).write_text("[]")
    elif change == "mode":
        next((public / "sealed-tasks").glob("*/agent/app.py")).chmod(0o755)
    elif change == "missing_oracle":
        next((public / "sealed-tasks").glob("*/oracle/app.py")).unlink()
    else:
        (public / "CLAIMS.md").write_text("An independently replicated overall upgrade.\n")
    with pytest.raises(ValueError):
        publication.verify_public_bundle(public)


def test_secret_in_captured_response_is_rejected_without_redaction(recorded, tmp_path):
    record = recorded(secret=True)
    before = hashes(record.root)
    with pytest.raises(ValueError, match="sensitive"):
        export(record, tmp_path / "public")
    assert not (tmp_path / "public").exists()
    assert hashes(record.root) == before


def test_public_url_route_is_not_a_personal_home_path():
    publication.authored.scan_public_file("fixture.py", b'user_route = "/users/a%20b"\n')


@pytest.mark.parametrize(
    "path",
    [
        "/" + "Users" + "/private-person/project",
        "/" + "home" + "/private-person/project",
        "C:" + "\\" + "Users" + "\\PrivatePerson\\project",
        "c:" + "\\" + "users" + "\\privateperson\\project",
    ],
)
def test_personal_host_paths_still_require_remediation(path):
    with pytest.raises(ValueError, match="personal_host_path"):
        publication.authored.scan_public_file("fixture.json", publication.canonical_bytes({"path": path}))


@pytest.fixture
def synthetic_allowance(monkeypatch):
    """Entirely invented data; never embed the private held-out fixture in public tests."""
    cases = [
        {
            "module": "logging_filter",
            "function": "redact",
            "args": [{"api_key": "fixture-key", "a/b~c": {"PASSWORD": "fixture-pass"}}],
            "result": {"api_key": "[REDACTED]", "a/b~c": {"PASSWORD": "[REDACTED]"}},
            "preserve_args": True,
        },
        {
            "module": "logging_filter",
            "function": "redact",
            "args": [{"client_secret": "fixture-two"}],
            "result": {"client_secret": "[REDACTED]"},
            "preserve_args": True,
        },
    ]
    raw = publication.canonical_bytes(cases)
    monkeypatch.setattr(publication, "SYNTHETIC_SHA256", publication.bytes_digest(raw))
    trial = "heldout-synthetic-redaction-r1-A"
    grade_name = f"evidence/trials/{trial}/attempt-1/grade.json"
    inputs = {
        "schema_version": "evalopt.grade-reproduction.v1",
        "task_id": publication.SYNTHETIC_TASK,
        "split": "heldout",
        "hidden_case_records": [
            {
                "request": {key: copy.deepcopy(case[key]) for key in ("module", "function", "args")},
                "actual": {"args": copy.deepcopy(case["args"]), "result": copy.deepcopy(case["result"])},
            }
            for case in cases
        ],
    }
    payloads = {
        publication.SYNTHETIC_PATH: raw,
        grade_name: publication.canonical_bytes({"grade": {"reproduction_inputs": inputs}}),
    }
    schedule = [{"trial_id": trial, "task_id": publication.SYNTHETIC_TASK}]
    return SimpleNamespace(payloads=payloads, schedule=schedule, grade_name=grade_name, cases=cases)


def test_exact_synthetic_fields_and_matching_case_replies_get_a_hash_bound_receipt(synthetic_allowance):
    fixture = synthetic_allowance
    before = fixture.payloads.copy()
    receipt = publication.scan_heldout_payloads(fixture.payloads, fixture.schedule)
    assert fixture.payloads == before
    assert receipt == publication.scan_heldout_payloads(fixture.payloads, fixture.schedule)
    assert receipt["source"] == {
        "task_id": publication.SYNTHETIC_TASK,
        "path": publication.SYNTHETIC_PATH,
        "sha256": publication.SYNTHETIC_SHA256,
    }
    assert set(receipt["files"]) == {publication.SYNTHETIC_PATH, fixture.grade_name}
    source_fields = {
        item["json_pointer"]: item["value_sha256"]
        for item in receipt["files"][publication.SYNTHETIC_PATH]["fields"]
    }
    assert source_fields["/0/args/0/api_key"] == publication.bytes_digest(
        publication.canonical_bytes("fixture-key")
    )
    assert source_fields["/0/args/0/a~1b~0c/PASSWORD"] == publication.bytes_digest(
        publication.canonical_bytes("fixture-pass")
    )
    assert "fixture-pass" not in json.dumps(receipt)
    assert receipt["review_reason"].strip()


@pytest.mark.parametrize(
    "mutation",
    [
        "source_bytes",
        "source_missing",
        "actual_value",
        "extra_actual_field",
        "extra_grade_field",
        "moved_value",
        "wrong_task",
        "unscheduled_trial",
        "wrong_request",
        "reordered_cases",
        "wrong_split",
        "outside_grade",
    ],
)
def test_synthetic_allowance_rejects_changed_fields_or_case_provenance(synthetic_allowance, mutation):
    fixture = synthetic_allowance
    payloads, schedule = fixture.payloads.copy(), copy.deepcopy(fixture.schedule)
    grade = json.loads(payloads[fixture.grade_name])
    inputs = grade["grade"]["reproduction_inputs"]
    records = inputs["hidden_case_records"]
    if mutation == "source_bytes":
        payloads[publication.SYNTHETIC_PATH] += b"\n"
    elif mutation == "source_missing":
        payloads.pop(publication.SYNTHETIC_PATH)
    elif mutation == "actual_value":
        records[0]["actual"]["args"][0]["api_key"] = "unexpected-live-value"
    elif mutation == "extra_actual_field":
        records[0]["actual"]["result"]["client_secret"] = "fixture-key"
    elif mutation == "extra_grade_field":
        grade["grade"]["api_key"] = "fixture-key"
    elif mutation == "moved_value":
        records[0]["actual"]["args"][0]["new_location"] = {"api_key": "fixture-key"}
    elif mutation == "wrong_task":
        schedule[0]["task_id"] = "another-task"
    elif mutation == "unscheduled_trial":
        schedule.clear()
    elif mutation == "wrong_request":
        records[0]["request"]["function"] = "another_function"
    elif mutation == "reordered_cases":
        records.reverse()
    elif mutation == "wrong_split":
        inputs["split"] = "development"
    elif mutation == "outside_grade":
        payloads["unrelated.json"] = payloads[fixture.grade_name]
    payloads[fixture.grade_name] = publication.canonical_bytes(grade)
    with pytest.raises(ValueError, match="sensitive"):
        publication.scan_heldout_payloads(payloads, schedule)


def test_synthetic_field_allowance_never_disables_raw_credential_patterns(synthetic_allowance, monkeypatch):
    cases = copy.deepcopy(synthetic_allowance.cases)
    cases[0]["args"][0]["api_key"] = "sk-" + "A" * 24
    raw = publication.canonical_bytes(cases)
    monkeypatch.setattr(publication, "SYNTHETIC_SHA256", publication.bytes_digest(raw))
    with pytest.raises(ValueError, match="api_credential"):
        publication.scan_heldout_payloads({publication.SYNTHETIC_PATH: raw}, [])


@pytest.mark.parametrize("raw", [b"NaN", b"Infinity", b'{"value": 1e999}'])
def test_nonfinite_response_replays_the_original_negative_grade(recorded, tmp_path, raw):
    record = recorded(raw_response=raw)
    public = tmp_path / "public"
    result = export(record, public)
    assert result["grade_records_replayed"] == 1
    grade = publication.read_json(
        public / "evidence/trials" / record.trial["trial_id"] / "attempt-1/grade.json"
    )["grade"]
    assert grade["reproduction_inputs"]["response"] is None
    assert grade["response_valid"] is False
    assert grade["valid_completion"] is False
    assert publication.verify_public_bundle(public) == result
