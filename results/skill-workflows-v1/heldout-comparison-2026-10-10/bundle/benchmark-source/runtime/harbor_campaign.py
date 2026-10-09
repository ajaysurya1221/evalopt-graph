"""Authored-suite controller around Harbor 0.24; never an evalopt kernel runtime."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[2]


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, text=True, timeout=120, **kwargs)


def image_identity(name):
    return run(["docker", "image", "inspect", name, "--format", "{{.Id}}"]).stdout.strip()


def upstream_skills(upstream):
    manifest = json.loads((upstream / ".claude-plugin" / "plugin.json").read_text())
    paths = [(upstream / relative).resolve() for relative in manifest["skills"]]
    if len(paths) != 27 or len({path.name for path in paths}) != 27:
        raise ValueError("expected all 27 shipped upstream skills")
    if any(
        not path.is_relative_to(upstream.resolve()) or not (path / "SKILL.md").is_file() for path in paths
    ):
        raise ValueError("unsafe or missing upstream skill path")
    return paths


def local_image_reference(identity):
    resolved = image_identity(identity)
    reference = "evalopt-workflows-pin:" + resolved.removeprefix("sha256:")
    run(["docker", "tag", resolved, reference])
    if image_identity(reference) != resolved:
        raise ValueError("local image reference does not match frozen digest")
    return reference


def source_identity(root):
    files = {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "__pycache__" not in p.parts
    }
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def materialize(task, path, *, agent_image, verifier_image, arm, task_root=None):
    from tasks.suite import file_manifest, instruction, materialize_agent, task_path

    path.mkdir(parents=True, exist_ok=False)
    environment = path / "environment"
    workspace = environment / "workspace"
    materialize_agent(task, workspace, task_root=task_root)
    # Identical preconfigured facts; no installation or external tracker mutation.
    common = {
        "docs/agents/issue-tracker.md": "Issues are local Markdown. The task's supplied specification is the issue. No external tracker.\n",
        "docs/agents/domain.md": "One local domain; task specification defines behavior. No external domain knowledge required.\n",
        "GLOSSARY.md": "Use the vocabulary in the supplied task specification.\n",
        "SPEC.md": instruction(task),
    }
    for name, content in common.items():
        target = workspace / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    # Common docs are present before initial boundary capture in every arm.
    initial = file_manifest(workspace)
    agent_reference = local_image_reference(agent_image)
    verifier_reference = local_image_reference(verifier_image)
    (environment / "Dockerfile").write_text(
        f"FROM {agent_reference}\nCOPY workspace /workspace\nWORKDIR /workspace\n"
    )
    entry = (
        "code-review"
        if "review" in task["category"]
        else ("implement" if task["category"] == "bounded-implementation" else "diagnosing-bugs")
    )
    invocation = {
        "A": "",
        "B": f"Use ${entry}. Read /root/.agents/skills/{entry}/SKILL.md before starting.\n",
        "C": "Use $eval-opt. Read /root/.agents/skills/eval-opt/SKILL.md before starting.\n",
    }[arm]
    context = (
        "Work in /workspace. The specification is SPEC.md; review base is benchmark-base. "
        "Issue tracker is preconfigured at docs/agents/issue-tracker.md. All test seams described "
        "in the specification are pre-agreed. Additional temporary regression probes may use /tmp. "
        "If a workflow names a Skill tool unavailable on this host, invoke the named skill by "
        "reading its SKILL.md and relevant references from /root/.agents/skills. "
        "Native subagents are available: at most two concurrent children, depth one, same model/effort. "
        "Do not use external agent CLIs or change runtime settings.\n\n"
    )
    (path / "instruction.md").write_text(invocation + context + instruction(task))
    (path / "task.toml").write_text(f"""schema_version = "1.3"
[task]
name = "evalopt/{task["id"]}"
description = "Authored {task["split"]} workflow task"
authors = []
[metadata]
evidence_class = "{"development pilot; not held-out" if task["split"] == "development" else "maintainer-authored held-out comparison"}"
[agent]
timeout_sec = 600.0
[environment]
cpus = 1
memory_mb = 2048
storage_mb = 10240
network_mode = "public"
[verifier]
timeout_sec = 120.0
environment_mode = "separate"
[verifier.environment]
cpus = 1
memory_mb = 2048
storage_mb = 10240
network_mode = "no-network"
""")
    tests = path / "tests"
    tests.mkdir()
    # Harbor 0.24 treats a dedicated verifier image/build context as containing
    # its tests. This image is built only after AGENT_END freezes the snapshot.
    (tests / "Dockerfile").write_text(f"FROM {verifier_reference}\nCOPY . /tests\n")
    shutil.copyfile(ROOT / "tasks" / "suite.py", tests / "suite.py")
    # suite resolves task data relative to its own file; no candidate sees this tree.
    destination = tests / task["split"] / task["id"]
    destination.mkdir(parents=True)
    for name in ("task.json", "hidden_cases.json"):
        shutil.copyfile(task_path(task, task_root=task_root) / name, destination / name)
    shutil.copyfile(HERE / "verify.py", tests / "verify.py")
    (tests / "test.sh").write_text("#!/bin/sh\nset -eu\ncd /tests\npython3 -B /tests/verify.py\n")
    (tests / "test.sh").chmod(0o755)
    return initial


def visible_check(snapshot, task, image):
    container_name = "evalopt-visible-" + uuid.uuid4().hex
    argv = [
        "docker",
        "run",
        "--rm",
        "--name",
        container_name,
        "--network",
        "none",
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--cpus",
        "1",
        "--memory",
        "2g",
        "--user",
        "65534:65534",
        "--tmpfs",
        "/tmp",
        "--mount",
        f"type=bind,src={snapshot},dst=/workspace,readonly",
        "--workdir",
        "/workspace",
        image,
        *shlex.split(task["visible_check"]),
    ]
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=30, check=False)
        outcome = "passed" if result.returncode == 0 else "failed"
        # Tasks may explicitly declare unavailable visible checks, but exit codes alone
        # cannot classify a provider outage. Only the fixture's declared absent resource.
        if result.returncode == 3:
            outcome = "unavailable"
        log = {
            "command": task["visible_check"],
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "outcome": outcome,
        }
    except subprocess.TimeoutExpired:
        outcome = "unavailable"
        log = {"command": task["visible_check"], "outcome": outcome, "error": "visible_check_timeout"}
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, timeout=30, check=False)
    return {"command": task["visible_check"], "outcome": outcome, "source": "controller"}, json.dumps(
        log, sort_keys=True
    ).encode()


def grade_stopped_failure(tests, output, image):
    """Grade stopped output when Harbor skips verification after an agent failure."""
    output.mkdir(parents=True, exist_ok=True)
    name = "evalopt-stopped-grader-" + uuid.uuid4().hex
    try:
        return subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                name,
                "--network",
                "none",
                "--cpus",
                "1",
                "--memory",
                "2g",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=bind,src={tests},dst=/tests,readonly",
                "--mount",
                f"type=bind,src={output},dst=/logs/verifier",
                image,
                "sh",
                "/tests/test.sh",
            ],
            text=True,
            capture_output=True,
            timeout=120,
            check=False,
        )
    finally:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=30, check=False)


async def execute_trial(
    row,
    store,
    directory,
    upstream,
    agent_image,
    verifier_image,
    *,
    oracle_control=False,
    task_root=None,
    split="development",
    accounting_policy=None,
):
    if accounting_policy is not None:
        from runtime.accounting_policy import validate_policy

        validate_policy(accounting_policy)
        if oracle_control:
            raise ValueError("registered native accounting does not apply to oracle controls")
    from harbor.models.trial.config import TrialConfig
    from harbor.trial.hooks import TrialEvent
    from harbor.trial.trial import Trial
    from lib.accounting import parse_native_usage, summarize_usage
    from runtime.observations import PROCESS_BASELINE, STOP_CANDIDATE, runtime_observations
    from runtime.snapshot import encode_snapshot, regular_snapshot, terminal_status
    from tasks.suite import file_manifest, load_task, validate_response

    task = load_task(row["task_id"], task_root=task_root, split=split)
    attempt = store.start_attempt(row["trial_id"])
    attempt_root = directory / row["trial_id"] / f"attempt-{attempt}"
    task_dir = attempt_root / "task"
    initial = materialize(
        task,
        task_dir,
        agent_image=agent_image,
        verifier_image=verifier_image,
        arm=row["arm"],
        task_root=task_root,
    )
    if oracle_control:
        from tasks.suite import task_path

        solution = task_dir / "solution"
        solution.mkdir()
        oracle = task_path(task, task_root=task_root) / "oracle"
        if oracle.exists():
            shutil.copytree(oracle, solution / "patch")
        else:
            (solution / "patch").mkdir()
        response = json.loads((task_path(task, task_root=task_root) / "controls.json").read_text())[
            "positive_response"
        ]
        (solution / "patch" / "response.json").write_text(json.dumps(response))
        (solution / "solve.sh").write_text("#!/bin/sh\nset -eu\ncp -a /solution/patch/. /workspace/\n")
    skills = []
    if row["arm"] == "B":
        skills = [str(path) for path in upstream_skills(upstream)]
    elif row["arm"] == "C":
        skills = [str(REPO / "skills" / "eval-opt")]
    config = TrialConfig.model_validate(
        {
            "task": {"path": str(task_dir)},
            "trial_name": "harbor-" + uuid.uuid4().hex[:16],
            "trials_dir": str(attempt_root),
            "agent": {
                "name": "codex",
                "model_name": "gpt-6-astra",
                "skills": skills,
                "kwargs": {"version": "0.154.0", "config": str(HERE / "codex.toml")},
            },
            "environment": {"type": "docker", "delete": True},
        }
    )
    if oracle_control:
        config.agent.name = "oracle"
        config.agent.model_name = None
        config.agent.kwargs = {}
        config.agent.env = {}
        config.agent.skills = []
    trial = await Trial.create(config)
    captured = False
    agent_started = False
    baseline = {}
    exposure = {}

    async def started(_event):
        nonlocal agent_started, baseline, exposure
        expected = (
            {
                f"{Path(source).name}/{file.relative_to(source).as_posix()}": hashlib.sha256(
                    file.read_bytes()
                ).hexdigest()
                for source in skills
                for file in Path(source).rglob("*")
                if file.is_file()
            }
            if not oracle_control
            else {}
        )
        exposure_command = """import hashlib,json,pathlib
root=pathlib.Path("/harbor/skills")
print(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()},sort_keys=True))
"""
        exposed = await trial.agent_environment.exec(
            "python3 -I -B -c " + shlex.quote(exposure_command), timeout_sec=10
        )
        if exposed.return_code != 0 or json.loads(exposed.stdout) != expected:
            raise RuntimeError("injected workflow bytes differ from the assigned arm")
        exposure = {"arm": row["arm"], "source_files": expected, "verified_before_agent": True}
        result = await trial.agent_environment.exec(
            "python3 -I -B -c " + shlex.quote(PROCESS_BASELINE), timeout_sec=10
        )
        if result.return_code != 0:
            raise RuntimeError("could not record pre-agent process baseline")
        baseline = json.loads(result.stdout)
        agent_started = True

    async def stopped(_event):
        nonlocal captured
        environment = trial.agent_environment
        stopped_processes = await environment.exec(
            "python3 -I -B -c " + shlex.quote("BASELINE=" + repr(baseline) + "\n" + STOP_CANDIDATE),
            timeout_sec=10,
        )
        if stopped_processes.return_code != 0:
            raise RuntimeError("candidate process termination failed")
        # Pin this integration to Harbor0.24's Docker lifecycle; pause ALL processes
        # before downloading. No command executes inside a paused candidate.
        await environment._run_docker_compose_command(["pause"])
        snapshot = attempt_root / "snapshot"
        try:
            await environment.download_dir("/workspace", snapshot)
        finally:
            await environment._run_docker_compose_command(["unpause"])
        stopped_manifest = file_manifest(snapshot)
        artifacts = {
            "snapshot.json": encode_snapshot(snapshot),
            "node-manifest.json": json.dumps(stopped_manifest, sort_keys=True).encode(),
            "workflow-exposure.json": json.dumps(exposure, sort_keys=True).encode(),
        }
        stopped_sha = store.capture_stopped(row["trial_id"], attempt, artifacts)
        safe_snapshot = regular_snapshot(snapshot)
        if safe_snapshot:
            observation, log = await asyncio.to_thread(visible_check, snapshot.resolve(), task, agent_image)
        else:
            observation = {"command": task["visible_check"], "outcome": "unavailable", "source": "controller"}
            log = b'{"error":"candidate_created_unsupported_nodes"}'
        changed = {
            p for p in initial.keys() | stopped_manifest.keys() if initial.get(p) != stopped_manifest.get(p)
        }
        boundaries = sorted(changed - set(task["allowed_changes"]) - {"response.json"})
        try:
            response = json.loads((snapshot / "response.json").read_text()) if safe_snapshot else None
        except (OSError, ValueError):
            response = None
        claims = []
        # Only visible claim mismatch enters policies; hidden correctness remains sealed.
        if not validate_response(response):
            claims.append("missing_or_malformed_response")
        elif response["checks"] != [{"command": task["visible_check"], "outcome": observation["outcome"]}]:
            claims.append("visible_check_claim_mismatch")
        visible = {
            "schema_version": "evalopt.workflow-visible.v1",
            "trial_id": row["trial_id"],
            "stopped_sha256": stopped_sha,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "required_gates": ["visible_check"],
            "gates": [
                {
                    "name": "visible_check",
                    "status": {"passed": "PASS", "failed": "FAIL", "unavailable": "NOT_CONFIGURED"}[
                        observation["outcome"]
                    ],
                    "producer": "controller",
                    "evidence_sha256": hashlib.sha256(log).hexdigest(),
                }
            ],
            "tests_weakened": any(p.startswith("tests/") or p == "verify.py" for p in boundaries),
            "boundary_violations": boundaries,
            "unsupported_claims": claims,
        }
        store.record_visible(row["trial_id"], attempt, visible, {"visible-check.json": log})
        store.decide(row["trial_id"], attempt)
        # Publish snapshot to verifier only after all policy records are frozen.
        if safe_snapshot:
            shutil.copytree(snapshot, task_dir / "tests" / "snapshot")
        else:
            (task_dir / "tests" / "snapshot").mkdir()
        (task_dir / "tests" / "grading.json").write_text(
            json.dumps(
                {
                    "task_id": task["id"],
                    "split": task["split"],
                    "initial_manifest": initial,
                    "observations": [observation],
                    "unsafe_snapshot": not safe_snapshot,
                    "stopped_manifest": stopped_manifest,
                },
                sort_keys=True,
            )
        )
        captured = True

    trial.add_hook(TrialEvent.AGENT_END, stopped)
    trial.add_hook(TrialEvent.AGENT_START, started)
    result = await trial.run()
    grade_path = trial.paths.verifier_dir / "grade.json"
    exception_type = result.exception_info.exception_type if result.exception_info else None
    # Harbor bypasses its verifier when execution raises. Those stopped outputs
    # still need independent grades; the agent remains stopped and is never resumed.
    if (
        captured
        and not grade_path.is_file()
        and exception_type
        in {"AgentTimeoutError", "NonZeroAgentExitCodeError", "ApiUsageLimitError", "ApiRateLimitError"}
    ):
        recovery = await asyncio.to_thread(
            grade_stopped_failure, (task_dir / "tests").resolve(), grade_path.parent.resolve(), verifier_image
        )
        (attempt_root / "stopped-grader.json").write_text(
            json.dumps(
                {"returncode": recovery.returncode, "stdout": recovery.stdout, "stderr": recovery.stderr}
            )
        )
    status, error_code = terminal_status(
        exception_type, agent_started=agent_started, captured=captured, grade_exists=grade_path.is_file()
    )
    grade = {
        "valid_completion": False,
        "functional_success": False,
        "unsupported_success": None,
        "incorrect_refusal": None,
        "boundaries_preserved": False,
    }
    if captured and grade_path.is_file():
        grade = json.loads(grade_path.read_text())
        if status == "timeout":
            grade["valid_completion"] = False
        grade["boundary_violation"] = not grade["boundaries_preserved"]
        store.record_grade(row["trial_id"], attempt, grade)
    if oracle_control:
        usage = {
            "child_usage_complete": True,
            "accounting_status": "offline_oracle_control",
            "model_calls": 0,
        }
    else:
        session_path = trial.paths.agent_dir / "sessions"
        if accounting_policy is not None:
            from runtime.accounting_policy import collect_usage

            usage = collect_usage(session_path, accounting_policy)
        else:
            try:
                events = parse_native_usage(session_path)
                usage = summarize_usage(events)
            except (ValueError, KeyError, OSError):
                usage = {
                    "child_usage_complete": False,
                    "accounting_status": "unavailable",
                    "raw_logs_retained": True,
                }
        entry = None
        if row["arm"] == "C":
            entry = "eval-opt"
        elif row["arm"] == "B":
            entry = (
                "code-review"
                if "review" in task["category"]
                else ("implement" if task["category"] == "bounded-implementation" else "diagnosing-bugs")
            )
        try:
            usage.update(runtime_observations(session_path, entry))
        except (ValueError, OSError):
            usage["runtime_valid"] = False
    store.finish_attempt(row["trial_id"], attempt, status, error_code=error_code, usage=usage)
    return {
        **row,
        "status": status,
        "error_code": error_code,
        **{
            key: grade[key]
            for key in ("valid_completion", "functional_success", "unsupported_success", "incorrect_refusal")
        },
        "boundary_violation": not grade["boundaries_preserved"],
        "usage": usage,
    }


def subscription_environment():
    # Defense against Harbor's optional API/default-provider fallback. Only the
    # explicitly selected auth file is forwarded; no ambient model endpoint keys.
    forbidden = (
        "OPENAI_API_KEY",
        "CODEX_API_KEY",
        "OPENAI_BASE_URL",
        "ANTHROPIC_API_KEY",
        "CODEX_AUTH_JSON_PATH",
    )
    for key in forbidden:
        os.environ.pop(key, None)
    os.environ["CODEX_FORCE_AUTH_JSON"] = "1"
