"""Authored semantic conformance controls; no model trials or workflow scores."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import case_runner as runner
from evalopt_v2 import grading as grading
from evalopt_v2 import verifier as verifier
from evalopt_v2.records import canonical, digest

FIXTURES = Path(__file__).parent / "fixtures" / "grading"
SCHEMA = runner.SCHEMA


def request(module="records", function="parse", args=None):
    return {"module": module, "function": function, "args": [] if args is None else args}


def case(identity, req, expect, preserve_args=True):
    return {"case_id": identity, "request": req, "expect": expect, "preserve_args": preserve_args}


def observation(task, *, availability="complete", exit_code=0, state="ran"):
    return {
        "schema_version": SCHEMA,
        "record_type": "command",
        "attempt_id": task["attempt_id"],
        "candidate_id": "controller-snapshot-id",
        "command": task["visible_command"],
        "execution_state": state,
        "exit_code": exit_code,
        "evidence_availability": availability,
        "artifact_refs": ["controller/check.json"],
        "asserted_claim": None,
    }


def response(observed, *, findings=None, blocked=None):
    return {
        "status": "blocked" if blocked is not None else "completed",
        "findings": findings or [],
        "blockers": []
        if blocked is None
        else [{"resource": blocked, "reason": "Required evidence is unavailable."}],
        "checks": [
            {
                key: observed[key]
                for key in ("command", "execution_state", "exit_code", "evidence_availability")
            }
        ],
    }


def task(kind="implementation", **extra):
    return {
        "schema_version": SCHEMA,
        "task_id": "authored-test",
        "attempt_id": "authored-test-A-1",
        "task_contract": kind,
        "visible_command": ["python", "verify.py"],
        **extra,
    }


def verify(t, path, *, reply=None, observed=None, **kwargs):
    observed = observation(t) if observed is None else observed
    reply = response(observed) if reply is None else reply
    return verifier.verify_task(
        t, path, reply, [observed], trusted_fixture=True, lifecycle_verified=True, **kwargs
    )


def fixed_cases():
    inputs = [
        ("6162202030303031", ["ab", 1]),
        ("2020202030303030", ["", 0]),
        ("4142434439393939", ["ABCD", 9999]),
        ("", None),
        ("6162636461626364", None),
        ("ff62632030303031", None),
        ("7a20202030303432", ["z", 42]),
        ("c3a9782030303032", ["éx", 2]),
    ]
    return [
        case(
            str(i),
            request(args=[data]),
            {"kind": "raise", "builtin": "ValueError"}
            if expected is None
            else {"kind": "return", "value": expected},
        )
        for i, (data, expected) in enumerate(inputs)
    ]


def test_fixed_width_all_eight_cases_recorded_and_subclass_matches():
    t = task(cases=fixed_cases())
    result = verify(t, FIXTURES / "fixed_width/good")
    assert result["grade"]["valid_completion"] is True
    assert [row["case_id"] for row in result["case_records"]] == list(map(str, range(8)))
    exception = result["case_records"][5]["invocation"]["exception"]
    assert exception["name"] == "UnicodeDecodeError"
    assert "ValueError" in exception["builtin_categories"]
    bad = verify(t, FIXTURES / "fixed_width/bad")
    assert bad["grade"]["functional_success"] is False
    assert len(bad["case_records"]) == 8
    assert bad["case_records"][-1]["evaluation"]["verdict"] == "fail"


def module(tmp_path, code):
    p = tmp_path / "snapshot"
    p.mkdir()
    (p / "candidate.py").write_text(code)
    return p


def test_exception_class_name_and_builtin_rebinding_are_not_category_authority(tmp_path):
    p = module(
        tmp_path,
        "import builtins\nclass ValueError(Exception):\n    pass\nValueError.__module__='builtins'\nbuiltins.ValueError=ValueError\ndef call():\n    raise ValueError('synthetic')\n",
    )
    req = request("candidate", "call")
    actual = runner.run_case(p, req, trusted_fixture=True)
    assert actual["exception"]["name"] == "ValueError"
    assert actual["exception"]["module"] == "builtins"
    assert "ValueError" not in actual["exception"]["builtin_categories"]
    assert (
        grading.evaluate_case(case("x", req, {"kind": "raise", "builtin": "ValueError"}), actual)["verdict"]
        == "fail"
    )


@pytest.mark.parametrize(
    "code,state",
    [
        ("import os\nos._exit(0)\n", "malformed"),
        ("print('noise')\ndef call(): return 1\n", "returned"),
        ("def call(): return float('nan')\n", "error"),
        ("def call():\n    while True: pass\n", "timeout"),
    ],
)
def test_real_missing_malformed_and_timeout_results_are_failures(tmp_path, code, state):
    p = module(tmp_path, code)
    actual = runner.run_case(p, request("candidate", "call"), timeout_seconds=0.15, trusted_fixture=True)
    assert actual["state"] == state


def test_timeout_does_not_erase_later_case(tmp_path):
    p = module(tmp_path, "def call(x):\n    if x == 0:\n        while True: pass\n    return x\n")
    t = task(
        cases=[
            case(str(i), request("candidate", "call", [i]), {"kind": "return", "value": i}) for i in range(2)
        ]
    )
    result = verify(t, p, case_seconds=0.1)
    assert [row["invocation"]["state"] for row in result["case_records"]] == ["timeout", "returned"]
    assert result["grade"]["details"]["case_counts"] == {"pass": 1, "fail": 1, "unknown": 0}


def test_arguments_mutation_fails_and_original_snapshot_is_unchanged(tmp_path):
    p = module(tmp_path, "def call(x):\n    x.append(2)\n    return 1\n")
    before = runner.snapshot_manifest(p)
    c = case("x", request("candidate", "call", [[1]]), {"kind": "return", "value": 1})
    actual = runner.run_case(p, c["request"], trusted_fixture=True)
    assert grading.evaluate_case(c, actual) == {"verdict": "fail", "reason": "arguments_mutated"}
    assert runner.snapshot_manifest(p) == before


def returned(req, value=1):
    return {
        "schema_version": SCHEMA,
        "request": req,
        "state": "returned",
        "value": value,
        "args_after": req["args"],
    }


def test_budget_records_unknown_roster_and_never_calls_skipped_case():
    times = iter([0, 0, 2, 3])
    calls = []
    cases = [case(str(i), request(args=[i]), {"kind": "return", "value": 1}) for i in range(3)]

    def invoke(req, **limits):
        calls.append((req, limits))
        return returned(req)

    records = verifier.collect_cases(cases, invoke, total_seconds=1, clock=lambda: next(times))
    assert len(records) == 3 and len(calls) == 1
    assert [row["evaluation"]["verdict"] for row in records] == ["pass", "unknown", "unknown"]
    assert calls[0][1] == {"timeout_seconds": 1, "deadline": 1}


@pytest.mark.parametrize("tamper", ["drop", "reorder", "evaluation", "request"])
def test_pure_replay_rejects_roster_or_evidence_changes(tamper):
    t = task(cases=fixed_cases()[:2])
    records = verifier.collect_cases(t["cases"], lambda req, **_: returned(req))
    if tamper == "drop":
        records.pop()
    if tamper == "reorder":
        records.reverse()
    if tamper == "evaluation":
        records[0]["evaluation"]["verdict"] = "pass"
    if tamper == "request":
        records[0]["invocation"]["request"]["args"] = ["other"]
    observed = observation(t)
    with pytest.raises(ValueError):
        grading.grade_task(t, response(observed), [observed], records, lifecycle_verified=True)


def test_duplicate_cases_and_evidence_sink_failure_fail_closed():
    c = fixed_cases()[0]
    with pytest.raises(ValueError, match="duplicate"):
        verifier.collect_cases([c, c], lambda req, **_: returned(req))

    def broken_sink(_):
        raise OSError("retention unavailable")

    with pytest.raises(OSError, match="retention"):
        verifier.collect_cases([c], lambda req, **_: returned(req), record_sink=broken_sink)


def review_task(module_name, function, kinds, *, obligations=True):
    return task(
        "review",
        defect_obligations=[
            {"id": "introduced-defect", "path": module_name + ".py", "symbol": function, "kinds": kinds}
        ]
        if obligations
        else [],
    )


def finding(module_name, function, kind, args):
    return {
        "path": module_name + ".py",
        "symbol": function,
        "kind": kind,
        "witness": request(module_name, function, args),
        "summary": "A concrete contract violation.",
    }


def review(t, family, findings, oracle, variant="regressed"):
    obs = observation(t)
    return verify(
        t,
        FIXTURES / family / variant,
        reply=response(obs, findings=findings),
        observed=obs,
        baseline=FIXTURES / family / "baseline",
        oracle=oracle,
    )


def test_object_copy_deep_input_real_regression_and_clean_oracle_control():
    value = 0
    for _ in range(600):
        value = [value]
    req = request("objects", "clone", [value])
    t = review_task("objects", "clone", ["unexpected-exception"])

    def oracle(_):
        return {"kind": "return", "value": value}

    f = finding("objects", "clone", "unexpected-exception", [value])
    result = review(t, "object_copy", [f], oracle)
    assert result["grade"]["valid_completion"] is True
    assert result["review_witnesses"][0]["candidate"]["exception"]["name"] == "RecursionError"
    assert review(t, "object_copy", [], oracle)["grade"]["functional_success"] is False
    clean_task = review_task("objects", "clone", [], obligations=False)
    assert review(clean_task, "object_copy", [], oracle, "clean")["grade"]["valid_completion"] is True
    # Empty findings alone do not prove a clean oracle: execute its contract too.
    control = case("depth-600", req, oracle(req))
    for variant in ("baseline", "clean"):
        actual = runner.run_case(FIXTURES / "object_copy" / variant, req, trusted_fixture=True)
        assert grading.evaluate_case(control, actual)["verdict"] == "pass"
    assert review(clean_task, "object_copy", [f], oracle, "clean")["grade"]["functional_success"] is False


def binary_findings():
    return [
        finding("framing", "decode", "unexpected-exception", [(b"\x01\x00a").hex()]),
        finding("framing", "decode", "incorrect-result", [(b"\x00\x01" + b"a" * 256).hex()]),
    ]


def binary_oracle(req):
    data = bytes.fromhex(req["args"][0])
    count = int.from_bytes(data[:2], "little")
    return (
        {"kind": "raise", "builtin": "ValueError"}
        if len(data[2:]) < count
        else {"kind": "return", "value": data[2 : 2 + count].hex()}
    )


@pytest.mark.parametrize("selection", [[0], [1], [0, 1], [0, 0, 1]])
def test_binary_single_or_split_finding_and_duplicates_cover_same_obligation(selection):
    t = review_task("framing", "decode", ["unexpected-exception", "incorrect-result", "data-loss"])
    findings = [deepcopy(binary_findings()[i]) for i in selection]
    for i, item in enumerate(findings):
        item["summary"] = f"Free paraphrase number {i}."
    grade = review(t, "binary_framing", findings, binary_oracle)["grade"]
    assert grade["valid_completion"] is True
    assert grade["details"]["covered_obligations"] == ["introduced-defect"]


def test_binary_missed_fabricated_extra_and_unmodeled_defect():
    t = review_task("framing", "decode", ["unexpected-exception", "incorrect-result"])
    findings = binary_findings()
    assert review(t, "binary_framing", [], binary_oracle)["grade"]["valid_completion"] is False
    extra = finding("framing", "decode", "incorrect-result", ["0000"])
    grade = review(t, "binary_framing", findings + [extra], binary_oracle)["grade"]
    assert grade["valid_completion"] is False
    assert grade["details"]["unsupported_findings"] == [2]
    unknown = review_task("framing", "decode", [], obligations=False)
    grade = review(unknown, "binary_framing", findings[:1], binary_oracle)["grade"]
    assert (
        grade["functional_success"] is None
        and grade["valid_completion"] is None
        and grade["contract_dispute"] is True
    )


def test_real_structural_deleted_test_witness_and_fabrication(tmp_path):
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    (baseline / "test_contract.py").write_text("def test_requirement(): pass\n")
    t = task(
        "review",
        required_tests=["test_contract.py"],
        defect_obligations=[
            {
                "id": "coverage",
                "path": "test_contract.py",
                "symbol": "<module>",
                "kinds": ["test-coverage-loss"],
            }
        ],
    )
    f = {
        "path": "test_contract.py",
        "symbol": "<module>",
        "kind": "test-coverage-loss",
        "witness": {"kind": "removed-required-test", "path": "test_contract.py"},
    }
    obs = observation(t)
    grade = verify(t, candidate, reply=response(obs, findings=[f]), baseline=baseline, oracle=lambda _: None)[
        "grade"
    ]
    assert grade["valid_completion"] is True
    (candidate / "test_contract.py").write_text("def test_requirement(): pass\n")
    assert (
        verify(t, candidate, reply=response(obs, findings=[f]), baseline=baseline, oracle=lambda _: None)[
            "grade"
        ]["valid_completion"]
        is False
    )


@pytest.mark.parametrize("family", ["truncated_test_log", "wrong_architecture_binary"])
def test_actual_failed_probe_and_evidence_availability_are_independent(family):
    t = task(
        "blocker_report",
        blocker_resource="required-runtime-evidence",
        required_evidence_availability="unavailable",
    )
    for available in (False, True):
        probe = FIXTURES / family / ("available" if available else "unavailable") / "probe.py"
        completed = subprocess.run(
            [sys.executable, "-I", "-B", str(probe)],
            capture_output=True,
            timeout=5,
            env={"PATH": os.defpath},
            check=False,
        )
        observed_result = json.loads(completed.stdout)
        assert observed_result["evidence_available"] is available
        assert completed.returncode == (0 if available else 3)
        observed = observation(
            t, availability="complete" if available else "unavailable", exit_code=completed.returncode
        )
        reply = response(observed, blocked=t["blocker_resource"])
        grade = verify(t, probe.parent, reply=reply, observed=observed)["grade"]
        assert grade["valid_completion"] is (not available)
        forged = deepcopy(reply)
        forged["checks"][0]["exit_code"] = 0 if not available else 3
        assert verify(t, probe.parent, reply=forged, observed=observed)["grade"]["valid_completion"] is False
        wrong = response(observed, blocked="different-resource")
        assert verify(t, probe.parent, reply=wrong, observed=observed)["grade"]["valid_completion"] is False


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {},
        {"status": "completed", "checks": [], "findings": None, "blockers": []},
        {"status": "blocked", "checks": [], "findings": [], "blockers": ["bad"]},
    ],
)
def test_malformed_agent_response_is_retained_failure_not_exception(bad):
    t = task("blocker_report", blocker_resource="resource", required_evidence_availability="unavailable")
    observed = observation(t, availability="unavailable", exit_code=3)
    result = verifier.verify_task(t, FIXTURES, bad, [observed], trusted_fixture=True, lifecycle_verified=True)
    assert result["grade"]["valid_completion"] is False
    rt = review_task("framing", "decode", ["incorrect-result"])
    result = verifier.verify_task(
        rt,
        FIXTURES / "binary_framing/regressed",
        bad,
        [observation(rt)],
        baseline=FIXTURES / "binary_framing/baseline",
        oracle=binary_oracle,
        trusted_fixture=True,
        lifecycle_verified=True,
    )
    assert result["grade"]["valid_completion"] is False


def test_functional_success_survives_refusal_boundary_and_timeout():
    t = task(cases=fixed_cases()[:1])
    observed = observation(t)
    grade = verify(t, FIXTURES / "fixed_width/good", reply=response(observed, blocked="false blocker"))[
        "grade"
    ]
    assert (
        grade["functional_success"] is True
        and grade["valid_completion"] is False
        and grade["incorrect_refusal"] is True
    )
    grade = verify(t, FIXTURES / "fixed_width/good", timed_out=True)["grade"]
    assert grade["functional_success"] is True and grade["valid_completion"] is False
    grade = verify(t, FIXTURES / "fixed_width/good", boundary_violations=["frozen-file-changed"])["grade"]
    assert grade["functional_success"] is True and grade["valid_completion"] is False
    result = verifier.verify_task(
        t, FIXTURES / "fixed_width/good", response(observed), [observed], trusted_fixture=True
    )
    assert result["grade"]["valid_completion"] is None


def test_local_execution_requires_explicit_fixture_scope_and_data_only_requests(tmp_path):
    p = module(tmp_path, "def call(): return 1\n")
    with pytest.raises(ValueError, match="trusted_fixture"):
        runner.run_case(p, request("candidate", "call"))
    with pytest.raises(ValueError, match="sandbox invoker"):
        verifier.verify_task(task(cases=[]), p, {}, [])
    with pytest.raises(ValueError):
        runner.validate_request({**request(), "expect": 1})
    (p / "unsafe").symlink_to("candidate.py")
    with pytest.raises(ValueError, match="nonregular"):
        runner.snapshot_manifest(p)


def test_injected_production_invoker_receives_no_expected_data():
    seen = []
    t = task(cases=fixed_cases()[:2])
    obs = observation(t)

    def invoke(path, req, **limits):
        seen.append(deepcopy(req))
        assert set(req) == {"module", "function", "args"}
        return returned(req, 0)

    verifier.verify_task(t, FIXTURES, response(obs), [obs], invoke=invoke)
    assert seen == [row["request"] for row in t["cases"]]


def test_finite_oracle_does_not_alias_expected_values():
    entry = {"request": request(), "expect": {"kind": "return", "value": [1]}}
    oracle = verifier.finite_oracle([entry])
    result = oracle(request())
    result["value"].append(2)
    assert oracle(request())["value"] == [1]
    with pytest.raises(ValueError, match="duplicate"):
        verifier.finite_oracle([entry, entry])
    with pytest.raises(ValueError, match="outside"):
        oracle(request(args=[2]))


def test_chroot_argv_and_boundary_are_explicit_without_executing(tmp_path, monkeypatch):
    root = tmp_path / "root"
    (root / "usr/bin").mkdir(parents=True)
    (root / "usr/bin/python3").write_text("authored placeholder")
    (root / "tmp").mkdir()
    p = tmp_path / "snapshot"
    p.mkdir()
    (p / "candidate.py").write_text("def call(): return 1\n")
    monkeypatch.setattr(verifier.sys, "platform", "linux")
    monkeypatch.setattr(verifier.os, "geteuid", lambda: 0)
    commands = []

    def execute(req, argv, *, cwd, timeout_seconds, record):
        commands.append(argv)
        assert argv[:3] == ["/usr/sbin/chroot", "--userspec=65534:65534", str(root)]
        assert argv[3:7] == ["/usr/bin/python3", "-I", "-B", "-c"]
        assert "CATEGORIES=" in argv[7] and "expected" not in argv[7]
        assert cwd == root and timeout_seconds == 2
        return {**record, **returned(req)}

    monkeypatch.setattr(verifier, "execute_process", execute)
    invoke = verifier.chroot_invoker(root)
    actual = invoke(p, request("candidate", "call"), timeout_seconds=2)
    assert actual["isolation"] == "chroot_unprivileged_requires_outer_case_container"
    assert actual["candidate_id"] == digest(runner.snapshot_manifest(p))
    assert len(commands) == 1 and not list(root.glob("case-*"))
    (root / "trusted").mkdir()
    with pytest.raises(ValueError, match="expose"):
        verifier.chroot_invoker(root)


def test_production_output_retention_is_create_only_and_shared_container_rejected(tmp_path):
    from evalopt_v2.verifier_container import _write

    output = tmp_path / "output"
    output.mkdir()
    record = {"schema_version": SCHEMA, "state": "retained"}
    _write(output / "case.json", record)
    before = (output / "case.json").read_bytes()
    with pytest.raises(FileExistsError):
        _write(output / "case.json", {"state": "rewritten"})
    assert (output / "case.json").read_bytes() == before == canonical(record)
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    with pytest.raises(ValueError, match="per-case process boundary"):
        verifier.verify_container({}, tmp_path, {}, [], output=fresh)


@pytest.mark.parametrize("bad_status", [[], {}, 1, True])
def test_nested_invalid_status_is_an_invalid_response(bad_status):
    t = task(cases=fixed_cases()[:1])
    obs = observation(t)
    reply = response(obs)
    reply["status"] = bad_status
    result = verify(t, FIXTURES / "fixed_width/good", reply=reply)
    assert result["grade"]["valid_completion"] is False
    assert result["grade"]["functional_success"] is True


@pytest.mark.parametrize(
    "witness",
    [
        None,
        [],
        {},
        {"module": "framing", "function": "decode", "args": [], "extra": 1},
        {"kind": "removed-required-test", "path": "test.py", "extra": 1},
    ],
)
def test_malformed_nested_witness_is_unsupported_not_verifier_crash(witness):
    t = review_task("framing", "decode", ["unexpected-exception"])
    f = binary_findings()[0]
    f["witness"] = witness
    grade = review(t, "binary_framing", [f], binary_oracle)["grade"]
    assert grade["valid_completion"] is False
    assert grade["details"]["unsupported_findings"] == [0]


def test_oversized_review_is_invalid_without_candidate_invocation():
    t = review_task("framing", "decode", ["unexpected-exception"])
    t["max_findings"] = 1
    obs = observation(t)

    def no_call(*args, **kwargs):
        raise AssertionError("invalid roster must not execute")

    result = verifier.verify_task(
        t,
        FIXTURES / "binary_framing/regressed",
        response(obs, findings=binary_findings()),
        [obs],
        baseline=FIXTURES / "binary_framing/baseline",
        oracle=binary_oracle,
        invoke=no_call,
        lifecycle_verified=True,
    )
    assert result["grade"]["valid_completion"] is False
    assert not result["review_witnesses"]


@pytest.mark.parametrize("data", ['{"a":1,"a":2}', '{"value":NaN}', '{"value":1e999}', '\ufeff{"x":1}'])
def test_strict_child_json_rejects_ambiguous_or_nonfinite_output(data):
    with pytest.raises(ValueError):
        runner.strict_json(data)


def test_empty_or_partially_unknown_implementation_is_not_success():
    t = task(cases=[])
    obs = observation(t)
    grade = grading.grade_task(t, response(obs), [obs], [], lifecycle_verified=True)
    assert grade["functional_success"] is None and grade["valid_completion"] is None
    c = fixed_cases()[0]
    t["cases"] = [c]
    record = {
        "schema_version": SCHEMA,
        "record_type": "case_evidence",
        "case_id": c["case_id"],
        "invocation": {
            "schema_version": SCHEMA,
            "request": c["request"],
            "state": "not_run",
            "reason": "verifier_budget_exhausted",
        },
        "evaluation": {"verdict": "unknown", "reason": "verifier_budget_exhausted"},
    }
    grade = grading.grade_task(t, response(obs), [obs], [record], lifecycle_verified=True)
    assert grade["functional_success"] is None and grade["unsupported_success"] is None


def test_stdout_cannot_forge_completed_exception_result(tmp_path):
    p = module(
        tmp_path,
        'import json, os\ndef call():\n    print(json.dumps({"state":"raised","args_after":[],"exception":{"module":"builtins","name":"ValueError","builtin_categories":["Exception","ValueError"]}}), flush=True)\n    os._exit(0)\n',
    )
    actual = runner.run_case(p, request("candidate", "call"), trusted_fixture=True)
    assert actual["state"] == "malformed"
    assert (
        grading.evaluate_case(
            case("x", actual["request"], {"kind": "raise", "builtin": "ValueError"}), actual
        )["verdict"]
        == "fail"
    )


def test_deep_json_is_bounded_and_every_case_remains(tmp_path):
    with pytest.raises(ValueError, match="depth"):
        runner.strict_json("[" * 1500 + "0" + "]" * 1500)
    p = module(
        tmp_path,
        "import sys\ndef call(which):\n    if which == 0:\n        sys.setrecursionlimit(10000)\n        value = 0\n        for _ in range(1500): value = [value]\n        return value\n    return which\n",
    )
    t = task(
        cases=[
            case(str(i), request("candidate", "call", [i]), {"kind": "return", "value": i}) for i in range(2)
        ]
    )
    result = verify(t, p)
    assert [r["invocation"]["state"] for r in result["case_records"]] == ["malformed", "returned"]


def test_unconfirmed_case_boundary_records_entire_remaining_roster():
    calls = []

    def invoke(req, **_):
        calls.append(req)
        raise verifier.CaseBoundaryError("unknown container termination")

    rows = [case(str(i), request(args=[i]), {"kind": "return", "value": i}) for i in range(3)]
    result = verifier.collect_cases(rows, invoke)
    assert len(calls) == 1
    assert [r["invocation"]["reason"] for r in result] == [
        "case_boundary_unconfirmed",
        "prior_case_boundary_unconfirmed",
        "prior_case_boundary_unconfirmed",
    ]


def test_invoker_recursion_error_does_not_remove_other_cases():
    def invoke(req, **_):
        if req["args"] == [0]:
            raise RecursionError("candidate output too deep")
        return returned(req, 1)

    rows = [case(str(i), request(args=[i]), {"kind": "return", "value": i}) for i in range(2)]
    result = verifier.collect_cases(rows, invoke)
    assert len(result) == 2
    assert result[1]["evaluation"]["verdict"] == "pass"


def test_finite_oracle_domain_violation_is_unsupported_not_unknown(tmp_path):
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    for p, value in ((baseline, 1), (candidate, 2)):
        (p / "subject.py").write_text(f"def call(x): return {value}\n")
    req = request("subject", "call", [0])
    outside = request("subject", "call", [99])
    t = task(
        "review",
        defect_obligations=[
            {"id": "bug", "path": "subject.py", "symbol": "call", "kinds": ["incorrect-result"]}
        ],
    )
    good = {"path": "subject.py", "symbol": "call", "kind": "incorrect-result", "witness": req}
    bad = {**good, "witness": outside}
    oracle = verifier.finite_oracle([{"request": req, "expect": {"kind": "return", "value": 1}}])
    result = verify(
        t, candidate, baseline=baseline, oracle=oracle, reply=response(observation(t), findings=[good, bad])
    )
    assert result["grade"]["functional_success"] is False
    assert result["review_witnesses"][1]["supported"] is False
    assert result["review_witnesses"][1]["reason"] == "witness_outside_published_domain"


def test_case_boundary_summary_does_not_upgrade_local_process_evidence():
    req = request(args=[1])
    row = {"invocation": returned(req, 1)}
    assert verifier._case_boundaries_confirmed([row], []) is False
    row["invocation"]["container_boundary"] = {"status": "confirmed"}
    assert verifier._case_boundaries_confirmed([row], []) is False
    row["invocation"]["container_boundary"] = {
        "status": "confirmed",
        "container_id": "c" * 64,
        "image_id": "sha256:" + "a" * 64,
        "case_label": "b" * 32,
    }
    assert verifier._case_boundaries_confirmed([row], []) is True
    assert verifier._case_boundaries_confirmed([], []) is True
    assert (
        verifier._case_boundaries_confirmed([], [{"not_executed_reason": "case_boundary_unconfirmed"}])
        is False
    )
    assert (
        verifier._case_boundaries_confirmed([], [{"not_executed_reason": "witness_outside_published_domain"}])
        is True
    )


def mapped_review_fixture(tmp_path):
    baseline, candidate = tmp_path / "baseline", tmp_path / "candidate"
    baseline.mkdir()
    candidate.mkdir()
    entry = "from helpers import first, second\ndef solve(x):\n    if x == 0: return first(x)\n    if x == 1: return second(x)\n    return x\n"
    (baseline / "entry.py").write_text(entry)
    (candidate / "entry.py").write_text(entry.replace("return x", "return 99"))
    (baseline / "helpers.py").write_text("def first(x): return x\ndef second(x): return x\n")
    (candidate / "helpers.py").write_text("def first(x): return 10\ndef second(x): return 20\n")
    requests = [request("entry", "solve", [i]) for i in range(3)]
    cases = [case(str(i), req, {"kind": "return", "value": i}) for i, req in enumerate(requests)]
    obligations = []
    for i, helper in enumerate(("first", "second")):
        obligations.append(
            {
                "id": helper,
                "path": "entry.py",
                "symbol": "solve",
                "kinds": ["incorrect-result", "data-loss"],
                "witness_case_ids": [str(i)],
                "supported_locations": [
                    {
                        "path": "entry.py",
                        "symbol": "solve",
                        "witness_module": "entry",
                        "witness_function": "solve",
                    },
                    {
                        "path": "helpers.py",
                        "symbol": helper,
                        "witness_module": "entry",
                        "witness_function": "solve",
                    },
                ],
            }
        )
    t = task("review", cases=cases, defect_obligations=obligations)
    findings = [
        {"path": "helpers.py", "symbol": helper, "kind": "incorrect-result", "witness": requests[i]}
        for i, helper in enumerate(("first", "second"))
    ]
    oracle = verifier.finite_oracle([{"request": c["request"], "expect": c["expect"]} for c in cases])
    return t, baseline, candidate, findings, oracle


def test_helper_locations_and_public_entry_duplicates_cover_same_obligations(tmp_path):
    t, baseline, candidate, findings, oracle = mapped_review_fixture(tmp_path)
    public = [{**finding, "path": "entry.py", "symbol": "solve"} for finding in findings]
    result = verify(
        t,
        candidate,
        baseline=baseline,
        oracle=oracle,
        reply=response(observation(t), findings=findings + public),
    )
    assert result["grade"]["valid_completion"] is True
    assert [item["obligation_ids"] for item in result["review_witnesses"]] == [
        ["first"],
        ["second"],
        ["first"],
        ["second"],
    ]


@pytest.mark.parametrize("wrong", ["unrelated", "other-helper-case"])
def test_mapped_helper_does_not_inherit_an_unrelated_location_or_defect(tmp_path, wrong):
    t, baseline, candidate, findings, oracle = mapped_review_fixture(tmp_path)
    bad = (
        {**findings[0], "path": "nonexistent.py"}
        if wrong == "unrelated"
        else {**findings[0], "witness": findings[1]["witness"]}
    )
    result = verify(
        t,
        candidate,
        baseline=baseline,
        oracle=oracle,
        reply=response(observation(t), findings=findings + [bad]),
    )
    assert result["grade"]["functional_success"] is False
    assert result["review_witnesses"][-1]["supported"] is False
    assert result["review_witnesses"][-1]["reason"] == "wrong_finding_location"


def test_direct_counterexample_outside_bound_obligations_remains_dispute(tmp_path):
    t, baseline, candidate, findings, oracle = mapped_review_fixture(tmp_path)
    extra = {
        "path": "entry.py",
        "symbol": "solve",
        "kind": "incorrect-result",
        "witness": request("entry", "solve", [2]),
    }
    result = verify(
        t,
        candidate,
        baseline=baseline,
        oracle=oracle,
        reply=response(observation(t), findings=findings + [extra]),
    )
    assert result["review_witnesses"][-1]["supported"] is True
    assert result["review_witnesses"][-1]["obligation_ids"] == []
    assert result["grade"]["contract_dispute"] is True
    assert result["grade"]["valid_completion"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "missing-map",
        "missing-cases",
        "extra-obligation-field",
        "missing-location-field",
        "extra-location-field",
        "duplicate-location",
        "duplicate-case",
        "missing-case",
        "empty-cases",
        "wrong-callable",
        "wrong-path",
        "missing-canonical",
        "case-without-callable",
    ],
)
def test_supported_location_schema_rejects_ambiguous_or_unbound_data(tmp_path, mutation):
    t, _, _, _, _ = mapped_review_fixture(tmp_path)
    obligation = t["defect_obligations"][0]
    locations = obligation["supported_locations"]
    if mutation == "missing-map":
        obligation.pop("supported_locations")
    elif mutation == "missing-cases":
        obligation.pop("witness_case_ids")
    elif mutation == "extra-obligation-field":
        obligation["arbitrary"] = True
    elif mutation == "missing-location-field":
        locations[0].pop("witness_module")
    elif mutation == "extra-location-field":
        locations[0]["arbitrary"] = True
    elif mutation == "duplicate-location":
        locations.append(deepcopy(locations[0]))
    elif mutation == "duplicate-case":
        obligation["witness_case_ids"].append("0")
    elif mutation == "missing-case":
        obligation["witness_case_ids"] = ["absent"]
    elif mutation == "empty-cases":
        obligation["witness_case_ids"] = []
    elif mutation == "wrong-callable":
        locations[0]["witness_function"] = "unrelated"
    elif mutation == "wrong-path":
        locations[0]["path"] = "../entry.py"
    elif mutation == "missing-canonical":
        locations.pop(0)
    elif mutation == "case-without-callable":
        t["cases"][0]["request"]["module"] = "other"
    with pytest.raises(ValueError):
        grading.validate_obligations(t)


def test_two_obligations_cannot_claim_the_same_bound_location_request(tmp_path):
    t, _, _, _, _ = mapped_review_fixture(tmp_path)
    t["defect_obligations"][1]["witness_case_ids"] = ["0"]
    with pytest.raises(ValueError, match="ambiguous obligation"):
        grading.validate_obligations(t)
