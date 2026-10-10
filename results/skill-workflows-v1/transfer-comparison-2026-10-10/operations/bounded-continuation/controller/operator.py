"""External storage admission loop; no changes to frozen trial semantics."""

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import types
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __name__ == "__main__":
    import hashlib as _hashlib

    try:
        _grant_path = Path(sys.argv[sys.argv.index("--grant") + 1])
        _grant_sha = sys.argv[sys.argv.index("--grant-sha256") + 1]
        _raw = _grant_path.read_bytes()
        if _hashlib.sha256(_raw).hexdigest() != _grant_sha:
            raise ValueError("bootstrap grant identity differs")
        _claimed = json.loads(_raw)["controller_files"]
        _files = ("amendment.py", "classifier.py", "observer.py", "bridge.py", "operator.py")
        if set(_claimed) != set(_files):
            raise ValueError("bootstrap source roster differs")
        for _file in _files:
            if _hashlib.sha256((HERE / _file).read_bytes()).hexdigest() != _claimed[_file]:
                raise ValueError("bootstrap source identity differs")
    except (IndexError, KeyError):
        raise ValueError("explicit grant and SHA256 required before source import") from None

# Read this trusted source directly: -B alone would still accept a poisoned .pyc.
if "amendment" not in sys.modules or __name__ == "__main__":
    _module = types.ModuleType("amendment")
    _module.__file__ = str(HERE / "amendment.py")
    sys.modules["amendment"] = _module
    exec(compile((HERE / "amendment.py").read_bytes(), _module.__file__, "exec"), _module.__dict__)
from amendment import REGISTRATION, SECOND, TRIAL, load_grant  # noqa: E402

COMMIT = "31231949412ea6d0101331720c0f0ed2d9f50b46"
IMAGE_LOCK_SHA = "fcb2e2b709674342e3749dba80409b50573ddc6a1a4cb49e1edb6e219e509bc1"
PROBE_IMAGE = "sha256:84c7fae6b256dcc56a350790e2a9715eefc7dad662a9d8e8a472363aa71ef18d"
GIB = 1024**3
FLOOR = 100 * GIB
WARNING = 150 * GIB
MAX_AGE = 60
INTERVAL = 30


def now():
    return datetime.now(timezone.utc).isoformat()


def sync_directory(path):
    descriptor = os.open(safe(path), os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def make_directory(path, *, exist_ok=False):
    safe(path).mkdir(exist_ok=exist_ok)
    sync_directory(path.parent)


def write_once(path, value):
    safe(path)
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def read(path):
    return json.loads(safe(path).read_text())


def safe(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("unsafe operator path")
    return path


@contextmanager
def lock(root):
    safe(root)
    make_directory(root, exist_ok=True)
    with safe(root / "operator.lock").open("a+") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def storage_reason(observation, current):
    for name in ("host", "vm"):
        item = observation.get(name, {})
        value, measured = item.get("free_bytes"), item.get("monotonic")
        if type(value) is not int or value < 0:
            return "invalid_storage_telemetry"
        if type(measured) not in (int, float) or not math.isfinite(measured):
            return "invalid_storage_telemetry"
        if not 0 <= current - measured <= MAX_AGE:
            return "stale_storage_telemetry"
        if value <= FLOOR:
            return name + "_storage_floor"
    return None


def check_snapshot(value, registration):
    if (
        value["source_commit"] != COMMIT
        or value["registration_sha256"] != registration
        or len(value["schedule"]) != 72
        or len(set(value["schedule"])) != 72
        or [s["trial_id"] for s in value["states"]] != value["schedule"]
    ):
        raise ValueError("snapshot registration or schedule differs")
    if value.get("capture_complete") is not False or value.get("historical_capture_exceptions") != [
        TRIAL + "/1",
        SECOND + "/1",
    ]:
        raise ValueError("capture exception scope differs")
    states = value["states"]
    for state in states:
        if (
            type(state["attempts"]) is not int
            or not 0 <= state["attempts"] <= 1
            or (state["status"] == "pending") != (state["attempts"] == 0)
        ):
            raise ValueError("invalid terminal/pending attempt count")
    if any(s["status"] == "running_or_interrupted" for s in states):
        raise ValueError("active attempt")
    expected = {f"{s['trial_id']}/{n}" for s in states for n in range(1, s["attempts"] + 1)}
    if expected != set(value["attempts"]):
        raise ValueError("attempt roster differs")
    pending = [s["trial_id"] for s in states if s["status"] == "pending"]
    if not value["stop_reason"] and value["next_trial"] != (pending[0] if pending else None):
        raise ValueError("next dispatch is not first pending trial")


def unchanged(before, after):
    if before["schedule"] != after["schedule"]:
        raise ValueError("schedule changed")
    if any(after["attempts"].get(key) != value for key, value in before["attempts"].items()):
        raise ValueError("retained attempt or capture identity changed")


def operate(registration, root, backend, *, limit=1):
    """Backend seam exists only for offline tests; production is System below."""
    if type(limit) is not int or not 1 <= limit <= 16:
        raise ValueError("admission limit must be 1..16")
    with lock(root):
        binding = {
            "schema_version": "evalopt.transfer-policy-v2.journal.v1",
            "grant_sha256": backend.ctx.grant_sha256,
        }
        if (root / "amendment.json").exists():
            if read(root / "amendment.json") != binding:
                raise ValueError("journal grant changed")
        else:
            if any(root.iterdir()):
                if {p.name for p in root.iterdir()} != {"operator.lock"}:
                    raise ValueError("unbound existing journal")
            write_once(root / "amendment.json", binding)
        if (root / "STOP.json").exists():
            raise ValueError("persistent stop requires explicit operator review; use no automatic restart")
        halted = None

        def stop(reason):
            nonlocal halted
            halted = halted or reason
            if not (root / "STOP.json").exists():
                try:
                    write_once(
                        root / "STOP.json",
                        {
                            "observed_at": now(),
                            "reason": halted,
                            "source_commit": COMMIT,
                            "registration_sha256": registration,
                            "grant_sha256": backend.ctx.grant_sha256,
                            "active_trial_policy": "await original frozen controller; no candidate signals",
                        },
                    )
                except OSError:
                    # An active child must still be awaited even if the disk cannot retain a latch.
                    # Its pre-spawn admission remains unclosed until a completion records this halt.
                    pass

        operations = sorted(root.glob("operation-*.start.json"))
        for ending in root.glob("operation-*.end.json"):
            if not ending.with_name(ending.name.replace(".end.json", ".start.json")).exists():
                stop("orphaned_operation_end")
                raise ValueError("orphaned operation end")
        if [p.name for p in operations] != [
            f"operation-{n:03}.start.json" for n in range(1, len(operations) + 1)
        ]:
            stop("noncontiguous_operation_roster")
            raise ValueError("operation roster changed")
        for operation in operations:
            ending = operation.with_name(operation.name.replace(".start.json", ".end.json"))
            if not ending.exists() or read(ending).get("stop_reason"):
                stop(read(ending)["stop_reason"] if ending.exists() else "prior_operation_requires_review")
                return {"dispatched": 0, "stop_reason": halted}
        prior = None
        # Unknown/orphan journal nodes cannot become implicit restart authority.
        preliminary = [p for p in root.glob("admission-*.json") if not p.name.endswith("-completion.json")]
        for item in root.iterdir():
            name = item.name
            if name in {"operator.lock", "amendment.json", "claims", "ledger", "observations"}:
                continue
            if re.fullmatch(
                r"operation-\d{3}\.(start|end)\.json|admission-\d{3}(-completion)?\.json|storage-\d{5}\.json|evalopt-storage-[0-9a-f]{32}(\.end)?\.json|inspection-[0-9a-f]{32}",
                name,
            ):
                continue
            numbered = re.fullmatch(r"(?:child|classification)-(\d{3})", name)
            if numbered and 1 <= int(numbered[1]) <= len(preliminary):
                continue
            stop("unexpected_external_journal_node")
            raise ValueError("unexplained external journal node")
        for subdir, expression in (
            ("claims", r"(?:observation-)?admission-(\d{3})\.json"),
            ("ledger", r"entry-(\d{3})\.json"),
        ):
            directory = root / subdir
            if directory.exists():
                for item in directory.iterdir():
                    match = re.fullmatch(expression, item.name)
                    if not match or not 1 <= int(match[1]) <= len(preliminary):
                        stop("orphaned_external_claim_or_ledger")
                        raise ValueError("orphaned external claim or ledger")
        admissions = sorted(
            p for p in root.glob("admission-*.json") if not p.name.endswith("-completion.json")
        )
        if [p.name for p in admissions] != [f"admission-{n:03}.json" for n in range(1, len(admissions) + 1)]:
            stop("noncontiguous_external_admission_roster")
            raise ValueError("external admission roster changed")
        for completion in root.glob("admission-*-completion.json"):
            if not completion.with_name(completion.name.replace("-completion.json", ".json")).exists():
                stop("orphaned_external_completion")
                raise ValueError("external admission was removed")
        for path in sorted(root.glob("admission-*.json")):
            finished = path.with_name(path.stem + "-completion.json")
            if path.name.endswith("-completion.json"):
                continue
            if not finished.exists():
                stop("unfinished_external_admission")
                return {"dispatched": 0, "stop_reason": "unfinished_external_admission"}
            completion = read(finished)
            if completion.get("stop_reason"):
                stop(completion["stop_reason"])
                return {"dispatched": 0, "stop_reason": halted}
            prior = completion["after"]
            check_snapshot(prior, registration)
        operation = root / f"operation-{len(operations) + 1:03}.start.json"
        write_once(
            operation,
            {
                "observed_at": now(),
                "registration_sha256": registration,
                "grant_sha256": backend.ctx.grant_sha256,
                "source_commit": COMMIT,
            },
        )
        dispatched = 0
        try:
            before = backend.inspect()
            check_snapshot(before, registration)
            if prior is None and len(before["attempts"]) != 56:
                raise ValueError("new journal requires original 56-attempt prefix")
            if prior is not None:
                unchanged(prior, before)
                if prior["attempts"] != before["attempts"]:
                    raise ValueError("attempts appeared outside completed operator admissions")
            while dispatched < limit:
                if before["stop_reason"]:
                    stop(before["stop_reason"])
                    break
                if before["next_trial"] is None:
                    break
                observation = backend.storage()
                reason = storage_reason(observation, backend.monotonic())
                sequence = len(list(root.glob("storage-*.json"))) + 1
                write_once(
                    root / f"storage-{sequence:05}.json",
                    {
                        "observed_at": now(),
                        "phase": "admission",
                        "readings": observation,
                        "warning": any(
                            observation.get(k, {}).get("free_bytes", WARNING + 1) <= WARNING
                            for k in ("host", "vm")
                        ),
                        "stop_reason": reason,
                    },
                )
                if reason:
                    stop(reason)
                    break
                if backend.interrupted:
                    stop("operator_signal")
                    break
                number = (
                    len([p for p in root.glob("admission-*.json") if not p.name.endswith("-completion.json")])
                    + 1
                )
                admission = root / f"admission-{number:03}.json"
                write_once(
                    admission,
                    {
                        "observed_at": now(),
                        "registration_sha256": registration,
                        "grant_sha256": backend.ctx.grant_sha256,
                        "source_commit": COMMIT,
                        "expected_trial": before["next_trial"],
                        "owner": backend.owner(),
                        "before": before,
                        "storage_receipt": f"storage-{sequence:05}.json",
                    },
                )
                if backend.interrupted:
                    stop("operator_signal")
                    break
                child = backend.start(number)
                last_sample = backend.monotonic()
                try:
                    while backend.poll(child) is None:
                        sample_started = backend.monotonic()
                        if sample_started - last_sample > MAX_AGE:
                            stop("stale_monitor_interval")
                        try:
                            sample = backend.storage()
                            last_sample = sample_started
                            reason = storage_reason(sample, backend.monotonic())
                            sequence += 1
                            write_once(
                                root / f"storage-{sequence:05}.json",
                                {
                                    "observed_at": now(),
                                    "phase": "active",
                                    "readings": sample,
                                    "stop_reason": reason,
                                },
                            )
                            if reason:
                                stop(reason)
                        except Exception as exc:
                            stop("monitor_error:" + type(exc).__name__)
                            # A failed probe may have unconfirmed cleanup. Never issue another.
                            break
                        if backend.interrupted:
                            stop("operator_signal")
                        # Never terminate/kill/cancel the dispatch waiter after a monitor failure.
                        backend.sleep(max(0, INTERVAL - (backend.monotonic() - sample_started)))
                except BaseException as exc:
                    stop("monitor_error:" + type(exc).__name__)
                # Even failed polling or sleeping must not abandon the active dispatch waiter.
                code, result = backend.finish(child)
                if backend.interrupted:
                    stop("operator_signal")
                if backend.monotonic() - last_sample > MAX_AGE:
                    stop("stale_monitor_interval")
                classification = backend.commit(number, result) if code == 0 and not halted else None
                if classification is None:
                    stop("unclassified_child_or_prior_monitor_stop")
                    break
                after = backend.inspect()
                check_snapshot(after, registration)
                unchanged(before, after)
                new = set(after["attempts"]) - set(before["attempts"])
                expected = before["next_trial"] + "/1"
                if (
                    code != 0
                    or new != {expected}
                    or result["scheduler"]["dispatched"] != [before["next_trial"]]
                ):
                    raise ValueError(
                        "frozen call did not finalize exactly the expected single pending attempt"
                    )
                write_once(
                    admission.with_name(admission.stem + "-completion.json"),
                    {
                        "observed_at": now(),
                        "returncode": code,
                        "scheduler": result["scheduler"],
                        "export_id": result.get("export_id"),
                        "stop_reason": halted,
                        "after": after,
                        "classification": classification,
                    },
                )
                dispatched += 1
                if after["stop_reason"]:
                    stop(after["stop_reason"])
                if result["scheduler"].get("reason") and classification["classification"] != "quarantine":
                    stop(result["scheduler"]["reason"])
                if halted or (root / "STOP.json").exists():
                    break
                before = after
        except Exception as exc:
            stop("operator_error:" + type(exc).__name__)
            raise
        finally:
            # If even this cannot be written, the already durable start blocks restart.
            write_once(
                operation.with_name(operation.name.replace(".start.json", ".end.json")),
                {"observed_at": now(), "dispatched": dispatched, "stop_reason": halted},
            )
        return {"dispatched": dispatched, "stop_reason": halted}


class System:
    def __init__(self, ctx, root):
        self.ctx = ctx
        self.registration, self.root = REGISTRATION, root
        self.interrupted = False
        module = types.ModuleType("observer")
        module.__file__ = str(HERE / "observer.py")
        sys.modules["observer"] = module
        exec(compile((HERE / "observer.py").read_bytes(), module.__file__, "exec"), module.__dict__)
        self.observer = module

    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        time.sleep(seconds)

    def command(self, action, output, cache):
        return [
            str(self.ctx.paths.python),
            "-I",
            "-B",
            "-X",
            "pycache_prefix=" + str(cache),
            str(HERE / "bridge.py"),
            action,
            "--grant",
            str(self.ctx.grant_path),
            "--grant-sha256",
            self.ctx.grant_sha256,
            "--output",
            str(output),
        ]

    def inspect(self):
        folder = self.root / ("inspection-" + uuid.uuid4().hex)
        make_directory(folder)
        output = folder / "result.json"
        argv = self.command("inspect", output, folder / "cache")
        write_once(folder / "start.json", {"observed_at": now(), "argv": argv})
        try:
            with (folder / "stdout.txt").open("xb") as stdout, (folder / "stderr.txt").open("xb") as stderr:
                subprocess.run(argv, check=True, stdout=stdout, stderr=stderr, timeout=300)
            result = read(output)
            if result.get("grant_sha256") != self.ctx.grant_sha256:
                raise ValueError("snapshot grant differs")
        except Exception as exc:
            write_once(
                folder / "end.json",
                {"observed_at": now(), "status": "failed", "error_type": type(exc).__name__},
            )
            raise
        write_once(
            folder / "end.json",
            {
                "observed_at": now(),
                "status": "completed",
                "snapshot_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            },
        )
        return result

    def owner(self):
        return self.observer.owner(self.ctx)

    def storage(self):
        return self.observer.Storage(self.ctx, self.root).storage()

    def commit(self, number, result):
        folder = self.root / f"classification-{number:03}"
        make_directory(folder)
        output = folder / "result.json"
        command = self.command("commit", output, folder / "cache")
        admission = self.root / f"admission-{number:03}.json"
        command.extend(
            [
                "--admission",
                str(admission),
                "--admission-sha256",
                hashlib.sha256(admission.read_bytes()).hexdigest(),
                "--child",
                str(self.root / f"child-{number:03}"),
            ]
        )
        write_once(folder / "start.json", {"observed_at": now(), "argv": command})
        try:
            with (folder / "stdout.txt").open("xb") as stdout, (folder / "stderr.txt").open("xb") as stderr:
                subprocess.run(command, check=True, stdout=stdout, stderr=stderr, timeout=300)
            classified = read(output)
            if (
                classified["grant_sha256"] != self.ctx.grant_sha256
                or classified["trial_id"] != result["scheduler"]["dispatched"][0]
            ):
                raise ValueError("classification identity differs")
        except BaseException as error:
            write_once(
                folder / "end.json",
                {"observed_at": now(), "status": "failed", "error_type": type(error).__name__},
            )
            raise
        write_once(
            folder / "end.json",
            {
                "observed_at": now(),
                "status": "completed",
                "result_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
            },
        )
        return classified

    def start(self, number):
        folder = self.root / f"child-{number:03}"
        make_directory(folder)
        command = self.command("run-one", folder / "result.json", folder / "cache")
        admission = self.root / f"admission-{number:03}.json"
        command.extend(
            [
                "--admission",
                str(admission),
                "--admission-sha256",
                hashlib.sha256(admission.read_bytes()).hexdigest(),
            ]
        )
        write_once(folder / "argv.json", command)
        stdout = (folder / "stdout.txt").open("xb")
        stderr = (folder / "stderr.txt").open("xb")
        try:
            process = subprocess.Popen(command, stdout=stdout, stderr=stderr, start_new_session=True)
        finally:
            stdout.close()
            stderr.close()
        return process, folder

    def poll(self, child):
        return child[0].poll()

    def finish(self, child):
        process, folder = child
        code = process.wait()
        result = read(folder / "result.json") if (folder / "result.json").exists() else {}
        write_once(
            folder / "exit.json",
            {
                "observed_at": now(),
                "returncode": code,
                "result_sha256": hashlib.sha256((folder / "result.json").read_bytes()).hexdigest()
                if (folder / "result.json").exists()
                else None,
            },
        )
        if result.get("grant_sha256") != self.ctx.grant_sha256:
            raise ValueError("child grant differs")
        return code, result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--grant-sha256", required=True)
    parser.add_argument("--limit", type=int, default=1)
    args = parser.parse_args()
    ctx = load_grant(args.grant, args.grant_sha256)
    root = HERE / "receipts"
    backend = System(ctx, root)

    def interrupted(_number, _frame):
        backend.interrupted = True

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, interrupted)
    print(json.dumps(operate(REGISTRATION, root, backend, limit=args.limit), sort_keys=True))


if __name__ == "__main__":
    main()
