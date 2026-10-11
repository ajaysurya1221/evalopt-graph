import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.accounting import derive_usage, validate_usage


def event(kind, payload, second=0):
    return {"type": kind, "payload": payload, "timestamp": f"2026-10-11T00:00:{second:02d}Z"}


def session(owner="parent", *, parent=None, start=1, end=10, ending="task_complete", metered=True):
    source = (
        "exec"
        if parent is None
        else {
            "subagent": {"thread_spawn": {"parent_thread_id": parent, "agent_path": "/" + owner, "depth": 1}}
        }
    )
    rows = [
        event("session_meta", {"id": owner, "cli_version": "0.154.0", "source": source}),
        event("turn_context", {"turn_id": owner}),
        event("event_msg", {"type": "task_started", "turn_id": owner}, start),
    ]
    if metered:
        rows.append(
            event(
                "token_usage_record",
                {
                    "thread_id": owner,
                    "turn_id": owner,
                    "response_id": "response-" + owner,
                    "usage": {"input_tokens": 100, "output_tokens": 7},
                },
                start + 1,
            )
        )
    if ending:
        rows.append(event("event_msg", {"type": ending, "turn_id": owner}, end))
    return rows


def add_spawn(rows, child, second=3):
    call = "spawn-" + child
    rows[3:3] = [
        event("response_item", {"type": "function_call", "name": "spawn_agent", "call_id": call}, second),
        event(
            "response_item",
            {
                "type": "function_call_output",
                "call_id": call,
                "output": json.dumps({"task_name": "/" + child}),
            },
            second,
        ),
    ]


def encode(rows):
    return b"".join(json.dumps(row, ensure_ascii=False).encode() + b"\n" for row in rows)


def family(*, child_ending="task_complete", child_metered=True):
    root = session()
    add_spawn(root, "child")
    child = session("child", parent="parent", start=4, end=8, ending=child_ending, metered=child_metered)
    child[1:1] = copy.deepcopy(root)
    return {"root.jsonl": encode(root), "child.jsonl": encode(child)}


class AccountingTests(unittest.TestCase):
    def test_complete_owner_exclusive_counters(self):
        result = derive_usage(family())
        self.assertEqual(result["accounting_status"], "complete")
        self.assertEqual(
            result["exact_totals"],
            {"input_tokens": 200, "output_tokens": 14, "model_calls": 2, "tool_calls": 1},
        )
        self.assertEqual(result["delegation_status"], "verified")
        self.assertTrue(result["efficiency_eligible"])

    def test_aborted_child_retains_known_lower_bound(self):
        result = derive_usage(family(child_ending="turn_aborted"))
        self.assertEqual(result["accounting_status"], "partial")
        self.assertEqual(result["lower_bounds"]["input_tokens"], 200)
        self.assertEqual(result["delegation_status"], "verified")
        self.assertIsNone(result["exact_totals"])
        self.assertFalse(result["efficiency_eligible"])

    def test_missing_end_is_unknown_delegation_not_exceeded(self):
        result = derive_usage(family(child_ending=None))
        self.assertEqual(result["provenance_status"], "valid")
        self.assertEqual(result["delegation_status"], "unverified")
        self.assertIn("owned_turn_end_missing", result["reasons"])

    def test_zero_owned_response_means_only_zero_lower_bound(self):
        result = derive_usage({"root": encode(session(metered=False, ending="turn_aborted"))})
        self.assertEqual(result["lower_bounds"]["model_calls"], 0)
        self.assertEqual(result["accounting_status"], "partial")
        self.assertIsNone(result["exact_totals"])

    def test_partial_tail_retains_only_complete_record_counters(self):
        result = derive_usage({"root": encode(session()) + b'{"payload":'})
        self.assertEqual(result["accounting_status"], "partial")
        self.assertEqual(result["lower_bounds"]["input_tokens"], 100)

    def test_unicode_separator_inside_tool_output(self):
        rows = session()
        rows.insert(3, event("response_item", {"type": "function_call_output", "output": "a\u0085b\u2028c"}))
        self.assertEqual(derive_usage({"root": encode(rows)})["accounting_status"], "complete")

    def test_duplicate_owned_response_invalidates_provenance(self):
        rows = session()
        rows.insert(4, copy.deepcopy(rows[3]))
        self.assertEqual(derive_usage({"root": encode(rows)})["provenance_status"], "invalid")

    def test_unknown_counter_rejected(self):
        rows = session()
        rows[3]["payload"]["usage"]["invented"] = 1
        self.assertEqual(derive_usage({"root": encode(rows)})["reasons"], ["unknown_or_missing_counter"])

    def test_bool_negative_and_missing_counters_rejected(self):
        for bad in (True, -1, None):
            rows = session()
            rows[3]["payload"]["usage"]["input_tokens"] = bad
            with self.subTest(value=bad):
                result = derive_usage({"root": encode(rows)})
                self.assertEqual(result["provenance_status"], "invalid")
                self.assertIsNone(result["lower_bounds"]["input_tokens"])

    def test_forged_copied_counter_rejected(self):
        files = family()
        rows = [json.loads(x) for x in files["child.jsonl"].split(b"\n") if x]
        for row in rows:
            if row["type"] == "token_usage_record" and row["payload"]["thread_id"] == "parent":
                row["payload"]["usage"]["input_tokens"] = 999
        files["child.jsonl"] = encode(rows)
        self.assertEqual(derive_usage(files)["provenance_status"], "invalid")

    def test_missing_child_and_unresolved_spawn_fail_closed(self):
        files = family()
        del files["child.jsonl"]
        self.assertEqual(derive_usage(files)["reasons"], ["child_roster_mismatch"])
        rows = session()
        add_spawn(rows, "child")
        del rows[4]
        self.assertEqual(derive_usage({"root": encode(rows)})["reasons"], ["unresolved_child_roster"])

    def test_depth_and_three_overlapping_children(self):
        root = session(end=20)
        files = {}
        for child in ("one", "two", "three"):
            add_spawn(root, child)
            files[child] = encode(session(child, parent="parent", start=5, end=15))
        files["root"] = encode(root)
        result = derive_usage(files)
        self.assertEqual(result["delegation_status"], "violated")
        self.assertEqual(result["lower_bounds"]["model_calls"], 4)
        child = session("one", parent="parent")
        child[0]["payload"]["source"]["subagent"]["thread_spawn"]["depth"] = 2
        self.assertEqual(
            derive_usage({"root": encode(root), "one": encode(child)})["delegation_status"], "violated"
        )

    def test_nonoverlapping_three_children_allowed(self):
        root = session(end=30)
        files = {}
        for index, child in enumerate(("one", "two", "three")):
            add_spawn(root, child)
            files[child] = encode(session(child, parent="parent", start=4 + index * 5, end=7 + index * 5))
        files["root"] = encode(root)
        self.assertEqual(derive_usage(files)["delegation_status"], "verified")

    def test_unknown_version_and_symlink(self):
        rows = session()
        rows[0]["payload"]["cli_version"] = "different"
        self.assertEqual(derive_usage({"root": encode(rows)})["provenance_status"], "invalid")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "real").write_bytes(encode(session()))
            (root / "link.jsonl").symlink_to(root / "real")
            self.assertEqual(derive_usage(root)["reasons"], ["native_log_symlink"])

    def test_empty_directory_unavailable_not_zero(self):
        result = derive_usage({})
        self.assertEqual(result["provenance_status"], "unavailable")
        self.assertTrue(all(value is None for value in result["lower_bounds"].values()))

    def test_derivation_preserves_all_source_bytes(self):
        files = family()
        before = copy.deepcopy(files)
        derive_usage(files)
        self.assertEqual(before, files)

    def test_projection_validation_rejects_coherent_completeness_and_counter_forgeries(self):
        complete = derive_usage(family())
        self.assertEqual(validate_usage(complete), complete)
        for case in ("bool_counter", "sum", "complete", "extra", "nulls"):
            changed = copy.deepcopy(complete)
            if case == "bool_counter":
                changed["lower_bounds"]["model_calls"] = True
            elif case == "sum":
                changed["agents"][0]["lower_bounds"]["input_tokens"] += 1
            elif case == "complete":
                changed["agents"][0]["complete"] = False
            elif case == "extra":
                changed["private"] = "not allowed"
            elif case == "nulls":
                changed["exact_totals"] = None
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_usage(changed)
        unavailable = derive_usage({})
        validate_usage(unavailable)
        unavailable["lower_bounds"]["model_calls"] = 0
        with self.assertRaisesRegex(ValueError, "fabricates_counters"):
            validate_usage(unavailable)

    def test_partial_tail_cannot_establish_no_unobserved_children(self):
        result = derive_usage({"root": encode(session()) + b'{"type":"session_meta"'})
        self.assertEqual(result["provenance_status"], "valid")
        self.assertEqual(result["delegation_status"], "unverified")

    def test_source_mutation_during_derivation_is_invalid(self):
        from unittest.mock import patch

        with patch(
            "evalopt_v2.accounting.snapshot",
            side_effect=[{"root": encode(session())}, {"root": encode(session()) + b"\n"}],
        ):
            result = derive_usage("unused-read-only-fixture")
        self.assertEqual(result["reasons"], ["native_logs_changed"])


if __name__ == "__main__":
    unittest.main()
