"""Controller-owned append-only attempt records and content-addressed evidence.

The directory must stay outside every agent sandbox. Hashes detect post-capture changes;
they do not establish who produced an observation or guarantee filesystem immutability.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .common import bytes_digest, canonical_bytes, digest, read_json, safe_name, write_once
from .manifest import schedule_identity
from .policies import evaluate_policies, replay_policies, validate_visible

INFRA_FAILURES = {
    "container_start",
    "container_transport",
    "provider_unavailable",
    "subscription_exhausted",
    "controller_interrupted",
    "verifier_infrastructure",
}
TERMINAL = {"completed", "agent_failure", "timeout", "budget_exhausted", "infra_failure"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CampaignStore:
    def __init__(self, root: Path | str, schedule: list[dict]):
        supplied = Path(root).absolute()
        if any(path.is_symlink() for path in (supplied, *supplied.parents)):
            raise ValueError("store must not traverse symlinks")
        self.root = supplied
        self.root.mkdir(parents=True, exist_ok=True)
        self.schedule_sha256 = schedule_identity(schedule)
        self.trials = {row["trial_id"]: row for row in schedule}
        registration = {
            "schema_version": "evalopt.workflow-schedule.v1",
            "schedule": schedule,
            "schedule_sha256": self.schedule_sha256,
        }
        target = self.root / "schedule.json"
        try:
            write_once(target, registration)
        except FileExistsError:
            if read_json(target) != registration:
                raise ValueError("store schedule changed") from None

    def _trial(self, trial_id: str) -> Path:
        safe_name(trial_id)
        if trial_id not in self.trials:
            raise ValueError("unscheduled trial")
        return self.root / "trials" / trial_id

    def _attempt(self, trial_id: str, attempt: int) -> Path:
        if type(attempt) is not int or attempt not in (1, 2):
            raise ValueError("only original attempt and one infrastructure retry are allowed")
        path = self._trial(trial_id) / f"attempt-{attempt}"
        start = read_json(path / "start.json")
        if start["trial_id"] != trial_id or start["schedule_sha256"] != self.schedule_sha256:
            raise ValueError("attempt identity changed")
        if any(parent.is_symlink() for parent in (path, *path.parents)):
            raise ValueError("attempt must not traverse symlinks")
        return path

    def start_attempt(self, trial_id: str) -> int:
        trial = self._trial(trial_id)
        trial.mkdir(parents=True, exist_ok=True)
        first = trial / "attempt-1"
        attempt = 1
        if first.exists():
            if (first / "finalize.json").exists():
                self.recover_attempt(trial_id, 1)
            finish = first / "finish.json"
            if not finish.exists():
                raise ValueError("trial is running or interrupted; explicitly classify before retry")
            self.verify_attempt(trial_id, 1)
            previous = read_json(finish)
            if previous["status"] != "infra_failure" or previous["error_code"] not in INFRA_FAILURES:
                raise ValueError("only classified infrastructure failures may be retried")
            attempt = 2
        path = trial / f"attempt-{attempt}"
        path.mkdir()  # Exclusive creation rejects duplicate concurrent dispatch.
        write_once(
            path / "start.json",
            {
                "schema_version": "evalopt.workflow-attempt.v1",
                "trial_id": trial_id,
                "attempt": attempt,
                "schedule_sha256": self.schedule_sha256,
                "started_at": _now(),
            },
        )
        return attempt

    def _open_attempt(self, trial_id: str, attempt: int) -> Path:
        path = self._attempt(trial_id, attempt)
        if (path / "finish.json").exists() or (path / "finalize.json").exists():
            raise ValueError("attempt already finished")
        return path

    def _capture(self, path: Path, namespace: str, artifacts: dict[str, bytes]) -> list[dict]:
        records = []
        for name, content in sorted(artifacts.items()):
            safe_name(name)
            if not isinstance(content, bytes):
                raise ValueError("artifact content must be bytes")
            target = path / namespace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.parent.is_symlink():
                raise ValueError("artifact directory cannot be a symlink")
            with target.open("xb") as stream:
                stream.write(content)
            records.append(
                {"path": f"{namespace}/{name}", "size": len(content), "sha256": bytes_digest(content)}
            )
        return records

    def capture_stopped(self, trial_id: str, attempt: int, artifacts: dict[str, bytes]) -> str:
        path = self._open_attempt(trial_id, attempt)
        if not artifacts:
            raise ValueError("stopped output requires retained artifacts")
        if (path / "stopped.json").exists():
            raise ValueError("stopped output already frozen")
        records = self._capture(path, "agent", artifacts)
        stopped = {
            "schema_version": "evalopt.workflow-stopped.v1",
            "trial_id": trial_id,
            "attempt": attempt,
            "artifacts": records,
        }
        write_once(path / "stopped.json", stopped)
        return digest(stopped)

    def record_visible(self, trial_id: str, attempt: int, visible: dict, logs: dict[str, bytes]) -> None:
        path = self._open_attempt(trial_id, attempt)
        validate_visible(visible)
        stopped = read_json(path / "stopped.json")
        self._verify_artifacts(path, stopped["artifacts"])
        if visible["trial_id"] != trial_id or visible["stopped_sha256"] != digest(stopped):
            raise ValueError("observation does not bind stopped output")
        # Gate evidence must be collected by the caller, not loaded from agent success files.
        available = {bytes_digest(content) for content in logs.values()}
        if any(gate["evidence_sha256"] not in available for gate in visible["gates"]):
            raise ValueError("controller gate log missing")
        if (path / "visible.json").exists():
            raise ValueError("visible observation already frozen")
        records = self._capture(path, "controller", logs)
        write_once(path / "controller-artifacts.json", records)
        write_once(path / "visible.json", visible)

    def decide(self, trial_id: str, attempt: int) -> dict:
        path = self._open_attempt(trial_id, attempt)
        if (path / "grade.json").exists():
            raise ValueError("hidden grade must not precede policies")
        self.verify_attempt(trial_id, attempt)
        result = evaluate_policies(read_json(path / "visible.json"))
        write_once(path / "policies.json", result)
        return result

    def record_grade(self, trial_id: str, attempt: int, grade: dict) -> None:
        path = self._open_attempt(trial_id, attempt)
        self.verify_attempt(trial_id, attempt)
        policies = read_json(path / "policies.json")  # Fails closed until policy file exists.
        write_once(
            path / "grade.json",
            {
                "schema_version": "evalopt.workflow-grade.v1",
                "trial_id": trial_id,
                "stopped_sha256": digest(read_json(path / "stopped.json")),
                "policies_sha256": digest(policies),
                "grade": grade,
            },
        )

    def finish_attempt(
        self,
        trial_id: str,
        attempt: int,
        status: str,
        *,
        error_code: str | None = None,
        usage: dict | None = None,
    ) -> None:
        path = self._attempt(trial_id, attempt)
        if (path / "finalize.json").exists():
            intended = read_json(path / "finalize.json")["finish"]
            if (status, error_code, usage) != (intended["status"], intended["error_code"], intended["usage"]):
                raise ValueError("cannot change a frozen finalization outcome")
            self.recover_attempt(trial_id, attempt)
            return
        path = self._open_attempt(trial_id, attempt)
        if status not in TERMINAL:
            raise ValueError("unknown terminal status")
        if (status == "infra_failure") != (error_code in INFRA_FAILURES):
            raise ValueError("infrastructure status requires a classified infrastructure error")
        if status == "completed":
            for artifact in ("stopped.json", "visible.json", "policies.json", "grade.json"):
                if not (path / artifact).is_file():
                    raise ValueError(f"completed attempt lacks {artifact}")
        self.verify_attempt(trial_id, attempt)
        finish = {
            "schema_version": "evalopt.workflow-finish.v1",
            "trial_id": trial_id,
            "attempt": attempt,
            "status": status,
            "error_code": error_code,
            "usage": usage,
            "finished_at": _now(),
        }
        # Commit the complete intended outcome and hashes before publishing either
        # terminal file. Recovery can replay these bytes; it never rehashes changed
        # evidence into a fresh supposedly successful attempt.
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

    @staticmethod
    def _published_files(path: Path) -> list[Path]:
        # Atomic-write scratch survives an abrupt process kill but is never published
        # as evidence. Retain it for diagnosis; no model can choose this namespace.
        return [
            item
            for item in sorted(path.rglob("*"))
            if item.is_file() and not item.name.startswith(".pending-")
        ]

    @classmethod
    def _artifact_records(cls, path: Path) -> list[dict]:
        return [
            {
                "path": str(item.relative_to(path)),
                "size": item.stat().st_size,
                "sha256": bytes_digest(item.read_bytes()),
            }
            for item in cls._published_files(path)
        ]

    def recover_attempt(self, trial_id: str, attempt: int) -> dict:
        """Reconcile a stopped controller's interrupted publication without changing outcomes.

        Invoke only after the controller owning the attempt has stopped. An empty
        directory created before start publication becomes an infrastructure failure;
        the original directory is retained and consumes the same one-retry allowance.
        """
        if type(attempt) is not int or attempt not in (1, 2):
            raise ValueError("invalid recovery attempt")
        path = self._trial(trial_id) / f"attempt-{attempt}"
        if not path.is_dir() or any(item.is_symlink() for item in (path, *path.parents)):
            raise ValueError("recovery requires an existing safe attempt directory")
        if not (path / "start.json").exists():
            if self._published_files(path):
                raise ValueError("cannot recover an unregistered nonempty attempt")
            write_once(
                path / "start.json",
                {
                    "schema_version": "evalopt.workflow-attempt.v1",
                    "trial_id": trial_id,
                    "attempt": attempt,
                    "schedule_sha256": self.schedule_sha256,
                    "started_at": _now(),
                    "recovered_before_dispatch": True,
                },
            )
            self.finish_attempt(trial_id, attempt, "infra_failure", error_code="controller_interrupted")
            return self.verify_attempt(trial_id, attempt)
        self._attempt(trial_id, attempt)
        if not (path / "finalize.json").exists():
            if (path / "manifest.json").exists():
                return self.verify_attempt(trial_id, attempt)
            raise ValueError(
                "attempt has no frozen finalization; classify controller interruption explicitly"
            )
        intent = read_json(path / "finalize.json")
        if (
            intent.get("schema_version"),
            intent.get("trial_id"),
            intent.get("attempt"),
            intent.get("schedule_sha256"),
        ) != (
            "evalopt.workflow-finalize.v1",
            trial_id,
            attempt,
            self.schedule_sha256,
        ):
            raise ValueError("finalization identity changed")
        self._verify_artifacts(path, intent["artifacts"])
        allowed = {item["path"] for item in intent["artifacts"]} | {
            "finalize.json",
            "finish.json",
            "manifest.json",
        }
        if {str(item.relative_to(path)) for item in self._published_files(path)} - allowed:
            raise ValueError("unexpected artifact after finalization freeze")
        finish = intent["finish"]
        records = list(intent["artifacts"])
        for name, value in (("finalize.json", intent), ("finish.json", finish)):
            raw = canonical_bytes(value) + b"\n"
            records.append({"path": name, "size": len(raw), "sha256": bytes_digest(raw)})
        manifest = {"schema_version": "evalopt.workflow-artifacts.v1", "artifacts": records}
        for name, value in (("finish.json", finish), ("manifest.json", manifest)):
            target = path / name
            try:
                write_once(target, value)
            except FileExistsError:
                if target.read_bytes() != canonical_bytes(value) + b"\n":
                    raise ValueError("finalization artifact differs from frozen intent") from None
        return self.verify_attempt(trial_id, attempt)

    @staticmethod
    def _verify_artifacts(path: Path, records: list[dict]) -> None:
        seen = set()
        for record in records:
            relative = Path(record["path"])
            if relative.is_absolute() or ".." in relative.parts or relative.as_posix() in seen:
                raise ValueError("invalid or duplicate artifact path")
            seen.add(relative.as_posix())
            target = path / relative
            if any(item.is_symlink() for item in (target, *target.parents)) or not target.is_file():
                raise ValueError("missing artifact or unsafe path")
            data = target.read_bytes()
            if len(data) != record["size"] or bytes_digest(data) != record["sha256"]:
                raise ValueError("captured artifact changed")

    def verify_attempt(self, trial_id: str, attempt: int) -> dict:
        path = self._attempt(trial_id, attempt)
        if (path / "finish.json").exists() and not (path / "manifest.json").exists():
            raise ValueError("finished attempt lacks immutable artifact manifest")
        if (path / "stopped.json").exists():
            self._verify_artifacts(path, read_json(path / "stopped.json")["artifacts"])
        if (path / "visible.json").exists():
            visible = validate_visible(read_json(path / "visible.json"))
            logs = read_json(path / "controller-artifacts.json")
            self._verify_artifacts(path, logs)
            if visible["stopped_sha256"] != digest(read_json(path / "stopped.json")):
                raise ValueError("stopped identity mismatch")
            if any(
                gate["evidence_sha256"] not in {item["sha256"] for item in logs} for gate in visible["gates"]
            ):
                raise ValueError("gate lacks controller log")
        replay = None
        if (path / "policies.json").exists():
            replay = replay_policies(read_json(path / "visible.json"), read_json(path / "policies.json"))
            if not replay:
                raise ValueError("policy replay differs")
        if (path / "grade.json").exists():
            grade = read_json(path / "grade.json")
            if grade["policies_sha256"] != digest(read_json(path / "policies.json")) or grade[
                "stopped_sha256"
            ] != digest(read_json(path / "stopped.json")):
                raise ValueError("grade is not bound to frozen output and policies")
        if (path / "manifest.json").exists():
            records = read_json(path / "manifest.json")["artifacts"]
            self._verify_artifacts(path, records)
            actual = {str(item.relative_to(path)) for item in self._published_files(path)} - {"manifest.json"}
            if actual != {item["path"] for item in records}:
                raise ValueError("unexpected or missing artifact")
        return {"trial_id": trial_id, "attempt": attempt, "verified": True, "kernel_replay": replay}

    def statuses(self) -> list[dict]:
        result = []
        for trial_id in self.trials:
            trial = self._trial(trial_id)
            attempts = sorted(trial.glob("attempt-*")) if trial.exists() else []
            status = "pending"
            if attempts:
                latest = attempts[-1]
                status = (
                    read_json(latest / "finish.json")["status"]
                    if (latest / "finish.json").exists()
                    else "running_or_interrupted"
                )
                if status == "infra_failure" and len(attempts) == 1:
                    status = "retryable_infrastructure"
            result.append({"trial_id": trial_id, "status": status, "attempts": len(attempts)})
        return result

    def export_rows(self) -> list[dict]:
        """Return every scheduled trial, including unavailable and unstarted outcomes."""
        rows = []
        for state in self.statuses():
            row = dict(self.trials[state["trial_id"]])
            row.update(status=state["status"], valid_completion=None)
            if state["attempts"]:
                attempt = state["attempts"]
                self.verify_attempt(state["trial_id"], attempt)
                path = self._attempt(state["trial_id"], attempt)
                if (path / "grade.json").exists():
                    grade = read_json(path / "grade.json")["grade"]
                    if not isinstance(grade, dict):
                        raise ValueError("grade must be an object")
                    reserved = set(row).intersection(grade) - {"valid_completion"}
                    if reserved:
                        raise ValueError("grade may not rewrite trial identity or status")
                    row.update(grade)
                if (path / "finish.json").exists():
                    row["usage"] = read_json(path / "finish.json")["usage"]
                if row["status"] in {"agent_failure", "timeout", "budget_exhausted"}:
                    row["valid_completion"] = False
            rows.append(row)
        return json.loads(json.dumps(rows))
