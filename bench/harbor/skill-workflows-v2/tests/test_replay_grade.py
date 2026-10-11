"""Retained-record replay controls: candidate execution is forbidden here."""

import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.case_runner import SCHEMA
from evalopt_v2.grading import evaluate_case, evaluate_witness, grade_task
from evalopt_v2.records import digest
from evalopt_v2.replay_grade import replay_grade


def request(value=1):
    return {"module": "candidate", "function": "solve", "args": [value]}


def invocation(req, value, identity="container-1", manifest=None):
    return {
        "schema_version": SCHEMA,
        "record_type": "case_invocation",
        "request": req,
        "state": "returned",
        "value": value,
        "args_after": req["args"],
        "candidate_id": digest({} if manifest is None else manifest),
        "container_boundary": {
            "status": "confirmed",
            "container_id": digest(identity),
            "image_id": "sha256:" + "a" * 64,
            "case_label": digest(identity)[:32],
        },
    }


def common(contract="implementation"):
    task = {
        "schema_version": SCHEMA,
        "task_id": "control",
        "attempt_id": "control-A-1",
        "task_contract": contract,
        "visible_command": ["python3", "verify.py"],
    }
    observation = {
        "schema_version": SCHEMA,
        "record_type": "command",
        "attempt_id": task["attempt_id"],
        "candidate_id": digest({}),
        "command": task["visible_command"],
        "execution_state": "ran",
        "exit_code": 0,
        "evidence_availability": "complete",
        "artifact_refs": ["stdout.bin"],
        "asserted_claim": None,
    }
    response = {
        "status": "completed",
        "findings": [],
        "blockers": [],
        "checks": [
            {
                key: observation[key]
                for key in ("command", "execution_state", "exit_code", "evidence_availability")
            }
        ],
    }
    args = {
        "response": response,
        "observations": [observation],
        "visible_candidate_id": digest({}),
        "boundary_violations": [],
        "lifecycle_verified": True,
        "timed_out": False,
        "candidate_manifest": {},
        "baseline_manifest": {},
    }
    return task, args


def bundle(task, args, records=(), witnesses=(), *, boundaries=True):
    records, witnesses = list(records), list(witnesses)
    grade = grade_task(
        task,
        args["response"],
        args["observations"],
        records,
        boundary_violations=args["boundary_violations"],
        review_witnesses=witnesses,
        lifecycle_verified=args["lifecycle_verified"],
        timed_out=args["timed_out"],
    )
    args["retained_records"] = deepcopy(records + witnesses)
    return {
        "schema_version": SCHEMA,
        "record_type": "verification_bundle",
        "grade": grade,
        "case_records": records,
        "review_witnesses": witnesses,
        "case_boundary_confirmed": boundaries,
    }


def implementation(*, unknown=False, timed_out=False, lifecycle=True):
    task, args = common()
    args.update(timed_out=timed_out, lifecycle_verified=lifecycle)
    task["cases"] = [
        {
            "case_id": str(index),
            "request": request(index),
            "expect": {"kind": "return", "value": index},
            "preserve_args": True,
        }
        for index in (1, 2)
    ]
    records = []
    for case in task["cases"]:
        actual = invocation(case["request"], case["request"]["args"][0], "container-" + case["case_id"])
        if unknown:
            actual = {
                "schema_version": SCHEMA,
                "request": case["request"],
                "state": "not_run",
                "reason": "verifier_budget_exhausted",
            }
        records.append(
            {
                "schema_version": SCHEMA,
                "record_type": "case_evidence",
                "case_id": case["case_id"],
                "invocation": actual,
                "evaluation": evaluate_case(case, actual),
            }
        )
    return task, args, bundle(task, args, records)


def review(*, duplicate=False, dispute=False, structural=False):
    task, args = common("review")
    args["oracle_cases"] = [{"request": request(), "expect": {"kind": "return", "value": 1}}]
    task.update(defect_obligations=[], preserve_review_args=True, max_findings=8)
    task["defect_obligations"] = (
        []
        if dispute
        else [{"id": "defect", "path": "candidate.py", "symbol": "solve", "kinds": ["incorrect-result"]}]
    )
    finding = {"path": "candidate.py", "symbol": "solve", "kind": "incorrect-result", "witness": request()}
    if structural:
        finding = {
            "path": "test_contract.py",
            "symbol": "<module>",
            "kind": "test-coverage-loss",
            "witness": {"kind": "removed-required-test", "path": "test_contract.py"},
        }
        task["required_tests"] = ["test_contract.py"]
        task["defect_obligations"] = [
            {
                "id": "defect",
                "path": "test_contract.py",
                "symbol": "<module>",
                "kinds": ["test-coverage-loss"],
            }
        ]
        args["baseline_manifest"] = {
            "test_contract.py": {"kind": "file", "mode": 0o644, "size": 1, "sha256": "a" * 64}
        }
    args["response"]["findings"] = [finding] * (2 if duplicate else 1)
    witnesses = []
    for index, item in enumerate(args["response"]["findings"]):
        witness = {"schema_version": SCHEMA, "record_type": "review_witness", "finding": item}
        if structural:
            witness.update(baseline_manifest=deepcopy(args["baseline_manifest"]), candidate_manifest={})
        else:
            witness.update(
                expect={"kind": "return", "value": 1},
                baseline=invocation(request(), 1, f"before-{index}"),
                candidate=invocation(request(), 0, f"after-{index}"),
            )
        witness.update(evaluate_witness(task, item, witness))
        witnesses.append(witness)
    return task, args, bundle(task, args, witnesses=witnesses)


@pytest.mark.parametrize(
    "unknown,timed_out,lifecycle,expected",
    [
        (False, False, True, True),
        (True, False, True, None),
        (False, False, None, None),
        (False, True, None, False),
    ],
)
def test_replays_complete_and_explicitly_unrun_rosters(unknown, timed_out, lifecycle, expected):
    task, args, original = implementation(unknown=unknown, timed_out=timed_out, lifecycle=lifecycle)
    before = deepcopy((task, args, original))
    assert replay_grade(task, original, **args)["valid_completion"] is expected
    assert (task, args, original) == before


@pytest.mark.parametrize(
    "duplicate,dispute,structural,expected",
    [
        (False, False, False, True),
        (True, False, False, True),
        (False, True, False, None),
        (False, False, True, True),
    ],
)
def test_replays_witness_coverage_duplicates_and_preserves_disputes(duplicate, dispute, structural, expected):
    task, args, original = review(duplicate=duplicate, dispute=dispute, structural=structural)
    result = replay_grade(task, original, **args)
    assert result["valid_completion"] is expected
    assert result["contract_dispute"] is dispute


def test_clean_review_empty_roster_is_valid():
    task, args = common("review")
    task["defect_obligations"] = []
    args["oracle_cases"] = []
    original = bundle(task, args)
    assert replay_grade(task, original, **args)["valid_completion"] is True


def test_genuine_blocker_replays_without_callable_execution():
    task, args = common("blocker_report")
    task.update(blocker_resource="external-evidence", required_evidence_availability="unavailable")
    args["observations"][0].update(exit_code=3, evidence_availability="unavailable")
    args["response"].update(
        status="blocked", blockers=[{"resource": "external-evidence", "reason": "unavailable"}]
    )
    args["response"]["checks"][0].update(exit_code=3, evidence_availability="unavailable")
    original = bundle(task, args)
    assert replay_grade(task, original, **args)["valid_completion"] is True


@pytest.mark.parametrize(
    "field",
    [
        "functional_success",
        "valid_completion",
        "contract_dispute",
        "response_valid",
        "claims_supported",
        "boundaries_preserved",
        "details",
        "outcome",
    ],
)
def test_any_altered_grade_projection_is_rejected(field):
    task, args, original = implementation()
    original["grade"][field] = "altered"
    with pytest.raises(ValueError, match="grade is not reproducible"):
        replay_grade(task, original, **args)


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "reordered",
        "schema",
        "extra",
        "evaluation",
        "request",
        "return",
        "snapshot",
        "container",
    ],
)
def test_corrupted_case_records_fail_even_when_bundle_and_sink_agree(change):
    task, args, original = implementation()
    records = original["case_records"]
    if change == "missing":
        records.pop()
    elif change == "duplicate":
        records[1] = deepcopy(records[0])
    elif change == "reordered":
        records.reverse()
    elif change == "schema":
        records[0]["schema_version"] = "wrong"
    elif change == "extra":
        records[0]["unexpected"] = True
    elif change == "evaluation":
        records[0]["evaluation"]["verdict"] = "fail"
    elif change == "request":
        records[0]["invocation"]["request"] = request(999)
    elif change == "return":
        records[0]["invocation"]["value"] = 999
    elif change == "snapshot":
        records[0]["invocation"]["candidate_id"] = "altered"
    elif change == "container":
        records[1]["invocation"]["container_boundary"]["container_id"] = records[0]["invocation"][
            "container_boundary"
        ]["container_id"]
    args["retained_records"] = deepcopy(records)
    with pytest.raises(ValueError):
        replay_grade(task, original, **args)


def test_bundle_copy_cannot_replace_independently_retained_invocation():
    task, args, original = implementation()
    original["case_records"][0]["invocation"]["value"] = 99
    with pytest.raises(ValueError, match="per-case records"):
        replay_grade(task, original, **args)


@pytest.mark.parametrize(
    "change", ["missing", "support", "obligation", "expect", "finding", "extra", "schema", "manifest"]
)
def test_review_records_are_recomputed_and_bound_to_frozen_contract(change):
    task, args, original = review(structural=change == "manifest")
    witnesses = original["review_witnesses"]
    if change == "missing":
        witnesses.clear()
    elif change == "support":
        witnesses[0]["supported"] = False
    elif change == "obligation":
        witnesses[0]["obligation_ids"] = []
    elif change == "expect":
        witnesses[0]["expect"]["value"] = 999
    elif change == "finding":
        witnesses[0]["finding"] = {"wrong": True}
    elif change == "extra":
        witnesses[0]["unexpected"] = True
    elif change == "schema":
        witnesses[0]["record_type"] = "agent_claim"
    elif change == "manifest":
        witnesses[0]["baseline_manifest"]["test_contract.py"]["size"] = 999
    args["retained_records"] = deepcopy(witnesses)
    with pytest.raises(ValueError):
        replay_grade(task, original, **args)


@pytest.mark.parametrize(
    "field,value",
    [("lifecycle_verified", None), ("timed_out", True), ("boundary_violations", ["frozen_file_changed"])],
)
def test_replay_uses_retained_completion_context(field, value):
    task, args, original = implementation()
    args[field] = value
    with pytest.raises(ValueError, match="grade is not reproducible"):
        replay_grade(task, original, **args)


def test_case_boundary_summary_cannot_be_overridden():
    task, args, original = implementation()
    original["case_boundary_confirmed"] = False
    with pytest.raises(ValueError, match="boundary summary"):
        replay_grade(task, original, **args)


def test_oracle_catalog_is_data_only_and_required_for_review():
    task, args, original = review()
    for invalid in (None, lambda _: pytest.fail("oracle code executed"), [{"code": "execute()"}]):
        args["oracle_cases"] = invalid
        with pytest.raises(ValueError):
            replay_grade(task, original, **args)


def test_replay_never_starts_processes_or_imports_candidates(monkeypatch):
    import importlib
    import subprocess

    task, args, original = implementation()

    def denied(*a, **k):
        pytest.fail("replay attempted execution")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(subprocess, "run", denied)
    monkeypatch.setattr(importlib, "import_module", denied)
    assert replay_grade(task, original, **args)["valid_completion"] is True


@pytest.mark.parametrize(
    "mode",
    ["supported", "duplicate", "out_of_domain", "invalid_response", "missing_execution", "malformed_finding"],
)
def test_actual_collector_bundles_replay_without_running_candidate(tmp_path, mode):
    from evalopt_v2.case_runner import snapshot_manifest
    from evalopt_v2.verifier import finite_oracle, verify_task

    task, args, _ = review(duplicate=mode == "duplicate")
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    for directory in (baseline, candidate):
        directory.mkdir()
        (directory / "candidate.py").write_text("raise AssertionError('must never execute')\n")
    args["baseline_manifest"] = snapshot_manifest(baseline)
    args["candidate_manifest"] = snapshot_manifest(candidate)
    if mode == "out_of_domain":
        args["response"]["findings"][0]["witness"] = request(999)
    elif mode == "invalid_response":
        args["response"]["status"] = []
    elif mode == "malformed_finding":
        args["response"]["findings"] = [None]
    count = 0

    def invoke(source, req, **limits):
        nonlocal count
        count += 1
        if mode == "missing_execution":
            raise OSError("synthetic missing evidence")
        return invocation(
            req, 1 if source == baseline else 0, f"container-{count}", snapshot_manifest(source)
        )

    retained = []
    original = verify_task(
        task,
        candidate,
        args["response"],
        args["observations"],
        baseline=baseline,
        oracle=finite_oracle(args["oracle_cases"]),
        invoke=invoke,
        lifecycle_verified=True,
        record_sink=retained.append,
    )
    args["retained_records"] = retained
    assert replay_grade(task, original, **args) == original["grade"]


def test_falsely_outside_domain_witness_is_rejected_even_if_grade_would_match():
    task, args, original = review()
    witness = original["review_witnesses"][0]
    for name in ("expect", "baseline", "candidate"):
        witness.pop(name)
    witness["not_executed_reason"] = "witness_outside_published_domain"
    witness.update(evaluate_witness(task, witness["finding"], witness))
    original = bundle(task, args, witnesses=[witness])
    with pytest.raises(ValueError, match="in-domain witness"):
        replay_grade(task, original, **args)


@pytest.mark.parametrize("field", ["expect", "baseline", "candidate"])
def test_missing_callable_witness_payload_is_explicit_replay_failure(field):
    task, args, original = review()
    original["review_witnesses"][0].pop(field)
    args["retained_records"] = deepcopy(original["review_witnesses"])
    with pytest.raises(ValueError):
        replay_grade(task, original, **args)


@pytest.mark.parametrize("contract", ["implementation", "review"])
def test_executed_invocation_cannot_omit_its_snapshot_binding(contract):
    task, args, original = implementation() if contract == "implementation" else review()
    actual = (
        original["case_records"][0]["invocation"]
        if contract == "implementation"
        else original["review_witnesses"][0]["candidate"]
    )
    actual.pop("candidate_id")
    args["retained_records"] = deepcopy(original["case_records"] + original["review_witnesses"])
    with pytest.raises(ValueError, match="lacks snapshot identity"):
        replay_grade(task, original, **args)


def test_visible_observation_is_bound_separately_to_normalized_snapshot():
    task, args, original = implementation()
    args["observations"][0]["candidate_id"] = "e" * 64
    with pytest.raises(ValueError, match="visible observation snapshot identity changed"):
        replay_grade(task, original, **args)
    # The normalized identity can differ from the raw callable manifest digest,
    # but only when the independent caller-supplied visible binding agrees.
    args["visible_candidate_id"] = "e" * 64
    assert replay_grade(task, original, **args)["valid_completion"] is True


@pytest.mark.parametrize(
    "boundary,confirmed",
    [
        (None, True),
        ({"status": "not_started"}, True),
        ({"status": "unconfirmed"}, False),
        ({"status": "confirmed"}, False),
        ({"status": "not_started", "container_id": "c" * 64}, False),
    ],
)
def test_safe_skip_never_overrides_explicit_uncertain_boundary(boundary, confirmed):
    from evalopt_v2.verifier import _case_boundaries_confirmed

    task, args, original = implementation(unknown=True)
    actual = original["case_records"][0]["invocation"]
    actual["reason"] = "case_setup_deadline"
    if boundary is not None:
        actual["container_boundary"] = boundary
    original["case_records"][0]["evaluation"] = evaluate_case(task["cases"][0], actual)
    assert _case_boundaries_confirmed(original["case_records"], []) is confirmed
    original = bundle(task, args, original["case_records"], boundaries=True)
    if confirmed:
        assert replay_grade(task, original, **args)["valid_completion"] is None
    else:
        with pytest.raises(ValueError):
            replay_grade(task, original, **args)


def test_no_start_unknown_replays_without_fabricating_candidate_identity():
    task, args, original = implementation(unknown=True)
    assert "candidate_id" not in original["case_records"][0]["invocation"]
    assert replay_grade(task, original, **args)["valid_completion"] is None


def test_confirmed_not_run_invocation_still_requires_snapshot_identity():
    task, args, original = implementation()
    actual = original["case_records"][0]["invocation"]
    actual.update(state="not_run", reason="case_setup_deadline")
    for field in ("candidate_id", "value", "args_after"):
        actual.pop(field)
    original["case_records"][0]["evaluation"] = evaluate_case(task["cases"][0], actual)
    original = bundle(task, args, original["case_records"])
    with pytest.raises(ValueError, match="lacks snapshot identity"):
        replay_grade(task, original, **args)


def test_actual_collector_timeout_error_preserves_incomplete_failure_evidence(tmp_path):
    from evalopt_v2.verifier import verify_task

    task, args, _ = implementation()
    retained = []

    def timed_out(*a, **k):
        raise TimeoutError("synthetic host timeout")

    original = verify_task(
        task,
        tmp_path,
        args["response"],
        args["observations"],
        invoke=timed_out,
        lifecycle_verified=True,
        record_sink=retained.append,
    )
    args["retained_records"] = retained
    assert all("candidate_id" not in record["invocation"] for record in retained)
    assert original["case_boundary_confirmed"] is False
    result = replay_grade(task, original, **args)
    assert result["functional_success"] is False and result["valid_completion"] is False
