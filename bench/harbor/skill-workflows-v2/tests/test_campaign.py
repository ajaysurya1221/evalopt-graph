"""Controller wiring controls use explicit fake dispatch; no agent/model requests."""

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2 import campaign
from evalopt_v2.accounting import derive_usage
from evalopt_v2.preflight import PreDispatchInfrastructureError
from evalopt_v2.records import canonical, task_outcome
from evalopt_v2.store import CampaignStore, read_json
from test_study import registered, tasks


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "campaign"
        self.registration = registered(tasks("development"), "development")
        self.sha = self.registration["registration_sha256"]
        self.store = CampaignStore.create(self.root, self.registration)
        self.first, self.second = self.registration["schedule"][:2]
        self.task = {
            "id": self.first["task_id"],
            "category": self.first["category"],
            "task_contract": "implementation",
            "visible_command": ["verify"],
            "cases": [{"case_id": "case-one"}],
        }
        for row in self.registration["schedule"]:
            path = self.root / "frozen/tasks/development" / row["task_id"]
            path.mkdir(parents=True, exist_ok=True)
            (path / "task.json").write_bytes(
                canonical(dict(self.task, id=row["task_id"], category=row["category"]))
            )
        self.permission = {
            "schema_version": "evalopt-workflows-v2/1",
            "kind": "subscription_permission",
            "ordinary_usage_allowed": True,
            "state": "allowed",
        }
        self.patches = []
        for name, value in (
            ("verify_frozen", lambda *a, **kw: self.store),
            ("__file__", str(self.root / "frozen/harness/evalopt_v2/campaign.py")),
            ("admission_environment", lambda root: {"running_owned_containers": 0}),
            ("subscription_permission", lambda: self.permission),
        ):
            patcher = patch.object(campaign, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.calls = []

    async def synthetic_dispatch(self, row, task_dir, path, *args, freeze_visible):
        self.calls.append(dict(row))
        task = read_json(task_dir / "task.json")
        await freeze_visible(campaign._missing_visible(task, row["attempt_id"]))
        return {
            "attempt_id": row["attempt_id"],
            "verification": None,
            "usage": derive_usage({}),
            "status": "timeout",
            "runtime_identity": {"verified": False},
        }

    def run_campaign(self, limit=1, dispatch=None, continuation="continue"):
        def projection(task, result, permission):
            grade = campaign.unavailable_grade(
                task, result["attempt_id"], "synthetic_timeout", timed_out=True
            )
            grade["runtime_identity_verified"] = False
            return grade, {"decision": continuation, "reasons": []}

        with (
            patch.object(campaign, "execute_one", dispatch or self.synthetic_dispatch),
            patch.object(campaign, "project_result", projection),
        ):
            return asyncio.run(campaign.execute_campaign(self.root, expected_sha256=self.sha, limit=limit))

    def test_sequential_limit_continuation_and_no_duplicate(self):
        result = self.run_campaign(2)
        self.assertEqual(result["state"], "dispatch_limit_reached")
        self.assertEqual(
            [row["trial_id"] for row in self.calls], [self.first["trial_id"], self.second["trial_id"]]
        )
        first_bytes = (self.store.path(self.first["trial_id"]) / "final.json").read_bytes()
        self.run_campaign(1)
        self.assertEqual(len(set(row["trial_id"] for row in self.calls)), 3)
        self.assertEqual((self.store.path(self.first["trial_id"]) / "final.json").read_bytes(), first_bytes)

    def test_timeout_is_a_failure_despite_missing_runtime_telemetry(self):
        grade = campaign.unavailable_grade(self.task, "attempt", "missing", timed_out=True)
        row = campaign.outcome_row(self.first, grade)
        self.assertIs(row["valid_completion"], False)
        self.assertIsNone(row["functional_success"])
        self.assertEqual(
            grade["unrun_case_roster"],
            [{"case_id": "case-one", "execution_state": "not_run", "reason": "missing"}],
        )

    def test_runtime_ineligible_normal_grade_retains_raw_but_reports_unknown(self):
        outcome = task_outcome(
            "attempt",
            "implementation",
            functional_success=True,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=True,
        )
        row = campaign.outcome_row(self.first, {"outcome": outcome, "runtime_identity_verified": False})
        self.assertIsNone(row["valid_completion"])
        self.assertIsNone(row["functional_success"])
        self.assertIs(row["raw_valid_completion"], True)
        self.assertIs(row["raw_functional_success"], True)

    def test_stopping_failure_prevents_every_later_dispatch(self):
        result = self.run_campaign(4, continuation="stop")
        self.assertEqual(result["state"], "stopped")
        self.assertEqual(len(self.calls), 1)
        with self.assertRaises(ValueError):
            self.run_campaign(4)
        self.assertEqual(len(self.calls), 1)

    def test_subscription_pause_and_fresh_resume_without_attempt(self):
        self.permission.update(ordinary_usage_allowed=False, state="exhausted")
        result = self.run_campaign(1)
        self.assertEqual(result["state"], "paused_subscription")
        self.assertFalse(self.store.trial_root(self.first["trial_id"]).exists())
        self.permission.update(ordinary_usage_allowed=True, state="allowed")
        self.run_campaign(1)
        self.assertEqual(len(self.calls), 1)
        self.assertTrue((self.root / "admission/pause-0001/resume.json").exists())

    def test_only_one_classified_precreation_retry(self):
        calls = 0

        async def dispatch(*args, **kwargs):
            nonlocal calls
            calls += 1
            raise PreDispatchInfrastructureError("offline_test")

        result = self.run_campaign(4, dispatch)
        self.assertEqual(result["state"], "stopped_infrastructure_retry_exhausted")
        self.assertEqual(calls, 2)
        self.assertEqual(self.store.attempt_number(self.first["trial_id"]), 2)
        self.assertFalse(self.store.trial_root(self.second["trial_id"]).exists())
        self.store.verify_trial(self.first["trial_id"])

    def test_generic_exception_preserved_unfinalized_and_no_resume(self):
        result = self.run_campaign(
            4, AsyncMock(side_effect=ValueError("secret-like diagnostic must not be copied"))
        )
        self.assertEqual(result["state"], "stopped_unfinalized")
        failure = read_json(self.store.path(self.first["trial_id"]) / "controller-failure.json")
        self.assertEqual(failure["error_type"], "ValueError")
        self.assertNotIn("secret-like", str(failure))
        with self.assertRaises(ValueError):
            self.run_campaign()

    def test_postcreation_transport_failure_never_retries(self):
        async def dispatch(row, task_dir, path, *args, **kwargs):
            path.mkdir()
            raise PreDispatchInfrastructureError("late_failure")

        result = self.run_campaign(4, dispatch)
        self.assertEqual(result["state"], "stopped_unfinalized")
        self.assertFalse((self.store.trial_root(self.first["trial_id"]) / "retry.json").exists())

    def test_unfrozen_controller_and_invalid_limit_rejected(self):
        with patch.object(campaign, "__file__", __file__), self.assertRaises(ValueError):
            self.run_campaign()
        with self.assertRaises(ValueError):
            self.run_campaign(True)

    def test_production_continuation_preserves_timeout_and_stops_other_failures(self):
        from evalopt_v2.lifecycle import close_attempt
        from test_capture import IDENTITY, FakeController, good_usage

        closure = close_attempt(
            FakeController(), IDENTITY, self.root / "closure-fixture", ["/workspace"], reason="deadline"
        )
        result = {
            "attempt_id": "attempt",
            "verification": None,
            "status": "timeout",
            "closure": closure,
            "usage": good_usage(),
            "runtime_identity": {"verified": True},
            "case_boundary_confirmed": True,
        }
        grade, decision = campaign.project_result(self.task, result, self.permission)
        self.assertIs(grade["outcome"]["valid_completion"], False)
        self.assertEqual(decision["decision"], "continue")
        for key, value in (
            ("runtime_identity", {"verified": False}),
            ("case_boundary_confirmed", False),
            ("capture_error_type", "ValueError"),
        ):
            changed = dict(result, **{key: value})
            self.assertEqual(
                campaign.project_result(self.task, changed, self.permission)[1]["decision"], "stop"
            )
        blocked = dict(self.permission, ordinary_usage_allowed=False, state="exhausted")
        self.assertEqual(
            campaign.project_result(self.task, result, blocked)[1]["reasons"],
            ["subscription_permission_unavailable"],
        )

    def test_disputed_task_never_supplies_known_kernel_truth(self):
        rows = [
            dict(row, valid_completion=(index == 0), functional_success=True, contract_dispute=(index == 0))
            for index, row in enumerate(self.registration["schedule"][:4])
        ]
        resolved = campaign.reconcile(self.registration["tasks"], rows, "development")
        stopped = [
            {"trial_id": row["trial_id"], "valid_completion": row["valid_completion"], "policies": None}
            for row in rows
        ]
        projected = campaign.kernel_ground_truth(stopped, resolved)
        self.assertTrue(all(row["valid_completion"] is None for row in projected))
        self.assertIs(projected[0]["raw_valid_completion"], True)
        self.assertEqual(campaign.kernel_metrics(projected)["M"]["false_rejection"], 0)
        self.assertEqual(campaign.kernel_metrics(projected)["M"]["unknown_outcomes"], 4)

    def test_nested_operator_lock_excludes_dispatch(self):
        with self.store.lock(), self.assertRaises(BlockingIOError):
            self.run_campaign()
        self.assertFalse(self.calls)


class AdmissionTests(unittest.TestCase):
    def test_storage_quiescence_and_daemon_fail_closed(self):
        import subprocess
        from collections import namedtuple

        Disk = namedtuple("Disk", "total used free")
        with (
            patch.object(campaign.shutil, "disk_usage", return_value=Disk(9, 8, 1)),
            self.assertRaises(ValueError),
        ):
            campaign.admission_environment(".")
        with patch.object(campaign.shutil, "disk_usage", return_value=Disk(9, 1, 3 * 1024**3)):
            for result in (
                subprocess.CompletedProcess([], 0, stdout=b"owned-container\n"),
                subprocess.CalledProcessError(1, []),
            ):
                with (
                    patch.object(
                        campaign.subprocess,
                        "run",
                        side_effect=result if isinstance(result, Exception) else None,
                        return_value=result,
                    ),
                    self.assertRaises((ValueError, subprocess.CalledProcessError)),
                ):
                    campaign.admission_environment(".")


if __name__ == "__main__":
    unittest.main()
