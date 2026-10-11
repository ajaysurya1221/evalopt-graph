"""Only authored local fixtures run here; no live agent outputs or model calls."""

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("authored_task_qa", HERE / "tasks" / "qa.py")
qa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qa)


class TaskControls(unittest.TestCase):
    def test_catalog_allocation(self):
        catalog = qa.strict_json((qa.ROOT / "catalog.json").read_bytes())
        qa.validate_tasks(catalog, "development")

    def test_unknown_task_rejected(self):
        with self.assertRaises(ValueError):
            qa.load("undeclared")

    def test_finite_oracle_rejects_unregistered_request(self):
        root, _, _ = qa.load("review-query-decoding")
        with self.assertRaises(ValueError):
            qa.oracle_for(root)({"module": "query_pairs", "function": "solve", "args": ["unlisted"]})

    def test_outside_domain_finding_is_incorrect_not_unavailable(self):
        root, task, controls = qa.load("review-query-decoding")
        response = copy.deepcopy(controls["positive_response"])
        response["findings"][0]["witness"]["args"] = ["unlisted"]
        result = qa.verify_task(
            task,
            root / "agent",
            response,
            [qa.visible_observation(root, root / "agent", task, controls)],
            baseline=root / "baseline",
            oracle=qa.oracle_for(root),
            trusted_fixture=True,
            lifecycle_verified=True,
        )
        self.assertIs(result["grade"]["functional_success"], False)
        self.assertIs(result["grade"]["valid_completion"], False)
        self.assertEqual(
            result["review_witnesses"][0]["not_executed_reason"],
            "witness_outside_published_domain",
        )

    def test_explicit_authored_root_isolated_from_default(self):
        name = "unavailable-cross-worker-replay"
        original, _, _ = qa.load(name)
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            metadata = next(
                row for row in qa.strict_json((qa.ROOT / "catalog.json").read_bytes()) if row["id"] == name
            )
            (target / "catalog.json").write_text(json.dumps([metadata]))
            shutil.copytree(original, target / "development" / name)
            self.assertEqual(qa.load(name, task_root=target)[0], target / "development" / name)
            self.assertEqual(qa.run_task(name, task_root=target)["passed"], 7)
            metadata["id"] = "../outside"
            (target / "catalog.json").write_text(json.dumps([metadata]))
            with self.assertRaises(ValueError):
                qa.load("../outside", task_root=target)
        self.assertEqual(qa.load(name)[0], original)


def control(name):
    def run(self):
        result = qa.run_task(name)
        self.assertGreaterEqual(result["passed"], 7)
        self.assertEqual(result["task_id"], name)

    return run


for metadata in qa.strict_json((qa.ROOT / "catalog.json").read_bytes()):
    setattr(TaskControls, "test_authored_" + metadata["id"].replace("-", "_"), control(metadata["id"]))


if __name__ == "__main__":
    unittest.main()
