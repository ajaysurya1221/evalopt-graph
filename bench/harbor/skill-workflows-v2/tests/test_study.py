import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.analysis import _contrast, reconcile
from evalopt_v2.analysis import report as raw_report
from evalopt_v2.registration import CATEGORIES, development_gate, registration, schedule


def tasks(stage="heldout"):
    count = 4 if stage == "heldout" else 2
    return [
        {
            "id": f"{stage}-case-{category}-{index}",
            "category": category,
            "split": stage,
            "source_cluster": f"{stage}-source-{category}-{index}",
            "evidence_opportunity": index % 2 == 0,
        }
        for category in CATEGORIES
        for index in range(count)
    ]


def registered(task_list, stage="heldout"):
    names = (
        "tasks",
        "grader",
        "skill_c",
        "skill_d",
        "upstream",
        "parser",
        "continuation_policy",
        "agent_image",
        "verifier_image",
        "analysis",
        "source",
        "controller",
    )
    admission = None
    if stage == "heldout":
        development = tasks("development")
        rows = [
            {**row, "valid_completion": row["task_id"].endswith("-0")}
            for row in schedule(development, "development")
        ]
        admission = {
            "tasks": development,
            "rows": rows,
            "controls_passed": True,
            "revision": 0,
            "result": development_gate(development, rows, controls_passed=True, revision=0),
        }
    return registration(task_list, stage, {name: "a" * 64 for name in names}, development_admission=admission)


def report(task_list, rows):
    return raw_report(task_list, rows, registration_record=registered(task_list))


class StudyTests(unittest.TestCase):
    def test_matched_blocks_and_determinism(self):
        rows = schedule(tasks(), "heldout")
        self.assertEqual(rows, schedule(list(reversed(tasks())), "heldout"))
        self.assertEqual(len(rows), 288)
        self.assertEqual(len({row["trial_id"] for row in rows}), 288)
        for start in range(0, len(rows), 4):
            block = rows[start : start + 4]
            self.assertEqual({row["arm"] for row in block}, {"A", "B", "C", "D"})
            self.assertEqual(len({(row["task_id"], row["repetition"]) for row in block}), 1)

    def test_unknown_and_duplicates_rejected(self):
        row = {**schedule(tasks(), "heldout")[0], "valid_completion": True}
        with self.assertRaises(ValueError):
            reconcile(tasks(), [row, row])
        row["category"] = "forged"
        with self.assertRaises(ValueError):
            reconcile(tasks(), [row])

    def test_dispute_propagates_to_all_arms_without_mutating_originals(self):
        rows = [{**row, "valid_completion": True} for row in schedule(tasks(), "heldout")]
        rows[0]["contract_dispute"] = True
        original = copy.deepcopy(rows)
        resolved = reconcile(tasks(), rows)
        self.assertEqual(rows, original)
        self.assertEqual(sum(row["reported_valid_completion"] is None for row in resolved), 12)
        self.assertTrue(all(row["valid_completion"] for row in resolved))

    def test_missing_rows_retained(self):
        resolved = reconcile(tasks(), [])
        self.assertEqual(len(resolved), 288)
        self.assertTrue(all(row["reported_valid_completion"] is None for row in resolved))

    def test_saturated_tie_is_not_equivalence_or_upgrade(self):
        rows = [{**row, "valid_completion": True} for row in schedule(tasks(), "heldout")]
        result = report(tasks(), rows)
        self.assertEqual(result["conclusion"], "inconclusive")
        self.assertEqual(result["contrasts"]["C-D"]["observed"]["ci95_pp"], [0, 0])
        self.assertFalse(result["upgrade_claim_allowed"])

    def test_known_failure_decides_all_three_consistency_despite_missing_attempt(self):
        task_list = tasks()
        patterns = dict(
            zip(
                (task["id"] for task in task_list[:5]),
                (
                    (False, None, True),
                    (None, True, True),
                    (True, True, True),
                    (False, False, False),
                    (None, None, None),
                ),
                strict=True,
            )
        )
        rows = [
            {
                **row,
                "valid_completion": patterns.get(row["task_id"], (True, True, True))[row["repetition"] - 1],
            }
            for row in schedule(task_list, "heldout")
        ]
        result = report(task_list, rows)
        for arm in "ABCD":
            self.assertEqual(result["arms"][arm]["all_three_success_tasks"], 20)
            self.assertEqual(result["arms"][arm]["all_three_unknown_tasks"], 2)
            self.assertEqual(result["arms"][arm]["unknown"], 5)

    def test_large_variable_benefit_passes_gatekeeping(self):
        rows = [
            {**row, "valid_completion": row["arm"] == "C" or row["task_id"].endswith("-0")}
            for row in schedule(tasks(), "heldout")
        ]
        for row in rows:
            row["functional_success"] = row["valid_completion"]
        result = report(tasks(), rows)
        self.assertTrue(result["mechanism_claim_allowed"])
        self.assertTrue(result["upgrade_claim_allowed"])

    def test_missing_c_destroys_positive_claim(self):
        rows = [
            {**row, "valid_completion": None if row["arm"] == "C" else False}
            for row in schedule(tasks(), "heldout")
        ]
        result = report(tasks(), rows)
        self.assertFalse(result["mechanism_claim_allowed"])
        self.assertEqual(result["arms"]["C"]["unknown"], 72)
        self.assertEqual(result["contrasts"]["C-D"]["unfavorable"]["estimate_pp"], 0)

    def test_development_gate_bounded(self):
        rows = [
            {**row, "valid_completion": row["task_id"].endswith("-0")}
            for row in schedule(tasks("development"), "development")
        ]
        self.assertEqual(
            development_gate(tasks("development"), rows, controls_passed=True, revision=0)["next"],
            "freeze_heldout",
        )
        self.assertEqual(
            development_gate(tasks("development"), rows, controls_passed=False, revision=1)["next"],
            "development_not_ready",
        )
        with self.assertRaises(ValueError):
            development_gate(tasks("development"), rows, controls_passed=True, revision=2)

    def test_registration_requires_every_identity(self):
        with self.assertRaises(ValueError):
            registration(tasks(), "heldout", {})
        modified = tasks()
        modified[1]["source_cluster"] = modified[4]["source_cluster"]
        with self.assertRaises(ValueError):
            schedule(modified, "heldout")

    def test_permutation_does_not_change_bootstrap(self):
        task_list = tasks()
        rows = [
            {**row, "valid_completion": row["arm"] == "C" or row["task_id"].endswith("-0")}
            for row in schedule(task_list, "heldout")
        ]
        resolved = reconcile(task_list, rows)
        options = {"unfavorable": False, "categories": CATEGORIES, "resamples": 1000}
        self.assertEqual(
            _contrast(task_list, resolved, "D", **options),
            _contrast(list(reversed(task_list)), list(reversed(resolved)), "D", **options),
        )

    def test_equal_rational_effects_are_exactly_degenerate(self):
        task_list = tasks()
        rows = []
        for row in schedule(task_list, "heldout"):
            c_passes = 3 if row["task_id"].endswith("-0") else 2
            passes = c_passes if row["arm"] == "C" else c_passes - 1
            rows.append({**row, "valid_completion": row["repetition"] <= passes})
        result = _contrast(
            task_list,
            reconcile(task_list, rows),
            "D",
            unfavorable=False,
            categories=CATEGORIES,
            resamples=1000,
        )
        self.assertEqual(result["status"], "degenerate")
        self.assertEqual(result["ci95_pp"][0], result["ci95_pp"][1])

    def test_development_dispute_and_forged_category_cannot_pass(self):
        task_list = tasks("development")
        rows = [
            {**row, "valid_completion": row["task_id"].endswith("-0")}
            for row in schedule(task_list, "development")
        ]
        rows[0]["contract_dispute"] = True
        self.assertFalse(development_gate(task_list, rows, controls_passed=True, revision=0)["ready"])
        rows[0]["category"] = (
            "ordinary-bug-repair"
            if rows[0]["category"] != "ordinary-bug-repair"
            else "bounded-implementation"
        )
        with self.assertRaises(ValueError):
            development_gate(task_list, rows, controls_passed=True, revision=0)

    def test_analysis_requires_frozen_task_identity(self):
        task_list = tasks()
        frozen = registered(task_list)
        with self.assertRaises(ValueError):
            raw_report(list(reversed(task_list)), [], registration_record=frozen)


if __name__ == "__main__":
    unittest.main()
