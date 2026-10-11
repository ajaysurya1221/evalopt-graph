"""Fresh difficulty fixture QA only: no live models or previous task imports."""

import copy
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("fresh_task_qa", HERE / "tasks/qa.py")
qa = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(qa)


class FreshTaskControls(unittest.TestCase):
    def test_exact_catalog_and_distinct_source_clusters(self):
        rows = qa.validate_catalog()
        self.assertEqual(len(rows), 8)
        self.assertEqual(len({r["source_cluster"] for r in rows}), 8)
        self.assertTrue(all(r["split"] == "difficulty" for r in rows))

    def test_exact_authored_manifest(self):
        manifest = json.loads((qa.ROOT / "manifest.json").read_text())
        files = {
            p.relative_to(qa.ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in qa.ROOT.rglob("*")
            if p.is_file() and p.name != "manifest.json" and "__pycache__" not in p.parts
        }
        self.assertEqual(manifest["files"], files)
        self.assertEqual(manifest["registered_cases"], 113)
        self.assertEqual(
            manifest["test_source_sha256"], hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        )

    def test_unknown_and_traversal_id_rejected(self):
        for name in ["undeclared", "../atomic-migration-batches", ""]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                qa.load(name)

    def test_finite_review_domain_rejects_unlisted_request(self):
        root, _, _ = qa.load("media-range-precedence")
        with self.assertRaises(qa.OracleDomainError):
            qa.oracle_for(root)({"module": "service", "function": "solve", "args": [{"unlisted": True}]})

    def test_owned_paths_and_findings_contract_are_visible(self):
        for metadata in qa.validate_catalog():
            root, task, _ = qa.load(metadata["id"])
            spec = (root / "agent/SPEC.md").read_text()
            self.assertEqual(spec, task["instruction"])
            self.assertIn("Do not create, remove or rename workspace files", spec)
            self.assertIn("Preserve their modes", spec)
            for name in task["allowed_changes"]:
                self.assertIn(name, spec)
            if task["task_contract"] == "review":
                self.assertIn("Each finding is {path:", spec)
                self.assertIn("Duplicate supported findings are neutral", spec)

    def test_independent_reference_never_delivered_in_agent_snapshot(self):
        for metadata in qa.validate_catalog():
            root, _, _ = qa.load(metadata["id"])
            self.assertTrue((root / "reference.py").is_file())
            self.assertFalse((root / "agent/reference.py").exists())
            self.assertFalse((root / "agent/oracle_cases.json").exists())
            self.assertFalse((root / "agent/task.json").exists())

    def test_source_arguments_are_bound_and_complete(self):
        for metadata in qa.validate_catalog():
            _, task, _ = qa.load(metadata["id"])
            self.assertGreaterEqual(len(task["cases"]), 12)
            self.assertTrue(all(c["preserve_args"] is True for c in task["cases"]))
            self.assertEqual(len({c["case_id"] for c in task["cases"]}), len(task["cases"]))

    def test_explicit_author_root_and_bad_catalog_do_not_fall_back(self):
        root, task, _ = qa.load("atomic-migration-batches")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            meta = next(r for r in qa.validate_catalog() if r["id"] == task["id"])
            (target / "catalog.json").write_text(json.dumps([meta]))
            shutil.copytree(root, target / "difficulty" / task["id"])
            selected, _, _ = qa.load(task["id"], task_root=target)
            self.assertEqual(selected, target / "difficulty" / task["id"])
            changed = copy.deepcopy(meta)
            changed["split"] = "development"
            (target / "catalog.json").write_text(json.dumps([changed]))
            with self.assertRaises(ValueError):
                qa.load(task["id"], task_root=target)


def fixture_control(name):
    def test(self):
        result = qa.run_task(name)
        self.assertGreaterEqual(result["passed"], 10)
        self.assertEqual(result["models_invoked"], 0)
        self.assertEqual(result["task_id"], name)

    return test


for metadata in qa.validate_catalog():
    setattr(
        FreshTaskControls, "test_fixture_" + metadata["id"].replace("-", "_"), fixture_control(metadata["id"])
    )

if __name__ == "__main__":
    unittest.main()
