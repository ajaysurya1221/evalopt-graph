import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.policies import evaluate_visible


class PoliciesTests(unittest.TestCase):
    def observe(self, code=0, availability="complete"):
        return {
            "schema_version": "evalopt-workflows-v2/1",
            "record_type": "command",
            "attempt_id": "one",
            "candidate_id": "snapshot",
            "command": ["python3", "verify.py"],
            "execution_state": "ran",
            "exit_code": code,
            "evidence_availability": availability,
            "artifact_refs": ["visible.log"],
            "asserted_claim": None,
        }

    def evaluate(self, observations, *, response=..., check_roster=None, **kwargs):
        bundle = {
            "attempt_id": "one",
            "snapshot_sha256": "snapshot",
            "task_contract": "implementation",
            "observations": observations,
            "boundary_violations": [],
            "boundaries_preserved": True,
            "snapshot_status": "complete",
            "execution_boundary": "confirmed",
            "response": {
                "status": "completed",
                "findings": [],
                "blockers": [],
                "checks": [
                    {
                        key: observation[key]
                        for key in ("command", "execution_state", "exit_code", "evidence_availability")
                    }
                    for observation in observations
                    if observation.get("record_type") == "command"
                ],
            },
        }
        if response is not ...:
            bundle["response"] = response
        return evaluate_visible(
            bundle,
            check_roster=check_roster or [{"check_id": "required", "command": ["python3", "verify.py"]}],
            attempt_id="one",
            candidate_id="snapshot",
            observed_at="2026-10-11T00:00:00+00:00",
            **kwargs,
        )

    def test_all_passing(self):
        result = self.evaluate([self.observe()])
        self.assertTrue(result["U"]["accepted"])
        self.assertTrue(result["M"]["accepted"])
        self.assertTrue(result["G"]["accepted"])

    def test_failed_unavailable_never_accepted_as_patch(self):
        result = self.evaluate([self.observe(3, "unavailable")])
        self.assertTrue(result["U"]["accepted"])
        self.assertFalse(result["M"]["accepted"])
        self.assertFalse(result["G"]["accepted"])

    def test_missing_required_check_is_unavailable(self):
        result = self.evaluate([])
        self.assertFalse(result["M"]["accepted"])
        self.assertFalse(result["G"]["accepted"])
        self.assertIsNone(result["visible_claims_supported"])
        self.assertIn(["visible_claims", "NOT_CONFIGURED"], result["kernel_input"]["gate_results"])

    def test_unexecuted_required_check_is_unknown_despite_accurate_report(self):
        missing = dict(
            self.observe(),
            execution_state="not_run",
            exit_code=None,
            evidence_availability="unavailable",
            artifact_refs=[],
        )
        result = self.evaluate([missing])
        self.assertIsNone(result["visible_claims_supported"])
        self.assertIn(["visible_claims", "NOT_CONFIGURED"], result["kernel_input"]["gate_results"])

    def test_missing_response_is_not_a_demonstrated_false_claim(self):
        result = self.evaluate([], response=None)
        self.assertIsNone(result["visible_claims_supported"])
        self.assertIn(["visible_claims", "NOT_CONFIGURED"], result["kernel_input"]["gate_results"])

    def test_malformed_status_is_unsupported_without_controller_crash_or_mutation(self):
        for status in ([], {}, ["completed"], 1, None):
            reply = {"status": status, "findings": [], "blockers": [], "checks": []}
            before = deepcopy(reply)
            with self.subTest(status=status):
                result = self.evaluate([self.observe()], response=reply)
                self.assertIs(result["visible_claims_supported"], False)
                self.assertIn(["visible_claims", "FAIL"], result["kernel_input"]["gate_results"])
                self.assertEqual(reply, before)

    def test_observed_contradiction_stays_false_when_another_required_check_is_missing(self):
        observed = self.observe(1)
        reply = {
            "status": "completed",
            "findings": [],
            "blockers": [],
            "checks": [
                {
                    key: observed[key]
                    for key in ("command", "execution_state", "exit_code", "evidence_availability")
                }
            ],
        }
        reply["checks"][0]["exit_code"] = 0
        result = self.evaluate(
            [observed],
            response=reply,
            check_roster=[
                {"check_id": "required", "command": observed["command"]},
                {"check_id": "missing", "command": ["python3", "other.py"]},
            ],
        )
        self.assertIs(result["visible_claims_supported"], False)
        self.assertIn(["visible_claims", "FAIL"], result["kernel_input"]["gate_results"])

    def test_claim_for_wholly_missing_observation_is_unverified(self):
        reply = {
            "status": "completed",
            "findings": [],
            "blockers": [],
            "checks": [
                {
                    "command": ["python3", "verify.py"],
                    "execution_state": "ran",
                    "exit_code": 0,
                    "evidence_availability": "complete",
                }
            ],
        }
        self.assertIsNone(self.evaluate([], response=reply)["visible_claims_supported"])

    def test_claim_contradicting_observed_not_run_remains_false(self):
        observation = dict(
            self.observe(),
            execution_state="not_run",
            exit_code=None,
            evidence_availability="unavailable",
            artifact_refs=[],
        )
        reply = {
            "status": "completed",
            "findings": [],
            "blockers": [],
            "checks": [
                {
                    "command": observation["command"],
                    "execution_state": "ran",
                    "exit_code": 0,
                    "evidence_availability": "complete",
                }
            ],
        }
        self.assertIs(self.evaluate([observation], response=reply)["visible_claims_supported"], False)

    def test_malformed_middle_check_is_failure_without_mutation(self):
        check = {
            "command": ["python3", "verify.py"],
            "execution_state": "ran",
            "exit_code": 0,
            "evidence_availability": "complete",
        }
        for malformed in ({}, [], {**check, "execution_state": []}, {**check, "exit_code": True}):
            reply = {
                "status": "completed",
                "findings": [],
                "blockers": [],
                "checks": [check, malformed, check],
            }
            before = deepcopy(reply)
            with self.subTest(malformed=malformed):
                self.assertIs(self.evaluate([], response=reply)["visible_claims_supported"], False)
                self.assertEqual(reply, before)

    def test_overdeep_response_is_bounded_data_rejection(self):
        from evalopt_v2.records import MAX_CANONICAL_DEPTH

        nested = "leaf"
        for _ in range(MAX_CANONICAL_DEPTH + 1):
            nested = [nested]
        reply = {"status": "completed", "findings": nested, "blockers": [], "checks": []}
        with self.assertRaisesRegex(ValueError, "depth"):
            self.evaluate([], response=reply)
        self.assertIs(reply["findings"], nested)

    def test_observation_splice_and_duplicate_rejected(self):
        for observations in (
            [dict(self.observe(), attempt_id="other")],
            [dict(self.observe(), candidate_id="other")],
            [self.observe(), self.observe()],
        ):
            with self.subTest(observations=observations), self.assertRaises(ValueError):
                self.evaluate(observations)

    def test_unavailable_is_distinct_from_failed(self):
        result = self.evaluate([self.observe(3, "unavailable")])
        self.assertIn(["visible-required", "NOT_CONFIGURED"], result["kernel_input"]["gate_results"])

    def test_hidden_grade_cannot_enter_adapter(self):
        with self.assertRaises(TypeError):
            self.evaluate([self.observe()], hidden_grade=True)

    def test_claim_record_cannot_replace_execution(self):
        with self.assertRaises(ValueError):
            self.evaluate(
                [
                    {
                        "schema_version": "evalopt-workflows-v2/1",
                        "record_type": "agent_claim",
                        "attempt_id": "one",
                        "claim": "passed",
                        "artifact_refs": [],
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
