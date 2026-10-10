import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.accounting import derive_usage
from evalopt_v2.analysis import reconcile
from evalopt_v2.descriptive import kernel_metrics, outcomes, resources
from evalopt_v2.registration import schedule
from test_accounting import family
from test_study import tasks


class DescriptiveTests(unittest.TestCase):
    def test_missing_secondary_outcomes_remain_unknown(self):
        rows = reconcile(tasks(), [])
        result = outcomes(rows)
        self.assertEqual(result["C"]["functional_success"]["unknown"], 72)
        self.assertEqual(result["B"]["incorrect_refusal"]["false"], 0)

    def test_disputed_functional_grade_is_unknown_but_observed_violation_remains(self):
        row = {
            **schedule(tasks(), "heldout")[0],
            "valid_completion": False,
            "functional_success": False,
            "contract_dispute": True,
            "boundary_violation": True,
        }
        result = outcomes(reconcile(tasks(), [row]))[row["arm"]]
        self.assertEqual(result["functional_success"]["false"], 0)
        self.assertEqual(result["boundary_violation"]["true"], 1)

    def test_dispute_masks_oracle_dependent_secondary_metrics_across_all_arms(self):
        rows = [
            {
                **row,
                "valid_completion": True,
                "functional_success": True,
                "unsupported_success": False,
                "incorrect_refusal": False,
                "boundary_violation": False,
            }
            for row in schedule(tasks(), "heldout")
        ]
        disputed = rows[0]["task_id"]
        for row in rows:
            if row["task_id"] == disputed:
                row.update(unsupported_success=True, incorrect_refusal=True)
        rows[0].update(contract_dispute=True, boundary_violation=True)
        before = copy.deepcopy(rows)
        result = outcomes(reconcile(tasks(), rows))
        self.assertEqual(rows, before)
        for arm in "ABCD":
            for metric in ("functional_success", "unsupported_success", "incorrect_refusal"):
                self.assertEqual(result[arm][metric]["unknown"], 3)
                self.assertEqual(result[arm][metric]["scheduled"], 72)
            for metric in ("unsupported_success", "incorrect_refusal"):
                self.assertEqual(result[arm][metric]["true"], 0)
                self.assertEqual(result[arm][metric]["false"], 69)
            self.assertEqual(result[arm]["boundary_violation"]["unknown"], 0)
        self.assertEqual(result[rows[0]["arm"]]["boundary_violation"]["true"], 1)

    def test_resource_lower_bounds_are_not_exact_totals(self):
        scheduled = schedule(tasks(), "heldout")
        trial = scheduled[0]
        usage = derive_usage(family(child_ending=None))
        attempts = [{"trial_id": trial["trial_id"], "attempt": 1, "usage": usage, "agent_wall_seconds": 600}]
        result = resources(scheduled, attempts)[trial["arm"]]
        self.assertIsNone(result["exact_totals"])
        self.assertGreater(result["observed_lower_bounds"]["input_tokens"], 0)
        self.assertEqual(result["partial_usage_attempts"], 1)
        self.assertFalse(result["efficiency_claim_allowed"])

    def test_all_attempts_count_once_including_infrastructure_retry(self):
        scheduled = schedule(tasks(), "heldout")
        trial = scheduled[0]
        usage = derive_usage(family())
        attempts = [{"trial_id": trial["trial_id"], "attempt": number, "usage": usage} for number in (1, 2)]
        result = resources(scheduled, attempts)[trial["arm"]]
        self.assertEqual(result["attempts"], 2)
        self.assertEqual(result["exact_totals"]["input_tokens"], 2 * usage["exact_totals"]["input_tokens"])
        with self.assertRaises(ValueError):
            resources(scheduled, attempts + attempts[:1])

    def test_unavailable_usage_is_not_zero(self):
        scheduled = schedule(tasks(), "heldout")
        trial = scheduled[0]
        result = resources(
            scheduled, [{"trial_id": trial["trial_id"], "attempt": 1, "usage": derive_usage({})}]
        )[trial["arm"]]
        self.assertIsNone(result["observed_lower_bounds"]["input_tokens"])
        self.assertIsNone(result["agent_wall_seconds_observed"])

    def test_reject_everything_has_zero_coverage_and_false_rejection(self):
        rows = [
            {
                "trial_id": "one",
                "valid_completion": True,
                "policies": {
                    "U": {"accepted": True},
                    "M": {"accepted": False},
                    "G": {"accepted": False, "decision": {"status": "BLOCKED"}},
                },
            }
        ]
        result = kernel_metrics(rows)
        self.assertEqual(result["G"]["approval_coverage"], 0)
        self.assertEqual(result["G"]["false_rejection"], 1)

    def test_artifact_failure_and_abstention_are_not_rejections(self):
        rows = [
            {
                "trial_id": "one",
                "valid_completion": None,
                "policies": {"G": {"accepted": False, "decision": {"status": "UNVERIFIED"}}},
            }
        ]
        result = kernel_metrics(rows)
        self.assertEqual(result["M"]["artifact_failures"], 1)
        self.assertEqual(result["M"]["rejected"], 0)
        self.assertEqual(result["G"]["abstained"], 1)
        self.assertEqual(result["G"]["unknown_outcomes"], 1)


if __name__ == "__main__":
    unittest.main()
