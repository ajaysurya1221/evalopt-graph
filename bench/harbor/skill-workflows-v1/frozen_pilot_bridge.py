#!/usr/bin/env python3
"""Isolated bridge to an unchanged registered pilot controller; no replacement runtime."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _regular(path):
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("bridge paths cannot traverse symlinks")
    return path


def _tree(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if "__pycache__" in path.parts:
            continue
        if path.is_symlink():
            raise ValueError("frozen source contains a symlink")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def _origins(source):
    repository = source.parents[2]
    for name, module in tuple(sys.modules.items()):
        prefix = name.split(".")[0]
        if prefix not in {"campaign", "lib", "runtime", "tasks", "evalopt_graph"}:
            continue
        filename = getattr(module, "__file__", None)
        if filename is None:
            continue
        expected = repository / "src" if prefix == "evalopt_graph" else source
        if not Path(filename).resolve().is_relative_to(expected):
            raise ValueError("frozen bridge imported a controller module from another source")


def perform(action, request):
    """Called in a fresh `python -I` process, before any benchmark package import."""
    if tuple(sys.version_info[:3]) != (3, 13, 12) or sys.implementation.name != "cpython":
        raise ValueError("frozen bridge requires CPython 3.13.12")
    source = _regular(request["frozen_source"])
    destination = _regular(request["campaign"])
    upstream = _regular(request["upstream"])
    registration = json.loads((destination / "registration-lock.json").read_bytes())
    if _digest(registration) != request["registration_sha256"]:
        raise ValueError("frozen registration differs from amendment")
    lock = json.loads((destination / "source-lock.json").read_bytes())
    if _tree(source) != lock["campaign_sha256"]:
        raise ValueError("frozen benchmark bytes changed before import")
    if _tree(source.parents[2] / "src/evalopt_graph") != lock["kernel_source_sha256"]:
        raise ValueError("frozen kernel bytes changed before import")
    sys.path[:0] = [str(source), str(source.parents[2] / "src")]
    import campaign
    from lib.common import bytes_digest, read_json, write_once
    from lib.manifest import build_schedule, validate_manifest
    from lib.store import CampaignStore

    _origins(source)
    if registration != campaign._registration_identity(destination):
        raise ValueError("frozen campaign registration files changed")
    if lock != campaign._source_lock(upstream):
        raise ValueError("frozen source, skill, upstream or kernel identity changed")
    manifest = validate_manifest(read_json(destination / "manifest.json"))
    schedule = build_schedule(manifest["tasks"], "pilot")
    store = CampaignStore(destination / "evidence", schedule)
    if action in {"verify", "execute"}:
        _, runtime, schedule, store = campaign._verify_campaign(destination, upstream)
    if action == "execute":
        trial_id = request["trial_id"]
        amendment = json.loads((destination / "amendments/partial-accounting-v1/amendment.json").read_bytes())
        if (
            _digest(amendment) != request.get("amendment_sha256")
            or amendment["pilot_registration_sha256"] != request["registration_sha256"]
            or amendment["source_lock"] != lock
            or trial_id not in amendment["pending_trial_ids"]
            or amendment["controller_sources"]["frozen_pilot_bridge.py"]
            != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        ):
            raise ValueError("dispatch is not bound to the approved amendment")
        state = next(item for item in store.statuses() if item["trial_id"] == trial_id)
        if state["status"] != "pending" or state["attempts"] != 0:
            raise ValueError("amendment dispatch permits pending first attempts only")
        receipt = _regular(request["permission_receipt"])
        expected = destination / "amendments/partial-accounting-v1/runs"
        if not receipt.is_relative_to(expected) or receipt.name != "permission.json":
            raise ValueError("permission receipt must belong to the amendment dispatch")
        campaign.subscription_environment()
        try:
            permission = campaign.read_subscription_permission()
        except (OSError, ValueError):
            permission = {}
        schema = (
            isinstance(permission, dict)
            and permission.get("schema_version") == "evalopt.subscription-permission.v1"
        )
        allowed = (
            schema
            and permission.get("ordinary_usage_allowed") is True
            and permission.get("state") == "allowed"
        )
        exhausted = (
            schema
            and permission.get("ordinary_usage_allowed") is False
            and permission.get("state") == "exhausted"
        )
        write_once(
            receipt,
            {
                "schema_version": "evalopt.amended-permission.v1",
                "trial_id": trial_id,
                "amendment_sha256": request["amendment_sha256"],
                "ordinary_usage_allowed": bool(allowed),
                "state": "allowed" if allowed else ("exhausted" if exhausted else "unavailable"),
            },
        )
        if not allowed:
            return {
                "dispatched": False,
                "reason": "subscription_exhausted" if exhausted else "subscription_permission_unavailable",
            }
        row = next(row for row in schedule if row["trial_id"] == trial_id)
        result = asyncio.run(
            campaign.execute_trial(
                row,
                store,
                destination / "private-harbor",
                upstream,
                runtime["agent_image"],
                runtime["verifier_image"],
            )
        )
        _origins(source)
        campaign._verify_campaign(destination, upstream)
        return {"dispatched": True, "trial_id": trial_id, "status": result["status"]}
    if action == "report":
        result = campaign.report(destination)
        _origins(source)
        return {"export_id": result["export_id"]}
    if action not in {"inspect", "verify"}:
        raise ValueError("unsupported frozen bridge action")
    states = store.statuses()
    attempts = []
    for state in states:
        for number in range(1, state["attempts"] + 1):
            store.verify_attempt(state["trial_id"], number)
            path = store.root / "trials" / state["trial_id"] / f"attempt-{number}"
            if not (path / "finish.json").is_file() or not (path / "manifest.json").is_file():
                raise ValueError("interrupted attempt requires separate recovery before amended resume")
            finish = read_json(path / "finish.json")
            attempts.append(
                {
                    "trial_id": state["trial_id"],
                    "attempt": number,
                    "status": finish["status"],
                    "error_code": finish.get("error_code"),
                    "finish_sha256": bytes_digest((path / "finish.json").read_bytes()),
                    "manifest_sha256": bytes_digest((path / "manifest.json").read_bytes()),
                    "usage": {
                        key: value
                        for key, value in (finish.get("usage") or {}).items()
                        if key
                        in {
                            "child_usage_complete",
                            "runtime_valid",
                            "input_tokens",
                            "output_tokens",
                            "model_calls",
                            "tool_calls",
                            "wall_seconds",
                            "agent_count",
                            "aggregation",
                            "schema_version",
                            "accounting_status",
                        }
                    },
                }
            )
    _origins(source)
    return {
        "registration_sha256": _digest(registration),
        "source_lock": lock,
        "schedule": schedule,
        "schedule_sha256": _digest(schedule),
        "states": states,
        "attempts": attempts,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("inspect", "verify", "execute", "report"))
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    request = json.loads(sys.stdin.read())
    # The parent captures this process's stdout/stderr privately. Only this bounded
    # structured result crosses the controller interface.
    result = perform(args.action, request)
    with args.result.open("x") as stream:
        json.dump(result, stream, sort_keys=True, allow_nan=False)


if __name__ == "__main__":
    main()
