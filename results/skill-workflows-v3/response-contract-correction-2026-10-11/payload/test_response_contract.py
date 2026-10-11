"""Pure response-contract controls: synthetic records, no candidate execution."""
# ruff: noqa: E402

import copy
import importlib
import importlib.util
import itertools
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from evalopt_v3 import grading
from evalopt_v3.materialize import task_instruction
from evalopt_v3.records import seal_observation
from evalopt_v3.reporting import check_claim
from evalopt_v3.response_contract import (
    ARRAY_FIELDS,
    CHECK_FIELDS,
    COMPLETED_EMPTY_FIELDS,
    RESPONSE_FIELDS,
    STATUS_VALUES,
    declared_contract,
    envelope_valid,
    response_contract_text,
    task_response_valid,
)

original_root = Path(os.environ["EVALOPT_ORIGINAL_ROOT"])
spec = importlib.util.spec_from_file_location(
    "original_evalopt_v3",
    original_root / "evalopt_v3/__init__.py",
    submodule_search_locations=[str(original_root / "evalopt_v3")],
)
original_package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = original_package
spec.loader.exec_module(original_package)
original_grading = importlib.import_module("original_evalopt_v3.grading")
original_reporting = importlib.import_module("original_evalopt_v3.reporting")
SCHEMA = "evalopt-workflows-v3/1"


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


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.forbidden = patch(
            "subprocess.run",
            side_effect=AssertionError("controls must not execute candidates or subprocesses"),
        )
        self.forbidden.start()
        self.addCleanup(self.forbidden.stop)

    def test_all_required_fields_and_values_are_visible(self):
        task, _, _, _ = fixture()
        declaration = declared_contract(task)
        text = response_contract_text(task)
        self.assertEqual(declaration["required"], list(RESPONSE_FIELDS))
        for name in RESPONSE_FIELDS + STATUS_VALUES + ARRAY_FIELDS + CHECK_FIELDS:
            with self.subTest(name=name):
                self.assertIn(name, text)
        self.assertIn("all four keys must be present", text)
        self.assertIn("including [] when empty", text)
        self.assertIn("repaired or success are invalid", text)

    def test_each_task_completion_condition_is_visible(self):
        for contract, fields in COMPLETED_EMPTY_FIELDS.items():
            task, _, _, _ = fixture(contract)
            text = response_contract_text(task)
            for name in fields:
                with self.subTest(contract=contract, field=name):
                    self.assertIn(name + "=[]", text)
            self.assertIn('status="completed"', text)
        self.assertIn("not summaries of bugs you fixed", response_contract_text(fixture()[0]))
        self.assertIn("optional top-level summary or validation_notes", response_contract_text(fixture()[0]))

    def test_materialized_prompt_delivers_shared_contract_to_every_arm(self):
        for contract in ("implementation", "review"):
            task, _, _, _ = fixture(contract)
            for arm in ("A", "B", "C", "D"):
                with self.subTest(contract=contract, arm=arm):
                    rendered = task_instruction(task, arm=arm)
                    self.assertIn(response_contract_text(task), rendered)
                    self.assertIn("Post-stop observations do not yet exist", rendered)
                    self.assertIn(task["instruction"], rendered)

    def test_declared_key_and_status_mutations_reach_validator(self):
        _, _, response, _ = fixture()
        self.assertTrue(envelope_valid(response, strict=True))
        for key in RESPONSE_FIELDS:
            for mode in ("missing", "wrong_type"):
                changed = copy.deepcopy(response)
                if mode == "missing":
                    changed.pop(key)
                else:
                    changed[key] = {} if key == "status" else None
                with self.subTest(key=key, mode=mode):
                    self.assertFalse(envelope_valid(changed, strict=True))
        for status in (*STATUS_VALUES, "repaired", "success", True, None, []):
            changed = dict(response, status=status)
            self.assertIs(envelope_valid(changed), type(status) is str and status in STATUS_VALUES)

    def test_correct_six_fields_remain_truthful_in_both_phase_directions(self):
        for initial, final in itertools.product((0, 1), repeat=2):
            with self.subTest(initial=initial, final=final):
                task, observations, response, cases = fixture(initial_code=initial, final_code=final)
                value = grade(grading, task, observations, response, cases)
                self.assertTrue(value["claims_supported"])
                self.assertTrue(value["functional_success"])
                self.assertTrue(value["valid_completion"])
                self.assertEqual(value, grade(original_grading, task, observations, response, cases))

    def test_checks_are_exact_and_future_checks_are_rejected(self):
        task, observations, response, cases = fixture()
        for mutation in (
            lambda r: r["checks"][0].update(phase="post_stop"),
            lambda r: r["checks"][0].update(exit_code=0),
            lambda r: r["checks"][0].update(extra="invented"),
            lambda r: r["checks"].append(copy.deepcopy(r["checks"][0])),
        ):
            changed = copy.deepcopy(response)
            mutation(changed)
            self.assertFalse(grade(grading, task, observations, changed, cases)["claims_supported"])

    def test_fixed_issue_summary_belongs_in_optional_prose(self):
        task, observations, response, cases = fixture()
        good = dict(response, summary="Fixed the parsing bug.", validation_notes="Additional local checks.")
        self.assertTrue(grade(grading, task, observations, good, cases)["valid_completion"])
        bad = dict(response, findings=[{"summary": "Fixed the parsing bug."}])
        value = grade(grading, task, observations, bad, cases)
        self.assertTrue(value["functional_success"])
        self.assertFalse(value["claims_supported"])
        self.assertFalse(value["valid_completion"])

    def test_clean_review_complete_and_missing_envelope(self):
        task, observations, response, cases = fixture("review")
        self.assertTrue(grade(grading, task, observations, response, cases)["valid_completion"])
        for key in ("status", "blockers"):
            changed = copy.deepcopy(response)
            changed.pop(key)
            value = grade(grading, task, observations, changed, cases)
            self.assertFalse(value["functional_success"])
            self.assertFalse(value["valid_completion"])
            self.assertEqual(value, grade(original_grading, task, observations, changed, cases))

    def test_demonstrated_review_witness_with_complete_envelope(self):
        task, observations, response, _ = fixture("review")
        request = {"module": "fixture", "function": "solve", "args": [1]}
        finding = dict(path="fixture.py", symbol="solve", kind="incorrect-result", witness=request)
        task["defect_obligations"] = [
            dict(id="wrong-result", path="fixture.py", symbol="solve", kinds=["incorrect-result"])
        ]
        expected = {"kind": "return", "value": 2}

        def returned(value):
            return dict(
                schema_version=SCHEMA,
                request=request,
                state="returned",
                value=value,
                args_after=[1],
                output_truncated=False,
                semantic_truncated=False,
                stdout_bytes=0,
                stderr_bytes=0,
                stdout_sha256="d" * 64,
                stderr_sha256="d" * 64,
            )

        witness = dict(
            schema_version=SCHEMA,
            record_type="review_witness",
            finding=finding,
            expect=expected,
            baseline=returned(2),
            candidate=returned(3),
            supported=True,
            obligation_ids=["wrong-result"],
            reason="introduced_violation",
        )
        response["findings"] = [finding]
        value = grade(grading, task, observations, response, [], [witness])
        self.assertTrue(value["functional_success"])
        self.assertTrue(value["valid_completion"])
        self.assertEqual(value["details"]["covered_obligations"], ["wrong-result"])
        incomplete = {key: item for key, item in response.items() if key != "blockers"}
        incomplete_value = grade(grading, task, observations, incomplete, [], [witness])
        self.assertFalse(incomplete_value["functional_success"])
        self.assertEqual(
            incomplete_value, grade(original_grading, task, observations, incomplete, [], [witness])
        )

    def test_blocker_report_schema_remains_supported(self):
        task, observations, response, _ = fixture("blocker_report")
        task.update(blocker_resource="required-fixture", required_evidence_availability="unavailable")
        observations = [
            seal_observation(
                {
                    **{key: value for key, value in item.items() if key != "observation_id"},
                    "execution_state": "not_run",
                    "exit_code": None,
                    "evidence_availability": "unavailable",
                    "artifact_refs": [],
                    "artifact_sha256": {},
                }
            )
            for item in observations
        ]
        response = dict(
            status="blocked",
            findings=[],
            blockers=[dict(resource="required-fixture", reason="The required evidence is missing.")],
            checks=[check_claim(observations[0])],
        )
        text = response_contract_text(task)
        for word in ("blocker-report", "blocked", "resource", "reason", "required-fixture", "unavailable"):
            self.assertIn(word, text)
        self.assertTrue(grade(grading, task, observations, response, [])["valid_completion"])

    def test_pure_semantic_parity_for_representative_malformed_json_values(self):
        variants = [None, [], True, "completed", {}, {"checks": []}]
        for contract in ("implementation", "review"):
            task, observations, good, cases = fixture(contract)
            responses = list(variants) + [good]
            for key in RESPONSE_FIELDS:
                responses.append({name: value for name, value in good.items() if name != key})
                for value in (None, {}, "text", False, 0, [], ["extra"]):
                    responses.append({**good, key: value})
            for index, response in enumerate(responses):
                with self.subTest(contract=contract, variant=index):

                    def result(module, task=task, observations=observations, response=response, cases=cases):
                        try:
                            return {"grade": grade(module, task, observations, response, cases)}
                        except (ValueError, TypeError, KeyError) as error:
                            return {"error_type": type(error).__name__}

                    self.assertEqual(result(grading), result(original_grading))
                    args = dict(
                        observations=observations,
                        supplied_observation_ids=[observations[0]["observation_id"]],
                        attempt_id=task["attempt_id"],
                        check_roster=[dict(check_id="required", command=task["visible_command"])],
                    )
                    from evalopt_v3.reporting import check_claims

                    self.assertEqual(
                        check_claims(response, **args), original_reporting.check_claims(response, **args)
                    )

    def test_review_cap_remains_identical_and_visible(self):
        task, _, response, _ = fixture("review")
        task["max_findings"] = 1
        self.assertIn("at most 1 findings", response_contract_text(task))
        self.assertTrue(task_response_valid(response, "review", 1))
        self.assertFalse(task_response_valid(dict(response, findings=[{}, {}]), "review", 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
