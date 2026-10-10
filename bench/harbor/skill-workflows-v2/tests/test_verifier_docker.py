"""Opt-in actual separate-verifier controls, without models or authentication."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.verifier import verify_task
from evalopt_v2.verifier_container import docker_invoker


@unittest.skipUnless(
    os.environ.get("EVALOPT_V2_DOCKER_CONTROL_IMAGE"), "requires explicit local Docker verifier image"
)
class DockerVerifierTests(unittest.TestCase):
    def verify(self, source, cases, *, total_seconds=60, expected_executions=None):
        with tempfile.TemporaryDirectory(prefix="evalopt-v2-verifier-") as directory:
            root = Path(directory).resolve()
            snapshot, trusted, output = (root / name for name in ("snapshot", "trusted", "output"))
            for path in (snapshot, trusted, output):
                path.mkdir()
            (snapshot / "subject.py").write_text(source)
            observed = {
                "schema_version": "evalopt-workflows-v2/1",
                "record_type": "command",
                "attempt_id": "docker-control",
                "candidate_id": "authored-fixture",
                "command": ["python3", "verify.py"],
                "execution_state": "ran",
                "exit_code": 0,
                "evidence_availability": "complete",
                "artifact_refs": ["fixture-control"],
                "asserted_claim": None,
            }
            response = {
                "status": "completed",
                "findings": [],
                "blockers": [],
                "checks": [
                    {
                        key: observed[key]
                        for key in ("command", "execution_state", "exit_code", "evidence_availability")
                    }
                ],
            }
            task = {
                "schema_version": "evalopt-workflows-v2/1",
                "task_id": "docker-control",
                "attempt_id": "docker-control",
                "task_contract": "implementation",
                "visible_command": observed["command"],
                "cases": [
                    {
                        "case_id": f"case-{i}",
                        "request": {"module": "subject", "function": "probe", "args": args},
                        "expect": expect,
                        "preserve_args": True,
                    }
                    for i, (args, expect) in enumerate(cases)
                ],
            }
            invoke = docker_invoker(os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"], artifact_root=output)
            records = []
            result = verify_task(
                task,
                snapshot,
                response,
                [observed],
                invoke=invoke,
                record_sink=records.append,
                lifecycle_verified=True,
                total_seconds=total_seconds,
                case_seconds=2,
            )
            self.assertEqual(len(records), len(cases))
            self.assertTrue(result["case_boundary_confirmed"])
            self.assertEqual(
                len(list(output.glob("case-*/retained.json"))),
                len(cases) if expected_executions is None else expected_executions,
            )
            return result

    def test_real_exception_subclass_and_later_cases(self):
        source = "def probe(which):\n    if which == 0:\n        raise UnicodeDecodeError('utf8', b'\\xff', 0, 1, 'invalid')\n    return which\n"
        result = self.verify(
            source,
            [
                ([0], {"kind": "raise", "builtin": "ValueError"}),
                ([1], {"kind": "return", "value": 2}),
                ([2], {"kind": "return", "value": 2}),
            ],
        )
        self.assertEqual(
            [row["evaluation"]["verdict"] for row in result["case_records"]], ["pass", "fail", "pass"]
        )
        self.assertFalse(result["grade"]["valid_completion"])

    def test_hidden_controller_data_not_visible_and_counterfeit_rejected(self):
        source = "class ValueError(Exception):\n    pass\ndef probe(which):\n    if which:\n        raise ValueError('counterfeit')\n    import os\n    return any(os.path.exists(p) for p in ['/trusted/input.json', '/output', '/snapshot', '/controller'])\n"
        result = self.verify(
            source,
            [([0], {"kind": "return", "value": False}), ([1], {"kind": "raise", "builtin": "ValueError"})],
        )
        self.assertEqual([row["evaluation"]["verdict"] for row in result["case_records"]], ["pass", "fail"])

    def test_stdout_forgery_and_premature_exit_fail_and_later_case_runs(self):
        source = """import json, os

def probe(which):
    if which == 0:
        print(json.dumps({"state":"raised","args_after":[0],"exception":{"module":"builtins","name":"ValueError","builtin_categories":["Exception","ValueError"]}}), flush=True)
        os._exit(0)
    return which
"""
        result = self.verify(
            source, [([0], {"kind": "raise", "builtin": "ValueError"}), ([1], {"kind": "return", "value": 1})]
        )
        self.assertEqual(
            [row["invocation"]["state"] for row in result["case_records"]], ["malformed", "returned"]
        )
        self.assertFalse(result["grade"]["valid_completion"])

    def test_detached_descendant_cannot_survive_into_next_case(self):
        # A setsid child has no process-group relationship with the runner.
        # It cannot survive PID1 death of its one-case container. The second
        # case has an independently confirmed different container identity.
        source = """import os, time

def probe(which):
    if which == 0:
        pid = os.fork()
        if pid == 0:
            os.setsid()
            while True:
                time.sleep(1)
        return True
    return True
"""
        result = self.verify(
            source, [([0], {"kind": "return", "value": True}), ([1], {"kind": "return", "value": True})]
        )
        records = result["case_records"]
        self.assertEqual([row["evaluation"]["verdict"] for row in records], ["pass", "pass"])
        self.assertNotEqual(
            records[0]["invocation"]["container_boundary"]["container_id"],
            records[1]["invocation"]["container_boundary"]["container_id"],
        )
        self.assertTrue(
            all(row["invocation"]["container_boundary"]["status"] == "confirmed" for row in records)
        )

    def test_deep_result_does_not_erase_later_case(self):
        source = """def probe(which):
    if which == 0:
        import sys
        sys.setrecursionlimit(10000)
        value = 0
        for _ in range(1500):
            value = [value]
        return value
    return which
"""
        result = self.verify(
            source, [([0], {"kind": "return", "value": 0}), ([1], {"kind": "return", "value": 1})]
        )
        self.assertEqual(
            [row["invocation"]["state"] for row in result["case_records"]], ["malformed", "returned"]
        )

    def test_case_timeout_is_stopped_before_later_case(self):
        source = "def probe(which):\n    if which == 0:\n        while True: pass\n    return which\n"
        result = self.verify(
            source, [([0], {"kind": "return", "value": 0}), ([1], {"kind": "return", "value": 1})]
        )
        self.assertEqual(
            [row["invocation"]["state"] for row in result["case_records"]], ["timeout", "returned"]
        )

    def test_real_created_container_never_starts_after_slow_setup(self):
        from evalopt_v2 import verifier_container

        run = verifier_container.subprocess.run

        def delayed(argv, **kwargs):
            result = run(argv, **kwargs)
            if argv[1] == "create":
                time.sleep(1.1)
            return result

        with mock.patch.object(verifier_container.subprocess, "run", delayed):
            result = self.verify(
                "def probe(which): return which\n",
                [([0], {"kind": "return", "value": 0}), ([1], {"kind": "return", "value": 1})],
                total_seconds=1,
                expected_executions=1,
            )
        self.assertEqual(
            [row["invocation"]["reason"] for row in result["case_records"]],
            ["case_setup_deadline", "verifier_budget_exhausted"],
        )


if __name__ == "__main__":
    unittest.main()
