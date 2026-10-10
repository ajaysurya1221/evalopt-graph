"""Atomic controller-only evidence store, bound to an external freeze digest.

Keep this directory outside every candidate mount. Hold the campaign lock across
admission/dispatch. This layer verifies evidence consistency; caller-owned
lifecycle observations establish whether the stopped attempt permits admission.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from .framing import strict_json
from .policies import replay_visible
from .records import canonical, digest, validate_record
from .registration import validate_registration


def _safe(name):
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for c in name)
    ):
        raise ValueError("unsafe store component")
    return name


def _sync(descriptor, *, directory=False):
    os.fsync(descriptor)
    if sys.platform == "darwin" and not directory:
        fcntl.fcntl(descriptor, 51)  # F_FULLFSYNC: request durable device-cache flush.


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        _sync(descriptor, directory=True)
    finally:
        os.close(descriptor)


def durable_mkdir(path):
    path.mkdir(mode=0o700)
    sync_directory(path.parent)
    sync_directory(path)


def exclusive_json(path: Path, value):
    """Publish full canonical bytes once; never leave a partial final filename."""
    data = canonical(value)
    if path.parent.resolve() != path.parent or path.is_symlink():
        raise ValueError("unsafe record path")
    temporary = path.parent / (".pending-" + uuid.uuid4().hex)
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        _sync(stream.fileno())
    # A crash before this link leaves only a pending file, never a success record.
    # A retained pending file blocks admission until its exact cleanup is reviewed.
    try:
        os.link(temporary, path, follow_symlinks=False)
        sync_directory(path.parent)
    finally:
        temporary.unlink()
        sync_directory(path.parent)


def read_json(path):
    if path.is_symlink() or path.resolve() != path:
        raise ValueError("unsafe record path")
    raw = path.read_bytes()
    value = strict_json(raw)
    if raw != canonical(value):
        raise ValueError("noncanonical retained record")
    return value


class CampaignStore:
    def __init__(self, root, *, expected_sha256):
        self.root = Path(root).absolute()
        if self.root.resolve() != self.root or not self.root.is_dir():
            raise ValueError("controller store must be an existing real directory")
        self.expected_sha256 = expected_sha256
        self.registration = validate_registration(
            read_json(self.root / "registration.json"), expected_sha256=expected_sha256
        )
        self.scheduled = {row["trial_id"]: row for row in self.registration["schedule"]}

    def _refresh(self):
        if read_json(self.root / "registration.json") != self.registration:
            raise ValueError("registration changed after opening store")
        if list(self.root.glob(".pending-*")):
            raise ValueError("interrupted durable publication requires inspection")

    @classmethod
    def create(cls, root, registration):
        validate_registration(registration, expected_sha256=registration["registration_sha256"])
        root = Path(root).absolute()
        if root.resolve() != root:
            raise ValueError("store parent must not contain symlinks")
        durable_mkdir(root)
        exclusive_json(root / "registration.json", registration)
        durable_mkdir(root / "attempts")
        durable_mkdir(root / "admission")
        return cls(root, expected_sha256=registration["registration_sha256"])

    @contextmanager
    def lock(self):
        descriptor = os.open(self.root / "controller.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._refresh()
            yield
        finally:
            os.close(descriptor)

    def trial_root(self, trial_id):
        _safe(trial_id)
        if trial_id not in self.scheduled:
            raise ValueError("unregistered trial")
        path = self.root / "attempts" / trial_id
        if path.resolve() != path:
            raise ValueError("symlink in attempt path")
        return path

    def attempt_number(self, trial_id):
        root = self.trial_root(trial_id)
        if not root.exists():
            return 1
        names = {child.name for child in root.iterdir()}
        if not names or names - {"attempt-1", "attempt-2", "retry.json"}:
            raise ValueError("interrupted or unexpected trial record")
        if "attempt-2" in names and ("attempt-1" not in names or "retry.json" not in names):
            raise ValueError("retry lacks original evidence and grant")
        return 2 if "attempt-2" in names else 1

    def path(self, trial_id, attempt=None):
        number = self.attempt_number(trial_id) if attempt is None else attempt
        if type(number) is not int or number not in (1, 2):
            raise ValueError("only one clean infrastructure retry permitted")
        path = self.trial_root(trial_id) / f"attempt-{number}"
        if path.resolve() != path:
            raise ValueError("symlink in numbered attempt")
        return path

    def next_row(self):
        self._refresh()
        self._check_pause()
        for trial_id, row in self.scheduled.items():
            trial = self.trial_root(trial_id)
            if not trial.exists():
                return dict(row)
            path = self.path(trial_id)
            if not (path / "final.json").is_file():
                raise ValueError("unfinished attempt blocks admission; never automatically redispatch")
            final = self.verify_trial(trial_id)
            if (trial / "retry.json").exists() and self.attempt_number(trial_id) == 1:
                self._verify_retry(trial_id)
                return dict(row)
            if final["continuation"]["decision"] != "continue":
                if not self._subscription_resume_covers(trial_id, final):
                    raise ValueError("finalized stopping condition blocks admission")
        return None

    def start(self, trial_id):
        next_row = self.next_row()
        if next_row is None or next_row["trial_id"] != trial_id:
            raise ValueError("dispatch must follow original schedule")
        trial = self.trial_root(trial_id)
        if not trial.exists():
            durable_mkdir(trial)
            number = 1
        else:
            self._verify_retry(trial_id)
            number = 2
        path = self.path(trial_id, number)
        durable_mkdir(path)
        exclusive_json(
            path / "start.json",
            {
                "row": next_row,
                "registration_sha256": self.expected_sha256,
                "attempt": number,
                "attempt_id": trial_id + f"--attempt-{number}",
            },
        )
        return path

    def _start(self, trial_id, attempt=None):
        self._refresh()
        number = self.attempt_number(trial_id) if attempt is None else attempt
        value = read_json(self.path(trial_id, number) / "start.json")
        expected = {
            "row": self.scheduled[trial_id],
            "registration_sha256": self.expected_sha256,
            "attempt": number,
            "attempt_id": trial_id + f"--attempt-{number}",
        }
        if value != expected:
            raise ValueError("attempt differs from frozen registration")
        return value

    def record_visible(self, trial_id, visible, policies):
        start = self._start(trial_id)
        path = self.path(trial_id)
        if (path / "grade.json").exists():
            raise ValueError("visible observations must precede hidden grading")
        if visible["attempt_id"] != start["attempt_id"]:
            raise ValueError("visible attempt differs from dispatch")
        replay_visible(visible, policies)
        exclusive_json(path / "visible-policy.json", {"visible": visible, "decisions": policies})
        return {"visible_sha256": digest(visible), "policy_sha256": digest(policies)}

    def record_grade(self, trial_id, grade):
        self._start(trial_id)
        path = self.path(trial_id)
        frozen = read_json(path / "visible-policy.json")
        replay_visible(frozen["visible"], frozen["decisions"])
        validate_record(grade["outcome"])
        if grade["outcome"]["attempt_id"] != frozen["visible"]["attempt_id"]:
            raise ValueError("grade differs from attempt")
        exclusive_json(path / "grade.json", grade)

    def _artifacts(self, path):
        files = {}

        def fail(error):
            raise error

        # rglob may silently skip unreadable directories. An incomplete inventory
        # cannot seal an attempt; every traversal/read error must stop finalization.
        for directory, dirs, names in os.walk(path, onerror=fail, followlinks=False):
            for name in sorted(dirs + names):
                child = Path(directory) / name
                mode = child.lstat().st_mode
                if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                    raise ValueError("unsafe evidence node")
                if child.name.startswith(".pending-"):
                    raise ValueError("interrupted publication cannot be sealed")
                if stat.S_ISREG(mode) and child != path / "final.json":
                    files[child.relative_to(path).as_posix()] = hashlib.sha256(child.read_bytes()).hexdigest()
        return files

    def _validate_contents(self, trial_id, outcome, attempt=None):
        start = self._start(trial_id, attempt)
        path = self.path(trial_id, attempt)
        frozen = read_json(path / "visible-policy.json")
        replay_visible(frozen["visible"], frozen["decisions"])
        grade = read_json(path / "grade.json")
        validate_record(outcome)
        if grade["outcome"] != outcome or outcome["attempt_id"] != start["attempt_id"]:
            raise ValueError("final outcome differs from retained grade")
        if frozen["visible"]["attempt_id"] != start["attempt_id"]:
            raise ValueError("visible evidence differs from attempt")

    def finalize(self, trial_id, outcome, continuation):
        path = self.path(trial_id)
        if (path / "final.json").exists():
            raise FileExistsError(path / "final.json")
        if continuation.get("decision") not in {"continue", "stop"}:
            raise ValueError("explicit continuation decision required")
        self._validate_contents(trial_id, outcome)
        exclusive_json(
            path / "final.json",
            {
                "registration_sha256": self.expected_sha256,
                "row": self.scheduled[trial_id],
                "outcome": outcome,
                "continuation": continuation,
                "files": self._artifacts(path),
            },
        )

    def _verify_attempt(self, trial_id, number):
        self._refresh()
        path = self.path(trial_id, number)
        final = read_json(path / "final.json")
        if (
            final["registration_sha256"] != self.expected_sha256
            or final["row"] != self.scheduled[trial_id]
            or self._artifacts(path) != final["files"]
        ):
            raise ValueError("finalized evidence changed")
        self._validate_contents(trial_id, final["outcome"], number)
        return final

    def verify_trial(self, trial_id):
        number = self.attempt_number(trial_id)
        first = self._verify_attempt(trial_id, 1)
        if number == 1:
            return first
        self._verify_retry(trial_id)
        return self._verify_attempt(trial_id, 2)

    def authorize_infrastructure_retry(self, trial_id):
        """Only the frozen pre-container Docker-inspection class is retryable.

        The controller emits infrastructure.json before any container creation
        or model dispatch. Absence of output, timeout, usage gaps and arbitrary
        exceptions are never substitutes for that affirmative phase observation.
        """
        if self.attempt_number(trial_id) != 1:
            raise ValueError("retry budget exhausted")
        for key in self.scheduled:
            if key == trial_id:
                break
            prior = self.verify_trial(key)
            if prior["continuation"]["decision"] != "continue" and not self._subscription_resume_covers(
                key, prior
            ):
                raise ValueError("earlier stop cannot be waived")
        final = self._verify_attempt(trial_id, 1)
        self._check_retry_failure(trial_id, final)
        exclusive_json(
            self.trial_root(trial_id) / "retry.json",
            {
                "registration_sha256": self.expected_sha256,
                "trial_id": trial_id,
                "next_attempt": 2,
                "first_final_sha256": digest(final),
                "classification": "docker_inspection_before_container_creation",
            },
        )

    def _check_retry_failure(self, trial_id, final):
        expected = {
            "classification": "docker_inspection_before_container_creation",
            "attempt_id": trial_id + "--attempt-1",
            "agent_dispatched": False,
            "container_creation_attempted": False,
        }
        if read_json(self.path(trial_id, 1) / "infrastructure.json") != expected:
            raise ValueError("failure is outside prospectively retryable class")
        if final["outcome"]["valid_completion"] is not None or final["outcome"]["timed_out"]:
            raise ValueError("task outcomes and timeouts are not infrastructure retries")
        frozen = read_json(self.path(trial_id, 1) / "visible-policy.json")
        visible = frozen["visible"]
        if (
            frozen["decisions"]["candidate_id"] is not None
            or visible["snapshot_sha256"] is not None
            or visible["response"] is not None
            or visible["snapshot_status"] != "unavailable"
            or visible["execution_boundary"] != "unconfirmed"
            or any(item["execution_state"] != "not_run" for item in visible["observations"])
            or final["outcome"]["verifier_status"] != "not_run"
            or final["outcome"]["functional_success"] is not None
            or (self.path(trial_id, 1) / "runtime").exists()
        ):
            raise ValueError("retry phase contradicts retained execution evidence")
        if final["continuation"] != {
            "decision": "stop",
            "reasons": ["docker_inspection_before_container_creation"],
        }:
            raise ValueError("other stopping conditions are not waived")

    def _verify_retry(self, trial_id):
        final = self._verify_attempt(trial_id, 1)
        self._check_retry_failure(trial_id, final)
        expected = {
            "registration_sha256": self.expected_sha256,
            "trial_id": trial_id,
            "next_attempt": 2,
            "first_final_sha256": digest(final),
            "classification": "docker_inspection_before_container_creation",
        }
        if read_json(self.trial_root(trial_id) / "retry.json") != expected:
            raise ValueError("retry grant differs from preserved failure")

    def _pause_entries(self):
        root = self.root / "admission"
        entries = sorted(root.iterdir())
        for index, path in enumerate(entries, 1):
            if path.name != f"pause-{index:04d}" or not path.is_dir() or path.is_symlink():
                raise ValueError("invalid admission journal")
        return entries

    def _check_pause(self):
        for path in self._pause_entries():
            paused = read_json(path / "pause.json")
            if paused["registration_sha256"] != self.expected_sha256:
                raise ValueError("pause belongs to another freeze")
            if not (path / "resume.json").exists():
                raise ValueError("subscription pause awaiting fresh permission")
            resumed = read_json(path / "resume.json")
            if (
                resumed["pause_sha256"] != digest(paused)
                or resumed["registration_sha256"] != self.expected_sha256
            ):
                raise ValueError("resume does not bind original pause")
            self._permission(resumed["permission"], allowed=True)

    @staticmethod
    def _permission(record, *, allowed):
        if (
            set(record) != {"schema_version", "kind", "ordinary_usage_allowed", "state"}
            or record["schema_version"] != "evalopt-workflows-v2/1"
            or record["kind"] != "subscription_permission"
            or record["ordinary_usage_allowed"] is not allowed
            or record["state"] not in ({"allowed"} if allowed else {"exhausted", "unavailable"})
        ):
            raise ValueError("fresh native subscription permission required")

    def pause_subscription(self, permission, *, stopped_trial_id=None):
        self._refresh()
        self._permission(permission, allowed=False)
        self._check_pause()
        final_sha = None
        if stopped_trial_id is not None:
            final = self.verify_trial(stopped_trial_id)
            if final["continuation"].get("reasons") != ["subscription_permission_unavailable"]:
                raise ValueError("subscription recovery cannot waive other stop reasons")
            final_sha = digest(final)
        path = self.root / "admission" / f"pause-{len(self._pause_entries()) + 1:04d}"
        durable_mkdir(path)
        exclusive_json(
            path / "pause.json",
            {
                "registration_sha256": self.expected_sha256,
                "permission": permission,
                "stopped_trial_id": stopped_trial_id,
                "stopped_final_sha256": final_sha,
            },
        )

    def resume_subscription(self, permission):
        """Caller obtains a fresh native permission; this never retries an attempt."""
        self._refresh()
        self._permission(permission, allowed=True)
        entries = self._pause_entries()
        if not entries:
            raise ValueError("no subscription pause")
        path = entries[-1]
        paused = read_json(path / "pause.json")
        if paused["registration_sha256"] != self.expected_sha256:
            raise ValueError("pause belongs to another registration")
        exclusive_json(
            path / "resume.json",
            {
                "registration_sha256": self.expected_sha256,
                "pause_sha256": digest(paused),
                "permission": permission,
            },
        )
        self._check_pause()

    def _subscription_resume_covers(self, trial_id, final):
        if final["continuation"].get("reasons") != ["subscription_permission_unavailable"]:
            return False
        for path in self._pause_entries():
            paused = read_json(path / "pause.json")
            if paused["stopped_trial_id"] == trial_id and paused["stopped_final_sha256"] == digest(final):
                return (path / "resume.json").exists()
        return False
