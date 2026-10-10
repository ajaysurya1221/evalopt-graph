#!/usr/bin/env python3
"""Trusted-path controller entrypoint; no candidate directory enters sys.path."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# -B disables writing caches, not reading them. Before the first frozen module
# import, reject both tagged caches and legacy sourceless bytecode. The trusted
# outer launcher verifies the external registration before re-executing this file.
if HERE.name == "harness" and HERE.parent.name == "frozen":
    if any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"} for path in HERE.rglob("*")):
        print('{"state":"stopped","reason":"frozen_harness_bytecode_forbidden"}', file=sys.stderr)
        raise SystemExit(1)
sys.path.insert(0, str(HERE))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    preserve = sub.add_parser("preserve")
    preserve.add_argument("--source", type=Path, default=HERE.parents[2])
    preflight = sub.add_parser("preflight")
    preflight.add_argument("--agent-image", required=True)
    preflight.add_argument("--verifier-image", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--destination", type=Path, required=True)
    prepare.add_argument("--task-root", type=Path, required=True)
    prepare.add_argument("--upstream", type=Path, required=True)
    prepare.add_argument("--admission", type=Path, required=True)
    prepare.add_argument("--agent-image", required=True)
    prepare.add_argument("--verifier-image", required=True)
    prepare.add_argument("--stage", choices=("development", "heldout"), default="development")
    prepare.add_argument("--development-admission", type=Path)
    for name in ("run", "replay"):
        command = sub.add_parser(name)
        command.add_argument("--campaign", type=Path, required=True)
        command.add_argument("--registration-sha256", required=True)
        if name == "run":
            command.add_argument("--limit", type=int, default=1)
        else:
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "preserve":
        from evalopt_v2.preservation import verify

        result = verify(args.source)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] == "PASS" else 1
    if args.command == "preflight":
        from evalopt_v2.preflight import (
            auth_path,
            image_identity,
            native_config,
            require_versions,
            subscription_permission,
        )

        result = {
            "versions": require_versions(),
            "agent_image": image_identity(args.agent_image),
            "verifier_image": image_identity(args.verifier_image),
        }
        auth_path()
        result["authentication"] = "chatgpt"
        result["native_config_sha256"] = native_config(HERE / "runtime/codex.toml")[1]
        result["subscription_permission"] = subscription_permission()
        result["model_availability"] = "not_probed_no_model_request"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["subscription_permission"]["ordinary_usage_allowed"] is True else 1
    if args.command == "prepare":
        from evalopt_v2.framing import strict_json
        from evalopt_v2.freeze import prepare as freeze
        from evalopt_v2.preservation import verify

        source = HERE.parents[2]
        if verify(source)["status"] != "PASS":
            raise ValueError("v1_preservation_failed")
        receipt = freeze(
            args.destination,
            harness=HERE,
            skill_c=source / "skills/eval-opt-v2",
            kernel=source / "src/evalopt_graph",
            task_root=args.task_root,
            upstream=args.upstream,
            agent_image=args.agent_image,
            verifier_image=args.verifier_image,
            admission=strict_json(args.admission.read_bytes()),
            stage=args.stage,
            development_admission=strict_json(args.development_admission.read_bytes())
            if args.development_admission
            else None,
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
        return 0
    from evalopt_v2.freeze import verify_frozen, verify_kernel_import

    root = args.campaign.absolute()
    verify_frozen(root, expected_sha256=args.registration_sha256)
    frozen_entry = root / "frozen/harness/run.py"
    if Path(__file__).resolve() != frozen_entry:
        # Reload all implementation modules from the verified frozen source.
        os.execv(sys.executable, [sys.executable, "-I", "-B", str(frozen_entry), *sys.argv[1:]])
    sys.path.insert(0, str(root / "frozen/kernel"))
    verify_kernel_import(root)
    from evalopt_v2.campaign import execute_campaign, replay
    from evalopt_v2.store import exclusive_json

    if args.command == "run":
        result = asyncio.run(
            execute_campaign(root, expected_sha256=args.registration_sha256, limit=args.limit)
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["state"] in {"complete", "dispatch_limit_reached"} else 1
    result = replay(root, expected_sha256=args.registration_sha256)
    exclusive_json(args.output, result)
    print(
        json.dumps(
            {
                "report": str(args.output),
                "finalized_rows": result["finalized_rows"],
                "retained_attempts": result["retained_attempts"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception as error:
        # CLI error messages must not echo private paths, subprocess auth or code.
        print(json.dumps({"state": "stopped", "error_type": type(error).__name__}), file=sys.stderr)
        code = 1
    raise SystemExit(code)
