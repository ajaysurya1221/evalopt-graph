"""Offline diagnostic transport controls. No Docker subprocess is invoked."""

import base64
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("diagnose_under_test", ROOT / "diagnose.py")
diagnose = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnose)
BUNDLE = ROOT.parents[2] / "heldout-comparison-2026-10-10/bundle"


class DiagnosticControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.destination = Path(self.temp.name) / "fresh"
        self.rows = [
            {
                "trial_id": "synthetic",
                "case_number": 1,
                "source_sha256": "a" * 64,
                "snapshot_sha256": "b" * 64,
                "payload": {"source": "# never executed", "request": {"args": []}},
            }
        ]

    def run_fake(self, command, **kwargs):
        self.assertEqual(kwargs["timeout"], 15)
        self.assertIs(kwargs["preexec_fn"], diagnose.cap_capture_files)
        kwargs["stdout"].write(b'{"synthetic":true}\n')
        return SimpleNamespace(returncode=0)

    def test_restrictions_no_mounts_or_environment(self):
        command = diagnose.argv("owned", "pass")
        for option, expected in (
            ("--network", "none"),
            ("--pull", "never"),
            ("--user", "65534:65534"),
            ("--cap-drop", "ALL"),
            ("--memory", "256m"),
            ("--cpus", "1"),
            ("--pids-limit", "64"),
        ):
            self.assertEqual(command[command.index(option) + 1], expected)
        self.assertIn("--read-only", command)
        self.assertEqual(command[-4:], ["-I", "-B", "-c", "pass"])
        self.assertFalse({"--mount", "-v", "--env", "-e", "--env-file"} & set(command))

    def test_exact_retained_roster_source_and_no_expectations(self):
        rows = diagnose.prepared_cases(BUNDLE)
        self.assertEqual(len(rows), 72)
        self.assertEqual(len({row["trial_id"] for row in rows}), 9)
        for row in rows:
            self.assertEqual(set(row["payload"]), {"source", "request"})
            self.assertEqual(set(row["payload"]["request"]), {"module", "function", "args"})

    def test_source_tamper_rejected_before_dispatch(self):
        original = Path.read_text

        def changed(path, *args, **kwargs):
            value = original(path, *args, **kwargs)
            if path.name == "snapshot.json":
                parsed = json.loads(value)
                parsed["nodes"]["records.py"]["data"] = base64.b64encode(b"pass\n").decode()
                return json.dumps(parsed)
            return value

        with patch.object(Path, "read_text", changed):
            with self.assertRaisesRegex(ValueError, "source differs"):
                diagnose.prepared_cases(BUNDLE)

    def test_regular_file_capture_bound(self):
        with patch.object(diagnose.resource, "setrlimit") as setlimit:
            diagnose.cap_capture_files()
        setlimit.assert_called_once_with(diagnose.resource.RLIMIT_FSIZE, (1048576, 1048576))

    def test_success_records_source_and_outputs(self):
        with patch.object(diagnose, "prepared_cases", return_value=self.rows):
            result = diagnose.execute(BUNDLE, self.destination, run=self.run_fake)
        self.assertEqual(len(result["records"]), 2)
        self.assertEqual(result["records"][0]["output"], {"synthetic": True})
        self.assertEqual(result["model_trials"], 0)
        self.assertFalse(result["original_trials_modified"])
        self.assertNotIn("payload", result["records"][0])

    def test_existing_destination_refused(self):
        self.destination.mkdir()
        runner = Mock()
        with self.assertRaisesRegex(ValueError, "fresh"):
            diagnose.execute(BUNDLE, self.destination, run=runner)
        runner.assert_not_called()

    def test_timeout_preserved_and_no_further_dispatch(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired("synthetic", 15))
        with patch.object(diagnose, "prepared_cases", return_value=self.rows):
            with self.assertRaisesRegex(RuntimeError, "transport timeout"):
                diagnose.execute(BUNDLE, self.destination, run=runner)
        self.assertEqual(runner.call_count, 1)
        failure = json.loads((self.destination / "case-001.failure.json").read_text())
        self.assertEqual(failure["container_absence"], "unverified")
        self.assertFalse(failure["further_dispatch"])
        self.assertFalse((self.destination / "results.json").exists())

    def test_stderr_aborts_and_is_retained(self):
        def failed(command, **kwargs):
            kwargs["stderr"].write(b"synthetic failure")
            return SimpleNamespace(returncode=0)

        runner = Mock(side_effect=failed)
        with patch.object(diagnose, "prepared_cases", return_value=self.rows):
            with self.assertRaisesRegex(RuntimeError, "transport failed"):
                diagnose.execute(BUNDLE, self.destination, run=runner)
        self.assertEqual(runner.call_count, 1)
        self.assertEqual((self.destination / "case-001.stderr").read_bytes(), b"synthetic failure")

    def test_overall_deadline_blocks_next_dispatch(self):
        runner = Mock()
        with patch.object(diagnose, "prepared_cases", return_value=self.rows):
            with self.assertRaises(TimeoutError):
                diagnose.execute(BUNDLE, self.destination, run=runner, monotonic=Mock(side_effect=[0, 301]))
        runner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
