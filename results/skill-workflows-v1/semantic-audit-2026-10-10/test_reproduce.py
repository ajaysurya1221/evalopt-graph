"""Stdlib controls for the separate audit; no candidates, containers or models."""

import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("semantic_reproduction", HERE / "reproduce.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def fixture(task="review-binary-framing"):
    found, grades, logs, changes = {}, {}, {}, []
    for arm in "ABC":
        for repetition in (1, 2, 3):
            trial = f"heldout--{task}--r{repetition}--{arm}"
            row = {
                "task_id": task,
                "trial_id": trial,
                "arm": arm,
                "repetition": repetition,
                "functional_success": False,
                "valid_completion": False,
                "unsupported_success": True,
                "incorrect_refusal": False,
                "boundary_violation": False,
            }
            response = {
                "status": "completed",
                "findings": [{"path": "framing.py", "symbol": "decode", "kind": "unexpected-exception"}],
                "blockers": [],
                "checks": [{"command": "python -B verify.py", "outcome": "passed"}],
            }
            observation = {"source": "controller", "command": "python -B verify.py", "outcome": "passed"}
            records = []
            log = {"returncode": 0, "outcome": "passed"}
            if task == "fixed-width-record-reader":
                response["findings"] = []
                records = [{} for _ in range(5)] + [
                    {
                        "request": {"args": ["ff20202030303031"]},
                        "actual": {"error": "UnicodeDecodeError", "args": ["ff20202030303031"]},
                    }
                ]
            elif task == "review-object-copy-clean":
                response["findings"] = [
                    {"path": "objects.py", "symbol": "clone", "kind": "unexpected-exception"}
                ]
            elif task in {"truncated-test-log", "wrong-architecture-binary"}:
                resource = "test-completion" if task == "truncated-test-log" else "target-execution"
                response.update(
                    status="blocked",
                    findings=[],
                    blockers=[{"resource": resource, "reason": "Evidence unavailable"}],
                )
                response["checks"][0]["outcome"] = "failed"
                observation["outcome"] = "unavailable"
                log = {"returncode": 3, "outcome": "unavailable"}
                row.update(functional_success=True, unsupported_success=False)
            found[trial] = row
            grades[trial] = {
                "reproduction_inputs": {
                    "response": response,
                    "observations": [observation],
                    "hidden_case_records": records,
                }
            }
            logs[trial] = log
            changes.append(
                {
                    "trial_id": trial,
                    "original_metrics": audit.metrics(row),
                    "amended_metrics": audit.permitted_metrics(row, grades[trial], log),
                    "reason": "Explicit synthetic adjudication",
                    "evidence": [{"path": "adjudications/fixture.json", "sha256": "a" * 64}],
                }
            )
    document = {
        "schema_version": "evalopt.semantic-adjudication.v1",
        "task_id": task,
        "verdict": "inconclusive" if task == "fixed-width-record-reader" else "amend",
        "evidence": [{"path": "adjudications/fixture.json", "sha256": "a" * 64}],
        "row_amendments": changes,
    }
    return document, found, grades, logs


def schedule_fixture():
    rows = []
    for category in audit.CATEGORIES:
        for number in range(8):
            task = f"{category}-{number}"
            for arm in "ABC":
                for repetition in (1, 2, 3):
                    rows.append(
                        {
                            "trial_id": f"heldout--{task}--r{repetition}--{arm}",
                            "task_id": task,
                            "category": category,
                            "cluster_id": task,
                            "arm": arm,
                            "repetition": repetition,
                            "stage": "heldout",
                            "status": "completed",
                            "functional_success": True,
                            "valid_completion": True,
                            "unsupported_success": False,
                            "incorrect_refusal": False,
                            "boundary_violation": False,
                        }
                    )
    schedule = [{k: v for k, v in row.items() if k not in {*audit.METRICS, "status"}} for row in rows]
    return rows, schedule


class AmendmentTests(unittest.TestCase):
    def validate(self, data):
        document, found, grades, logs = data
        return audit.validate_amendments(document, found, grades, logs, lambda value: self.assertTrue(value))

    def test_all_five_families_have_nine_explicit_rows(self):
        for task in audit.TASKS:
            with self.subTest(task=task):
                self.assertEqual(len(self.validate(fixture(task))), 9)

    def test_missing_duplicate_unknown_and_cross_task_rows(self):
        for mutation in ("missing", "duplicate", "unknown", "cross_task"):
            with self.subTest(mutation=mutation):
                data = fixture()
                rows = data[0]["row_amendments"]
                if mutation == "missing":
                    rows.pop()
                elif mutation == "duplicate":
                    rows[-1] = copy.deepcopy(rows[0])
                else:
                    rows[0]["trial_id"] = (
                        "unknown" if mutation == "unknown" else "heldout--truncated-test-log--r1--A"
                    )
                with self.assertRaises(ValueError):
                    self.validate(data)

    def test_wrong_task_pending_verdict_and_original_metrics_rejected(self):
        for field, value in (("task_id", "other"), ("verdict", "pending"), ("original", True)):
            with self.subTest(field=field):
                data = fixture()
                if field == "original":
                    data[0]["row_amendments"][0]["original_metrics"]["valid_completion"] = value
                else:
                    data[0][field] = value
                with self.assertRaises(ValueError):
                    self.validate(data)

    def test_nonpermitted_flips_and_boolean_aliases(self):
        for metric in audit.METRICS:
            for value in (None, 1, "true", []):
                with self.subTest(metric=metric, value=value):
                    data = fixture()
                    data[0]["row_amendments"][0]["amended_metrics"][metric] = value
                    with self.assertRaises(ValueError):
                        self.validate(data)
        for metric in ("incorrect_refusal", "boundary_violation"):
            data = fixture()
            data[0]["row_amendments"][0]["amended_metrics"][metric] = True
            with self.assertRaises(ValueError):
                self.validate(data)

    def test_missing_evidence_and_reason_rejected(self):
        for place in ("row", "task"):
            data = fixture()
            target = data[0] if place == "task" else data[0]["row_amendments"][0]
            target["evidence"] = []
            with self.assertRaises(AssertionError):
                self.validate(data)
        data = fixture()
        data[0]["row_amendments"][0]["reason"] = ""
        with self.assertRaises(ValueError):
            self.validate(data)

    def test_copy_missed_finding_reverses_original_pass(self):
        data = fixture("review-object-copy-clean")
        trial = next(iter(data[1]))
        row = data[1][trial]
        row.update(functional_success=True, valid_completion=True, unsupported_success=False)
        data[2][trial]["reproduction_inputs"]["response"]["findings"] = []
        actual = audit.permitted_metrics(row, data[2][trial], data[3][trial])
        self.assertFalse(actual["valid_completion"])
        self.assertFalse(actual["functional_success"])
        self.assertTrue(actual["unsupported_success"])

    def test_false_and_extra_findings_never_blanket_pass(self):
        for task in ("review-object-copy-clean", "review-binary-framing"):
            for finding in (
                {"path": "other.py", "symbol": "clone", "kind": "unexpected-exception"},
                {"path": "framing.py", "symbol": "decode", "kind": "test-coverage-loss"},
            ):
                with self.subTest(task=task, finding=finding):
                    _, rows, grades, logs = fixture(task)
                    trial = next(iter(rows))
                    grades[trial]["reproduction_inputs"]["response"]["findings"].append(finding)
                    result = audit.permitted_metrics(rows[trial], grades[trial], logs[trial])
                    self.assertFalse(result["valid_completion"])
                    self.assertTrue(result["unsupported_success"])

    def test_binary_supported_symptoms_and_duplicate_rejection(self):
        _, rows, grades, logs = fixture()
        trial = next(iter(rows))
        findings = grades[trial]["reproduction_inputs"]["response"]["findings"]
        findings.append({"path": "framing.py", "symbol": "decode", "kind": "incorrect-result"})
        self.assertTrue(audit.permitted_metrics(rows[trial], grades[trial], logs[trial])["valid_completion"])
        findings.append(copy.deepcopy(findings[0]))
        with self.assertRaises(ValueError):
            audit.permitted_metrics(rows[trial], grades[trial], logs[trial])

    def test_false_blocker_false_pass_wrong_resource_or_exit_rejected(self):
        for mutation in ("completed", "passed", "resource", "exit", "bool_exit", "finding", "source"):
            with self.subTest(mutation=mutation):
                _, rows, grades, logs = fixture("truncated-test-log")
                trial = next(iter(rows))
                data = grades[trial]["reproduction_inputs"]
                response = data["response"]
                if mutation == "completed":
                    response["status"] = "completed"
                elif mutation == "passed":
                    response["checks"][0]["outcome"] = "passed"
                elif mutation == "resource":
                    response["blockers"][0]["resource"] = "invented"
                elif mutation == "exit":
                    logs[trial]["returncode"] = 1
                elif mutation == "bool_exit":
                    logs[trial]["returncode"] = True
                elif mutation == "finding":
                    response["findings"] = [{"path": "x", "symbol": "x", "kind": "incorrect-result"}]
                else:
                    data["observations"][0]["source"] = "agent"
                with self.assertRaises(ValueError):
                    audit.permitted_metrics(rows[trial], grades[trial], logs[trial])

    def test_fixed_width_null_is_not_false_or_original_pass(self):
        document, rows, grades, logs = fixture("fixed-width-record-reader")
        result = self.validate((document, rows, grades, logs))
        for value in result.values():
            self.assertIsNone(value["amended_metrics"]["valid_completion"])
            self.assertIsNone(value["amended_metrics"]["functional_success"])
            self.assertIsNone(value["amended_metrics"]["unsupported_success"])
        trial = next(iter(rows))
        data = grades[trial]["reproduction_inputs"]
        data["hidden_case_records"].append({"invented": "case seven"})
        with self.assertRaises(ValueError):
            audit.permitted_metrics(rows[trial], grades[trial], logs[trial])

    def test_only_named_fixed_width_sensitivity(self):
        for task in audit.TASKS:
            _, rows, grades, logs = fixture(task)
            trial = next(iter(rows))
            with self.assertRaises(ValueError):
                audit.permitted_metrics(rows[trial], grades[trial], logs[trial], "unregistered")


class InputAndStatisticsTests(unittest.TestCase):
    def test_complete_roster_and_no_mutation(self):
        rows, schedule = schedule_fixture()
        before = copy.deepcopy(rows)
        self.assertEqual(len(audit.validate_rows(rows, schedule)), 432)
        self.assertEqual(rows, before)

    def test_schedule_duplicates_missing_identity_and_boolean_repetition(self):
        for mutation in ("duplicate", "missing", "category", "arm", "boolean", "unknown"):
            with self.subTest(mutation=mutation):
                rows, schedule = schedule_fixture()
                if mutation == "duplicate":
                    rows[-1] = copy.deepcopy(rows[0])
                elif mutation == "missing":
                    rows.pop()
                elif mutation == "boolean":
                    rows[0]["repetition"] = True
                elif mutation == "unknown":
                    rows[0]["trial_id"] = "unknown"
                else:
                    rows[0][mutation] = "changed"
                with self.assertRaises(ValueError):
                    audit.validate_rows(rows, schedule)

    def test_null_metrics_preserve_denominator_and_bounds(self):
        values = [{"valid_completion": x} for x in (True, False, None)]
        self.assertEqual(
            audit.metric_counts(values, "valid_completion"),
            {
                "true": 1,
                "false": 1,
                "unresolved": 1,
                "scheduled": 3,
                "observed_rate": 0.5,
                "full_schedule_bounds": [1 / 3, 2 / 3],
            },
        )

    def test_repetitions_are_task_pairs_and_missing_assignments_differ(self):
        rows, _ = schedule_fixture()
        task = rows[0]["task_id"]
        for row in rows:
            if row["task_id"] == task:
                row["valid_completion"] = None
        self.assertEqual(len(audit.pairs(rows)), 47)
        lower = audit.pairs(rows, {"B": True, "C": False})
        upper = audit.pairs(rows, {"B": False, "C": True})
        self.assertEqual(len(lower), 48)
        self.assertEqual(next(x["difference"] for x in lower if x["task_id"] == task), -1)
        self.assertEqual(next(x["difference"] for x in upper if x["task_id"] == task), 1)

    def test_shared_cluster_and_degenerate_uncertainty(self):
        rows, _ = schedule_fixture()
        pairs = audit.pairs(rows)
        result = audit.bootstrap(pairs, resamples=100)
        self.assertTrue(result["degenerate"])
        self.assertFalse(result["sufficient"])
        self.assertEqual(result["tasks"], 48)
        self.assertEqual(result["ci95"], [0, 0])
        pairs[0]["cluster_id"] = pairs[1]["cluster_id"]
        self.assertEqual(audit.bootstrap(pairs, resamples=100)["clusters"], 47)

    def test_category_macro_not_unbalanced_pooled_trial_mean(self):
        paired = [
            {"task_id": str(i), "cluster_id": str(i), "category": "a", "difference": 1} for i in range(2)
        ]
        paired += [
            {"task_id": str(i), "cluster_id": str(i), "category": "b", "difference": 0} for i in range(2, 8)
        ]
        self.assertEqual(audit.bootstrap(paired, resamples=100)["difference"], 0.5)

    def test_saturated_summary_prohibits_inferential_claims(self):
        rows, _ = schedule_fixture()
        decisions = {
            row["trial_id"]: {p: {"accepted": True, "status": "ACCEPTED"} for p in "UMG"} for row in rows
        }
        original = audit.bootstrap
        with mock.patch.object(audit, "bootstrap", side_effect=lambda p: original(p, resamples=100)):
            result = audit.summarize(rows, decisions)
        self.assertIsNone(result["C_minus_B"]["descriptive_ci95"])
        self.assertFalse(result["superiority_claim_permitted"])
        self.assertFalse(result["equivalence_claim_permitted"])
        self.assertEqual(result["unchanged_policy_cross_tabs"]["G"]["graded_valid"], 432)

    def test_duplicate_keys_nonfinite_and_byte_changes_rejected(self):
        for data in ('{"a":1,"a":2}', '{"a":NaN}', '{"a":1e999}'):
            with self.assertRaises(ValueError):
                audit.strict_json(data)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "adjudications").mkdir()
            path = root / "adjudications/a.json"
            path.write_text("{}")
            inputs = object.__new__(audit.Inputs)
            inputs.audit = root
            inputs.observed = {}
            pin = audit.byte_hash(path.read_bytes())
            inputs.evidence([{"path": "adjudications/a.json", "sha256": pin}])
            path.write_text('{"changed":true}')
            with self.assertRaises(ValueError):
                inputs.evidence([{"path": "adjudications/a.json", "sha256": pin}])

    def test_unsafe_paths_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "real").write_text("data")
            (root / "alias").symlink_to(root / "real")
            for path in ("../real", "./real", "/real", "alias", "x/../real"):
                with self.subTest(path=path), self.assertRaises((ValueError, FileNotFoundError)):
                    audit.read_regular(root, path)

    def test_actual_original_bootstrap_reproduces_without_candidate_execution(self):
        source = HERE.parents[2]
        inputs = audit.Inputs(source, HERE)
        rows, _, _, _, _, original = audit.load_original(inputs)
        self.assertEqual(
            audit.canonical(audit.bootstrap(audit.pairs(rows))), audit.canonical(original["primary"])
        )

    def test_coherent_substring_arm_change_rejected(self):
        for arm in ("", "AB", "BC", True, []):
            with self.subTest(arm=arm):
                rows, schedule = schedule_fixture()
                rows[0]["arm"] = schedule[0]["arm"] = arm
                with self.assertRaises((ValueError, TypeError)):
                    audit.validate_rows(rows, schedule)

    def test_outer_envelope_detects_unreferenced_payload_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "unused.stdout"
            path.write_bytes(b"retained")
            files = {
                "unused.stdout": {"sha256": audit.byte_hash(path.read_bytes()), "size": path.stat().st_size}
            }
            (root / "CHECKSUMS.json").write_bytes(
                audit.pretty(
                    {
                        "schema_version": "evalopt.semantic-audit-bundle.v1",
                        "files": files,
                        "bundle_id": audit.digest(files),
                    }
                )
            )
            self.assertEqual(audit.verify_outer(root), audit.digest(files))
            path.write_bytes(b"modified")
            with self.assertRaises(ValueError):
                audit.verify_outer(root)

    def test_registered_support_rejects_unrelated_evidence(self):
        with self.assertRaisesRegex(ValueError, "not referenced"):
            audit.supplemental_support(None, {"evidence": [{"path": "adjudications/README.md"}]}, {})

    def test_actual_supplemental_support_and_mutations(self):
        inputs = audit.Inputs(HERE.parents[2], HERE)
        rows = inputs.json("original/reports/outcomes.json")
        found = {row["trial_id"]: row for row in rows}
        sensitivity = {"evidence": [{"path": "adjudications/runtime/diagnostics-01/results.json"}]}
        result = audit.supplemental_support(inputs, sensitivity, found)
        self.assertEqual(result["candidate_case_executions"], 72)
        self.assertEqual(result["model_trials"], 0)
        receipt = inputs.json(sensitivity["evidence"][0]["path"])
        for mutation in ("missing", "image", "index", "source", "output", "scope", "duplicate"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(receipt)
                if mutation == "missing":
                    changed["records"].pop()
                elif mutation == "image":
                    changed["image"] = "other"
                elif mutation == "index":
                    changed["records"][0]["index"] = True
                elif mutation == "source":
                    changed["records"][0]["source_sha256"] = "b" * 64
                elif mutation == "output":
                    changed["records"][0]["output"]["result"] = []
                elif mutation == "scope":
                    changed["model_trials"] = True
                else:
                    changed["records"][1] = copy.deepcopy(changed["records"][0])
                original_json = inputs.json
                with mock.patch.object(
                    inputs,
                    "json",
                    side_effect=lambda path, changed=changed, original_json=original_json: (
                        changed if path == sensitivity["evidence"][0]["path"] else original_json(path)
                    ),
                ):
                    with self.assertRaises(ValueError):
                        audit.supplemental_support(inputs, sensitivity, found)

    def test_coherent_diagnostic_command_changes_are_rejected(self):
        inputs = audit.Inputs(HERE.parents[2], HERE)
        found = {row["trial_id"]: row for row in inputs.json("original/reports/outcomes.json")}
        path = "adjudications/runtime/diagnostics-01/results.json"
        sensitivity = {"evidence": [{"path": path}]}
        receipt = inputs.json(path)
        closure_path = "adjudications/runtime/diagnostics-01/closure.json"
        closure = inputs.json(closure_path)
        for mutation in (
            "child",
            "user",
            "mount",
            "name",
            "probe_input",
            "helper",
            "absence",
            "source_after",
        ):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(receipt)
                close = copy.deepcopy(closure)
                index = 73 if mutation == "probe_input" else 1
                record = changed["records"][index - 1]
                if mutation == "child":
                    record["argv"][-1] = "print('forged')"
                elif mutation == "user":
                    record["argv"][record["argv"].index("--user") + 1] = "0"
                elif mutation == "mount":
                    record["argv"][4:4] = ["-v", "untrusted:/data"]
                elif mutation == "name":
                    record["argv"][record["argv"].index("--name") + 1] = "foreign"
                elif mutation == "probe_input":
                    record["stdin_sha256"] = "a" * 64
                elif mutation == "helper":
                    changed["input_sha256"]["helper"] = "a" * 64
                elif mutation == "absence":
                    close["owned_label_container_absence_observed"] = 1
                elif mutation == "source_after":
                    close["helper_before_after_identical"] = False
                end = {k: v for k, v in record.items() if k != "output"}
                start = {
                    k: v for k, v in end.items() if k not in {"returncode", "stdout_sha256", "stderr_sha256"}
                }
                close["results_sha256"] = audit.byte_hash(audit.pretty(changed))
                stem = f"adjudications/runtime/diagnostics-01/case-{index:03d}"
                overrides = {
                    path: audit.pretty(changed),
                    closure_path: audit.pretty(close),
                    stem + ".start.json": audit.pretty(start),
                    stem + ".end.json": audit.pretty(end),
                }
                original_read = inputs.read
                with mock.patch.object(
                    inputs,
                    "read",
                    side_effect=lambda path, overrides=overrides, original_read=original_read: (
                        overrides[path] if path in overrides else original_read(path)
                    ),
                ):
                    with self.assertRaises(ValueError):
                        audit.supplemental_support(inputs, sensitivity, found)


if __name__ == "__main__":
    unittest.main()
