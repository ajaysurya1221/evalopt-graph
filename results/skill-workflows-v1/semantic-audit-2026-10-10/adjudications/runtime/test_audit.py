"""Offline semantic, evidence-binding, and scenario-separation controls."""

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("audit_under_test", ROOT / "audit.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
BUNDLE = ROOT.parents[2] / "heldout-comparison-2026-10-10/bundle"


class SemanticRules(unittest.TestCase):
    def test_exception_subclass_satisfies_named_base(self):
        self.assertTrue(
            audit.semantic_case(
                {"args": ["ff"], "raises": "ValueError"}, {"args": ["ff"], "error": "UnicodeDecodeError"}
            )
        )

    def test_unrelated_or_foreign_exception_rejected(self):
        for name in ("TypeError", "records.ValueError", "Exception", "UnicodeErrorFake"):
            with self.subTest(name=name):
                self.assertFalse(
                    audit.semantic_case({"args": [], "raises": "ValueError"}, {"args": [], "error": name})
                )

    def test_argument_mutation_and_missing_args_rejected(self):
        case = {"args": ["0000"], "raises": "ValueError"}
        for actual in ({"error": "ValueError"}, {"error": "ValueError", "args": ["other"]}):
            with self.subTest(actual=actual):
                self.assertFalse(audit.semantic_case(case, actual))

    def test_boolean_integer_result_alias_rejected(self):
        self.assertFalse(audit.semantic_case({"args": [], "result": 1}, {"args": [], "result": True}))

    def test_unknown_never_becomes_failed_or_passed(self):
        values = audit.metrics_for(None)
        for field in ("functional_success", "valid_completion", "unsupported_success"):
            self.assertIsNone(values[field])

    def test_changed_static_source_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact manually audited"):
            audit.source_review(b"def parse_records(x): return []\n", "r1--A")

    def test_empty_probe_roster_rejected(self):
        value = audit.read_json(ROOT / "probe-output.json")
        value["copy_nesting"] = []
        with self.assertRaisesRegex(ValueError, "roster"):
            audit.validate_probe(value)

    def test_changed_recursion_settings_rejected(self):
        value = audit.read_json(ROOT / "probe-output.json")
        value["runtime"]["recursion_limit"] = 10000
        with self.assertRaisesRegex(ValueError, "recursion limit"):
            audit.validate_probe(value)

    def test_changed_network_argv_rejected(self):
        result = audit.read_json(ROOT / "diagnostics-01/results.json")
        command = result["records"][0]["argv"].copy()
        child = command[-1]
        command[command.index("--network") + 1] = "host"
        with self.assertRaisesRegex(ValueError, "isolation arguments"):
            audit.validate_argv(command, probe=False, image=result["image"], child=child)

    def test_added_mount_argv_rejected(self):
        result = audit.read_json(ROOT / "diagnostics-01/results.json")
        command = result["records"][0]["argv"].copy()
        child = command[-1]
        command += ["--mount", "synthetic"]
        with self.assertRaisesRegex(ValueError, "executable arguments"):
            audit.validate_argv(command, probe=False, image=result["image"], child=child)

    def test_diagnostic_missing_case_rejected(self):
        original = audit.read_json

        def modified(path):
            value = original(path)
            if path.name == "results.json":
                value["records"].pop(0)
            return value

        with patch.object(audit, "read_json", side_effect=modified):
            with self.assertRaisesRegex(ValueError, "record roster"):
                audit.diagnostic_evidence(BUNDLE)

    def test_diagnostic_swapped_order_rejected(self):
        original = audit.read_json

        def modified(path):
            value = original(path)
            if path.name == "results.json":
                value["records"][0], value["records"][1] = value["records"][1], value["records"][0]
            return value

        with patch.object(audit, "read_json", side_effect=modified):
            with self.assertRaisesRegex(ValueError, "end differs"):
                audit.diagnostic_evidence(BUNDLE)

    def test_boolean_boundary_alias_rejected(self):
        original = audit.read_json

        def modified(path):
            value = original(path)
            if path.name == "grade.json":
                value["grade"]["boundaries_preserved"] = 1
            return value

        task = original(BUNDLE / "sealed-tasks" / audit.FIXED / "task.json")
        with patch.object(audit, "read_json", side_effect=modified):
            with self.assertRaisesRegex(ValueError, "grade condition"):
                audit.validate_common(BUNDLE, "heldout--fixed-width-record-reader--r1--A", task)


class RetainedEvidence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixed = audit.build_task(BUNDLE, audit.FIXED)
        cls.copy = audit.build_task(BUNDLE, audit.COPY)

    def test_exact_nine_rows_per_family_and_complete_arm_repetition_roster(self):
        for value in (self.fixed, self.copy):
            actual = [row["trial_id"] for row in value["row_amendments"]]
            expected = ["heldout--" + value["task_id"] + "--" + suffix for suffix in audit.SOURCE_PINS]
            self.assertEqual(actual, expected)

    def test_no_original_missing_reply_is_created(self):
        for row in self.fixed["row_amendments"]:
            self.assertEqual(row["amended_metrics"], audit.metrics_for(None))
            cases = row["retained_case_audit"]
            self.assertEqual(sum(case["executed_in_original_trace"] for case in cases), 6)
            for case in cases[6:]:
                self.assertIsNone(case["actual"])
                self.assertIsNone(case["semantic_pass"])

    def test_supplemental_not_folded_into_trace_only(self):
        for name in ("source_assisted", "supplemental_diagnostic"):
            for row in self.fixed["sensitivities"][name]["row_amendments"]:
                self.assertEqual(row["original_metrics"], audit.metrics_for(False))
                self.assertEqual(row["amended_metrics"], audit.metrics_for(True))
                primary = next(x for x in self.fixed["row_amendments"] if x["trial_id"] == row["trial_id"])
                self.assertIsNone(primary["amended_metrics"]["valid_completion"])

    def test_supplemental_contains_all_eight_new_cases_per_source(self):
        rows = self.fixed["sensitivities"]["supplemental_diagnostic"]["row_amendments"]
        for row in rows:
            self.assertEqual([x["case_number"] for x in row["diagnostic_cases"]], list(range(1, 9)))
            self.assertTrue(all(x["original_trace"] is False for x in row["diagnostic_cases"]))

    def test_copy_clean_response_is_not_given_a_free_pass(self):
        clean = next(row for row in self.copy["row_amendments"] if row["trial_id"].endswith("r1--B"))
        self.assertEqual(clean["retained_response"]["findings"], [])
        self.assertEqual(clean["original_metrics"], audit.metrics_for(True))
        self.assertEqual(clean["amended_metrics"], audit.metrics_for(False))

    def test_same_copy_rule_for_every_matching_finding(self):
        for row in self.copy["row_amendments"]:
            expected = row["retained_response"]["findings"] == audit.FINDING
            self.assertIs(row["amended_metrics"]["functional_success"], expected)

    def test_original_inputs_are_hash_bound(self):
        for family in (self.fixed, self.copy):
            for row in family["row_amendments"]:
                for reference in row["evidence"]:
                    path = BUNDLE / reference["path"].removeprefix("original/")
                    self.assertEqual(audit.sha(path.read_bytes()), reference["sha256"])

    def test_generated_decisions_reproduce_exactly(self):
        for value in (self.fixed, self.copy):
            self.assertEqual(value, audit.read_json(ROOT / (value["task_id"] + ".json")))

    def test_artifacts_do_not_contain_private_paths(self):
        data = json.dumps([self.fixed, self.copy])
        for marker in ("/Users/", "/home/", "access_token", "refresh_token"):
            self.assertNotIn(marker, data)

    def test_source_sensitivity_and_primary_objects_are_separate(self):
        value = copy.deepcopy(self.fixed)
        value["sensitivities"]["source_assisted"]["row_amendments"][0]["amended_metrics"][
            "valid_completion"
        ] = False
        self.assertIsNone(value["row_amendments"][0]["amended_metrics"]["valid_completion"])


if __name__ == "__main__":
    unittest.main()
