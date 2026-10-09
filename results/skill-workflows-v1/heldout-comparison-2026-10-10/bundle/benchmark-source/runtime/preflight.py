"""Pinned runtime probes. Never prints credentials or raw model trajectories."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODEL = "gpt-6-astra"


def command(argv: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(argv, text=True, capture_output=True, timeout=timeout, check=False)


def probe(image: str, output: Path, *, live: bool = False, upstream: Path | None = None) -> dict:
    from lib.accounting import parse_native_usage, summarize_usage
    from runtime.harbor_campaign import REPO, source_identity, upstream_skills

    output.mkdir(parents=True, exist_ok=False)
    os.chmod(output, 0o700)
    checks = {}
    version = command(["docker", "image", "inspect", image, "--format", "{{.Id}}"])
    checks["image_present"] = version.returncode == 0
    result = {
        "schema_version": "evalopt.runtime-preflight.v1",
        "checks": checks,
        "image_id": version.stdout.strip() if version.returncode == 0 else None,
        "live_requested": live,
        "benchmark_trials": 0,
    }
    if not checks["image_present"]:
        (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    image = result["image_id"]
    name = "evalopt-preflight-" + uuid.uuid4().hex[:12]
    args = [
        "docker",
        "create",
        "--name",
        name,
        "--cpus",
        "1",
        "--memory",
        "2g",
        "--mount",
        f"type=bind,src={HERE / 'codex.toml'},dst=/run/codex.toml,readonly",
    ]
    auth = Path.home() / ".codex" / "auth.json"
    if live:
        if not auth.is_file():
            raise ValueError("existing subscription authentication file unavailable")
        args += ["--mount", f"type=bind,src={auth},dst=/run/auth.json,readonly"]
    else:
        args += ["--network", "none"]
    args += [image, "sleep", "infinity"]
    created = command(args)
    if created.returncode:
        raise RuntimeError("could not create preflight container")
    try:
        if command(["docker", "start", name]).returncode:
            raise RuntimeError("could not start preflight container")
        setup = "mkdir -p /root/.codex /workspace && cp /run/codex.toml /root/.codex/config.toml"
        if live:
            setup += " && ln -s /run/auth.json /root/.codex/auth.json"
        if command(["docker", "exec", name, "sh", "-c", setup]).returncode:
            raise RuntimeError("could not initialize isolated configuration")
        expected_skills = ["diagnosing-bugs", "implement", "tdd", "code-review", "eval-opt"]
        if upstream:
            sources = upstream_skills(upstream)
            sources.append(REPO / "skills" / "eval-opt")
            command(["docker", "exec", name, "mkdir", "-p", "/root/.agents/skills"])
            for source in sources:
                if command(
                    ["docker", "cp", str(source), f"{name}:/root/.agents/skills/{source.name}"]
                ).returncode:
                    raise RuntimeError("skill injection failed")
            result["skill_sources"] = {
                "upstream": source_identity(upstream / "skills"),
                "evalopt": source_identity(REPO / "skills" / "eval-opt"),
            }
        ver = command(["docker", "exec", name, "codex", "--version"])
        checks["codex_version"] = ver.stdout.strip() == "codex-cli 0.154.0"
        features = command(["docker", "exec", name, "codex", "features", "list"])
        checks["configuration_parses"] = features.returncode == 0
        checks["native_multi_agent_enabled"] = any(
            line.split() == ["multi_agent", "stable", "true"] for line in features.stdout.splitlines()
        )
        if live and all(checks.values()):
            auth_status = command(["docker", "exec", name, "codex", "login", "status"])
            checks["subscription_auth"] = auth_status.returncode == 0 and "ChatGPT" in (
                auth_status.stdout + auth_status.stderr
            )
            if checks["subscription_auth"]:
                prompt = (
                    "Runtime preflight only. Use native subagents to start two children concurrently. "
                    "Each child must return a distinct word and stop without tools or edits. "
                    "Wait for both, then return PREFLIGHT_COMPLETE. Do not change model or effort. "
                    "Do not read credentials, host settings, or network resources."
                )
                if upstream:
                    prompt += (
                        " Before delegating, use a shell read command to load each of these skill files "
                        "in full, solely to verify loader compatibility (do not execute their workflows): "
                        + " ".join(f"/root/.agents/skills/{skill}/SKILL.md" for skill in expected_skills)
                    )
                run = command(
                    [
                        "docker",
                        "exec",
                        name,
                        "codex",
                        "exec",
                        "--strict-config",
                        "--skip-git-repo-check",
                        "--dangerously-bypass-approvals-and-sandbox",
                        "--json",
                        "--model",
                        MODEL,
                        prompt,
                    ],
                    timeout=180,
                )
                # Private raw output is retained for accounting audit, never printed/published.
                (output / "events.jsonl").write_text(run.stdout)
                (output / "stderr.txt").write_text(run.stderr)
                checks["live_exit_zero"] = run.returncode == 0
                checks["live_completion_marker"] = "PREFLIGHT_COMPLETE" in run.stdout
                command(["docker", "cp", f"{name}:/root/.codex/sessions", str(output / "sessions")])
                contexts, subagents = [], set()
                tool_output = []
                for path in (output / "sessions").rglob("*.jsonl"):
                    for line in path.read_text().splitlines():
                        try:
                            event = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        payload = event.get("payload", {})
                        if event.get("type") == "response_item" and payload.get("type") in {
                            "function_call_output",
                            "custom_tool_call_output",
                        }:
                            tool_output.append(str(payload.get("output", "")))
                        if event.get("type") == "turn_context":
                            contexts.append({"model": payload.get("model"), "effort": payload.get("effort")})
                        if event.get("type") == "session_meta" and isinstance(payload.get("source"), dict):
                            subagents.add(payload.get("id"))
                result["returned_contexts"] = contexts
                result["child_sessions"] = len(subagents)
                checks["model_identity"] = bool(contexts) and all(c["model"] == MODEL for c in contexts)
                checks["reasoning_identity"] = bool(contexts) and all(
                    c["effort"] == "ultra" for c in contexts
                )
                checks["two_native_children"] = len(subagents) == 2
                result["skill_loads"] = {
                    skill: f"name: {skill}" in "\n".join(tool_output).replace("\\n", "\n")
                    for skill in expected_skills
                }
                checks["skill_and_dependency_loading"] = upstream is not None and all(
                    result["skill_loads"].values()
                )
                try:
                    result["usage"] = summarize_usage(parse_native_usage(output / "sessions"))
                    checks["complete_usage_accounting"] = True
                except (ValueError, KeyError, OSError):
                    checks["complete_usage_accounting"] = False
        result["config_sha256"] = hashlib.sha256((HERE / "codex.toml").read_bytes()).hexdigest()
        result["status"] = "PASS" if live and all(checks.values()) else "NOT_READY"
        result["accounting_audit_required"] = not checks.get("complete_usage_accounting", False)
        (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n")
        return result
    finally:
        command(["docker", "rm", "-f", name])


if __name__ == "__main__":
    sys.path.insert(0, str(HERE.parent))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--upstream", type=Path)
    parser.add_argument(
        "--live", action="store_true", help="Use existing subscription for one bounded native preflight"
    )
    args = parser.parse_args()
    print(json.dumps(probe(args.image, args.output, live=args.live, upstream=args.upstream), indent=2))
