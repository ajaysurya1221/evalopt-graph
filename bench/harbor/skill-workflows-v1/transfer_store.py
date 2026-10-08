"""Transfer reward records using the campaign's crash-safe attempt transactions.

These are original verifier outcomes, not authored-suite grades or U/M/G inputs.
Raw Harbor logs and stopped archives stay private; their identities are retained.
"""

from __future__ import annotations

import math

from lib.common import exact, is_digest, read_json, write_once
from lib.store import INFRA_FAILURES, TERMINAL, CampaignStore, _now

USAGE_FIELDS = {
    "schema_version",
    "input_tokens",
    "output_tokens",
    "model_calls",
    "tool_calls",
    "wall_seconds",
    "agent_count",
    "aggregation",
    "child_usage_complete",
    "accounting_status",
    "runtime_valid",
    "returned_models",
    "returned_efforts",
    "cli_versions",
    "entrypoint_load_observed",
    "workflow_exposure_verified",
    "native_agent_stopped",
    "execution_boundary_complete",
    "agent_deadline_expired",
    "native_stop_wall_seconds",
}


def safe_usage(usage):
    return {key: value for key, value in (usage or {}).items() if key in USAGE_FIELDS}


def validate_result(value, scheduled):
    keys = set(scheduled) | {
        "schema_version",
        "status",
        "error_code",
        "upstream_reward",
        "functional_success",
        "artifact_capture_complete",
        "runtime_evidence_complete",
        "execution_boundary_complete",
        "usage",
        "original_result_sha256",
        "raw_artifact_manifest_sha256",
        "evidence_projection",
    }
    exact(value, keys, "transfer result")
    if value["schema_version"] != "evalopt.transfer-retained-result.v1":
        raise ValueError("unsupported transfer result schema")
    if any(value[key] != expected for key, expected in scheduled.items()):
        raise ValueError("transfer result changes registered trial identity")
    if value["status"] not in TERMINAL or (
        (value["status"] == "infra_failure") != (value["error_code"] in INFRA_FAILURES)
    ):
        raise ValueError("invalid transfer result status or infrastructure classification")
    reward = value["upstream_reward"]
    if reward is not None and (
        type(reward) not in (int, float) or not math.isfinite(reward) or reward not in (0, 1)
    ):
        raise ValueError("only original binary upstream rewards are supported")
    expected_success = None if reward is None else bool(reward)
    if value["status"] == "completed" and reward is None:
        raise ValueError("completed transfer requires original verifier reward")
    if reward is not None and value["execution_boundary_complete"] is not True:
        raise ValueError("unbounded transfer execution cannot retain a scored verifier reward")
    if value["functional_success"] is not expected_success:
        raise ValueError("transfer success must preserve original verifier reward")
    if any(
        type(value[key]) is not bool
        for key in ("artifact_capture_complete", "runtime_evidence_complete", "execution_boundary_complete")
    ):
        raise ValueError("transfer completeness flags must be booleans")
    if not isinstance(value["usage"], dict) or set(value["usage"]) - USAGE_FIELDS:
        raise ValueError("private or unsupported transfer usage field")
    complete = value["execution_boundary_complete"] and all(
        value["usage"].get(key) is True
        for key in (
            "child_usage_complete",
            "runtime_valid",
            "workflow_exposure_verified",
            "native_agent_stopped",
            "entrypoint_load_observed",
        )
    )
    if value["runtime_evidence_complete"] is not complete:
        raise ValueError("transfer runtime completeness disagrees with retained observations")
    if not is_digest(value["original_result_sha256"]) or not is_digest(value["raw_artifact_manifest_sha256"]):
        raise ValueError("transfer source artifact identities are unresolved")
    if (
        value["evidence_projection"]
        != "allowlisted controller summary; original logs and archives retained privately"
    ):
        raise ValueError("transfer evidence projection scope changed")
    return value


class TransferStore(CampaignStore):
    """One original plus one classified infrastructure retry; never fabricate policies."""

    def record_visible(self, *args, **kwargs):
        raise ValueError("transfer does not use authored visible observations")

    def decide(self, *args, **kwargs):
        raise ValueError("U/M/G policies are not part of transfer")

    def record_grade(self, *args, **kwargs):
        raise ValueError("transfer preserves upstream rewards, not authored grades")

    def record_result(
        self, trial_id, attempt, result, *, original_result_sha256, raw_artifact_manifest_sha256
    ):
        path = self._open_attempt(trial_id, attempt)
        scheduled = self.trials[trial_id]
        if any(result.get(key) != expected for key, expected in scheduled.items()):
            raise ValueError("runtime result changes registered trial identity")
        record = {
            **scheduled,
            "schema_version": "evalopt.transfer-retained-result.v1",
            **{
                key: result[key]
                for key in (
                    "status",
                    "error_code",
                    "upstream_reward",
                    "functional_success",
                    "artifact_capture_complete",
                    "runtime_evidence_complete",
                    "execution_boundary_complete",
                )
            },
            "usage": safe_usage(result.get("usage")),
            "original_result_sha256": original_result_sha256,
            "raw_artifact_manifest_sha256": raw_artifact_manifest_sha256,
            "evidence_projection": "allowlisted controller summary; original logs and archives retained privately",
        }
        validate_result(record, scheduled)
        write_once(path / "transfer-result.json", record)

    def finish_attempt(self, trial_id, attempt, status, *, error_code=None, usage=None):
        path = self._attempt(trial_id, attempt)
        if (path / "finalize.json").exists():
            intended = read_json(path / "finalize.json")["finish"]
            if (status, error_code, usage) != (intended["status"], intended["error_code"], intended["usage"]):
                raise ValueError("cannot change a frozen finalization outcome")
            self.recover_attempt(trial_id, attempt)
            return
        path = self._open_attempt(trial_id, attempt)
        if status not in TERMINAL or ((status == "infra_failure") != (error_code in INFRA_FAILURES)):
            raise ValueError("invalid transfer terminal status or infrastructure classification")
        if status == "completed" and not (path / "transfer-result.json").is_file():
            raise ValueError("completed transfer lacks its original verifier reward")
        self.verify_attempt(trial_id, attempt)
        if (path / "transfer-result.json").is_file():
            result = read_json(path / "transfer-result.json")
            if (status, error_code, usage) != (result["status"], result["error_code"], result["usage"]):
                raise ValueError("terminal transfer record differs from original result")
        finish = {
            "schema_version": "evalopt.transfer-finish.v1",
            "trial_id": trial_id,
            "attempt": attempt,
            "status": status,
            "error_code": error_code,
            "usage": usage,
            "finished_at": _now(),
        }
        write_once(
            path / "finalize.json",
            {
                "schema_version": "evalopt.workflow-finalize.v1",
                "trial_id": trial_id,
                "attempt": attempt,
                "schedule_sha256": self.schedule_sha256,
                "finish": finish,
                "artifacts": self._artifact_records(path),
            },
        )
        self.recover_attempt(trial_id, attempt)

    def verify_attempt(self, trial_id, attempt):
        path = self._attempt(trial_id, attempt)
        forbidden = {
            "stopped.json",
            "visible.json",
            "controller-artifacts.json",
            "policies.json",
            "grade.json",
        }
        if any((path / name).exists() for name in forbidden):
            raise ValueError("authored grading or U/M/G artifact in transfer store")
        result = super().verify_attempt(trial_id, attempt)
        outcome = None
        if (path / "transfer-result.json").exists():
            outcome = validate_result(read_json(path / "transfer-result.json"), self.trials[trial_id])
        if (path / "finish.json").exists():
            finish = read_json(path / "finish.json")
            if finish["schema_version"] != "evalopt.transfer-finish.v1":
                raise ValueError("unsupported transfer finish schema")
            if finish["status"] == "completed" and (outcome is None or outcome["upstream_reward"] is None):
                raise ValueError("completed transfer has no original verifier reward")
            if outcome and any(finish[key] != outcome[key] for key in ("status", "error_code", "usage")):
                raise ValueError("transfer finish differs from retained reward record")
        return {**result, "kernel_replay": None, "original_reward_retained": outcome is not None}

    def export_rows(self):
        raise ValueError("use the transfer-specific reward report")
