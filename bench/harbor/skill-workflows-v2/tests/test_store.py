import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.policies import evaluate_visible
from evalopt_v2.records import canonical, digest, task_outcome
from evalopt_v2.store import CampaignStore, exclusive_json, read_json
from test_study import registered, tasks


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        registration = registered(tasks("development"), "development")
        self.expected = registration["registration_sha256"]
        self.store = CampaignStore.create(Path(self.temporary.name).resolve() / "store", registration)
        self.first, self.second = [row["trial_id"] for row in registration["schedule"][:2]]

    def reopen(self):
        return CampaignStore(self.store.root, expected_sha256=self.expected)

    def visible(self):
        attempt = self.first + "--attempt-1"
        observation = {
            "schema_version": "evalopt-workflows-v2/1",
            "record_type": "command",
            "attempt_id": attempt,
            "candidate_id": "snapshot",
            "command": ["verify"],
            "execution_state": "ran",
            "exit_code": 1,
            "evidence_availability": "complete",
            "artifact_refs": ["stdout.bin"],
            "asserted_claim": None,
        }
        bundle = {
            "attempt_id": attempt,
            "snapshot_sha256": "snapshot",
            "task_contract": "implementation",
            "observations": [observation],
            "boundary_violations": [],
            "boundaries_preserved": True,
            "snapshot_status": "complete",
            "execution_boundary": "confirmed",
            "response": None,
        }
        decisions = evaluate_visible(
            bundle,
            check_roster=[{"check_id": "check", "command": ["verify"]}],
            attempt_id=attempt,
            candidate_id="snapshot",
            observed_at="2026-10-11T00:00:00+00:00",
        )
        return bundle, decisions

    def predispatch_visible(self):
        from evalopt_v2.campaign import _missing_visible

        attempt = self.first + "--attempt-1"
        bundle = _missing_visible({"task_contract": "implementation", "visible_command": ["verify"]}, attempt)
        return bundle, evaluate_visible(
            bundle,
            check_roster=[{"check_id": "check", "command": ["verify"]}],
            attempt_id=attempt,
            candidate_id=None,
            observed_at="2026-10-11T00:00:00+00:00",
        )

    def outcome(self):
        return task_outcome(
            self.first + "--attempt-1",
            "implementation",
            functional_success=False,
            boundary_preserved=True,
            claims_supported=False,
            lifecycle_verified=True,
        )

    def finish(self, decision="continue"):
        self.store.record_visible(self.first, *self.visible())
        self.store.record_grade(self.first, {"outcome": self.outcome()})
        self.store.finalize(self.first, self.outcome(), {"decision": decision})

    def test_hidden_grade_before_policy_forbidden(self):
        self.store.start(self.first)
        with self.assertRaises(FileNotFoundError):
            self.store.record_grade(self.first, {"outcome": self.outcome()})

    def test_interrupted_attempt_never_redispatched(self):
        self.store.start(self.first)
        with self.assertRaises(ValueError):
            self.reopen().next_row()

    def test_finalize_then_resume_exact_next_row(self):
        self.store.start(self.first)
        self.finish()
        self.assertEqual(self.reopen().next_row()["trial_id"], self.second)
        with self.assertRaises(FileExistsError):
            self.store.finalize(self.first, self.outcome(), {"decision": "continue"})

    def test_stop_blocks_next(self):
        self.store.start(self.first)
        self.finish("stop")
        with self.assertRaises(ValueError):
            self.store.next_row()

    def test_mutated_artifact_blocks_next(self):
        path = self.store.start(self.first)
        self.finish()
        (path / "grade.json").write_text(json.dumps({"valid_completion": True}))
        with self.assertRaises(ValueError):
            self.store.next_row()

    def test_additional_file_blocks_replay(self):
        path = self.store.start(self.first)
        self.finish()
        (path / "later-success.json").write_text("{}")
        with self.assertRaises(ValueError):
            self.store.verify_trial(self.first)

    def test_recomputed_registration_cannot_replace_external_digest(self):
        path = self.store.root / "registration.json"
        value = copy.deepcopy(self.store.registration)
        value["identities"]["grader"] = "b" * 64
        value["registration_sha256"] = digest(
            {key: item for key, item in value.items() if key != "registration_sha256"}
        )
        path.write_bytes(canonical(value))
        with self.assertRaises(ValueError):
            self.reopen()
        with self.assertRaises(ValueError):
            self.store.next_row()

    def test_reordered_registration_schedule_is_invalid_even_with_new_digest(self):
        value = copy.deepcopy(self.store.registration)
        value["schedule"].reverse()
        value["registration_sha256"] = digest(
            {key: item for key, item in value.items() if key != "registration_sha256"}
        )
        with self.assertRaises(ValueError):
            CampaignStore.create(Path(self.temporary.name).resolve() / "other", value)

    def test_lock_excludes_second_controller(self):
        with self.store.lock():
            with self.assertRaises(BlockingIOError):
                with self.reopen().lock():
                    self.fail("second controller admitted")

    def test_final_outcome_must_match_canonical_grade(self):
        path = self.store.start(self.first)
        self.store.record_visible(self.first, *self.visible())
        self.store.record_grade(self.first, {"outcome": self.outcome()})
        other = task_outcome(
            self.first + "--attempt-1",
            "implementation",
            functional_success=True,
            boundary_preserved=True,
            claims_supported=True,
            lifecycle_verified=True,
        )
        with self.assertRaises(ValueError):
            self.store.finalize(self.first, other, {"decision": "continue"})
        (path / "grade.json").write_text('{"outcome":')
        with self.assertRaises(ValueError):
            self.store.finalize(self.first, self.outcome(), {"decision": "continue"})

    def test_policy_is_recomputed_from_all_retained_inputs(self):
        self.store.start(self.first)
        bundle, decisions = self.visible()
        decisions["M"]["accepted"] = True
        with self.assertRaises(ValueError):
            self.store.record_visible(self.first, bundle, decisions)

    def test_interrupted_atomic_publish_never_exposes_partial_record(self):
        output = self.store.root / "probe.json"
        with patch("evalopt_v2.store.os.link", side_effect=OSError("simulated crash before publication")):
            with self.assertRaises(OSError):
                exclusive_json(output, {"data": "complete"})
        self.assertFalse(output.exists())

    def test_noncanonical_and_duplicate_json_rejected(self):
        path = self.store.root / "registration.json"
        raw = path.read_bytes()
        path.write_bytes(b" " + raw)
        with self.assertRaises(ValueError):
            self.reopen()

        path.write_bytes(b'{"stage":"development",' + raw[1:])
        with self.assertRaises(ValueError):
            self.reopen()

    def test_one_clean_retry_preserves_original_and_timeout_never_retries(self):
        path = self.store.start(self.first)
        self.store.record_visible(self.first, *self.predispatch_visible())
        outcome = task_outcome(
            self.first + "--attempt-1", "implementation", functional_success=None, verifier_status="not_run"
        )
        self.store.record_grade(self.first, {"outcome": outcome})
        exclusive_json(
            path / "infrastructure.json",
            {
                "classification": "docker_inspection_before_container_creation",
                "attempt_id": self.first + "--attempt-1",
                "agent_dispatched": False,
                "container_creation_attempted": False,
            },
        )
        self.store.finalize(
            self.first,
            outcome,
            {"decision": "stop", "reasons": ["docker_inspection_before_container_creation"]},
        )
        first_bytes = (path / "final.json").read_bytes()
        self.store.authorize_infrastructure_retry(self.first)
        self.assertEqual(self.store.next_row()["trial_id"], self.first)
        second = self.store.start(self.first)
        self.assertEqual(second.name, "attempt-2")
        self.assertEqual((path / "final.json").read_bytes(), first_bytes)
        with self.assertRaises(ValueError):
            self.store.authorize_infrastructure_retry(self.first)

    def test_bound_subscription_resume_does_not_consume_later_retry(self):
        self.store.start(self.first)
        self.store.record_visible(self.first, *self.predispatch_visible())
        outcome = self.outcome()
        self.store.record_grade(self.first, {"outcome": outcome})
        self.store.finalize(
            self.first, outcome, {"decision": "stop", "reasons": ["subscription_permission_unavailable"]}
        )
        permission = {
            "schema_version": "evalopt-workflows-v2/1",
            "kind": "subscription_permission",
            "ordinary_usage_allowed": False,
            "state": "exhausted",
        }
        self.store.pause_subscription(permission, stopped_trial_id=self.first)
        self.store.resume_subscription(dict(permission, ordinary_usage_allowed=True, state="allowed"))
        self.first = self.second
        path = self.store.start(self.first)
        self.store.record_visible(self.first, *self.predispatch_visible())
        outcome = task_outcome(
            self.first + "--attempt-1", "implementation", functional_success=None, verifier_status="not_run"
        )
        self.store.record_grade(self.first, {"outcome": outcome})
        exclusive_json(
            path / "infrastructure.json",
            {
                "classification": "docker_inspection_before_container_creation",
                "attempt_id": self.first + "--attempt-1",
                "agent_dispatched": False,
                "container_creation_attempted": False,
            },
        )
        self.store.finalize(
            self.first,
            outcome,
            {"decision": "stop", "reasons": ["docker_inspection_before_container_creation"]},
        )
        self.store.authorize_infrastructure_retry(self.first)
        self.assertEqual(self.store.next_row()["trial_id"], self.first)
        self.assertEqual(self.store.start(self.first).name, "attempt-2")

    def test_retry_rejects_contradictory_execution_and_timeout(self):
        path = self.store.start(self.first)
        self.store.record_visible(self.first, *self.visible())
        outcome = task_outcome(
            self.first + "--attempt-1", "implementation", functional_success=None, verifier_status="not_run"
        )
        self.store.record_grade(self.first, {"outcome": outcome})
        exclusive_json(
            path / "infrastructure.json",
            {
                "classification": "docker_inspection_before_container_creation",
                "attempt_id": self.first + "--attempt-1",
                "agent_dispatched": False,
                "container_creation_attempted": False,
            },
        )
        self.store.finalize(
            self.first,
            outcome,
            {"decision": "stop", "reasons": ["docker_inspection_before_container_creation"]},
        )
        with self.assertRaisesRegex(ValueError, "contradicts"):
            self.store.authorize_infrastructure_retry(self.first)
        changed = copy.deepcopy(read_json(path / "final.json"))
        changed["outcome"] = task_outcome(
            self.first + "--attempt-1",
            "implementation",
            functional_success=None,
            verifier_status="not_run",
            timed_out=True,
        )
        with self.assertRaisesRegex(ValueError, "timeouts"):
            self.store._check_retry_failure(self.first, changed)

    def test_evidence_walk_errors_cannot_seal_partial_inventory(self):
        path = self.store.start(self.first)

        def broken_walk(root, *, onerror, followlinks):
            yield str(root), [], ["start.json"]
            onerror(PermissionError("unreadable fixture directory"))

        with patch("evalopt_v2.store.os.walk", broken_walk), self.assertRaises(PermissionError):
            self.store._artifacts(path)

    def test_arbitrary_failure_does_not_receive_retry(self):
        self.store.start(self.first)
        self.finish("stop")
        with self.assertRaises((ValueError, FileNotFoundError)):
            self.store.authorize_infrastructure_retry(self.first)

    def test_subscription_pause_requires_new_permission_and_does_not_dispatch(self):
        permission = {
            "schema_version": "evalopt-workflows-v2/1",
            "kind": "subscription_permission",
            "ordinary_usage_allowed": False,
            "state": "exhausted",
        }
        self.store.pause_subscription(permission)
        with self.assertRaises(ValueError):
            self.store.next_row()
        with self.assertRaises(ValueError):
            self.store.resume_subscription(permission)
        self.store.resume_subscription(dict(permission, ordinary_usage_allowed=True, state="allowed"))
        self.assertEqual(self.store.next_row()["trial_id"], self.first)
        self.assertFalse(self.store.trial_root(self.first).exists())


if __name__ == "__main__":
    unittest.main()
