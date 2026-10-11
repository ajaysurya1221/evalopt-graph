import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.git_index import workspace_manifest
from evalopt_v2.materialize import boundary_violations, materialize


class MaterializeTests(unittest.TestCase):
    def test_real_mixed_layers_are_identical_across_arms(self):
        tasks = Path(__file__).resolve().parents[1] / "tasks/development/review-template-values"
        with tempfile.TemporaryDirectory() as directory:
            records = [materialize(tasks, Path(directory).resolve() / arm, arm=arm) for arm in "ABCD"]
            for record in records:
                self.assertEqual(record["initial_sha256"], records[0]["initial_sha256"])
                self.assertTrue(record["git_status"])
                self.assertNotIn("oracle_cases.json", record["initial_manifest"])
                self.assertNotIn("task.json", record["initial_manifest"])
            self.assertEqual(records[2]["instruction"], records[3]["instruction"])
            self.assertIn("$code-review", records[1]["instruction"])
            self.assertNotIn("$eval-opt", records[0]["instruction"])

    def test_existing_destination_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                materialize(Path(directory), Path(directory), arm="A")

    def test_only_owned_file_is_mutable(self):
        before = {
            "code.py": {"kind": "file", "mode": 420, "sha256": "one"},
            "verify.py": "frozen",
            ".git/config": "frozen",
        }
        after = {
            "code.py": {"kind": "file", "mode": 420, "sha256": "two"},
            "verify.py": "changed",
            ".git/config": "frozen",
            "extra.py": "new",
        }
        self.assertEqual(boundary_violations(before, after, ["code.py"]), ["extra.py", "verify.py"])

    def test_owned_file_mode_presence_and_type_are_frozen(self):
        before = {"code.py": {"kind": "file", "mode": 420, "sha256": "one"}}
        for after in (
            {},
            {"code.py": {"kind": "directory", "mode": 420}},
            {"code.py": {"kind": "file", "mode": 493, "sha256": "one"}},
        ):
            self.assertEqual(boundary_violations(before, after, ["code.py"]), ["code.py"])

    def test_hostile_host_git_defaults_do_not_change_workspace_or_run_templates(self):
        task = Path(__file__).resolve().parents[1] / "tasks/development/review-template-values"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            clean = materialize(task, root / "clean", arm="C")
            home = root / "hostile-home"
            config = home / ".config/git"
            config.mkdir(parents=True)
            (config / "ignore").write_text("*.py\n*.md\n")
            (config / "attributes").write_text("*.py working-tree-encoding=UTF-16\n")
            template = root / "templates"
            (template / "hooks").mkdir(parents=True)
            hook = template / "hooks/pre-commit"
            hook.write_text("#!/bin/sh\nexit 99\n")
            hook.chmod(0o755)
            (template / "unexpected-template").write_text("must not enter the workspace")
            (home / ".gitconfig").write_text(f"[init]\n\ttemplateDir = {template}\n")
            with patch.dict(
                os.environ,
                {
                    "HOME": str(home),
                    "XDG_CONFIG_HOME": str(home / ".config"),
                    "GIT_TEMPLATE_DIR": str(template),
                    "GIT_ATTR_NOSYSTEM": "0",
                    "GIT_CONFIG_COUNT": "1",
                    "GIT_CONFIG_KEY_0": "core.excludesFile",
                    "GIT_CONFIG_VALUE_0": str(config / "ignore"),
                },
            ):
                hostile = materialize(task, root / "hostile", arm="D")
            self.assertEqual(clean["initial_manifest"], hostile["initial_manifest"])
            self.assertEqual(clean["git_status"], hostile["git_status"])
            self.assertEqual(clean["instruction"], hostile["instruction"])
            self.assertFalse((root / "hostile/.git/hooks").exists())
            self.assertFalse((root / "hostile/.git/unexpected-template").exists())

    def test_materialized_modes_are_independent_of_calling_umask(self):
        bench = Path(__file__).resolve().parents[1]
        task = bench / "tasks/development/review-template-values"
        script = (
            "import json,os,sys;from pathlib import Path;"
            "sys.path.insert(0,sys.argv[1]);"
            "from evalopt_v2.materialize import materialize;"
            "os.umask(int(sys.argv[4],8));"
            "print(json.dumps(materialize(Path(sys.argv[2]),Path(sys.argv[3]),arm='C')['initial_manifest'],sort_keys=True))"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifests = []
            for mask in ("022", "077"):
                result = subprocess.run(
                    [sys.executable, "-I", "-B", "-c", script, str(bench), str(task), str(root / mask), mask],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                manifests.append(json.loads(result.stdout))
            self.assertEqual(manifests[0], manifests[1])

    def test_real_git_v4_index_remains_captured_as_boundary_violation(self):
        task = Path(__file__).resolve().parents[1] / "tasks/development/review-template-values"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve() / "workspace"
            initial = materialize(task, root, arm="A")["initial_manifest"]
            subprocess.run(
                ["git", "update-index", "--index-version=4"], cwd=root, check=True, capture_output=True
            )
            stopped = workspace_manifest(root)
            self.assertEqual(stopped[".git/index"]["kind"], "git-index-unparsed")
            self.assertEqual(boundary_violations(initial, stopped, []), [".git/index"])


if __name__ == "__main__":
    unittest.main()
