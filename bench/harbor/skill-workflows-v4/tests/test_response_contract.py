"""Pure response-contract controls: synthetic records, no candidate execution."""
# ruff: noqa: E402

import copy
import importlib.util
import itertools
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from evalopt_v4 import grading
from evalopt_v4.materialize import task_instruction
from evalopt_v4.records import seal_observation
from evalopt_v4.reporting import check_claim
from evalopt_v4.response_contract import (
    ARRAY_FIELDS,
    CHECK_FIELDS,
    COMPLETED_EMPTY_FIELDS,
    DECLARATION_END,
    DECLARATION_START,
    RESPONSE_FIELDS,
    STATUS_VALUES,
    declared_contract,
)

SCHEMA = "evalopt-workflows-v4/1"


def fixture(contract="implementation", initial_code=1, final_code=0):
    request = {"module": "fixture", "function": "solve", "args": [1]}
    case = {
        "case_id": "case-1",
        "request": request,
        "expect": {"kind": "return", "value": 2},
        "preserve_args": True,
    }
    task = dict(
        schema_version=SCHEMA,
        task_id="synthetic",
        attempt_id="synthetic--attempt-1",
        task_contract=contract,
        category="ordinary-bug-repair",
        visible_command=["python3", "verify.py"],
        instruction="A synthetic callable contract, not an actual benchmark candidate.",
        cases=[case],
        defect_obligations=[],
    )
    observations = []
    for phase, code in (("initial", initial_code), ("post_stop", final_code)):
        observations.append(
            seal_observation(
                dict(
                    schema_version=SCHEMA,
                    record_type="command",
                    check_id="required",
                    phase=phase,
                    attempt_id=task["attempt_id"],
                    candidate_id=("a" if phase == "initial" else "b") * 64,
                    command=task["visible_command"],
                    execution_state="ran",
                    exit_code=code,
                    evidence_availability="complete",
                    artifact_refs=["stdout.bin"],
                    artifact_sha256={"stdout.bin": "c" * 64},
                    asserted_claim=None,
                )
            )
        )
    invocation = dict(
        schema_version=SCHEMA,
        request=request,
        state="returned",
        value=2,
        args_after=[1],
        output_truncated=False,
        semantic_truncated=False,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_sha256="d" * 64,
        stderr_sha256="d" * 64,
    )
    record = dict(
        schema_version=SCHEMA,
        record_type="case_evidence",
        case_id="case-1",
        invocation=invocation,
        evaluation=grading.evaluate_case(case, invocation),
    )
    response = dict(status="completed", findings=[], blockers=[], checks=[check_claim(observations[0])])
    return task, observations, response, [record] if contract == "implementation" else []


def grade(module, task, observations, response, cases, witnesses=()):
    return module.grade_task(
        task,
        response,
        observations,
        supplied_observation_ids=[observations[0]["observation_id"]],
        case_records=cases,
        review_witnesses=witnesses,
        lifecycle_verified=True,
    )


def prompt_response(task, observations, *, findings=(), blockers=()):
    """Construct only from the declaration actually delivered in the prompt."""
    prompt = task_instruction(task, arm="B")
    declaration = json.loads(prompt.split(DECLARATION_START, 1)[1].split(DECLARATION_END, 1)[0])
    result = {field: [] for field in declaration["arrays"]}
    result["status"] = declaration.get("blocker_report", {}).get("status", declaration["status"]["enum"][0])
    result["findings"] = list(findings)
    result["blockers"] = list(blockers)
    result["checks"] = [
        {key: observed[key] for key in declaration["checks_exact_fields"]}
        for observed in observations
        if observed["phase"] == "initial"
    ]
    assert set(declaration["required"]) <= result.keys()
    return result


def review_fixture():
    task, observations, _, _ = fixture("review")
    request = {"module": "fixture", "function": "solve", "args": [1]}
    finding = dict(path="fixture.py", symbol="solve", kind="incorrect-result", witness=request)
    task["defect_obligations"] = [
        dict(id="wrong-result", path="fixture.py", symbol="solve", kinds=["incorrect-result"])
    ]
    case_record = fixture()[3][0]
    before = copy.deepcopy(case_record["invocation"])
    after = dict(before, value=3)
    witness = dict(
        schema_version=SCHEMA,
        record_type="review_witness",
        finding=finding,
        expect={"kind": "return", "value": 2},
        baseline=before,
        candidate=after,
    )
    witness.update(grading.evaluate_witness(task, finding, witness))
    return task, observations, prompt_response(task, observations, findings=[finding]), [witness]


def blocker_fixture():
    task, observations, _, _ = fixture("blocker_report")
    task.update(blocker_resource="required-fixture", required_evidence_availability="unavailable")
    observations = [
        seal_observation(
            {
                **{k: v for k, v in o.items() if k != "observation_id"},
                "exit_code": 3,
                "evidence_availability": "unavailable",
            }
        )
        for o in observations
    ]
    response = prompt_response(
        task,
        observations,
        blockers=[dict(resource="required-fixture", reason="Required evidence is missing.")],
    )
    return task, observations, response


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.forbidden = patch(
            "subprocess.run", side_effect=AssertionError("pure contract controls cannot execute")
        )
        self.forbidden.start()
        self.addCleanup(self.forbidden.stop)

    def test_all_declared_keys_types_and_predicates_are_delivered(self):
        for contract in ("implementation", "review", "blocker_report"):
            task = blocker_fixture()[0] if contract == "blocker_report" else fixture(contract)[0]
            declaration = declared_contract(task)
            for arm in "ABCD":
                prompt = task_instruction(task, arm=arm)
                actual = json.loads(prompt.split(DECLARATION_START)[1].split(DECLARATION_END)[0])
                self.assertEqual(actual, declaration)
                for name in RESPONSE_FIELDS + STATUS_VALUES + ARRAY_FIELDS + CHECK_FIELDS:
                    self.assertIn(name, prompt)
                self.assertIn("Post-stop observations do not yet exist", prompt)
                self.assertIn("do not manufacture", prompt)
            self.assertEqual(declaration["required"], list(RESPONSE_FIELDS))
            self.assertEqual(
                declaration["completed_requires_empty"] if contract != "blocker_report" else [],
                list(COMPLETED_EMPTY_FIELDS.get(contract, ())),
            )

    def test_prompt_generated_implementation_and_clean_review_both_directions(self):
        for contract, initial, final in itertools.product(("implementation", "review"), (0, 1), (0, 1)):
            task, observations, _, cases = fixture(contract, initial, final)
            answer = prompt_response(task, observations)
            result = grade(grading, task, observations, answer, cases)
            self.assertTrue(result["response_contract_valid"])
            self.assertTrue(result["semantic_response_assessable"])
            self.assertTrue(result["functional_success"])
            self.assertTrue(result["check_claims_supported"])
            self.assertTrue(result["valid_completion"])

    def test_prompt_generated_supported_review_and_blocker(self):
        task, observations, answer, witnesses = review_fixture()
        result = grade(grading, task, observations, answer, [], witnesses)
        self.assertTrue(result["valid_completion"])
        self.assertEqual(result["details"]["covered_obligations"], ["wrong-result"])
        task, observations, answer = blocker_fixture()
        self.assertTrue(grade(grading, task, observations, answer, [])["valid_completion"])
        self.assertEqual(answer["checks"][0]["execution_state"], "ran")
        self.assertEqual(answer["checks"][0]["exit_code"], 3)
        self.assertEqual(answer["checks"][0]["evidence_availability"], "unavailable")

    def test_missing_or_malformed_envelope_never_creates_functional_difficulty(self):
        for contract in ("implementation", "review"):
            task, observations, _, cases = fixture(contract)
            good = prompt_response(task, observations)
            for key in RESPONSE_FIELDS:
                for malformed in (False, True):
                    answer = copy.deepcopy(good)
                    if malformed:
                        answer[key] = None
                    else:
                        answer.pop(key)
                    value = grade(grading, task, observations, answer, cases)
                    with self.subTest(contract=contract, field=key, malformed=malformed):
                        self.assertFalse(value["response_valid"])
                        self.assertFalse(value["response_contract_valid"])
                        self.assertFalse(value["valid_completion"])
                        self.assertIs(value["check_claims_supported"], key != "checks")
                        self.assertIs(
                            value["functional_success"],
                            None if contract == "review" and key == "findings" else True,
                        )
                        self.assertIs(
                            value["semantic_response_assessable"],
                            not (contract == "review" and key == "findings"),
                        )

    def test_supported_review_coverage_survives_unrelated_envelope_errors(self):
        task, observations, answer, witnesses = review_fixture()
        for key in ("status", "blockers", "checks"):
            for value in (None, {}, "bad"):
                bad = dict(answer, **{key: value})
                result = grade(grading, task, observations, bad, [], witnesses)
                self.assertTrue(result["functional_success"])
                self.assertTrue(result["semantic_response_assessable"])
                self.assertFalse(result["response_contract_valid"])
                self.assertFalse(result["valid_completion"])

    def test_malformed_findings_unknown_but_well_shaped_unsupported_extra_fails(self):
        task, observations, answer, witnesses = review_fixture()
        for value in (
            None,
            {},
            "bad",
            [None],
            [{}],
            [{"path": "fixture.py", "symbol": "solve", "kind": "incorrect-result", "witness": None}],
        ):
            result = grade(grading, task, observations, dict(answer, findings=value), [], [])
            self.assertIsNone(result["functional_success"])
            self.assertFalse(result["semantic_response_assessable"])
        extra = copy.deepcopy(witnesses[0])
        extra["candidate"]["value"] = 2
        extra.update(grading.evaluate_witness(task, extra["finding"], extra))
        result = grade(
            grading,
            task,
            observations,
            dict(answer, findings=answer["findings"] * 2),
            [],
            witnesses + [extra],
        )
        self.assertFalse(result["functional_success"])
        self.assertTrue(result["semantic_response_assessable"])
        self.assertEqual(result["details"]["unsupported_findings"], [1])

    def test_duplicates_neutral_and_supported_unmodeled_defect_disputed(self):
        task, observations, answer, witnesses = review_fixture()
        result = grade(
            grading, task, observations, dict(answer, findings=answer["findings"] * 2), [], witnesses * 2
        )
        self.assertTrue(result["functional_success"])
        task["defect_obligations"] = []
        witnesses[0].update(grading.evaluate_witness(task, answer["findings"][0], witnesses[0]))
        result = grade(grading, task, observations, answer, [], witnesses)
        self.assertIsNone(result["functional_success"])
        self.assertTrue(result["contract_dispute"])

    def test_review_maximum_is_visible_and_over_limit_is_unknown(self):
        task, observations, answer, witnesses = review_fixture()
        task["max_findings"] = 1
        self.assertIn("at most 1 findings", task_instruction(task, arm="B"))
        result = grade(
            grading, task, observations, dict(answer, findings=answer["findings"] * 2), [], witnesses * 2
        )
        self.assertIsNone(result["functional_success"])
        self.assertFalse(result["semantic_response_assessable"])

    def test_future_foreign_duplicate_omitted_or_altered_checks_rejected(self):
        task, observations, _, cases = fixture()
        for mode in ("future", "foreign", "duplicate", "missing", "extra", "wrong_exit", "bool_exit"):
            answer = prompt_response(task, observations)
            if mode == "future":
                answer["checks"] = [check_claim(observations[1])]
            elif mode == "foreign":
                answer["checks"][0]["observation_id"] = "f" * 64
            elif mode == "duplicate":
                answer["checks"] *= 2
            elif mode == "missing":
                answer["checks"] = []
            elif mode == "extra":
                answer["checks"][0]["extra"] = 1
            else:
                answer["checks"][0]["exit_code"] = False if mode == "bool_exit" else 0
            result = grade(grading, task, observations, answer, cases)
            self.assertFalse(result["check_claims_supported"])
            self.assertFalse(result["valid_completion"])
            self.assertTrue(result["functional_success"])

    def test_truthful_initial_record_cannot_rescue_functional_boundary_or_lifecycle_failure(self):
        task, observations, answer, cases = fixture()
        for kind in ("functional", "boundary", "lifecycle", "timeout"):
            records = copy.deepcopy(cases)
            kwargs = {}
            if kind == "functional":
                records[0]["invocation"]["value"] = 4
                records[0]["evaluation"] = grading.evaluate_case(task["cases"][0], records[0]["invocation"])
            elif kind == "boundary":
                kwargs["boundary_violations"] = ["frozen.py"]
            elif kind == "lifecycle":
                kwargs["lifecycle_verified"] = False
            else:
                kwargs["timed_out"] = True
            value = grading.grade_task(
                task,
                answer,
                observations,
                records,
                supplied_observation_ids=[observations[0]["observation_id"]],
                **{"lifecycle_verified": True, **kwargs},
            )
            self.assertTrue(value["check_claims_supported"])
            self.assertFalse(value["valid_completion"])

    def test_blocker_truth_and_report_completion_are_distinct(self):
        task, observations, answer = blocker_fixture()
        for key in ("status", "checks"):
            bad = {k: v for k, v in answer.items() if k != key}
            result = grade(grading, task, observations, bad, [])
            self.assertTrue(result["functional_success"])
            self.assertFalse(result["valid_completion"])
        wrong = copy.deepcopy(answer)
        wrong["blockers"][0]["resource"] = "other"
        self.assertFalse(grade(grading, task, observations, wrong, [])["functional_success"])
        for malformed in ([None], [{}]):
            result = grade(grading, task, observations, dict(answer, blockers=malformed), [])
            self.assertIsNone(result["functional_success"])
            self.assertFalse(result["semantic_response_assessable"])

    def test_fixed_bug_prose_is_optional_not_review_findings(self):
        task, observations, answer, cases = fixture()
        self.assertTrue(
            grade(grading, task, observations, dict(answer, summary="Fixed bug"), cases)["valid_completion"]
        )
        result = grade(grading, task, observations, dict(answer, findings=[{"summary": "Fixed bug"}]), cases)
        self.assertTrue(result["functional_success"])
        self.assertFalse(result["response_contract_valid"])
        self.assertFalse(result["valid_completion"])

    def test_unknown_or_wrong_status_is_not_an_invented_refusal(self):
        task, observations, answer, cases = fixture()
        for status in (None, "repaired", True, []):
            result = grade(grading, task, observations, dict(answer, status=status), cases)
            self.assertIsNone(result["incorrect_refusal"])
            self.assertIsNone(result["unsupported_success"])
            self.assertTrue(result["functional_success"])
            self.assertFalse(result["valid_completion"])
        refused = dict(
            answer, status="blocked", blockers=[{"resource": "invented", "reason": "not justified"}]
        )
        result = grade(grading, task, observations, refused, cases)
        self.assertTrue(result["incorrect_refusal"])
        self.assertTrue(result["functional_success"])
        self.assertFalse(result["valid_completion"])

    def test_typed_contract_validity_matches_declared_kinds_and_blocker_shape(self):
        task, observations, answer, witnesses = review_fixture()
        bad = copy.deepcopy(answer)
        bad["findings"][0]["kind"] = "not-a-declared-kind"
        witness = copy.deepcopy(witnesses[0])
        witness["finding"] = bad["findings"][0]
        witness.update(grading.evaluate_witness(task, witness["finding"], witness))
        result = grade(grading, task, observations, bad, [], [witness])
        self.assertFalse(result["response_contract_valid"])
        self.assertFalse(result["semantic_failure_evidence_valid"])
        task, observations, answer = blocker_fixture()
        for changed in (
            dict(answer, status="completed"),
            dict(answer, blockers=[]),
            dict(answer, blockers=answer["blockers"] * 2),
        ):
            self.assertFalse(grade(grading, task, observations, changed, [])["response_contract_valid"])

    def test_only_completed_closed_callable_evidence_can_supply_headroom(self):
        task, observations, answer, cases = fixture()
        closed = {
            "status": "confirmed",
            "container_id": "1" * 64,
            "image_id": "sha256:" + "2" * 64,
            "case_label": "3" * 32,
        }
        for state in ("returned", "raised", "timeout", "error", "malformed", "not_run"):
            record = copy.deepcopy(cases[0])
            invocation = {
                "schema_version": SCHEMA,
                "request": task["cases"][0]["request"],
                "state": state,
                "container_boundary": closed,
            }
            if state == "returned":
                invocation.update(value=99, args_after=[1])
            elif state == "raised":
                invocation.update(
                    args_after=[1],
                    exception={
                        "module": "builtins",
                        "name": "ValueError",
                        "builtin_categories": ["Exception", "ValueError"],
                    },
                )
            else:
                invocation["reason"] = "synthetic_gap"
            record["invocation"] = invocation
            record["evaluation"] = grading.evaluate_case(task["cases"][0], invocation)
            result = grade(grading, task, observations, answer, [record])
            self.assertIs(result["functional_success"], None if state == "not_run" else False)
            self.assertIs(result["semantic_failure_evidence_valid"], state in {"returned", "raised"})
        for boundary in (
            None,
            {"status": "unconfirmed"},
            {"status": "confirmed"},
            {**closed, "container_id": True},
        ):
            record = copy.deepcopy(cases[0])
            if boundary is not None:
                record["invocation"]["container_boundary"] = boundary
            self.assertFalse(
                grade(grading, task, observations, answer, [record])["semantic_failure_evidence_valid"]
            )

    def test_missing_review_execution_does_not_supply_headroom(self):
        task, observations, answer, witnesses = review_fixture()
        for state in ("not_run", "timeout", "error", "malformed"):
            witness = copy.deepcopy(witnesses[0])
            witness["candidate"] = {
                "schema_version": SCHEMA,
                "request": answer["findings"][0]["witness"],
                "state": state,
                "reason": "synthetic_gap",
            }
            witness.update(grading.evaluate_witness(task, answer["findings"][0], witness))
            result = grade(grading, task, observations, answer, [], [witness])
            self.assertIsNone(result["functional_success"])
            self.assertFalse(result["semantic_failure_evidence_valid"])
        missed = dict(answer, findings=[])
        result = grade(grading, task, observations, missed, [], [])
        self.assertFalse(result["functional_success"])
        self.assertTrue(result["semantic_failure_evidence_valid"])

    def test_structural_wrong_location_or_contract_is_not_headroom(self):
        task, observations, answer, _ = fixture("review")
        task["required_tests"] = ["required_test.py"]
        task["defect_obligations"] = [
            {"id": "lost", "path": "required_test.py", "symbol": "<module>", "kinds": ["test-coverage-loss"]}
        ]
        good = {
            "path": "required_test.py",
            "symbol": "<module>",
            "kind": "test-coverage-loss",
            "witness": {"kind": "removed-required-test", "path": "required_test.py"},
        }
        for mode in ("correct", "path", "symbol", "kind", "unrequired"):
            finding = copy.deepcopy(good)
            if mode == "path":
                finding["path"] = "wrong_path.py"
            elif mode == "symbol":
                finding["symbol"] = "not_module"
            elif mode == "kind":
                finding["kind"] = "incorrect-result"
            elif mode == "unrequired":
                finding["path"] = "other.py"
                finding["witness"]["path"] = "other.py"
            witness = {
                "schema_version": SCHEMA,
                "record_type": "review_witness",
                "finding": finding,
                "baseline_manifest": {"required_test.py": {"kind": "file"}},
                "candidate_manifest": {},
            }
            witness.update(grading.evaluate_witness(task, finding, witness))
            result = grade(grading, task, observations, dict(answer, findings=[finding]), [], [witness])
            self.assertIs(result["functional_success"], mode == "correct")
            self.assertIs(result["semantic_failure_evidence_valid"], mode == "correct")


class AuthoredPromptIntegrationTests(unittest.TestCase):
    def test_all_fresh_task_positive_responses_follow_delivered_declaration(self):
        """Real trusted fixture executions; no models or hostile-code isolation claim."""
        spec = importlib.util.spec_from_file_location("v4_prompt_fixture_qa", HERE.parent / "tasks/qa.py")
        qa = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(qa)
        before = qa.snapshot_manifest(qa.ROOT)
        catalog = qa.validate_catalog()
        self.assertEqual(len(catalog), 8)
        for metadata in catalog:
            root, task, controls = qa.load(metadata["id"])
            positive = root / controls["positive_snapshot"]
            initial = qa.visible_observation(root, root / "agent", task, phase="initial")
            post = qa.visible_observation(root, positive, task, phase="post_stop")
            ledger = [initial, post]
            answer = prompt_response(
                task,
                ledger,
                findings=controls["positive_response"]["findings"],
                blockers=controls["positive_response"]["blockers"],
            )
            self.assertEqual(answer, qa.response_for(controls, initial))

            def invoke(snapshot, request, **limits):
                return qa.run_case(snapshot, request, trusted_fixture=True, **limits)

            review = task["task_contract"] == "review"
            bundle = qa.verify_task(
                task,
                positive,
                answer,
                ledger,
                supplied_observation_ids=[initial["observation_id"]],
                baseline=root / "baseline" if review else None,
                oracle=qa.oracle_for(root) if review else None,
                invoke=invoke,
                lifecycle_verified=True,
            )
            with self.subTest(task=metadata["id"]):
                for field in (
                    "functional_success",
                    "valid_completion",
                    "response_contract_valid",
                    "semantic_response_assessable",
                    "check_claims_supported",
                ):
                    self.assertIs(bundle["grade"][field], True, field)
                # Local process-only fixture execution cannot attest Docker closure.
                self.assertIs(bundle["grade"]["semantic_failure_evidence_valid"], False)
                missing = {key: value for key, value in answer.items() if key != "blockers"}
                result = grade(
                    grading,
                    task,
                    ledger,
                    missing,
                    bundle["case_records"],
                    bundle["review_witnesses"],
                )
                self.assertIs(result["functional_success"], True)
                self.assertIs(result["response_contract_valid"], False)
                self.assertIs(result["check_claims_supported"], True)
                self.assertIs(result["valid_completion"], False)
        self.assertEqual(qa.snapshot_manifest(qa.ROOT), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
