#!/usr/bin/env python3
"""Append-only partial-accounting amendment for a preserved, frozen 36-trial pilot."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import uuid
from contextlib import contextmanager
from pathlib import Path

from lib.common import (
    bytes_digest,
    canonical_bytes,
    digest,
    exact,
    is_digest,
    read_json,
    safe_name,
    write_once,
)
from runtime.controller import require_controller
from runtime.partial_accounting import derive_partial_usage

HERE = Path(__file__).resolve().parent
AMENDMENT = "amendments/partial-accounting-v1"
COUNTERS = ("input_tokens", "output_tokens", "model_calls", "tool_calls")
SOURCE_FILES = (
    "amended_pilot.py",
    "frozen_pilot_bridge.py",
    "lib/common.py",
    "lib/accounting.py",
    "runtime/controller.py",
    "runtime/partial_accounting.py",
)
POLICY = {
    "accepted_accounting": ["complete", "partial"],
    "required_provenance": "valid",
    "required_delegation_boundary": "verified",
    "runtime_valid_required": True,
    "pending_first_attempts_only": True,
    "original_outcomes_unchanged": True,
    "partial_counts_are_lower_bounds": True,
    "partial_efficiency_comparisons": False,
}


def _safe(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("amendment paths cannot traverse symlinks")
    return path


def _put(path, value):
    try:
        write_once(path, value)
    except FileExistsError:
        if read_json(path) != value:
            raise ValueError("immutable amendment artifact differs") from None


def code_identity():
    return {name: bytes_digest(_safe(HERE / name).read_bytes()) for name in SOURCE_FILES}


@contextmanager
def _lock(campaign):
    with _safe(campaign / ".scheduler.lock").open("a+") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError("another pilot controller holds the scheduler lock") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


class FrozenBridge:
    """Run only frozen benchmark imports in a separate isolated interpreter."""

    def __init__(self, python):
        self.python = str(python)

    def __call__(self, action, request):
        private = _safe(Path(request["campaign"]) / "private-amendment-bridge" / uuid.uuid4().hex)
        private.mkdir(parents=True, exist_ok=False)
        result_path = private / "result.json"
        result = subprocess.run(
            [
                self.python,
                "-I",
                "-B",
                "-X",
                "pycache_prefix=" + str(private / "empty-bytecode-cache"),
                str(HERE / "frozen_pilot_bridge.py"),
                action,
                "--result",
                str(result_path),
            ],
            input=canonical_bytes(request),
            capture_output=True,
            check=False,
            timeout=1200 if action == "execute" else 180,
        )
        (private / "stdout.txt").write_bytes(result.stdout)
        (private / "stderr.txt").write_bytes(result.stderr)
        if result.returncode != 0 or not result_path.is_file():
            raise ValueError("frozen bridge failed; inspect its retained private diagnostics")
        return read_json(result_path)


def _request(campaign, local, registration_sha256):
    return {
        "campaign": str(campaign),
        "frozen_source": local["frozen_source"],
        "upstream": local["upstream"],
        "registration_sha256": registration_sha256,
    }


def _attempt_key(record):
    safe_name(record["trial_id"])
    if record["attempt"] != 1:
        raise ValueError("this amendment does not authorize retries")
    return record["trial_id"] + "/attempt-1"


def _bound_attempt(record):
    return {key: record[key] for key in ("trial_id", "attempt", "finish_sha256", "manifest_sha256")}


def _session_root(campaign, record):
    attempt = _safe(campaign / "private-harbor" / _attempt_key(record))
    roots = sorted(attempt.glob("harbor-*/agent/sessions"))
    if not roots:
        return None
    if len(roots) != 1:
        raise ValueError("retained attempt requires exactly one native session directory")
    root = _safe(roots[0])
    for path in root.rglob("*"):
        _safe(path)
        if not path.is_dir() and not path.is_file():
            raise ValueError("native session tree contains a special node")
    return root


def admit(finish_usage, derived):
    """An explicit continuation decision; never rewrite original usage completeness."""
    if finish_usage.get("runtime_valid") is not True:
        return False, "runtime_identity_requires_remediation"
    if derived.get("provenance_status") != "valid":
        return False, "accounting_provenance_requires_remediation"
    if derived.get("delegation_boundary_status") != "verified":
        return False, "delegation_boundary_requires_remediation"
    if derived.get("accounting_status") not in {"complete", "partial"}:
        return False, "usage_accounting_requires_remediation"
    if any(
        type(derived.get("lower_bounds", {}).get(key)) is not int or derived["lower_bounds"][key] < 0
        for key in COUNTERS
    ):
        return False, "usage_accounting_requires_remediation"
    if derived["accounting_status"] == "partial" and (
        derived.get("child_usage_complete") is not False
        or derived.get("efficiency_eligible") is not False
        or derived.get("complete_usage") is not None
    ):
        return False, "contradictory_partial_accounting"
    if derived["accounting_status"] == "complete" and (
        derived.get("child_usage_complete") is not True
        or derived.get("efficiency_eligible") is not True
        or not isinstance(derived.get("complete_usage"), dict)
        or any(derived["complete_usage"].get(key) != derived["lower_bounds"][key] for key in COUNTERS)
    ):
        return False, "contradictory_complete_accounting"
    if finish_usage.get("child_usage_complete") is True:
        complete = derived.get("complete_usage")
        if (
            derived["accounting_status"] != "complete"
            or not isinstance(complete, dict)
            or any(
                complete.get(key) != finish_usage.get(key)
                for key in (*COUNTERS, "wall_seconds", "agent_count", "aggregation")
            )
        ):
            return False, "original_complete_accounting_changed"
    return True, None


def _derive(campaign, record, amendment_sha256):
    sessions = _session_root(campaign, record)
    derived = (
        derive_partial_usage(sessions)
        if sessions
        else {
            "schema_version": "evalopt.partial-workflow-usage.v1",
            "accounting_status": "unavailable",
            "provenance_status": "unavailable",
            "child_usage_complete": False,
            "lower_bounds": dict.fromkeys(COUNTERS),
            "completeness_reasons": ["native_session_logs_missing"],
            "efficiency_eligible": False,
            "delegation_boundary_status": "unverified",
            "agents": [],
            "complete_usage": None,
            "source_log_sha256": [],
        }
    )
    allowed, reason = admit(record["usage"], derived)
    return {
        "schema_version": "evalopt.amended-attempt-usage.v1",
        "amendment_sha256": amendment_sha256,
        **_bound_attempt(record),
        "derived_usage": derived,
        "continuation_admissible": allowed,
        "continuation_blocker": reason,
        "scope": "controller-derived usage from hash-bound retained native logs; hashes are content identity, not authentication",
    }


def register(campaign, frozen_source, upstream, *, authorization, python=None, bridge=None):
    """Freeze the amendment before resuming any pending trial; does not dispatch."""
    controller = require_controller()
    campaign, frozen_source, upstream = map(_safe, (campaign, frozen_source, upstream))
    if authorization != "partial accounting":
        raise ValueError("registration requires the explicit partial accounting authorization")
    local = {
        "frozen_source": str(frozen_source),
        "upstream": str(upstream),
        "python": str(python or sys.executable),
    }
    registration_sha256 = digest(read_json(campaign / "registration-lock.json"))
    bridge = bridge or FrozenBridge(local["python"])
    with _lock(campaign):
        info = bridge("verify", _request(campaign, local, registration_sha256))
        if len(info["schedule"]) != 36 or any(row["stage"] != "pilot" for row in info["schedule"]):
            raise ValueError("amendment requires the original 36-trial pilot")
        states = info["states"]
        baseline = info["attempts"]
        if len(baseline) != 9 or any(row["attempt"] != 1 or row["status"] != "completed" for row in baseline):
            raise ValueError("amendment must preserve exactly the nine original completed attempts")
        pending = [
            row["trial_id"]
            for row in info["schedule"]
            if next(s for s in states if s["trial_id"] == row["trial_id"])["status"] == "pending"
        ]
        if len(pending) != 27 or any(s["attempts"] != 0 for s in states if s["trial_id"] in pending):
            raise ValueError("amendment requires exactly 27 pending first attempts")
        stops = sorted((campaign / "runs").glob("run-*/end.json"))
        if not stops or read_json(stops[-1]).get("reason") != "usage_accounting_requires_remediation":
            raise ValueError("amendment requires the retained accounting pause")
        initial = [_derive(campaign, row, None) for row in baseline]
        if any(not row["continuation_admissible"] for row in initial):
            raise ValueError(
                "retained pilot has a structural/runtime blocker; partial usage approval is insufficient"
            )
        record = {
            "schema_version": "evalopt.partial-accounting-amendment.v1",
            "authorization": {"decision": "allow_partial_accounting", "statement": authorization},
            "controller": controller,
            "controller_sources": code_identity(),
            "policy": POLICY,
            "pilot_registration_sha256": registration_sha256,
            "source_lock": info["source_lock"],
            "schedule_sha256": info["schedule_sha256"],
            "baseline_attempts": [_bound_attempt(row) for row in baseline],
            "pending_trial_ids": pending,
            "baseline_usage": {_attempt_key(row): digest(row["derived_usage"]) for row in initial},
            "pause_receipt": {
                "path": stops[-1].relative_to(campaign).as_posix(),
                "sha256": bytes_digest(stops[-1].read_bytes()),
            },
            "local_sources_sha256": digest(local),
        }
        identity = digest(record)
        sidecars = [{**row, "amendment_sha256": identity} for row in initial]
        root = campaign / AMENDMENT
        _put(root / "local-sources.json", local)
        _put(root / "amendment.json", record)
        for sidecar in sidecars:
            _put(root / "usage" / (_attempt_key(sidecar) + ".json"), sidecar)
        return {"amendment_sha256": identity, "preserved_attempts": 9, "pending_trials": 27}


def verify(campaign, amendment_sha256, *, bridge=None, live=False, _active_run=None, _new_trial=None):
    require_controller()
    campaign = _safe(campaign)
    root = campaign / AMENDMENT
    record = read_json(_safe(root / "amendment.json"))
    if not is_digest(amendment_sha256) or digest(record) != amendment_sha256:
        raise ValueError("amendment differs from explicit identity")
    if record["schema_version"] != "evalopt.partial-accounting-amendment.v1" or record["policy"] != POLICY:
        raise ValueError("unsupported accounting amendment policy")
    if record["controller"] != require_controller() or record["controller_sources"] != code_identity():
        raise ValueError("amendment controller source or interpreter changed")
    local = read_json(_safe(root / "local-sources.json"))
    exact(local, {"frozen_source", "upstream", "python"}, "local amendment sources")
    if digest(local) != record["local_sources_sha256"]:
        raise ValueError("local amendment source binding changed")
    pause = record["pause_receipt"]
    pause_path = _safe(campaign / pause["path"])
    if not pause_path.is_relative_to(campaign) or bytes_digest(pause_path.read_bytes()) != pause["sha256"]:
        raise ValueError("original accounting pause changed")
    bridge = bridge or FrozenBridge(local["python"])
    info = bridge(
        "verify" if live else "inspect", _request(campaign, local, record["pilot_registration_sha256"])
    )
    if info["source_lock"] != record["source_lock"] or info["schedule_sha256"] != record["schedule_sha256"]:
        raise ValueError("frozen pilot conditions differ from amendment")
    attempts = {_attempt_key(row): row for row in info["attempts"]}
    for original in record["baseline_attempts"]:
        current = attempts.get(_attempt_key(original))
        if current is None or _bound_attempt(current) != original:
            raise ValueError("original pilot attempt changed")
        key = _attempt_key(original)
        saved_path = _safe(root / "usage" / (key + ".json"))
        if not saved_path.is_file():
            raise ValueError("original pilot usage sidecar is missing")
        if digest(_derive(campaign, current, amendment_sha256)["derived_usage"]) != record[
            "baseline_usage"
        ].get(key):
            raise ValueError("original pilot accounting source or derived usage changed")
    permitted = {row["trial_id"] for row in record["baseline_attempts"]} | set(record["pending_trial_ids"])
    if len(permitted) != 36 or permitted != {row["trial_id"] for row in info["schedule"]}:
        raise ValueError("amendment trial roster differs from frozen pilot")
    for row in attempts.values():
        if row["trial_id"] not in permitted:
            raise ValueError("unscheduled amendment attempt")
    for path in sorted((root / "usage").glob("*/attempt-*.json")):
        saved = read_json(_safe(path))
        key = _attempt_key(saved)
        if key not in attempts or saved != _derive(campaign, attempts[key], amendment_sha256):
            raise ValueError("derived usage, raw logs, or attempt binding changed")
    captured = set()
    for run_path in sorted((root / "runs").glob("run-*")):
        _safe(run_path)
        start = read_json(_safe(run_path / "start.json"))
        if start.get("amendment_sha256") != amendment_sha256:
            raise ValueError("amended run belongs to a different amendment")
        if not (run_path / "end.json").is_file() and run_path.name != _active_run:
            raise ValueError("interrupted amended controller requires explicit recovery")
        completed = set()
        for path in sorted(run_path.glob("*/completed.json")):
            receipt = read_json(_safe(path))
            key = _attempt_key(receipt)
            if key in captured or key not in attempts or receipt.get("amendment_sha256") != amendment_sha256:
                raise ValueError("duplicate or unregistered amended completion receipt")
            sidecar_path = _safe(root / "usage" / (key + ".json"))
            if (
                not sidecar_path.is_file()
                or receipt.get("sidecar_sha256") != digest(read_json(sidecar_path))
                or _bound_attempt(receipt) != _bound_attempt(attempts[key])
                or receipt["trial_id"] not in start["pending_at_start"]
            ):
                raise ValueError("completed amended attempt or accounting receipt changed")
            captured.add(key)
            completed.add(receipt["trial_id"])
        if (run_path / "end.json").is_file():
            end = read_json(_safe(run_path / "end.json"))
            if set(end["dispatched"]) != completed or len(end["dispatched"]) != len(completed):
                raise ValueError("amended run completion roster differs from captured attempts")
    baseline_keys = {_attempt_key(row) for row in record["baseline_attempts"]}
    for key, row in attempts.items():
        if key not in baseline_keys | captured and row["trial_id"] != _new_trial:
            raise ValueError("new attempt lacks its immutable amendment completion receipt")
    return {"amendment": record, "info": info, "local": local}


def derive_attempt(campaign, amendment_sha256, trial_id, attempt=1, *, bridge=None):
    verified = verify(campaign, amendment_sha256, bridge=bridge)
    row = next(
        item
        for item in verified["info"]["attempts"]
        if item["trial_id"] == trial_id and item["attempt"] == attempt
    )
    sidecar = _derive(_safe(campaign), row, amendment_sha256)
    _put(Path(campaign) / AMENDMENT / "usage" / (_attempt_key(row) + ".json"), sidecar)
    return sidecar


def _pause(info, sidecars):
    by_trial = {row["trial_id"]: row for row in sidecars}
    for row in info["attempts"]:
        if row["error_code"] == "subscription_exhausted":
            return "subscription_exhausted", row["trial_id"]
        if row["status"] == "infra_failure":
            return "infrastructure_failure_requires_inspection", row["trial_id"]
        sidecar = by_trial.get(row["trial_id"])
        if sidecar is None or not sidecar["continuation_admissible"]:
            return (sidecar or {}).get(
                "continuation_blocker"
            ) or "usage_accounting_requires_remediation", row["trial_id"]
    if any(row["status"] == "running_or_interrupted" for row in info["states"]):
        return "interrupted_controller_requires_recovery", None
    return None, None


def _all_sidecars(campaign, amendment_sha256, info):
    result = []
    for row in info["attempts"]:
        sidecar = _derive(campaign, row, amendment_sha256)
        _put(campaign / AMENDMENT / "usage" / (_attempt_key(row) + ".json"), sidecar)
        result.append(sidecar)
    return result


def run(campaign, amendment_sha256, *, limit=None, bridge=None):
    """Resume only still-pending first attempts; fresh failures pause without retry."""
    campaign = _safe(campaign)
    if limit is not None and (type(limit) is not int or limit <= 0):
        raise ValueError("limit must be positive")
    with _lock(campaign):
        verified = verify(campaign, amendment_sha256, bridge=bridge, live=True)
        bridge = bridge or FrozenBridge(verified["local"]["python"])
        info = verified["info"]
        sidecars = _all_sidecars(campaign, amendment_sha256, info)
        reason, blocked = _pause(info, sidecars)
        queue = [
            row
            for row in info["schedule"]
            if next(s for s in info["states"] if s["trial_id"] == row["trial_id"])["status"] == "pending"
        ]
        if limit is not None:
            queue = queue[:limit]
        runs = campaign / AMENDMENT / "runs"
        number = 1
        while (runs / f"run-{number:04d}").exists():
            number += 1
        run_root = runs / f"run-{number:04d}"
        _put(
            run_root / "start.json",
            {
                "schema_version": "evalopt.amended-run.v1",
                "amendment_sha256": amendment_sha256,
                "pending_at_start": [row["trial_id"] for row in queue],
            },
        )
        dispatched = []
        try:
            for row in [] if reason else queue:
                verified = verify(
                    campaign, amendment_sha256, bridge=bridge, live=True, _active_run=run_root.name
                )
                request = _request(
                    campaign, verified["local"], verified["amendment"]["pilot_registration_sha256"]
                )
                request.update(
                    trial_id=row["trial_id"],
                    amendment_sha256=amendment_sha256,
                    permission_receipt=str(run_root / row["trial_id"] / "permission.json"),
                )
                result = bridge("execute", request)
                if result.get("dispatched") is not True:
                    reason, blocked = result.get("reason", "dispatch_requires_inspection"), row["trial_id"]
                    break
                dispatched.append(row["trial_id"])
                verified = verify(
                    campaign,
                    amendment_sha256,
                    bridge=bridge,
                    live=True,
                    _active_run=run_root.name,
                    _new_trial=row["trial_id"],
                )
                info = verified["info"]
                recorded = [item for item in info["attempts"] if item["trial_id"] == row["trial_id"]]
                if (
                    len(recorded) != 1
                    or result.get("trial_id") != row["trial_id"]
                    or result.get("status") != recorded[0]["status"]
                ):
                    raise ValueError("bridge dispatch result differs from retained attempt")
                sidecars = _all_sidecars(campaign, amendment_sha256, info)
                captured = next(item for item in sidecars if item["trial_id"] == row["trial_id"])
                _put(
                    run_root / row["trial_id"] / "completed.json",
                    {
                        "schema_version": "evalopt.amended-completion.v1",
                        "amendment_sha256": amendment_sha256,
                        **_bound_attempt(recorded[0]),
                        "sidecar_sha256": digest(captured),
                    },
                )
                reason, blocked = _pause(info, sidecars)
                if reason:
                    break
        except BaseException as exc:
            _put(
                run_root / "end.json",
                {
                    "schema_version": "evalopt.amended-stop.v1",
                    "status": "interrupted",
                    "reason": type(exc).__name__,
                    "dispatched": dispatched,
                },
            )
            raise
        remaining = sum(row["status"] == "pending" for row in info["states"])
        summary = {
            "schema_version": "evalopt.amended-stop.v1",
            "status": "paused" if reason else ("limited" if remaining else "finished"),
            "reason": reason,
            "trial_id": blocked,
            "dispatched": dispatched,
            "pending_trials": remaining,
        }
        _put(run_root / "end.json", summary)
        return {**summary, "accounting_report": report(campaign, amendment_sha256, bridge=bridge)}


def summarize_resources(
    amendment_sha256, registration_sha256, schedule, attemptstates, sidecars, frozen_export_id
):
    """Pure public arithmetic; counters remain supplied controller evidence, not authentication."""
    require_controller()
    if len(schedule) != 36 or len({row["trial_id"] for row in schedule}) != 36:
        raise ValueError("resource report requires the registered 36-trial pilot")
    states = {row["trial_id"]: row for row in attemptstates}
    if len(states) != len(attemptstates) or set(states) != {row["trial_id"] for row in schedule}:
        raise ValueError("resource status roster differs from schedule")
    if len({_attempt_key(row) for row in sidecars}) != len(sidecars):
        raise ValueError("duplicate resource attempt")
    arms = {}
    arm_by_trial = {row["trial_id"]: row["arm"] for row in schedule}
    if any(row["trial_id"] not in states or row["amendment_sha256"] != amendment_sha256 for row in sidecars):
        raise ValueError("resource attempt is unscheduled or belongs to another amendment")
    for arm in "ABC":
        selected = [row for row in sidecars if arm_by_trial[row["trial_id"]] == arm]
        scheduled = [row for row in schedule if row["arm"] == arm]
        valid = [
            row["derived_usage"]
            for row in selected
            if row["derived_usage"]["provenance_status"] == "valid"
            and all(
                type(row["derived_usage"]["lower_bounds"].get(key)) is int
                and row["derived_usage"]["lower_bounds"][key] >= 0
                for key in COUNTERS
            )
        ]
        complete = [row for row in valid if row["accounting_status"] == "complete"]
        partial = [row for row in valid if row["accounting_status"] == "partial"]
        arms[arm] = {
            "scheduled_trials": len(scheduled),
            "pending_trials": sum(states[row["trial_id"]]["status"] == "pending" for row in scheduled),
            "retained_attempts": len(selected),
            "complete_attempts": len(complete),
            "partial_attempts": len(partial),
            "unavailable_accounting_attempts": len(selected) - len(valid),
            "continuation_blocked_attempts": sum(not row["continuation_admissible"] for row in selected),
            "runtime_invalid_attempts": sum(
                row["continuation_blocker"] == "runtime_identity_requires_remediation" for row in selected
            ),
            "observed_lower_bounds": {
                key: sum(row["lower_bounds"][key] for row in valid) for key in COUNTERS
            },
            "partial_attempts_lower_bounds": {
                key: sum(row["lower_bounds"][key] for row in partial) for key in COUNTERS
            },
            "complete_attempts_exact_totals": {
                key: sum(row["complete_usage"][key] for row in complete) for key in COUNTERS
            },
        }
    return {
        "schema_version": "evalopt.amended-resource-report.v1",
        "amendment_sha256": amendment_sha256,
        "pilot_registration_sha256": registration_sha256,
        "frozen_export_id": frozen_export_id,
        "schedule_sha256": digest(schedule),
        "attempt_sidecars": {_attempt_key(row): digest(row) for row in sidecars},
        "arms": arms,
        "scheduled_trials": 36,
        "retained_attempts": len(sidecars),
        "pending_trials": sum(row["status"] == "pending" for row in attemptstates),
        "efficiency_comparison_eligible": len(sidecars) == 36
        and all(
            row["continuation_admissible"] and row["derived_usage"]["efficiency_eligible"] for row in sidecars
        ),
        "scope": "arithmetic replay from sanitized, source-bound controller counters; raw native logs are private; no independent raw-log replay or authentication claim",
        "resource_semantics": "observed lower bounds include complete and partial attempts once; exact totals cover complete attempts only and must not be added to lower bounds; missing usage is not zero",
        "outcome_analysis": "unchanged frozen report; partial accounting does not remove or rescore outcomes",
        "dollar_cost": None,
    }


def report(campaign, amendment_sha256, *, bridge=None):
    """Keep frozen outcome analysis untouched and add a separately identified usage report."""
    campaign = _safe(campaign)
    verified = verify(campaign, amendment_sha256, bridge=bridge)
    info = verified["info"]
    bridge = bridge or FrozenBridge(verified["local"]["python"])
    sidecars = _all_sidecars(campaign, amendment_sha256, info)
    original = bridge(
        "report", _request(campaign, verified["local"], verified["amendment"]["pilot_registration_sha256"])
    )
    payload = summarize_resources(
        amendment_sha256,
        verified["amendment"]["pilot_registration_sha256"],
        info["schedule"],
        info["states"],
        sidecars,
        original["export_id"],
    )
    identity = digest(payload)
    _put(campaign / AMENDMENT / "reports" / identity / "resource-report.json", payload)
    return {"report_sha256": identity, "frozen_export_id": original["export_id"], "resource_report": payload}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "verify", "derive", "run", "report"))
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--amendment-sha256")
    parser.add_argument("--frozen-source", type=Path)
    parser.add_argument("--upstream", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--authorization")
    parser.add_argument("--trial-id")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    if args.command == "register":
        if not args.frozen_source or not args.upstream:
            parser.error("register requires --frozen-source and --upstream")
        result = register(
            args.campaign,
            args.frozen_source,
            args.upstream,
            authorization=args.authorization,
            python=args.python,
        )
    elif args.command == "verify":
        result = verify(args.campaign, args.amendment_sha256, live=True)
        result = {
            "verified": True,
            "amendment_sha256": args.amendment_sha256,
            "retained_attempts": len(result["info"]["attempts"]),
        }
    elif args.command == "derive":
        result = derive_attempt(args.campaign, args.amendment_sha256, args.trial_id)
    elif args.command == "run":
        result = run(args.campaign, args.amendment_sha256, limit=args.limit)
    else:
        result = report(args.campaign, args.amendment_sha256)
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 2 if result.get("status") == "paused" else 0


if __name__ == "__main__":
    raise SystemExit(main())
