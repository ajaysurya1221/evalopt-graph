"""One Harbor 0.24/Codex 0.154 trial with external closure and no auto-next.

RetainedCodex is an explicit adapter: it retains Harbor's native exec flags,
config rendering and skill loader, but omits run()'s finally-copy/delete and
trajectory cost conversion. A separate supervisor stops the entire container.
Auth directories never enter the required capture roster. Native log custody is
not an attestation against a malicious agent able to edit its own files.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

from .accounting import derive_usage
from .capture import LABEL, DockerController
from .case_runner import snapshot_manifest
from .framing import SCHEMA, strict_json
from .git_index import workspace_manifest
from .lifecycle import prepare_supervisor, read_record, recover_closure, signal_agent_complete, write_once
from .materialize import boundary_violations, materialize
from .observe import command_record, visible_check
from .preflight import (
    CLI,
    MODEL,
    auth_path,
    export_upstream_skills,
    image_identity,
    native_config,
    require_versions,
    runtime_observations,
    skill_sources,
    subscription_permission,
)
from .records import canonical, digest
from .snapshot import extract_capture, final_response, session_files

CAPTURE_PATHS = ["/workspace", "/tmp/codex-home/sessions"]
NATIVE_FLAGS = [
    "exec",
    "--dangerously-bypass-approvals-and-sandbox",
    "--skip-git-repo-check",
    "--model",
    MODEL,
    "--json",
    "--enable",
    "unified_exec",
]

# A pre-agent controller command, never candidate supplied. Hashes prove exposure
# of bytes before dispatch; they do not prove the agent read the skill.
EXPOSURE = r"""import hashlib,json,pathlib,stat,tomllib
result={}
for name in ('workspace','skills'):
 root=pathlib.Path('/workspace' if name=='workspace' else '/root/.agents/skills')
 nodes={}
 for p in sorted(root.rglob('*')):
  s=p.lstat(); n=p.relative_to(root).as_posix()
  if stat.S_ISDIR(s.st_mode): nodes[n]={'kind':'directory','mode':stat.S_IMODE(s.st_mode)}
  elif stat.S_ISREG(s.st_mode):
   b=p.read_bytes();nodes[n]={'kind':'file','mode':stat.S_IMODE(s.st_mode),'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}
  else: raise RuntimeError('unsafe exposure node')
 result[name]=nodes
result['config']=tomllib.loads(pathlib.Path('/tmp/codex-home/config.toml').read_text())
print(json.dumps(result,sort_keys=True,allow_nan=False))
"""


def retained_codex_class():
    # Lazy dependency: ordinary offline controller tests need no Harbor import.
    from harbor.agents.installed.codex import Codex

    class RetainedCodex(Codex):
        def _env_sources(self):
            return (self._resolved_env_vars, self._extra_env)

        async def prepare(self, environment, *, auth, config):
            self._retained_env = {"CODEX_HOME": "/tmp/codex-home"}
            await self.exec_as_agent(
                environment,
                command="mkdir -p /tmp/codex-home/sessions /tmp/codex-secrets /root/.agents/skills /logs/agent",
                env=self._retained_env,
            )
            await environment.upload_file(auth, "/tmp/codex-secrets/auth.json")
            effective = self._build_effective_config(None)
            if canonical(effective) != canonical(config) or self.build_cli_flags():
                raise ValueError("native_effective_config_or_flags_changed")
            await self._upload_effective_config(environment, effective, "/tmp/codex-home/config.toml")
            await self.exec_as_agent(
                environment,
                command="chmod 600 /tmp/codex-secrets/auth.json; ln -s /tmp/codex-secrets/auth.json /tmp/codex-home/auth.json",
                env=self._retained_env,
            )
            loader = self._build_register_skills_command()
            if loader:
                await self.exec_as_agent(environment, command=loader, env=self._retained_env)

        async def run(self, instruction, environment, context):
            # No cleanup/copy/exec finally block. Captures follow whole-container
            # termination, and include sessions only, never CODEX_HOME/auth.json.
            command = (
                shlex.join(["codex", *NATIVE_FLAGS, "--", instruction])
                + " 2>&1 </dev/null | tee /logs/agent/codex.txt"
            )
            return await self.exec_as_agent(
                environment, command=command, env=self._retained_env, cwd="/workspace"
            )

    return RetainedCodex


def stage_skills(sources, destination, *, upstream=None):
    destination = Path(destination)
    destination.mkdir()
    if upstream is not None:
        export_upstream_skills(upstream, destination)
    else:
        for name, source in sources.items():
            snapshot_manifest(source)
            shutil.copytree(source, destination / name)
    return snapshot_manifest(destination)


def lifecycle_observation(usage):
    """Native parent completion is independent of child-cap verification.

    External cutoff establishes termination, never an unobserved native end.
    Missing usage alone does not erase a separately observed normal native end.
    """
    parent_completion = None
    agents = usage.get("agents", [])
    if usage.get("provenance_status") == "valid" and agents:
        parent = agents[0]
        reasons = set(parent.get("reasons", []))
        if parent.get("agent") == "agent-0" and parent.get("parent") is None:
            if "owned_turn_aborted" in reasons:
                parent_completion = False
            elif not reasons.intersection(
                {
                    "owned_turns_missing",
                    "owned_turn_start_missing",
                    "owned_turn_end_missing",
                    "partial_native_record",
                }
            ):
                parent_completion = True
    delegation = usage.get("delegation_status")
    verified = (
        False
        if delegation == "violated" or parent_completion is False
        else True
        if delegation == "verified" and parent_completion is True
        else None
    )
    return {
        "schema_version": SCHEMA,
        "kind": "native_lifecycle_observation",
        "parent_native_completion": parent_completion,
        "delegation_status": delegation,
        "lifecycle_verified": verified,
    }


def _inspect_runtime_container(name, image, label):
    # Separate selected JSON objects avoid retaining Docker Config.Env/auth.
    outputs = []
    for expression in (
        "{{.Id}}",
        "{{.Image}}",
        '{{index .Config.Labels "' + LABEL + '"}}',
        "{{.HostConfig.NanoCpus}}",
        "{{.HostConfig.Memory}}",
        "{{.HostConfig.RestartPolicy.Name}}",
        "{{.HostConfig.AutoRemove}}",
    ):
        result = subprocess.run(
            ["docker", "container", "inspect", "--format", expression, name],
            capture_output=True,
            check=True,
            timeout=15,
        )
        outputs.append(result.stdout.decode().strip())
    cid, actual_image, actual_label, cpus, memory, restart, autoremove = outputs
    if (
        actual_image != image
        or actual_label != label
        or cpus != "1000000000"
        or memory != "2147483648"
        or restart not in {"", "no"}
        or autoremove != "false"
    ):
        raise ValueError("agent_container_conditions_mismatch")
    identity = {"container_id": cid, "image_id": image, "attempt_label": label}
    DockerController().inspect_owned(identity)
    return identity


async def wait_record(path, process, *, seconds):
    deadline = time.monotonic() + seconds
    while not Path(path).exists():
        if process.poll() is not None:
            raise ValueError("supervisor_exited_without_required_record")
        if time.monotonic() >= deadline:
            raise TimeoutError("supervisor_record_timeout")
        await asyncio.sleep(0.05)
    return read_record(path)


def spawn_supervisor(directory, identity):
    prepared = prepare_supervisor(directory, identity, CAPTURE_PATHS, seconds=600, worker_pid=os.getpid())
    package_parent = Path(__file__).resolve().parents[1]
    cache = Path(directory) / "python-cache"
    cache.mkdir()
    code = "import sys;sys.path.insert(0,sys.argv[1]);from evalopt_v2.lifecycle import supervisor_main;sys.exit(supervisor_main(sys.argv[2:]))"
    argv = [
        sys.executable,
        "-I",
        "-B",
        "-X",
        f"pycache_prefix={cache}",
        "-c",
        code,
        str(package_parent),
        "--spec",
        prepared["spec"],
        "--spec-sha256",
        prepared["spec_sha256"],
    ]
    # File stdout/stderr are private controller diagnostics, no terminal/PTY.
    with (
        (Path(directory) / "stdout.log").open("xb") as stdout,
        (Path(directory) / "stderr.log").open("xb") as stderr,
    ):
        process = subprocess.Popen(
            argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr, start_new_session=True
        )
    return prepared, process


async def run_supervised(agent, environment, instruction, context, *, identity, directory):
    prepared, process = spawn_supervisor(directory, identity)
    ready = await wait_record(Path(directory) / "ready.json", process, seconds=15)
    if ready.get("spec_sha256") != prepared["spec_sha256"] or ready.get("kind") != "supervisor_ready":
        raise ValueError("supervisor_ready_identity_mismatch")
    error = None
    agent_task = asyncio.create_task(agent.run(instruction, environment, context))
    end_task = asyncio.create_task(wait_record(Path(directory) / "end.json", process, seconds=600 + 180))
    done, _ = await asyncio.wait({agent_task, end_task}, return_when=asyncio.FIRST_COMPLETED)
    if agent_task in done:
        try:
            agent_task.result()
        except Exception as exc:
            error = type(exc).__name__
        signal_agent_complete(prepared["spec"], prepared["spec_sha256"])
    end = await end_task
    if not agent_task.done():
        # Whole container is already closed; waiting/cancelling the Docker exec
        # client here cannot extend or substitute the candidate's cutoff.
        try:
            await asyncio.wait_for(agent_task, timeout=20)
        except Exception as exc:
            error = type(exc).__name__
    closure = recover_closure(Path(directory) / "closure")
    if end.get("closure_sha256") != __import__("evalopt_v2.lifecycle", fromlist=["digest"]).digest(closure):
        raise ValueError("supervisor_closure_changed")
    return closure, error


def _unknown_runtime():
    return {
        "schema_version": SCHEMA,
        "kind": "runtime_identity",
        "verified": False,
        "reason": "native_identity_unavailable",
    }


async def finish_stopped(
    row, task_dir, root, materialized, closure, *, verifier_image, freeze_visible, agent_error=None
):
    """Visible freeze is mandatory and strictly precedes hidden invocation."""
    attempt_id = row.get("attempt_id", row["trial_id"] + "--attempt-1")
    task = dict(materialized["task"], attempt_id=attempt_id)
    stopped, native = root / "stopped", root / "native-sessions"
    capture_ok = False
    extraction_error, native_error, files = None, None, {}
    response = {"schema_version": SCHEMA, "kind": "response_capture", "status": "missing", "response": None}
    runtime = _unknown_runtime()
    violations = []
    if closure["execution_boundary"] == "confirmed":
        # Functional grading can still inspect a complete stopped workspace when
        # native telemetry is missing. Missing native facts remain unknown and
        # independently block normal completion/next-trial admission.
        for index, (source, destination, name) in enumerate(
            (("/workspace", stopped, "workspace"), ("/tmp/codex-home/sessions", native, "sessions"))
        ):
            try:
                captured = read_record(root / "supervisor/closure" / f"capture-{index:03d}.json")
                if captured.get("source") != source or captured.get("status") != "complete":
                    raise ValueError("capture_roster_changed_or_incomplete")
                extract_capture(
                    root / "supervisor/closure" / captured["file"],
                    destination,
                    root_name=name,
                    expected_sha256=captured["sha256"],
                )
                if index == 0:
                    violations = boundary_violations(
                        materialized["initial_manifest"],
                        workspace_manifest(stopped),
                        task.get("allowed_changes", []),
                    )
                    capture_ok = True
                else:
                    files = session_files(native)
                    runtime = runtime_observations(files)
                    response = final_response(files)
            except (OSError, ValueError, UnicodeError) as exc:
                if index == 0:
                    extraction_error = type(exc).__name__
                else:
                    native_error = type(exc).__name__
    usage = derive_usage(files)
    lifecycle = lifecycle_observation(usage)
    if capture_ok:
        observed = await asyncio.to_thread(
            visible_check,
            stopped,
            task,
            attempt_id=attempt_id,
            candidate_id=digest(workspace_manifest(stopped)),
            image=verifier_image,
            directory=root / "visible",
        )
    else:
        observed = command_record(
            attempt_id=attempt_id,
            candidate_id="unavailable",
            command=task["visible_command"],
            execution_state="not_run",
            exit_code=None,
            availability="unavailable",
            artifact_refs=[],
        )
    visible = {
        "schema_version": SCHEMA,
        "kind": "stopped_visible_evidence",
        "attempt_id": attempt_id,
        "task_contract": task["task_contract"],
        "observations": [observed],
        "response": response["response"],
        "response_capture": response,
        "boundaries_preserved": not violations if capture_ok else None,
        "boundary_violations": violations,
        "snapshot_sha256": digest(workspace_manifest(stopped)) if capture_ok else None,
        "execution_boundary": closure["execution_boundary"],
        "snapshot_status": "complete" if capture_ok else "unavailable",
    }
    write_once(root / "visible-bundle.json", visible)
    visible_before = canonical(visible)
    frozen = freeze_visible(visible)
    if not inspect.isawaitable(frozen):
        raise ValueError("freeze_visible_must_be_awaitable")
    receipt = await frozen
    if canonical(visible) != visible_before:
        raise ValueError("freeze_callback_mutated_visible_evidence")
    if not isinstance(receipt, dict) or not receipt:
        raise ValueError("durable_policy_receipt_required")
    write_once(root / "policy-receipt.json", receipt)
    verification = None
    if capture_ok:
        from .verifier import finite_oracle, verify_task
        from .verifier_container import docker_invoker

        index = 0
        verify_dir = root / "verifier"
        verify_dir.mkdir()
        (verify_dir / "containers").mkdir()

        def retain(record):
            nonlocal index
            write_once(verify_dir / f"case-{index:04d}.json", record)
            index += 1

        oracle_file = Path(task_dir) / "oracle_cases.json"
        oracle = finite_oracle(strict_json(oracle_file.read_bytes())) if oracle_file.exists() else None
        verification = await asyncio.to_thread(
            verify_task,
            task,
            stopped,
            response["response"],
            [observed],
            baseline=Path(task_dir) / "baseline" if task["task_contract"] == "review" else None,
            oracle=oracle,
            boundary_violations=violations,
            lifecycle_verified=lifecycle["lifecycle_verified"],
            timed_out=closure["reason"] == "deadline",
            total_seconds=120,
            case_seconds=5,
            record_sink=retain,
            invoke=docker_invoker(verifier_image, artifact_root=verify_dir / "containers"),
        )
        write_once(verify_dir / "verification.json", verification)
    result = {
        "schema_version": SCHEMA,
        "kind": "executed_trial",
        "attempt_id": attempt_id,
        "status": "timeout"
        if closure["reason"] == "deadline"
        else "completed"
        if capture_ok and agent_error is None and native_error is None and closure["snapshot"] == "complete"
        else "agent_failure",
        "closure": closure,
        "usage": usage,
        "native_lifecycle": lifecycle,
        "runtime_identity": runtime,
        "response_capture": response,
        "visible_bundle": visible,
        "policy_receipt": receipt,
        "verification": verification,
        "case_boundary_confirmed": verification.get("case_boundary_confirmed")
        if isinstance(verification, dict)
        else None,
        "agent_error_type": agent_error,
        "capture_error_type": extraction_error,
        "native_error_type": native_error,
    }
    write_once(root / "result.json", result)
    return result


async def execute_one(
    row, task_dir, attempt_dir, upstream, skill_c, skill_d, agent_image, verifier_image, *, freeze_visible
):
    if not callable(freeze_visible):
        raise ValueError("freeze_visible_callback_required")
    root = Path(attempt_dir).absolute()
    if root.exists() or root.is_symlink() or root.resolve() != root:
        raise ValueError("fresh_attempt_runtime_directory_required")
    versions = require_versions()
    image_identity(agent_image)
    image_identity(verifier_image)
    auth = auth_path()
    runtime_config = Path(__file__).resolve().parents[1] / "runtime/codex.toml"
    config, config_sha = native_config(runtime_config)
    root.mkdir(parents=True, mode=0o700)
    materialized = materialize(task_dir, root / "initial", arm=row["arm"])
    if materialized["task"]["task_id"] != row["task_id"]:
        raise ValueError("scheduled_task_changed")
    expected_skills = stage_skills(
        skill_sources(row["arm"], upstream, skill_c, skill_d),
        root / "skills",
        upstream=upstream if row["arm"] == "B" else None,
    )
    attempt_id = row.get("attempt_id", row["trial_id"] + "--attempt-1")
    initial_observation = await asyncio.to_thread(
        visible_check,
        root / "initial",
        materialized["task"],
        attempt_id=attempt_id,
        candidate_id=materialized["initial_sha256"],
        image=verifier_image,
        directory=root / "initial-visible",
    )
    instruction = (
        materialized["instruction"]
        + "\nController observation on the initial workspace (post-stop checks will run independently):\n"
        + json.dumps(initial_observation, sort_keys=True)
    )
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.models.agent.context import AgentContext
    from harbor.models.task.config import EnvironmentConfig
    from harbor.models.trial.paths import TrialPaths

    label = "trial-" + uuid.uuid4().hex
    envdir = root / "environment"
    envdir.mkdir()
    # JSON is valid YAML. Unique project/container identities ensure Harbor's
    # initial compose-down cannot target any pre-existing trial.
    compose = {
        "services": {
            "main": {
                "image": agent_image,
                "pull_policy": "never",
                "container_name": label,
                "labels": {LABEL: label},
                "restart": "no",
                "working_dir": "/workspace",
            }
        }
    }
    (envdir / "docker-compose.yaml").write_text(json.dumps(compose))
    paths = TrialPaths(root / "harbor")
    paths.mkdir()
    env = DockerEnvironment(
        environment_dir=envdir,
        environment_name=label,
        session_id=label,
        trial_paths=paths,
        task_env_config=EnvironmentConfig(
            docker_image=agent_image, cpus=1, memory_mb=2048, workdir="/workspace"
        ),
        keep_containers=True,
        enable_environment_dir_upload=False,
        mounts=[],
    )
    await env.start(force_build=False)
    identity = await asyncio.to_thread(_inspect_runtime_container, label, agent_image, label)
    write_once(root / "identity.json", identity)
    await env.upload_dir(root / "initial", "/workspace")
    await env.upload_dir(root / "skills", "/harbor/skills")
    agent = retained_codex_class()(
        logs_dir=paths.agent_dir,
        model_name=MODEL,
        version=CLI,
        config=config,
        skills_dir="/harbor/skills",
        mcp_servers=[],
        extra_env={},
    )
    await agent.prepare(env, auth=auth, config=config)
    version = await env.exec(command="codex --version", timeout_sec=10)
    if version.return_code != 0 or version.stdout.strip() != "codex-cli " + CLI:
        raise ValueError("container_codex_version_mismatch")
    exposure = await env.exec(command=shlex.join(["python3", "-I", "-B", "-c", EXPOSURE]), timeout_sec=20)
    if exposure.return_code != 0:
        raise ValueError("workflow_exposure_unavailable")
    actual = strict_json(exposure.stdout)
    if (
        canonical(actual.get("workspace")) != canonical(snapshot_manifest(root / "initial"))
        or canonical(actual.get("skills")) != canonical(expected_skills)
        or canonical(actual.get("config")) != canonical(config)
    ):
        raise ValueError("workflow_exposure_changed")
    write_once(
        root / "exposure.json",
        {
            "schema_version": SCHEMA,
            "kind": "workflow_exposure",
            "versions": versions,
            "native_flags": NATIVE_FLAGS,
            "native_config_sha256": config_sha,
            "observed": actual,
            "proof": "controller_pre_agent_byte_observation",
            "read_by_agent_proven": False,
        },
    )
    permission = await asyncio.to_thread(subscription_permission)
    write_once(root / "permission.json", permission)
    if permission["ordinary_usage_allowed"] is not True:
        raise ValueError("included_usage_permission_unavailable")
    closure, error = await run_supervised(
        agent, env, instruction, AgentContext(), identity=identity, directory=root / "supervisor"
    )
    return await finish_stopped(
        row,
        task_dir,
        root,
        materialized,
        closure,
        verifier_image=verifier_image,
        freeze_visible=freeze_visible,
        agent_error=error,
    )
