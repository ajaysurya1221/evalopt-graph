"""Private, campaign-specific bridge into unchanged frozen transfer code."""

import argparse
import asyncio
import json
import os
import stat
import sys
import types
from pathlib import Path

# -I omits script-directory imports; load only this explicitly source-bound module.
HERE = Path(__file__).resolve().parent
# Read this trusted source directly: -B alone would still accept a poisoned .pyc.
if "amendment" not in sys.modules or __name__ == "__main__":
    _module = types.ModuleType("amendment")
    _module.__file__ = str(HERE / "amendment.py")
    sys.modules["amendment"] = _module
    exec(compile((HERE / "amendment.py").read_bytes(), _module.__file__, "exec"), _module.__dict__)
from amendment import (  # noqa: E402
    COMMIT,
    REGISTRATION,
    TRIAL,
    digest,
    hashed,
    load_grant,
    read,
    safe,
    source_check,
    validate_progress,
    verify_prefix,
    verify_waiver,
)


def origins(ctx):
    bench = ctx.paths.source / "bench/harbor/skill-workflows-v1"
    for name, module in list(sys.modules.items()):
        if name in {"campaign", "transfer_campaign", "transfer_store"} or name.startswith(
            ("lib.", "runtime.")
        ):
            if not Path(module.__file__).resolve().is_relative_to(bench):
                raise ValueError("mixed frozen module origin")


class Callbacks:
    """Explicit callback adapters; verifier/executor are invoked under frozen lock."""

    def __init__(self, ctx, transfer, validate_attempt, admission=None, claim=None):
        self.ctx, self.transfer, self.validate_attempt = ctx, transfer, validate_attempt
        self.admission = admission
        self.claim = claim
        self.claimed = False
        self.policy = None
        self.expected = None
        self.dispatched = False

    def verify(self, destination, upstream):
        if destination != self.ctx.paths.campaign or upstream != self.ctx.paths.upstream:
            raise ValueError("callback destination differs")
        source_check(self.ctx)
        verify_prefix(self.ctx)
        result = self.transfer.verify_campaign(destination, upstream)
        manifest, _, schedule, store = result
        remaining = validate_progress(self.ctx, schedule, store)
        self.policy = self.transfer.read_accounting_policy(destination, manifest)
        next_row = remaining[0] if remaining else None
        if self.admission is not None and not self.dispatched:
            expected_id = self.admission["expected_trial"]
            if not next_row or next_row["trial_id"] != expected_id:
                raise ValueError("admission token next row differs")
            if [s["trial_id"] for s in store.statuses() if s["attempts"]] != [
                s["trial_id"] for s in self.admission["before"]["states"] if s["attempts"]
            ]:
                raise ValueError("attempts changed after external admission")
        if self.expected is None and not self.dispatched:
            self.expected = next_row
        if not self.dispatched and digest(next_row) != digest(self.expected):
            raise ValueError("pending row changed inside scheduler lock")
        origins(self.ctx)
        if self.claim is not None and not self.claimed:
            self.claim()
            self.claimed = True
        return result

    def gate(self, record):
        return verify_waiver(
            self.ctx, record, self.policy, self.transfer.transfer_usage_reason, self.validate_attempt
        )

    async def execute(self, row, store, private_root, upstream, agent_image, verifier_image):
        # Recheck after the scheduler's awaited permission lookup; no stale parent snapshot admission.
        _, _, schedule, checked_store = self.verify(self.ctx.paths.campaign, upstream)
        remaining = validate_progress(self.ctx, schedule, checked_store)
        if (
            self.dispatched
            or not remaining
            or digest(row) != digest(remaining[0])
            or digest(row) != digest(self.expected)
            or digest(row) not in {digest(r) for r in self.ctx.pending_rows}
            or private_root != self.ctx.paths.campaign / "private-harbor"
        ):
            raise ValueError("dispatch outside exact pending whitelist/order")
        self.dispatched = True
        return await self.transfer.execute_registered(
            row, store, private_root, upstream, agent_image, verifier_image
        )


def callbacks(ctx, admission=None, claim=None):
    import transfer_campaign as transfer
    from runtime.accounting_policy import validate_attempt

    return Callbacks(ctx, transfer, validate_attempt, admission, claim)


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


def snapshot(ctx):
    import campaign

    destination = ctx.paths.campaign
    adapter = callbacks(ctx)
    with campaign._scheduler_lock(destination):
        manifest, _, schedule, store = adapter.verify(destination, ctx.paths.upstream)
        prepared = read(destination / "preparation.json")
        queue, reason, blocked = campaign._dispatch_queue(
            store,
            schedule,
            retry_infrastructure=False,
            resume_quota=False,
            recover_interrupted=False,
            usage_gate=adapter.gate,
        )
        states, attempts = store.statuses(), {}
        for state in states:
            for number in range(1, state["attempts"] + 1):
                store.verify_attempt(state["trial_id"], number)
                folder = store.root / "trials" / state["trial_id"] / f"attempt-{number}"
                finish = read(folder / "finish.json")
                if finish["status"] == "infra_failure":
                    reason = reason or "infrastructure_requires_operator_review"
                retained = read(folder / "transfer-result.json")
                raw = destination / "private-harbor" / state["trial_id"] / f"attempt-{number}"
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
                if state["trial_id"] == TRIAL and number == 1:
                    adapter.gate(campaign._verified_usage_record(store, TRIAL, 1))
                    identity["capture"] = {
                        "complete": False,
                        "archives": {},
                        "exception": "preserved_historical_missing_capture",
                        "original_reason": "runtime_identity_requires_remediation",
                        "grant_sha256": ctx.grant_sha256,
                    }
                else:
                    identity["capture"] = captured(
                        raw, retained, prepared["capture_paths"][retained["task_id"]]
                    )
                attempts[f"{state['trial_id']}/{number}"] = identity
        verify_prefix(ctx)
        return {
            "schema_version": "transfer-continuation-snapshot.v1",
            "source_commit": COMMIT,
            "registration_sha256": REGISTRATION,
            "grant_sha256": ctx.grant_sha256,
            "schedule": [r["trial_id"] for r in schedule],
            "states": states,
            "attempts": attempts,
            "next_trial": queue[0]["trial_id"] if queue else None,
            "stop_reason": reason,
            "blocked_trial": blocked,
            "active_attempts": 0,
            "capture_complete": False,
            "historical_capture_exception": TRIAL + "/1",
            "new_captures_complete": True,
            "archive_bytes": sum(
                a["size"] for item in attempts.values() for a in item["capture"]["archives"].values()
            ),
        }


def admission_token(ctx, path, expected_sha):
    path = safe(path)
    receipts = ctx.code_root / "receipts"
    if (
        path.parent != receipts
        or not __import__("re").fullmatch(r"admission-\d{3}\.json", path.name)
        or hashed(path) != expected_sha
        or path.with_name(path.stem + "-completion.json").exists()
        or (receipts / "STOP.json").exists()
    ):
        raise ValueError("invalid or consumed external admission token")
    value = read(path)
    if (
        value.get("grant_sha256") != ctx.grant_sha256
        or value.get("registration_sha256") != REGISTRATION
        or value.get("source_commit") != COMMIT
        or value.get("expected_trial") != value["before"]["next_trial"]
        or value["before"].get("grant_sha256") != ctx.grant_sha256
    ):
        raise ValueError("admission token identity differs")
    return {**value, "_token_path": str(path), "_token_sha256": expected_sha}


def claim_admission(ctx, admission):
    """Exclusive durable token consumption inside the frozen scheduler lock."""
    token = safe(admission["_token_path"])
    observed = admission_token(ctx, token, admission["_token_sha256"])
    if digest(observed) != digest(admission):
        raise ValueError("admission token changed before claim")
    root = ctx.code_root / "receipts/claims"
    if not root.exists():
        root.mkdir()
        parent = os.open(safe(root.parent), os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    claim = safe(root / token.name)
    with claim.open("x") as stream:
        json.dump(
            {
                "schema_version": "evalopt.transfer-admission-claim.v1",
                "grant_sha256": ctx.grant_sha256,
                "admission_sha256": admission["_token_sha256"],
                "expected_trial": admission["expected_trial"],
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    parent = os.open(root, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


async def run_one(ctx, admission):
    import campaign
    import transfer_campaign as transfer

    adapter = callbacks(ctx, admission, lambda: claim_admission(ctx, admission))
    result = await campaign.run_pilot(
        ctx.paths.campaign,
        ctx.paths.upstream,
        limit=1,
        retry_infrastructure=False,
        resume_quota=False,
        recover_interrupted=False,
        verifier=adapter.verify,
        executor=adapter.execute,
        reporter=transfer.report,
        usage_gate=adapter.gate,
    )
    verify_prefix(ctx)
    return {
        "scheduler": result["scheduler"],
        "export_id": result.get("export_id"),
        "grant_sha256": ctx.grant_sha256,
        "operational_amendment": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inspect", "run-one"))
    parser.add_argument("--grant", type=Path, required=True)
    parser.add_argument("--grant-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--admission-sha256")
    args = parser.parse_args()
    ctx = load_grant(args.grant, args.grant_sha256)
    source_check(ctx)
    bench = ctx.paths.source / "bench/harbor/skill-workflows-v1"
    sys.path[:0] = [str(bench), str(ctx.paths.source / "src")]
    import transfer_campaign  # noqa: F401

    origins(ctx)
    if args.action == "inspect":
        if args.admission is not None or args.admission_sha256 is not None:
            raise ValueError("inspection takes no dispatch token")
        result = snapshot(ctx)
    else:
        token = admission_token(ctx, args.admission, args.admission_sha256)
        result = asyncio.run(run_one(ctx, token))
    safe(args.output.parent)
    with args.output.open("x") as stream:
        json.dump(result, stream, sort_keys=True, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
