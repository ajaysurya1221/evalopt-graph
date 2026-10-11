import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v3.analysis import reconcile
from evalopt_v3.analysis import report as raw_report
from evalopt_v3.registration import (
    CATEGORIES,
    IDENTITIES,
    difficulty_gate,
    registration,
    schedule,
    validate_registration,
)


def tasks(stage="difficulty"):
    return [
        dict(
            id=f"{stage}-case-{category}-{i}",
            category=category,
            split=stage,
            source_cluster=f"{stage}-source-{category}-{i}",
            evidence_opportunity=category == CATEGORIES[-1],
        )
        for category, n in zip(CATEGORIES, (2, 2, 1, 1, 1, 1), strict=True)
        for i in range(n)
    ]


def registered(task_list, stage="difficulty"):
    return registration(task_list, stage, {name: "a" * 64 for name in IDENTITIES})


def report(task_list, rows):
    return raw_report(task_list, rows, registration_record=registered(task_list))


def outcomes():
    passing = {t["id"] for t in tasks()[::2]}
    return [
        dict(
            r,
            valid_completion=r["task_id"] in passing,
            functional_success=r["task_id"] in passing,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=True,
            timed_out=False,
            runtime_identity_verified=True,
            contract_dispute=False,
            incorrect_refusal=False,
            verifier_status="completed",
        )
        for r in schedule(tasks())
    ]


class StudyTests(unittest.TestCase):
    def test_fixed_screen(self):
        a = schedule(tasks())
        self.assertEqual(a, schedule(list(reversed(tasks()))))
        self.assertEqual(len(a), 16)
        self.assertEqual(len({r["trial_id"] for r in a}), 16)
        self.assertEqual({r["arm"] for r in a}, {"B"})
        self.assertEqual({r["repetition"] for r in a}, {1, 2})
        for stage in ("development", "heldout"):
            with self.assertRaises(ValueError):
                schedule(tasks(stage), stage)

    def test_pass_is_not_benchmark_authorization(self):
        gate = difficulty_gate(tasks(), outcomes(), controls_passed=True)
        self.assertTrue(gate["ready"])
        self.assertEqual(gate["next"], "stop_and_report")
        self.assertFalse(gate["larger_benchmark_authorized"])
        value = report(tasks(), outcomes())
        self.assertFalse(value["upgrade_claim_allowed"])
        self.assertFalse(value["mechanism_claim_allowed"])

    def test_reporting_never_manufactures_difficulty(self):
        rows = outcomes()
        before = difficulty_gate(tasks(), rows, controls_passed=True)
        for r in rows:
            r.update(claims_supported=False, valid_completion=False)
        self.assertEqual(before, difficulty_gate(tasks(), rows, controls_passed=True))
        for r in rows:
            r["functional_success"] = True
        self.assertFalse(difficulty_gate(tasks(), rows, controls_passed=True)["ready"])

    def test_bad_ordinary_failures_do_not_supply_headroom(self):
        for patch in (
            {"timed_out": True},
            {"incorrect_refusal": True},
            {"boundary_preserved": False},
            {"lifecycle_verified": False},
            {"verifier_status": "not_run"},
        ):
            rows = outcomes()
            for r in rows:
                if not r["functional_success"]:
                    r.update(patch)
            with self.subTest(patch=patch):
                self.assertFalse(difficulty_gate(tasks(), rows, controls_passed=True)["ready"])

    def test_timeout_only_task_cannot_supply_second_consistent_failure(self):
        rows = outcomes()
        ordinary_failure = next(
            r["task_id"] for r in rows if not r["functional_success"] and r["category"] == CATEGORIES[0]
        )
        other_failure = next(t["id"] for t in tasks() if t["category"] == CATEGORIES[-1])
        for row in rows:
            fail = row["task_id"] in (ordinary_failure, other_failure)
            row.update(
                functional_success=not fail,
                valid_completion=not fail,
                timed_out=row["task_id"] == other_failure,
            )
        result = difficulty_gate(tasks(), rows, controls_passed=True)
        self.assertTrue(result["checks"]["success_range_4_to_12"])
        self.assertTrue(result["checks"]["ordinary_genuine_consistent_failure"])
        self.assertFalse(result["checks"]["two_genuine_consistent_failures"])
        self.assertFalse(result["ready"])

    def test_missing_and_disputed_remain_in_denominator(self):
        rows = outcomes()
        rows[0]["contract_dispute"] = True
        original = copy.deepcopy(rows)
        value = reconcile(tasks(), rows)
        self.assertEqual(rows, original)
        self.assertEqual(sum(r["reported_valid_completion"] is None for r in value), 2)
        self.assertFalse(difficulty_gate(tasks(), rows, controls_passed=True)["ready"])
        self.assertEqual(len(reconcile(tasks(), [])), 16)
        self.assertFalse(difficulty_gate(tasks(), rows[:-1], controls_passed=True)["ready"])

    def test_duplicate_and_forged_rows(self):
        rows = outcomes()
        for altered in (
            rows + [rows[0]],
            [dict(rows[0], arm="C")],
            [dict(rows[0], repetition=True)],
            [dict(rows[0], functional_success=1)],
        ):
            with self.assertRaises(ValueError):
                difficulty_gate(tasks(), altered, controls_passed=True)

    def test_saturation_and_all_failure_block(self):
        for value in (True, False):
            rows = outcomes()
            for r in rows:
                r["functional_success"] = value
            self.assertFalse(difficulty_gate(tasks(), rows, controls_passed=True)["ready"])
        self.assertFalse(difficulty_gate(tasks(), outcomes(), controls_passed=False)["ready"])

    def test_two_attempts_are_not_independent_tasks(self):
        rows = outcomes()
        for r in rows:
            r["functional_success"] = r["repetition"] == 1
        gate = difficulty_gate(tasks(), rows, controls_passed=True)
        self.assertEqual(gate["upstream_successes"], 8)
        self.assertFalse(gate["ready"])

    def test_identity_and_registration_boundaries(self):
        frozen = registered(tasks())
        self.assertEqual(validate_registration(frozen, expected_sha256=frozen["registration_sha256"]), frozen)
        for key, value in (
            ("stage", "heldout"),
            ("larger_benchmark_authorized", True),
            ("comparison_claim_allowed", True),
        ):
            with self.assertRaises(ValueError):
                validate_registration(
                    dict(frozen, **{key: value}), expected_sha256=frozen["registration_sha256"]
                )
        bad = tasks()
        bad[1]["source_cluster"] = bad[0]["source_cluster"]
        with self.assertRaises(ValueError):
            schedule(bad)
        with self.assertRaises(ValueError):
            raw_report(list(reversed(tasks())), [], registration_record=frozen)


if __name__ == "__main__":
    unittest.main()
