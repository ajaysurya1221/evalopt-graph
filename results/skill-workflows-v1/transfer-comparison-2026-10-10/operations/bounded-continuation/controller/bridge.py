"""Source-bound callbacks and retrospective ledger; never alter frozen trial gates."""

import argparse
import asyncio
import json
import re
import stat
import sys
import time
import types
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

for _name in ("amendment", "classifier", "observer"):
    if _name not in sys.modules or __name__ == "__main__":
        _module = types.ModuleType(_name)
        _module.__file__ = str(HERE / (_name + ".py"))
        sys.modules[_name] = _module
        exec(compile((HERE / (_name + ".py")).read_bytes(), _module.__file__, "exec"), _module.__dict__)
import classifier  # noqa: E402
import observer  # noqa: E402
from amendment import (  # noqa: E402
    COMMIT,
    REGISTRATION,
    SECOND,
    TRIAL,
    digest,
    hashed,
    historical_gate,
    load_grant,
    mkdir,
    nodes,
    read,
    safe,
    source_check,
    validate_progress,
    verify_prefix,
    write_once,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def origins(ctx):
    bench = ctx.paths.source / "bench/harbor/skill-workflows-v1"
    for name, module in list(sys.modules.items()):
        if name in {"campaign", "transfer_campaign", "transfer_store"} or name.startswith(
            ("lib.", "runtime.")
        ):
            if not Path(module.__file__).resolve().is_relative_to(bench):
                raise ValueError("mixed frozen module origin")


def frozen(ctx):
    source_check(ctx)
    bench = ctx.paths.source / "bench/harbor/skill-workflows-v1"
    sys.path[:0] = [str(bench), str(ctx.paths.source / "src")]
    import campaign
    import transfer_campaign
    from runtime import accounting_policy, observations, transfer

    origins(ctx)
    return types.SimpleNamespace(
        campaign=campaign,
        transfer=transfer_campaign,
        accounting=accounting_policy,
        runtime=transfer,
        observations=observations,
    )


def require(condition, message):
    if not condition:
        raise ValueError(message)


def captured(raw, retained, paths):
    """Operational checks only: small metadata hashes and archive stat identities."""
    if hashed(raw / "result.json") != retained["original_result_sha256"]:
        raise ValueError("raw result changed")
    if hashed(raw / "artifacts.json") != retained["raw_artifact_manifest_sha256"]:
        raise ValueError("raw artifact manifest changed")
    tree = read(raw / "artifacts.json")["tree"]
    stopped_path = raw / "stopped/stopped.json"
    expected = tree["stopped/stopped.json"]
    if expected["type"] != "file" or expected["sha256"] != hashed(stopped_path):
        raise ValueError("capture metadata changed")
    stopped = read(stopped_path)
    records = stopped["artifacts"]
    if (
        retained["artifact_capture_complete"] is not True
        or stopped["all_outputs_complete"] is not True
        or [r["source"] for r in records] != paths
    ):
        raise ValueError("capture incomplete or path roster changed")
    fingerprints = {}
    for index, record in enumerate(records):
        name = f"output-{index}.tar"
        if (
            record["path"] != name
            or record["complete"] is not True
            or record["returncode"] != 0
            or record["error"] is not None
            or type(record["bytes"]) is not int
            or record["bytes"] < 0
        ):
            raise ValueError("invalid or incomplete archive record")
        path = safe(raw / "stopped" / name)
        observed = path.stat()
        node = tree["stopped/" + name]
        if (
            not stat.S_ISREG(observed.st_mode)
            or node["type"] != "file"
            or observed.st_size != record["bytes"]
            or node["size"] != record["bytes"]
            or node["sha256"] != record["sha256"]
        ):
            raise ValueError("archive identity or size changed")
        fingerprints[name] = {
            "size": observed.st_size,
            "device": observed.st_dev,
            "inode": observed.st_ino,
            "mtime_ns": observed.st_mtime_ns,
            "ctime_ns": observed.st_ctime_ns,
            "controller_sha256": record["sha256"],
        }
    return {"metadata_sha256": hashed(stopped_path), "archives": fingerprints}


def fingerprint(ctx, trial):
    """Operational no-new-writer identity, with full hashes for nonarchive metadata.

    Archive stat fingerprints do not replace final streamed raw-byte QA.
    """
    result = {}
    for label, base in [
        ("store", ctx.paths.campaign / "evidence/trials" / trial / "attempt-1"),
        ("raw", ctx.paths.campaign / "private-harbor" / trial / "attempt-1"),
    ]:
        for name, path in nodes(base).items():
            s = path.stat()
            item = {
                "mode": stat.S_IMODE(s.st_mode),
                "kind": "directory" if stat.S_ISDIR(s.st_mode) else "file",
            }
            if item["kind"] == "file":
                item.update(
                    size=s.st_size,
                    device=s.st_dev,
                    inode=s.st_ino,
                    mtime_ns=s.st_mtime_ns,
                    ctime_ns=s.st_ctime_ns,
                )
                if not name.endswith(".tar"):
                    item["sha256"] = hashed(path)
            result[label + "/" + name] = item
    return result


def ledger(ctx):
    root = ctx.code_root / "receipts/ledger"
    if not root.exists():
        return []
    files = sorted(root.iterdir())
    require(
        [p.name for p in files] == [f"entry-{n:03}.json" for n in range(1, len(files) + 1)],
        "ledger gaps or extra files",
    )
    previous = ctx.grant_sha256
    records = []
    for index, path in enumerate(files):
        value = read(path)
        row = ctx.pending_rows[index]
        require(
            value["schema_version"] == "evalopt.transfer-policy-v2.ledger.v1"
            and value["grant_sha256"] == ctx.grant_sha256
            and value["previous_sha256"] == previous
            and digest(value["row"]) == digest(row)
            and type(value["attempt"]) is int
            and value["attempt"] == 1,
            "ledger identity/chain differs",
        )
        require(
            value["classification"]["classification"] in ("strict_pass", "quarantine"), "unknown ledger class"
        )
        require(value["trial_id"] == row["trial_id"], "ledger trial differs")
        require(
            digest(value["fingerprint"]) == digest(fingerprint(ctx, row["trial_id"])),
            "prior attempt changed after ledger",
        )
        for pin in value["pins"].values():
            require(hashed(safe(pin["path"])) == pin["sha256"], "ledger pinned evidence changed")
        require(
            value["classification"]["input_sha256"] == digest(read(safe(value["inputs"]["path"])))
            and hashed(safe(value["inputs"]["path"])) == value["inputs"]["sha256"],
            "ledger classifier inputs changed",
        )
        verify_input_binding(ctx, value)
        records.append(value)
        previous = hashed(path)
    return records


def native_correspondence(ctx, admission, child_folder):
    result = read(child_folder / "result.json")
    exit_record = read(child_folder / "exit.json")
    require(
        type(exit_record.get("returncode")) is int
        and exit_record["returncode"] == 0
        and exit_record["result_sha256"] == hashed(child_folder / "result.json"),
        "child exit/result not bound",
    )
    require(result.get("grant_sha256") == ctx.grant_sha256, "child grant differs")
    end = result["scheduler"]
    expected = admission["expected_trial"]
    require(end["dispatched"] == [expected], "native child dispatched different rows")
    candidates = []
    for folder in sorted((ctx.paths.campaign / "runs").glob("run-*")):
        path = folder / "end.json"
        if path.exists() and digest(read(path)) == digest(end):
            candidates.append(folder)
    require(len(candidates) == 1, "genuine native end missing/ambiguous")
    native = candidates[0]
    require(
        re.fullmatch(r"run-\d{4}", native.name)
        and int(native.name[4:])
        == 57 + ctx.pending_rows.index(next(r for r in ctx.pending_rows if r["trial_id"] == expected)),
        "native run ordinal differs",
    )
    start = read(native / "start.json")
    require(
        start.get("schema_version") == "evalopt.scheduler-run.v1"
        and start.get("registration_sha256") == REGISTRATION,
        "native start identity differs",
    )
    require(
        all(start[k] is False for k in ("retry_infrastructure", "resume_quota", "recover_interrupted")),
        "native retry options changed",
    )
    permission_paths = list(native.glob("permission-*.json"))
    require(len(permission_paths) == 1, "native permission roster differs")
    permission = read(permission_paths[0])
    p = permission["permission"]
    require(
        permission.get("schema_version") == "evalopt.scheduler-permission.v1"
        and p.get("schema_version") == "evalopt.subscription-permission.v1"
        and permission["trial_id"] == expected
        and p["ordinary_usage_allowed"] is True
        and p["state"] == "allowed",
        "ordinary subscription permission absent",
    )
    attempt_start = read(ctx.paths.campaign / "evidence/trials" / expected / "attempt-1/start.json")
    require(
        classifier.instant(admission["observed_at"])
        <= classifier.instant(start["started_at"])
        <= classifier.instant(permission["checked_at"])
        <= classifier.instant(attempt_start["started_at"])
        <= classifier.instant(end["ended_at"])
        <= classifier.instant(exit_record["observed_at"]),
        "native permission/attempt chronology differs",
    )
    require(
        classifier.instant(start["started_at"]) >= classifier.instant(admission["observed_at"])
        and classifier.instant(end["ended_at"]) <= classifier.instant(exit_record["observed_at"]),
        "native/child chronology differs",
    )
    return native, result, exit_record


def collect_classification(ctx, row, store, admission, child_folder, api):
    """Read-only collector returning pure predicate input and source pins.

    Called only after child exit. Existing immutable finalization and native end
    must exist. Never runs capture, verifier, model, candidate, or stop guard.
    """
    trial = row["trial_id"]
    store.verify_attempt(trial, 1)
    attempt = ctx.paths.campaign / "evidence/trials" / trial / "attempt-1"
    raw = ctx.paths.campaign / "private-harbor" / trial / "attempt-1"
    native, result, exit_record = native_correspondence(ctx, admission, child_folder)
    finish = read(attempt / "finish.json")
    retained = read(attempt / "transfer-result.json")
    summary = read(raw / "result.json")
    artifacts = read(raw / "artifacts.json")
    require(
        hashed(raw / "result.json") == retained["original_result_sha256"]
        and hashed(raw / "artifacts.json") == retained["raw_artifact_manifest_sha256"],
        "raw projection pins differ",
    )
    raw_tree = api.runtime.tree_manifest(raw)
    raw_tree.pop("artifacts.json", None)
    require(digest(raw_tree) == digest(artifacts["tree"]), "raw artifact bytes/roster differ")
    require(
        not any(name == "stopped" or name.startswith("stopped/") for name in raw_tree),
        "stopped capture exists",
    )
    candidates = list(raw.glob("harbor-*/result.json"))
    require(len(candidates) == 1, "native result roster differs")
    harbor_root = candidates[0].parent
    harbor = read(candidates[0])
    sessions = harbor_root / "agent/sessions"
    policy = api.transfer.read_accounting_policy(ctx.paths.campaign)
    verified = api.campaign._verified_usage_record(store, trial, 1)
    strict_reason = api.transfer.transfer_usage_reason(verified, policy)
    from harbor.models.trial.config import TrialConfig

    sources = read(ctx.paths.campaign / "private-sources.json")
    expected = api.runtime.trial_configuration(
        row, Path(sources["prepared"]), raw, ctx.paths.upstream, Path(sources["evalopt_skill"])
    )
    require(
        re.fullmatch(r"harbor-transfer-[0-9a-f]{16}", harbor["config"]["trial_name"]) is not None,
        "native trial name differs",
    )
    expected["trial_name"] = harbor["config"]["trial_name"]
    require(
        digest(TrialConfig.model_validate(expected).model_dump(mode="json")) == digest(harbor["config"]),
        "original trial configuration changed",
    )
    prepared = read(ctx.paths.campaign / "preparation.json")
    start = read(raw / "start.json")
    require(
        digest(start["row"]) == digest(row)
        and start["harbor_version"] == "0.24.0"
        and start["preparation_sha256"] == hashed(ctx.paths.campaign / "preparation.json")
        and digest(start["image"]) == digest(prepared["image_lock"]["images"][row["task_id"]]),
        "raw execution registration differs",
    )
    exposure = read(raw / "workflow-exposure.json")
    from runtime.transfer import expected_skill_files

    require(
        digest(exposure["source_files"]) == digest(expected_skill_files(harbor["config"]["agent"]["skills"])),
        "injected skills differ",
    )
    stop = read(raw / "native-stop.json")
    identity = read(raw / "native-identity.json")
    failure = read(raw / "native-stop-failure.json")
    require(
        digest(identity["service_contracts"]) == digest(prepared["service_contracts"][row["task_id"]]),
        "native service contract differs",
    )
    usage = api.accounting.collect_usage(sessions, policy)
    entry = api.runtime.ENTRYPOINTS[row["task_id"]] if row["arm"] == "B" else "eval-opt"
    usage.update(api.observations.runtime_observations(sessions, entry))
    usage.update(
        agent_started=True,
        workflow_exposure_verified=exposure["verified_before_agent"] is True,
        native_agent_stopped=stop["confirmed"] is True,
        execution_boundary_complete=stop["boundary_confirmed"] is True,
        agent_deadline_expired=stop["reason"] == "original_agent_deadline",
        native_stop_wall_seconds=stop["controller_wall_seconds"],
    )
    require(digest(usage) == digest(summary["usage"]), "unchanged native usage/runtime differs")
    model = types.SimpleNamespace(
        exception_info=types.SimpleNamespace(**harbor["exception_info"])
        if harbor["exception_info"] is not None
        else None,
        verifier_result=types.SimpleNamespace(**harbor["verifier_result"])
        if harbor["verifier_result"] is not None
        else None,
    )
    reproduced = api.runtime.summarize_result(row, model, agent_started=True, stopped=None, usage=usage)
    require(digest(reproduced) == digest(summary), "frozen controller summary differs")
    safe_usage = api.transfer.safe_usage(usage, policy)
    require(
        digest(safe_usage) == digest(finish["usage"])
        and digest(finish["usage"]) == digest(retained["usage"]),
        "safe usage projection differs",
    )
    for key in retained:
        if key in summary and key not in ("usage", "schema_version"):
            require(digest(retained[key]) == digest(summary[key]), "retained summary differs")
    data = {
        "row": row,
        "finish": finish,
        "summary": dict(summary, usage=safe_usage),
        "harbor": harbor,
        "stop": stop,
        "stop_failure": failure,
        "identity": identity,
        "exposure": exposure,
        "native_end": result["scheduler"],
        "child_result": result,
        "child_returncode": exit_record["returncode"],
        "strict_reason": strict_reason,
        "raw_nodes": sorted(n for n, v in raw_tree.items() if v["type"] == "file"),
        "services": prepared["service_contracts"][row["task_id"]],
        "collected_at": now(),
    }
    paths = {"store/" + p.name: p for p in attempt.iterdir() if p.is_file()}
    paths.update({"raw/" + n: raw / n for n, v in raw_tree.items() if v["type"] == "file"})
    paths.update(
        {
            "raw/artifacts.json": raw / "artifacts.json",
            "native/start.json": native / "start.json",
            "native/end.json": native / "end.json",
            "native/permission.json": next(native.glob("permission-*.json")),
            "child/result.json": child_folder / "result.json",
            "child/exit.json": child_folder / "exit.json",
        }
    )
    pins = {name: {"path": str(path), "sha256": hashed(path)} for name, path in paths.items()}
    return (
        data,
        pins,
        lambda record: api.accounting.validate_attempt(
            {**record, "artifact_valid": True, "accounting_context": verified["accounting_context"]}, policy
        ),
    )


def native_run_roster(ctx, closed, *, current=False, completed_current=False):
    root = ctx.paths.campaign / "runs"
    expected = 56 + closed + int(current)
    paths = sorted(root.iterdir())
    require(
        [p.name for p in paths] == [f"run-{n:04}" for n in range(1, expected + 1)],
        "undeclared native run roster",
    )
    for index, path in enumerate(paths[56:], 57):
        expected_files = {"start.json", "permission-0001.json", "end.json"}
        if current and index == expected and not completed_current:
            require(
                {p.name for p in path.iterdir()} in ({"start.json"}, {"start.json", "permission-0001.json"}),
                "active native run files differ",
            )
        else:
            require(
                {p.name for p in path.iterdir()} == expected_files, "final native run files missing or extra"
            )


class Callbacks:
    def __init__(self, ctx, api, admission=None, claim=None):
        self.ctx, self.api, self.admission, self.claim = ctx, api, admission, claim
        self.claimed = False
        self.dispatched = False
        self.expected = None
        self.policy = None
        self.prior = []
        self.verifications = 0

    def verify(self, destination, upstream, *, read_only=False):
        require(
            destination == self.ctx.paths.campaign and upstream == self.ctx.paths.upstream,
            "callback paths differ",
        )
        source_check(self.ctx)
        verify_prefix(self.ctx)
        if read_only:
            import transfer_publish

            schedule, store = transfer_publish._registration(destination, private=True)
            result = (read(destination / "manifest.json"), {}, schedule, store)
        else:
            result = self.api.transfer.verify_campaign(destination, upstream)
        manifest, _, schedule, store = result
        remaining = validate_progress(self.ctx, schedule, store)
        self.policy = self.api.transfer.read_accounting_policy(destination, manifest)
        self.prior = ledger(self.ctx)
        native_run_roster(
            self.ctx, len(self.prior), current=self.admission is not None and self.verifications > 0
        )
        finished_new = 72 - len(remaining) - 56
        require(
            finished_new == len(self.prior) or (self.dispatched and finished_new == len(self.prior) + 1),
            "unacknowledged new attempt cannot be adopted",
        )
        next_row = remaining[0] if remaining else None
        if not self.dispatched:
            if self.expected is None:
                self.expected = next_row
            require(digest(next_row) == digest(self.expected), "next row changed under lock")
            if self.admission is not None:
                require(
                    next_row is not None and next_row["trial_id"] == self.admission["expected_trial"],
                    "admission row differs",
                )
                require(
                    [s["trial_id"] for s in store.statuses() if s["attempts"]]
                    == [s["trial_id"] for s in self.admission["before"]["states"] if s["attempts"]],
                    "retained attempt prefix changed",
                )
        origins(self.ctx)
        if self.claim is not None and not self.claimed:
            self.claim()
            self.claimed = True
        self.verifications += 1
        return result

    def gate(self, record):
        reason = historical_gate(
            self.ctx,
            record,
            self.policy,
            self.api.transfer.transfer_usage_reason,
            self.api.accounting.validate_attempt,
        )
        if reason is None:
            return None
        # The current dispatched row can never read or create its own waiver.
        if self.dispatched and record.get("trial_id") == self.expected["trial_id"]:
            return reason
        entries = [e for e in self.prior if e["trial_id"] == record.get("trial_id")]
        if not entries:
            return reason
        entry = entries[0]
        require(type(record.get("attempt")) is int and record["attempt"] == 1, "ledger attempt differs")
        finish = read(
            self.ctx.paths.campaign / "evidence/trials" / record["trial_id"] / "attempt-1/finish.json"
        )
        require(digest({k: record.get(k) for k in finish}) == digest(finish), "ledger gate finish differs")
        if entry["classification"]["classification"] == "quarantine":
            require(reason == classifier.REASON, "quarantined reason changed")
            data = read(safe(entry["inputs"]["path"]))
            actual = classifier.classify(
                data,
                validate_accounting=lambda r: self.api.accounting.validate_attempt(
                    {**r, "artifact_valid": True, "accounting_context": record["accounting_context"]},
                    self.policy,
                ),
            )
            require(digest(actual) == digest(entry["classification"]), "quarantine predicate replay differs")
            return None
        return reason

    async def execute(self, row, store, private_root, upstream, agent_image, verifier_image):
        _, _, schedule, checked = self.verify(self.ctx.paths.campaign, upstream)
        remaining = validate_progress(self.ctx, schedule, checked)
        require(
            not self.dispatched
            and remaining
            and digest(row) == digest(remaining[0]) == digest(self.expected)
            and digest(row) in {digest(r) for r in self.ctx.pending_rows}
            and private_root == self.ctx.paths.campaign / "private-harbor",
            "dispatch outside fixed whitelist",
        )
        observation = observer.observe(
            self.ctx, self.admission["owner"], phase="under_native_lock_after_permission"
        )
        write_once(
            self.ctx.code_root
            / "receipts/claims"
            / ("observation-" + Path(self.admission["_token_path"]).name),
            observation,
        )
        source_check(self.ctx)
        verify_prefix(self.ctx)
        latest = validate_progress(self.ctx, schedule, checked)
        require(latest and digest(latest[0]) == digest(row), "queue changed after final observation")
        observer.validate_observation(
            self.ctx,
            observation,
            phase="under_native_lock_after_permission",
            current_monotonic=time.monotonic(),
        )
        # Observer was after permission and under lock. No await or model call occurs before frozen dispatch.
        self.dispatched = True
        return await self.api.transfer.execute_registered(
            row, store, private_root, upstream, agent_image, verifier_image
        )


def snapshot(ctx, api):
    with api.campaign._scheduler_lock(ctx.paths.campaign):
        adapter = Callbacks(ctx, api)
        _, _, schedule, store = adapter.verify(ctx.paths.campaign, ctx.paths.upstream, read_only=True)
        queue, reason, blocked = api.campaign._dispatch_queue(
            store,
            schedule,
            retry_infrastructure=False,
            resume_quota=False,
            recover_interrupted=False,
            usage_gate=adapter.gate,
        )
        prepared = read(ctx.paths.campaign / "preparation.json")
        attempts = {}
        classified = {e["trial_id"]: e for e in adapter.prior}
        for state in store.statuses():
            if not state["attempts"]:
                continue
            trial = state["trial_id"]
            store.verify_attempt(trial, 1)
            folder = store.root / "trials" / trial / "attempt-1"
            raw = ctx.paths.campaign / "private-harbor" / trial / "attempt-1"
            retained = read(folder / "transfer-result.json")
            identity = {
                name: hashed(folder / name)
                for name in (
                    "start.json",
                    "finish.json",
                    "finalize.json",
                    "manifest.json",
                    "transfer-result.json",
                )
            }
            if trial in (TRIAL, SECOND) or (
                trial in classified and classified[trial]["classification"]["classification"] == "quarantine"
            ):
                identity["capture"] = {
                    "complete": False,
                    "archives": {},
                    "exception": "preserved_unscored_boundary_failure",
                    "grant_sha256": ctx.grant_sha256,
                }
            else:
                identity["capture"] = captured(raw, retained, prepared["capture_paths"][retained["task_id"]])
            attempts[trial + "/1"] = identity
        return {
            "schema_version": "evalopt.transfer-policy-v2.snapshot.v1",
            "source_commit": COMMIT,
            "registration_sha256": REGISTRATION,
            "grant_sha256": ctx.grant_sha256,
            "schedule": [r["trial_id"] for r in schedule],
            "states": store.statuses(),
            "attempts": attempts,
            "next_trial": queue[0]["trial_id"] if queue else None,
            "stop_reason": reason,
            "blocked_trial": blocked,
            "active_attempts": 0,
            "ledger_count": len(adapter.prior),
            "capture_complete": False,
            "historical_capture_exceptions": [TRIAL + "/1", SECOND + "/1"],
            "new_captures_complete": all(
                e["classification"]["classification"] == "strict_pass" for e in adapter.prior
            ),
            "quarantine_trials": [
                e["trial_id"] for e in adapter.prior if e["classification"]["classification"] == "quarantine"
            ],
        }


def admission_token(ctx, path, expected_sha):
    path = safe(path)
    root = ctx.code_root / "receipts"
    require(
        path.parent == root
        and re.fullmatch(r"admission-\d{3}\.json", path.name)
        and hashed(path) == expected_sha
        and not (root / "STOP.json").exists()
        and not path.with_name(path.stem + "-completion.json").exists(),
        "invalid/consumed admission",
    )
    value = read(path)
    number = int(path.stem.split("-")[-1])
    require(
        1 <= number <= 16
        and value["grant_sha256"] == ctx.grant_sha256
        and value["registration_sha256"] == REGISTRATION
        and value["source_commit"] == COMMIT
        and value["expected_trial"]
        == ctx.pending_rows[number - 1]["trial_id"]
        == value["before"]["next_trial"],
        "admission identity/order differs",
    )
    require(
        value["before"]["grant_sha256"] == ctx.grant_sha256
        and type(value["before"].get("ledger_count")) is int
        and value["before"]["ledger_count"] == number - 1,
        "admission ledger position differs",
    )
    for n in range(1, number):
        completion = root / f"admission-{n:03}-completion.json"
        require(
            completion.is_file() and read(completion)["stop_reason"] is None, "unfinished prior admission"
        )
    return {**value, "_token_path": str(path), "_token_sha256": expected_sha}


def claim_admission(ctx, admission):
    observed = admission_token(ctx, safe(admission["_token_path"]), admission["_token_sha256"])
    require(digest(observed) == digest(admission), "token changed before claim")
    root = ctx.code_root / "receipts/claims"
    if not root.exists():
        mkdir(root)
    write_once(
        root / Path(admission["_token_path"]).name,
        {
            "schema_version": "evalopt.transfer-policy-v2.claim.v1",
            "grant_sha256": ctx.grant_sha256,
            "admission_sha256": admission["_token_sha256"],
            "expected_trial": admission["expected_trial"],
        },
    )


async def run_one(ctx, api, admission):
    adapter = Callbacks(ctx, api, admission, lambda: claim_admission(ctx, admission))
    result = await api.campaign.run_pilot(
        ctx.paths.campaign,
        ctx.paths.upstream,
        limit=1,
        retry_infrastructure=False,
        resume_quota=False,
        recover_interrupted=False,
        verifier=adapter.verify,
        executor=adapter.execute,
        reporter=api.transfer.report,
        usage_gate=adapter.gate,
    )
    verify_prefix(ctx)
    return {
        "scheduler": result["scheduler"],
        "export_id": result.get("export_id"),
        "grant_sha256": ctx.grant_sha256,
        "operational_amendment": True,
    }


def verify_input_binding(ctx, entry):
    """Source correspondence, not just a hash of arbitrary supplied JSON."""
    trial = entry["trial_id"]
    row = entry["row"]
    number = ctx.pending_rows.index(row) + 1
    require(
        safe(entry["inputs"]["path"])
        == ctx.code_root / "receipts" / f"child-{number:03}" / "classification-inputs.json",
        "classifier input ownership differs",
    )
    data = read(safe(entry["inputs"]["path"]))
    raw = ctx.paths.campaign / "private-harbor" / trial / "attempt-1"
    attempt = ctx.paths.campaign / "evidence/trials" / trial / "attempt-1"
    child = ctx.code_root / "receipts" / f"child-{number:03}"
    native = ctx.paths.campaign / "runs" / f"run-{number + 56:04}"
    required = {"store/" + p.name: p for p in attempt.iterdir() if p.is_file()}
    raw_tree = read(raw / "artifacts.json")["tree"]
    if entry["classification"]["classification"] == "quarantine":
        required.update({"raw/" + n: raw / n for n, v in raw_tree.items() if v["type"] == "file"})
    else:
        required.update(
            {
                "raw/result.json": raw / "result.json",
                "raw/artifacts.json": raw / "artifacts.json",
                "raw/stopped/stopped.json": raw / "stopped/stopped.json",
            }
        )
    required.update(
        {
            "admission.json": ctx.code_root / "receipts" / f"admission-{number:03}.json",
            "claim.json": ctx.code_root / "receipts/claims" / f"admission-{number:03}.json",
            "dispatch-observation.json": ctx.code_root
            / "receipts/claims"
            / f"observation-admission-{number:03}.json",
        }
    )
    required.update(
        {
            "raw/artifacts.json": raw / "artifacts.json",
            "native/start.json": native / "start.json",
            "native/end.json": native / "end.json",
            "native/permission.json": native / "permission-0001.json",
            "child/result.json": child / "result.json",
            "child/exit.json": child / "exit.json",
        }
    )
    require(set(entry["pins"]) == set(required), "ledger pin roster differs")
    require(
        all(safe(entry["pins"][name]["path"]) == path for name, path in required.items()),
        "ledger pin ownership differs",
    )
    require(
        digest(data["row"]) == digest(row)
        and digest(data["finish"]) == digest(read(attempt / "finish.json")),
        "ledger row/finish input differs",
    )
    require(
        digest(data["native_end"]) == digest(read(native / "end.json"))
        and digest(data["child_result"]) == digest(read(child / "result.json"))
        and data["child_returncode"] == read(child / "exit.json")["returncode"],
        "ledger native/child inputs differ",
    )
    if entry["classification"]["classification"] == "quarantine":
        for key, name in {
            "stop": "native-stop.json",
            "stop_failure": "native-stop-failure.json",
            "identity": "native-identity.json",
            "exposure": "workflow-exposure.json",
        }.items():
            require(digest(data[key]) == digest(read(raw / name)), "ledger stop/runtime input differs")
        summary = read(raw / "result.json")
        summary["usage"] = read(attempt / "finish.json")["usage"]
        require(digest(data["summary"]) == digest(summary), "ledger summary input differs")
        harbor = list(raw.glob("harbor-*/result.json"))
        require(
            len(harbor) == 1 and digest(data["harbor"]) == digest(read(harbor[0])),
            "ledger Harbor input differs",
        )
        require(
            data["raw_nodes"] == sorted(n for n, v in raw_tree.items() if v["type"] == "file"),
            "ledger raw roster input differs",
        )
        prepared = read(ctx.paths.campaign / "preparation.json")
        require(
            digest(data["services"]) == digest(prepared["service_contracts"][row["task_id"]]),
            "ledger service input differs",
        )
    admission = read(required["admission.json"])
    claim = read(required["claim.json"])
    native_correspondence(ctx, admission, child)
    require(
        admission["grant_sha256"] == ctx.grant_sha256
        and admission["expected_trial"] == trial
        and claim["grant_sha256"] == ctx.grant_sha256
        and claim["admission_sha256"] == hashed(required["admission.json"])
        and claim["expected_trial"] == trial,
        "ledger claim/admission differs",
    )
    require(
        entry["before_snapshot_sha256"] == digest(admission["before"])
        and entry["after_prefix_sha256"] == digest(entry["fingerprint"]),
        "ledger prefix identity differs",
    )
    dispatch = observer.validate_observation(
        ctx, read(required["dispatch-observation.json"]), phase="under_native_lock_after_permission"
    )
    observed = observer.validate_observation(
        ctx, entry["observation"], phase="post_child_before_ledger_commit"
    )
    require(
        classifier.instant(read(child / "exit.json")["observed_at"])
        <= classifier.instant(observed["checked_at"])
        <= classifier.instant(entry["committed_at"])
        and (
            classifier.instant(entry["committed_at"]) - classifier.instant(observed["checked_at"])
        ).total_seconds()
        + observed["elapsed_seconds"]
        <= 60,
        "quarantine observation/commit chronology differs",
    )
    require(
        classifier.instant(dispatch["checked_at"])
        <= classifier.instant(read(attempt / "start.json")["started_at"]),
        "dispatch observation after attempt start",
    )
    return data


def commit_completed(ctx, api, admission, child_folder):
    """Called in a new bridge only AFTER the operator waited for child exit."""
    import transfer_publish

    with api.campaign._scheduler_lock(ctx.paths.campaign):
        source_check(ctx)
        verify_prefix(ctx)
        schedule, store = transfer_publish._registration(ctx.paths.campaign, private=True)
        remaining = validate_progress(ctx, schedule, store)
        prior = ledger(ctx)
        native_run_roster(ctx, len(prior), current=True, completed_current=True)
        number = len(prior) + 1
        require(1 <= number <= 16, "ledger capacity exceeded")
        row = ctx.pending_rows[number - 1]
        require(
            admission["expected_trial"] == row["trial_id"] and 72 - len(remaining) == 56 + number,
            "only one expected new finalized attempt permitted",
        )
        require(child_folder == ctx.code_root / "receipts" / f"child-{number:03}", "child path differs")
        claim = read(ctx.code_root / "receipts/claims" / Path(admission["_token_path"]).name)
        require(
            claim["admission_sha256"] == admission["_token_sha256"]
            and claim["grant_sha256"] == ctx.grant_sha256
            and claim["expected_trial"] == row["trial_id"],
            "dispatch claim differs",
        )
        native, result, exit_record = native_correspondence(ctx, admission, child_folder)
        policy = api.transfer.read_accounting_policy(ctx.paths.campaign)
        record = api.campaign._verified_usage_record(store, row["trial_id"], 1)
        reason = api.transfer.transfer_usage_reason(record, policy)
        folder = store.root / "trials" / row["trial_id"] / "attempt-1"
        raw = ctx.paths.campaign / "private-harbor" / row["trial_id"] / "attempt-1"
        if reason == classifier.REASON:
            data, pins, validator = collect_classification(ctx, row, store, admission, child_folder, api)
            classification = classifier.classify(data, validate_accounting=validator)
        elif reason is None:
            end = result["scheduler"]
            require(
                end["status"] in ("limited", "finished") and end.get("reason") is None,
                "strict result has unexpected native pause",
            )
            captured(
                raw,
                read(folder / "transfer-result.json"),
                read(ctx.paths.campaign / "preparation.json")["capture_paths"][row["task_id"]],
            )
            data = {
                "row": row,
                "finish": read(folder / "finish.json"),
                "native_end": end,
                "child_result": result,
                "child_returncode": exit_record["returncode"],
                "strict_reason": None,
            }
            classification = {
                "schema_version": "evalopt.transfer-policy-v2.classification.v1",
                "classification": "strict_pass",
                "trial_id": row["trial_id"],
                "attempt": 1,
                "input_sha256": digest(data),
            }
            paths = {"store/" + p.name: p for p in folder.iterdir() if p.is_file()}
            paths.update(
                {
                    "raw/result.json": raw / "result.json",
                    "raw/artifacts.json": raw / "artifacts.json",
                    "raw/stopped/stopped.json": raw / "stopped/stopped.json",
                    "native/start.json": native / "start.json",
                    "native/end.json": native / "end.json",
                    "native/permission.json": native / "permission-0001.json",
                    "child/result.json": child_folder / "result.json",
                    "child/exit.json": child_folder / "exit.json",
                }
            )
            pins = {name: {"path": str(path), "sha256": hashed(path)} for name, path in paths.items()}
        else:
            raise ValueError("future gate outside approved phenotype: " + str(reason))
        pins.update(
            {
                name: {"path": str(path), "sha256": hashed(path)}
                for name, path in {
                    "admission.json": safe(admission["_token_path"]),
                    "claim.json": ctx.code_root / "receipts/claims" / Path(admission["_token_path"]).name,
                    "dispatch-observation.json": ctx.code_root
                    / "receipts/claims"
                    / ("observation-" + Path(admission["_token_path"]).name),
                }.items()
            }
        )
        # Frozen outputs and native pause remain untouched. Fresh absence permits later admission only.
        observation = observer.observe(ctx, admission["owner"], phase="post_child_before_ledger_commit")
        verify_prefix(ctx)
        source_check(ctx)
        observer.validate_observation(
            ctx, observation, phase="post_child_before_ledger_commit", current_monotonic=time.monotonic()
        )
        before_fp = fingerprint(ctx, row["trial_id"])
        inputs = child_folder / "classification-inputs.json"
        write_once(inputs, data)
        entry = {
            "schema_version": "evalopt.transfer-policy-v2.ledger.v1",
            "grant_sha256": ctx.grant_sha256,
            "previous_sha256": hashed(ctx.code_root / "receipts/ledger" / f"entry-{number - 1:03}.json")
            if prior
            else ctx.grant_sha256,
            "row": row,
            "trial_id": row["trial_id"],
            "attempt": 1,
            "classification": classification,
            "inputs": {"path": str(inputs), "sha256": hashed(inputs)},
            "pins": pins,
            "fingerprint": before_fp,
            "before_snapshot_sha256": digest(admission["before"]),
            "after_prefix_sha256": digest(before_fp),
            "observation": observation,
            "committed_at": now(),
        }
        require(
            digest(before_fp) == digest(fingerprint(ctx, row["trial_id"])),
            "attempt changed during classification",
        )
        verify_input_binding(ctx, entry)
        ledger_root = ctx.code_root / "receipts/ledger"
        if not ledger_root.exists():
            mkdir(ledger_root)
        observer.validate_observation(
            ctx, observation, phase="post_child_before_ledger_commit", current_monotonic=time.monotonic()
        )
        write_once(ledger_root / f"entry-{number:03}.json", entry)
        return {
            "classification": classification["classification"],
            "ledger_sha256": hashed(ledger_root / f"entry-{number:03}.json"),
            "trial_id": row["trial_id"],
            "grant_sha256": ctx.grant_sha256,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "run-one", "commit"))
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--grant-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--admission-sha256")
    parser.add_argument("--child", type=Path)
    args = parser.parse_args()
    ctx = load_grant(args.grant, args.grant_sha256)
    api = frozen(ctx)
    if args.action == "inspect":
        require(args.admission is None and args.child is None, "inspect cannot take dispatch context")
        result = snapshot(ctx, api)
    else:
        admission = admission_token(ctx, args.admission, args.admission_sha256)
        result = (
            asyncio.run(run_one(ctx, api, admission))
            if args.action == "run-one"
            else commit_completed(ctx, api, admission, safe(args.child))
        )
    write_once(args.output, result)


if __name__ == "__main__":
    main()
