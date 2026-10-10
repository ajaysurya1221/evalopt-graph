import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.records import (
    MAX_CANONICAL_DEPTH,
    MAX_CANONICAL_NODES,
    canonical,
    task_outcome,
    validate_record,
)


class RecordsTests(unittest.TestCase):
    def command(self):
        return {
            "schema_version": "evalopt-workflows-v2/1",
            "record_type": "command",
            "attempt_id": "one",
            "candidate_id": "abc",
            "command": ["./probe"],
            "execution_state": "ran",
            "exit_code": 3,
            "evidence_availability": "unavailable",
            "artifact_refs": [],
            "asserted_claim": "prerequisite unavailable",
        }

    def test_failed_and_unavailable_are_independent(self):
        self.assertEqual(validate_record(self.command())["exit_code"], 3)

    def test_missing_exit_is_not_an_exited_command(self):
        record = self.command()
        record["exit_code"] = None
        with self.assertRaises(ValueError):
            validate_record(record)

    def test_producer_label_does_not_create_authentication(self):
        record = self.command()
        record["producer"] = "controller"
        with self.assertRaises(ValueError):
            validate_record(record)

    def test_claims_never_parse_as_observations(self):
        record = {
            "schema_version": "evalopt-workflows-v2/1",
            "record_type": "agent_claim",
            "attempt_id": "one",
            "claim": "tests pass",
            "artifact_refs": [],
        }
        self.assertEqual(validate_record(record)["record_type"], "agent_claim")

    def test_bool_exit_and_nonfinite_rejected(self):
        for bad in (True, "0", 0.0):
            record = self.command()
            record["exit_code"] = bad
            with self.assertRaises(ValueError):
                validate_record(record)
        for bad in ({1: "a"}, float("nan"), (1, 2)):
            with self.assertRaises(ValueError):
                canonical(bad)

    def test_six_hundred_nested_copy_values_remain_supported(self):
        value = "leaf"
        for _ in range(600):
            value = [value]
        self.assertEqual(canonical(value), b"[" * 600 + b'"leaf"' + b"]" * 600 + b"\n")
        cursor = value
        for _ in range(600):
            self.assertEqual(len(cursor), 1)
            cursor = cursor[0]
        self.assertEqual(cursor, "leaf")

    def test_container_depth_boundary_is_bounded_and_does_not_mutate(self):
        value = None
        for _ in range(MAX_CANONICAL_DEPTH):
            value = [value]
        self.assertEqual(
            canonical(value), b"[" * MAX_CANONICAL_DEPTH + b"null" + b"]" * MAX_CANONICAL_DEPTH + b"\n"
        )
        rejected = [value]
        with self.assertRaisesRegex(ValueError, "JSON depth exceeded"):
            canonical(rejected)
        self.assertIs(rejected[0], value)

    def test_malformed_middle_value_is_rejected_without_mutation(self):
        invalid = object()
        value = {"before": [1, 2], "middle": [invalid], "after": {"value": 3}}
        with self.assertRaises(ValueError):
            canonical(value)
        self.assertEqual(value["before"], [1, 2])
        self.assertIs(value["middle"][0], invalid)
        self.assertEqual(value["after"], {"value": 3})

    def test_cycles_are_rejected_but_shared_values_are_allowed(self):
        shared = {"value": [1, 2]}
        self.assertEqual(canonical([shared, shared]), b'[{"value":[1,2]},{"value":[1,2]}]\n')
        cyclic = []
        cyclic.append(cyclic)
        with self.assertRaisesRegex(ValueError, "cyclic"):
            canonical(cyclic)
        self.assertIs(cyclic[0], cyclic)

    def test_node_budget_bounds_wide_inputs(self):
        value = [None] * MAX_CANONICAL_NODES
        with self.assertRaisesRegex(ValueError, "node budget"):
            canonical(value)
        self.assertEqual(len(value), MAX_CANONICAL_NODES)

    def test_serializer_recursion_failure_is_data_rejection(self):
        with patch("evalopt_v2.records.json.dumps", side_effect=RecursionError("synthetic encoder depth")):
            with self.assertRaisesRegex(ValueError, "serialization depth"):
                canonical({"value": 1})

    def test_unhashable_record_type_is_rejected_cleanly(self):
        for kind in ([], {}):
            value = dict(self.command(), record_type=kind)
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                validate_record(value)

    def test_timeout_false_despite_functional_success(self):
        value = task_outcome(
            "one",
            "implementation",
            functional_success=True,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=None,
            timed_out=True,
        )
        self.assertIs(value["valid_completion"], False)

    def test_normal_unknown_lifecycle_remains_unknown(self):
        value = task_outcome(
            "one",
            "implementation",
            functional_success=True,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=None,
        )
        self.assertIsNone(value["valid_completion"])

    def test_disagreement_is_not_success(self):
        value = task_outcome(
            "one",
            "implementation",
            functional_success=True,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=True,
            contract_dispute=True,
        )
        self.assertIsNone(value["valid_completion"])
        forged = copy.deepcopy(value)
        forged["valid_completion"] = True
        with self.assertRaises(ValueError):
            validate_record(forged)

    def test_derived_outcome_cannot_disagree_with_retained_components(self):
        value = task_outcome("one", "implementation", functional_success=False)
        self.assertFalse(value["functional_success"])
        self.assertIsNone(value["lifecycle_verified"])
        for field, bad in (("valid_completion", None), ("reasons", []), ("timed_out", True)):
            changed = {**value, field: bad}
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_record(changed)


if __name__ == "__main__":
    unittest.main()
