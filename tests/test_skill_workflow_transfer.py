"""Offline transfer adapter controls; never pull images or invoke a model."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("tomllib", reason="Harbor transfer preparation requires Python 3.11+")
import tomllib  # noqa: E402

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"
sys.path.insert(0, str(BENCH))
from runtime import transfer  # noqa: E402


class FakeRuntime:
    def __init__(self):
        self.calls = []
        self.images = {}
        self.dirty = False

    def run(self, argv):
        self.calls.append(argv)
        if argv[0] == "git":
            if argv[3] == "status":
                output = " M changed\n" if self.dirty else ""
            else:
                output = transfer.UPSTREAM_PIN if Path(argv[2]).name == "upstream" else transfer.SOURCE_PIN
            return SimpleNamespace(stdout=output)
        if argv[:3] == ["docker", "image", "inspect"]:
            return SimpleNamespace(stdout=json.dumps([self.images[argv[3]]]))
        if argv[:2] == ["docker", "tag"]:
            match = next(info for info in self.images.values() if info["Id"] == argv[2])
            self.images[argv[3]] = copy.deepcopy(match)
            return SimpleNamespace(stdout="")
        if argv[:2] == ["docker", "pull"]:
            return SimpleNamespace(stdout="")
        raise AssertionError(f"unexpected command: {argv}")


@pytest.fixture
def fixture(tmp_path):
    source, upstream, skill = tmp_path / "source", tmp_path / "upstream", tmp_path / "eval-opt"
    source.mkdir()
    runtime = FakeRuntime()
    eligible = []
    names = list(transfer.ENTRYPOINTS) + [
        "prove-plus-comm",
        "pypi-server",
        "sqlite-db-truncate",
        "write-compressor",
    ]
    for index, name in enumerate(names):
        root = source / name
        (root / "environment").mkdir(parents=True)
        (root / "tests").mkdir()
        (root / "solution").mkdir()
        timeout = 1800.0 if name in {"custom-memory-heap-crash", "make-mips-interpreter"} else 900.0
        category = (
            "debugging"
            if name in {"build-cython-ext", "custom-memory-heap-crash"}
            else "software-engineering"
        )
        image = f"fixture/{name}:original"
        task = f'''version = "1.0"
[metadata]
category = "{category}"
tags = []
[agent]
timeout_sec = {timeout}
[verifier]
timeout_sec = {timeout}
[environment]
build_timeout_sec = 600.0
docker_image = "{image}"
cpus = 1
memory = "2G"
storage = "10G"
'''
        (root / "task.toml").write_text(task)
        (root / "instruction.md").write_bytes(b"Original task. Keep its service running.\n")
        (root / "environment/Dockerfile").write_bytes(b"FROM original-base\nWORKDIR /app\n")
        (root / "tests/test.sh").write_bytes(b"#!/bin/sh\necho 1 > /logs/verifier/reward.txt\n")
        (root / "tests/test.sh").chmod(0o755)
        (root / "solution/solve.sh").write_bytes(b"#!/bin/sh\ntrue\n")
        eligible.append(
            {
                "task_id": name,
                "category": category,
                "agent_seconds": timeout,
                "verifier_seconds": timeout,
                "image_source": image,
                "task_toml_sha256": hashlib.sha256(task.encode()).hexdigest(),
            }
        )
        identity = "sha256:" + f"{index + 1:064x}"
        runtime.images[image] = {
            "Id": identity,
            "Os": "linux",
            "Architecture": "amd64",
            "RepoDigests": [f"fixture/{name}@{identity}"],
        }
    excluded = source / "zz-image-task"
    excluded.mkdir()
    (excluded / "task.toml").write_text("""[metadata]
category="vision"
tags=["images"]
[agent]
timeout_sec=2000
[verifier]
timeout_sec=900
[environment]
cpus=2
memory="4G"
gpus=1
""")
    skill_names = ["implement", "diagnosing-bugs", "code-review"] + [f"dependency-{i}" for i in range(24)]
    for name in skill_names:
        folder = upstream / "skills" / name
        folder.mkdir(parents=True)
        (folder / "SKILL.md").write_text(f"---\nname: {name}\n---\nUse the task contract.\n")
    (upstream / ".claude-plugin").mkdir()
    (upstream / ".claude-plugin/plugin.json").write_text(
        json.dumps({"skills": ["skills/" + name for name in skill_names]})
    )
    skill.mkdir()
    (skill / "SKILL.md").write_text("---\nname: eval-opt\n---\nUse the task contract.\n")
    selection = {
        "source_commit": transfer.SOURCE_PIN,
        "eligible": eligible,
        "selected": eligible[:12],
        "images_resolved": False,
        "trials_run": 0,
    }
    return SimpleNamespace(
        source=source, upstream=upstream, skill=skill, runtime=runtime, selection=selection, root=tmp_path
    )


def prepare(fixture):
    lock = transfer.resolve_image_lock(fixture.source, fixture.selection, runner=fixture.runtime.run)
    destination = fixture.root / "prepared"
    prepared = transfer.prepare_transfer(
        fixture.source,
        fixture.selection,
        lock,
        destination,
        upstream=fixture.upstream,
        evalopt_skill=fixture.skill,
        runner=fixture.runtime.run,
    )
    return destination, prepared


def test_preflight_preserves_eligible_and_all_exclusions_without_pulling(fixture):
    lock = transfer.resolve_image_lock(fixture.source, fixture.selection, runner=fixture.runtime.run)
    assert lock["agent_trials"] == 0
    assert lock["catalog"]["selection"] == fixture.selection
    assert lock["catalog"]["eligible_not_selected"] == [
        "prove-plus-comm",
        "pypi-server",
        "sqlite-db-truncate",
        "write-compressor",
    ]
    assert lock["catalog"]["excluded"] == [
        {
            "task_id": "zz-image-task",
            "reasons": ["category", "cpu", "memory", "gpu", "timeout", "excluded_tag"],
        }
    ]
    assert len(lock["images"]) == 12
    assert not any(call[:2] == ["docker", "pull"] for call in fixture.runtime.calls)


def test_only_explicit_preflight_pull_resolves_original_images(fixture):
    transfer.resolve_image_lock(fixture.source, fixture.selection, pull=True, runner=fixture.runtime.run)
    pulls = [call for call in fixture.runtime.calls if call[:2] == ["docker", "pull"]]
    assert pulls == [
        ["docker", "pull", "--platform", "linux/amd64", row["image_source"]]
        for row in fixture.selection["selected"]
    ]


@pytest.mark.parametrize("mutation", ["selection", "dirty", "architecture", "no-digest"])
def test_preflight_rejects_drift_instead_of_substituting(fixture, mutation):
    if mutation == "selection":
        fixture.selection["selected"] = fixture.selection["selected"][1:]
    elif mutation == "dirty":
        fixture.runtime.dirty = True
    elif mutation == "architecture":
        next(iter(fixture.runtime.images.values()))["Architecture"] = "arm64"
    else:
        next(iter(fixture.runtime.images.values()))["RepoDigests"] = []
    with pytest.raises(ValueError):
        transfer.resolve_image_lock(fixture.source, fixture.selection, runner=fixture.runtime.run)


def test_preparation_changes_only_invocation_and_image_identity(fixture):
    root, result = prepare(fixture)
    for name in transfer.ENTRYPOINTS:
        original = fixture.source / name
        data = tomllib.loads((original / "task.toml").read_text())
        for arm in ("B", "C"):
            target = root / arm / name
            text = (target / "instruction.md").read_bytes()
            assert text.startswith((original / "instruction.md").read_bytes())
            assert transfer.COMMON_CONTEXT.encode() in text
            configured = tomllib.loads((target / "task.toml").read_text())
            assert configured["agent"] == data["agent"]
            assert configured["verifier"] == data["verifier"]
            assert (
                configured["environment"] | {"docker_image": data["environment"]["docker_image"]}
                == data["environment"]
            )
            assert (target / "tests/test.sh").read_bytes() == (original / "tests/test.sh").read_bytes()
            assert (target / "environment/Dockerfile").read_bytes() == (
                original / "environment/Dockerfile"
            ).read_bytes()
            assert (target / "solution/solve.sh").read_bytes() == (
                original / "solution/solve.sh"
            ).read_bytes()
    assert result["manifest"]["raw_artifacts_publication_ready"] is False
    assert "leaderboard" in result["manifest"]["evidence_class"]


def test_entrypoint_mapping_is_frozen_from_task_facts(fixture):
    root, _ = prepare(fixture)
    assert transfer.ENTRYPOINTS["fix-git"] == "diagnosing-bugs"
    assert transfer.ENTRYPOINTS["git-leak-recovery"] == "diagnosing-bugs"
    assert transfer.ENTRYPOINTS["kv-store-grpc"] == "implement"
    assert "Use $diagnosing-bugs" in (root / "B/fix-git/instruction.md").read_text()
    assert "Use $eval-opt" in (root / "C/fix-git/instruction.md").read_text()


@pytest.mark.parametrize("mutation", ["grader", "config", "skill", "manifest"])
def test_launch_validation_rejects_post_freeze_changes(fixture, mutation):
    root, result = prepare(fixture)
    targets = {
        "grader": root / "B/fix-git/tests/test.sh",
        "config": root / "codex.toml",
        "skill": fixture.skill / "SKILL.md",
        "manifest": root / "preparation.json",
    }
    with targets[mutation].open("a") as stream:
        stream.write("\n")
    with pytest.raises(ValueError):
        transfer.validate_prepared(
            root,
            result["preparation_sha256"],
            upstream=fixture.upstream,
            evalopt_skill=fixture.skill,
            runner=fixture.runtime.run,
        )


def test_clean_preparation_validates_without_docker_or_model_activity(fixture):
    root, result = prepare(fixture)
    fixture.runtime.calls.clear()
    transfer.validate_prepared(
        root,
        result["preparation_sha256"],
        upstream=fixture.upstream,
        evalopt_skill=fixture.skill,
        runner=fixture.runtime.run,
    )
    assert all(call[0] == "git" for call in fixture.runtime.calls)


@pytest.mark.parametrize("changed", transfer.RUNTIME_SOURCE_FILES)
def test_launch_rejects_changed_adapter_or_shared_helper(fixture, monkeypatch, changed):
    root, prepared = prepare(fixture)
    original = transfer.runtime_sources()
    assert prepared["manifest"]["runtime_sources"] == original
    monkeypatch.setattr(transfer, "runtime_sources", lambda: original | {changed: "0" * 64})
    with pytest.raises(ValueError, match="shared runtime helper"):
        transfer.validate_prepared(
            root,
            prepared["preparation_sha256"],
            upstream=fixture.upstream,
            evalopt_skill=fixture.skill,
            runner=fixture.runtime.run,
        )


def test_wrong_harbor_version_rejected_before_trial_or_image_operations(monkeypatch):
    monkeypatch.setattr(transfer.importlib.metadata, "version", lambda _package: "0.24.1")
    with pytest.raises(ValueError, match="exactly Harbor 0.24.0"):
        asyncio.run(
            transfer.execute_transfer_trial(
                {},
                prepared_root=Path("unused"),
                preparation_sha256="unused",
                directory=Path("unused"),
                upstream=Path("unused"),
                evalopt_skill=Path("unused"),
                runtime_preflight=Path("unused"),
            )
        )


@pytest.mark.parametrize("mutation", [None, "injected", "registered", "extra"])
def test_exposure_verifies_complete_injected_and_registered_skill_bytes(fixture, mutation):
    expected = transfer.expected_skill_files([str(fixture.skill)])
    actual = {"injected": expected.copy(), "registered": expected.copy()}
    if mutation in {"injected", "registered"}:
        actual[mutation]["eval-opt/SKILL.md"] = "0" * 64
    elif mutation == "extra":
        actual["registered"]["personal/SKILL.md"] = "0" * 64
    calls = []

    class Environment:
        async def exec(self, command, timeout_sec):
            calls.append(command)
            assert timeout_sec == 15
            if command == "fixture-register-skills":
                assert len(calls) == 2  # Verify source bytes before copying.
                return SimpleNamespace(return_code=0, stdout="")
            assert "node -e" in command and "python" not in command
            value = actual if len(calls) == 3 else actual["injected"]
            return SimpleNamespace(return_code=0, stdout=json.dumps(value))

    call = transfer.verify_workflow_exposure(
        Environment(), [str(fixture.skill)], "C", "fixture-register-skills"
    )
    if mutation is None:
        result = asyncio.run(call)
        assert result["verified_before_agent"] is True
        assert result["source_files"] == expected
        assert len(calls) == 3
    else:
        with pytest.raises(RuntimeError, match="workflow bytes differ"):
            asyncio.run(call)
        assert len(calls) == (1 if mutation == "injected" else 3)


def test_native_stop_failure_must_block_verifier():
    class Environment:
        async def exec(self, command, timeout_sec):
            assert "stopExecution" in command and "SIGKILL" in command
            assert timeout_sec == 10
            return SimpleNamespace(return_code=1, stdout="")

    with pytest.raises(RuntimeError, match="verifier must not run"):
        asyncio.run(transfer.stop_native_agent(Environment(), {}))


def test_watchdog_stops_at_deadline_before_delayed_harbor_end_hook():
    async def exercise():
        stopped = asyncio.Event()
        calls = []

        async def stop(environment, identity):
            calls.append((environment, identity))
            stopped.set()
            return {"confirmed": True, "controller_wall_seconds": 0.01}

        guard = transfer.NativeStopGuard("container", {"native": "fixture"}, 0.001, stop=stop)
        await asyncio.wait_for(stopped.wait(), timeout=1)
        assert guard.expired  # No AGENT_END callback has run yet.
        observed = await guard.finish()
        await guard.close()
        assert len(calls) == 1
        assert observed["reason"] == "original_agent_deadline"
        assert observed["agent_phase_elapsed_seconds"] >= 0.001
        assert observed["agent_deadline_seconds"] == 0.001

    asyncio.run(exercise())


def test_normal_agent_end_cancels_watchdog_and_stops_once():
    async def exercise():
        calls = []

        async def stop(_environment, _identity):
            calls.append(1)
            return {"confirmed": True, "controller_wall_seconds": 0.01}

        guard = transfer.NativeStopGuard(None, {}, 900, stop=stop)
        observed = await guard.finish()
        await guard.close()
        assert calls == [1]
        assert not guard.expired
        assert guard.task.cancelled()
        assert observed["reason"] == "agent_end"

    asyncio.run(exercise())


def test_deadline_stop_failure_is_not_treated_as_agent_quiescence():
    async def exercise():
        async def stop(_environment, _identity):
            raise RuntimeError("unconfirmed termination")

        guard = transfer.NativeStopGuard(None, {}, 0.001, stop=stop)
        with pytest.raises(RuntimeError, match="unconfirmed termination"):
            await asyncio.wait_for(guard.task, timeout=1)
        with pytest.raises(RuntimeError, match="unconfirmed termination"):
            await guard.finish()
        assert guard.result is None

    asyncio.run(exercise())


def test_node_stop_matches_only_runtime_identity_rechecks_pid_and_is_bounded(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is a transfer runtime dependency, unavailable for this offline control")
    script = (
        transfer.NODE_RUNTIME
        + r"""
const assert = require('node:assert/strict');
const root = process.argv[1];
const launcher = path.join(root,'codex.js'), service = path.join(root,'server.js');
fs.writeFileSync(launcher,''); fs.writeFileSync(service,'');
const identity = {native:[{device:'1',inode:'2'}],node:{device:'1',inode:'3'},launcher};
const native = {pid:101,started:'10',executable:identity.native[0],argv:['codex','exec']};
const wrapper = {pid:102,started:'11',executable:identity.node,argv:['node',launcher]};
const server = {pid:103,started:'12',executable:identity.node,argv:['node',service]};
const namedImpostor = {pid:104,started:'13',executable:{device:'1',inode:'4'},argv:['codex','exec']};
assert.equal(isNativeAgent(native,identity),true);
assert.equal(isNativeAgent(wrapper,identity),true);
assert.equal(isNativeAgent(server,identity),false);
assert.equal(isNativeAgent(namedImpostor,identity),false);
(async()=>{
  let rows=[native,wrapper,server], killed=[];
  const result=await stopNative(identity,{
    scan:()=>rows.filter(row=>isNativeAgent(row,identity)),
    reread:pid=>rows.find(row=>row.pid===pid),
    kill:pid=>{killed.push(pid);rows=rows.filter(row=>row.pid!==pid)},sleep:async()=>{},
  });
  assert.equal(result.confirmed,true); assert.deepEqual(killed,[101,102]);
  assert.deepEqual(rows,[server]);
  let scans=0;
  const reused=await stopNative(identity,{
    scan:()=>scans++ ? [] : [native], reread:()=>({...native,started:'new'}),
    kill:()=>{throw new Error('killed reused PID')},sleep:async()=>{},
  });
  assert.equal(reused.confirmed,true); assert.deepEqual(reused.signaled,[]);
  let attempts=0;
  await assert.rejects(()=>stopNative(identity,{
    scan:()=>[native],reread:()=>native,kill:()=>{attempts++},sleep:async()=>{},
  }),/bounded stop/);
  assert.equal(attempts,80);
  console.log('native stop controls passed');
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    )
    completed = subprocess.run(
        [node, "-e", script, str(tmp_path)], capture_output=True, text=True, timeout=15
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "native stop controls passed"


@pytest.mark.skipif(
    not os.environ.get("EVALOPT_TRANSFER_DOCKER_CONTROL_IMAGE"),
    reason="explicit cached image required for the offline Docker process control",
)
def test_pinned_harbor_skill_registration_lifecycle_without_models(fixture, tmp_path):
    image = os.environ["EVALOPT_TRANSFER_DOCKER_CONTROL_IMAGE"]
    assert transfer.re.fullmatch(r"sha256:[0-9a-f]{64}", image)
    harbor_python = BENCH.parents[2] / ".venv-harbor/bin/python"
    if not harbor_python.is_file():
        pytest.skip("isolated pinned Harbor environment unavailable for lifecycle control")
    probe = r"""
import asyncio, importlib.metadata, json, logging, sys
from pathlib import Path
from types import SimpleNamespace
from harbor.agents.installed.codex import Codex
assert importlib.metadata.version('harbor') == '0.24.0'
agent=object.__new__(Codex)
agent.logs_dir=Path(sys.argv[1]);agent.skills_dir='/harbor/skills'
agent._version='0.154.0';agent.logger=logging.getLogger('offline-lifecycle')
calls=[]
class Environment:
    async def exec(self, command, **kwargs):
        calls.append(command)
        return SimpleNamespace(return_code=0,stdout='codex-cli 0.154.0',stderr='')
asyncio.run(agent.setup(Environment()))
command=agent._build_register_skills_command()
assert command and command not in calls
assert not any('codex exec' in call for call in calls)
print(json.dumps({'registration_command':command,'setup_registered_skills':False,'model_calls':0}))
"""
    completed = subprocess.run(
        [str(harbor_python), "-I", "-B", "-c", probe, str(tmp_path / "harbor-logs")],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert completed.returncode == 0, completed.stderr
    lifecycle = json.loads(completed.stdout)
    assert lifecycle["setup_registered_skills"] is False
    assert lifecycle["model_calls"] == 0
    container = "evalopt-transfer-lifecycle-" + uuid.uuid4().hex[:16]

    def docker(*args, timeout=15):
        return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=True)

    class Environment:
        async def exec(self, command, timeout_sec):
            result = docker("exec", container, "bash", "-lc", command, timeout=timeout_sec)
            return SimpleNamespace(return_code=result.returncode, stdout=result.stdout, stderr=result.stderr)

    try:
        docker(
            "run",
            "-d",
            "--rm",
            "--pull",
            "never",
            "--network",
            "none",
            "--name",
            container,
            image,
            "sleep",
            "60",
        )
        docker("exec", container, "mkdir", "-p", "/harbor/skills")
        docker("cp", str(fixture.skill), container + ":/harbor/skills/eval-opt")
        docker("exec", container, "test", "!", "-e", "/root/.agents/skills")
        result = asyncio.run(
            transfer.verify_workflow_exposure(
                Environment(),
                [str(fixture.skill)],
                "C",
                lifecycle["registration_command"],
            )
        )
        assert result["verified_before_agent"] is True
        # Repeating the native run's original copy keeps the exact byte exposure.
        repeated = asyncio.run(
            transfer.verify_workflow_exposure(
                Environment(),
                [str(fixture.skill)],
                "C",
                lifecycle["registration_command"],
            )
        )
        assert repeated == result
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=10, check=False)


@pytest.mark.skipif(
    not os.environ.get("EVALOPT_TRANSFER_DOCKER_CONTROL_IMAGE"),
    reason="explicit cached image required for the offline Docker process control",
)
@pytest.mark.parametrize("detached_writer", [False, True])
def test_docker_cutoff_stops_writes_and_preserves_required_detached_service(detached_writer):
    image = os.environ["EVALOPT_TRANSFER_DOCKER_CONTROL_IMAGE"]
    assert transfer.re.fullmatch(r"sha256:[0-9a-f]{64}", image)
    script = (
        transfer.NODE_RUNTIME
        + r"""
const assert = require('node:assert/strict'), cp = require('node:child_process'), http = require('node:http');
const delay = ms => new Promise(resolve=>setTimeout(resolve,ms));
const detachedWriter=JSON.parse(process.argv[1]);
const actual=collectRuntime('/usr/local/bin/codex'); assert.ok(actual.native.length);
const root='/tmp/transfer-control/codex', launcher=root+'/bin/codex.js', binary=root+'/vendor/fixture/codex';
fs.mkdirSync(path.dirname(launcher),{recursive:true});fs.mkdirSync(path.dirname(binary),{recursive:true});
fs.mkdirSync('/app',{recursive:true}); fs.copyFileSync(process.execPath,binary);fs.chmodSync(binary,0o755);
fs.writeFileSync('/app/server.py',"require('node:http').createServer((req,res)=>res.end('alive')).listen(5328);");
const writer='sleep 0.8; echo late-pass > /tmp/late-result';
const nativeCode="const cp=require('node:child_process'),fs=require('node:fs');"
 +"cp.spawnSync('/bin/sh',['-c','setsid node /app/server.py >/tmp/service.log 2>&1 </dev/null &'],{stdio:'ignore'});"
 +(detachedWriter
   ? "cp.spawnSync('/bin/sh',['-c',"+JSON.stringify("setsid sh -c '"+writer+"' >/tmp/writer.log 2>&1 </dev/null &")+"],{stdio:'ignore'});"
   : "cp.spawn('/bin/sh',['-c',"+JSON.stringify(writer)+"],{detached:true,stdio:'ignore'});")
 +"fs.writeFileSync('/tmp/native-ready','yes');setInterval(()=>{},1000);";
fs.writeFileSync(launcher,"const cp=require('node:child_process');cp.spawn("
 +JSON.stringify(binary)+",['-e',"+JSON.stringify(nativeCode)+"],{stdio:'ignore'});setInterval(()=>{},1000);");
const baselineService=cp.spawn('/bin/sleep',['60'],{stdio:'ignore'});
const identity=collectRuntime(launcher);
identity.baseline=Object.fromEntries(processSnapshot().map(row=>[String(row.pid),row.started]));
identity.service_contracts=[{script:'/app/server.py',tcp_port:5328}];
cp.spawn(process.execPath,[launcher],{stdio:'ignore'});
const get=()=>new Promise((resolve,reject)=>{
 const request=http.get('http://127.0.0.1:5328',response=>{let body='';response.on('data',data=>body+=data);response.on('end',()=>resolve(body));});
 request.on('error',reject);request.setTimeout(500,()=>request.destroy(new Error('HTTP timeout')));
});
(async()=>{
 let ready=false;
 for(let i=0;i<80;i++){try{if(fs.existsSync('/tmp/native-ready')&&await get()==='alive'){ready=true;break;}}catch{}await delay(10);}
 assert.ok(ready);assert.equal(agentProcesses(identity).length,2);
 const result=await stopExecution(identity);
 assert.equal(result.confirmed,true);assert.equal(result.boundary_confirmed,!detachedWriter,JSON.stringify(result));
 assert.equal(agentProcesses(identity).length,0);
 assert.ok(processInfo(baselineService.pid),'startup service survives');
 assert.equal(result.services_preserved.length,1);
 if(!detachedWriter) assert.equal(await get(),'alive','required detached server survives');
 else assert.ok(result.issues.some(issue=>issue.kind==='unclassified_new_process'));
 await delay(1000);assert.equal(fs.existsSync('/tmp/late-result'),false,'no post-cutoff tool writes');
 for(const service of result.services_preserved) process.kill(service.pid,'SIGKILL');
 baselineService.kill('SIGKILL');
 console.log(JSON.stringify({control:'PASS',boundary_confirmed:result.boundary_confirmed,late_write_prevented:true,model_calls:0}));
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )
    container = "evalopt-transfer-cutoff-" + uuid.uuid4().hex[:16]
    try:
        completed = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--name",
                container,
                "--pull",
                "never",
                "--network",
                "none",
                "--init",
                "--pids-limit",
                "128",
                "--memory",
                "512m",
                "--cpus",
                "1",
                image,
                "node",
                "-e",
                script,
                json.dumps(detached_writer),
            ],
            capture_output=True,
            text=True,
            timeout=25,
        )
    finally:
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=10, check=False)
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout) == {
        "control": "PASS",
        "boundary_confirmed": not detached_writer,
        "late_write_prevented": True,
        "model_calls": 0,
    }


def test_runtime_configuration_preserves_original_environment_and_verifier(fixture):
    row = {"stage": "transfer", "task_id": "kv-store-grpc", "arm": "B", "trial_id": "transfer-example"}
    config = transfer.trial_configuration(
        row, fixture.root, fixture.root / "out", fixture.upstream, fixture.skill
    )
    assert config["agent"]["model_name"] == "gpt-6-astra"
    assert config["agent"]["kwargs"]["version"] == "0.154.0"
    assert "env" not in config["agent"]
    assert len(config["agent"]["skills"]) == 27
    assert "verifier" not in config
    assert set(config["environment"]) == {"type", "delete"}
    assert "override_timeout_sec" not in config["agent"]
    row["arm"] = "C"
    assert transfer.trial_configuration(
        row, fixture.root, fixture.root / "out", fixture.upstream, fixture.skill
    )["agent"]["skills"] == [str(fixture.skill)]
    row["arm"] = "A"
    with pytest.raises(ValueError):
        transfer.trial_configuration(row, fixture.root, fixture.root / "out", fixture.upstream, fixture.skill)


def test_subscription_auth_uses_host_switch_without_scrubber_secret(fixture, monkeypatch):
    from runtime.harbor_campaign import subscription_environment

    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
        monkeypatch.setenv(key, "synthetic-forbidden-provider-value")
    monkeypatch.setenv("CODEX_FORCE_AUTH_JSON", "0")
    subscription_environment()
    assert os.environ["CODEX_FORCE_AUTH_JSON"] == "1"
    for key in ("OPENAI_API_KEY", "CODEX_API_KEY", "OPENAI_BASE_URL", "ANTHROPIC_API_KEY"):
        assert key not in os.environ
    row = {"stage": "transfer", "task_id": "kv-store-grpc", "arm": "B", "trial_id": "transfer-example"}
    config = transfer.trial_configuration(
        row, fixture.root, fixture.root / "out", fixture.upstream, fixture.skill
    )
    assert not config["agent"].get("env")
    assert "CODEX_FORCE_AUTH_JSON" not in json.dumps(config)


def test_ready_flag_without_retained_native_probe_cannot_launch(tmp_path):
    (tmp_path / "summary.json").write_text('{"status":"PASS"}')
    with pytest.raises(ValueError, match="preflight incomplete"):
        transfer.validate_runtime_preflight(tmp_path, {})


def test_capture_pauses_and_resumes_services_without_killing_them(tmp_path):
    commands, sources = [], []

    class Environment:
        async def _run_docker_compose_command(self, command):
            commands.append(command)
            return SimpleNamespace(stdout="a" * 64 if command[0] == "ps" else "")

    async def archive(container, source, destination, maximum):
        sources.append(source)
        destination.write_bytes(b"private-tar-placeholder")
        return {
            "source": source,
            "path": destination.name,
            "complete": True,
            "sha256": "fixture",
            "bytes": 23,
        }

    record = asyncio.run(
        transfer.capture_stopped(Environment(), tmp_path / "stopped", ["/app"], 1000, archive=archive)
    )
    assert commands == [["ps", "-q", "main"], ["pause"], ["unpause"]]
    assert sources == ["/app"]
    assert record["primary_output_complete"] is True
    assert record["all_outputs_complete"] is True
    assert record["required_services_preserved"] is True
    assert record["publication_ready"] is False


def test_capture_resumes_container_even_when_archive_fails(tmp_path):
    commands = []

    class Environment:
        async def _run_docker_compose_command(self, command):
            commands.append(command)
            return SimpleNamespace(stdout="b" * 64)

    async def broken(*_args):
        raise ValueError("capture unavailable")

    with pytest.raises(ValueError):
        asyncio.run(
            transfer.capture_stopped(Environment(), tmp_path / "stopped", ["/app"], 1000, archive=broken)
        )
    assert commands[-1] == ["unpause"]


def test_capture_requires_installed_output_as_well_as_app(tmp_path):
    class Environment:
        async def _run_docker_compose_command(self, _command):
            return SimpleNamespace(stdout="a" * 64)

    async def archive(_container, source, _destination, _maximum):
        return {"source": source, "complete": source == "/app"}

    stopped = asyncio.run(
        transfer.capture_stopped(
            Environment(), tmp_path / "stopped", ["/app", "/usr/local/bin/pmars"], 1000, archive=archive
        )
    )
    assert stopped["primary_output_complete"] is True
    assert stopped["all_outputs_complete"] is False
    result = SimpleNamespace(exception_info=None, verifier_result=SimpleNamespace(rewards={"reward": 1}))
    summary = transfer.summarize_result(
        {}, result, agent_started=True, stopped=stopped, usage={"execution_boundary_complete": True}
    )
    assert summary["artifact_capture_complete"] is False
    assert summary["functional_success"] is True


@pytest.mark.parametrize("mode", ["cancel", "limit", "nonzero"])
def test_archive_cleans_up_copy_process_and_never_extracts(tmp_path, monkeypatch, mode):
    calls = []

    class Stream:
        def __init__(self, payloads):
            self.payloads = iter(payloads)

        async def read(self, _size=-1):
            value = next(self.payloads, b"")
            if isinstance(value, BaseException):
                raise value
            return value

    class Process:
        returncode = None
        killed = False
        stdout = Stream([asyncio.CancelledError()] if mode == "cancel" else [b"opaque TAR bytes", b""])
        stderr = Stream([b"copy diagnostic"])

        def kill(self):
            self.killed = True
            self.returncode = -9

        async def wait(self):
            if self.returncode is None:
                self.returncode = 1 if mode == "nonzero" else 0
            return self.returncode

    process = Process()

    async def start(*argv, **_kwargs):
        calls.append(argv)
        return process

    monkeypatch.setattr(transfer.asyncio, "create_subprocess_exec", start)
    destination = tmp_path / "output.tar"
    call = transfer._archive_container_path("a" * 64, "/app", destination, 1 if mode == "limit" else 1000)
    if mode == "cancel":
        with pytest.raises(asyncio.CancelledError):
            asyncio.run(call)
        assert process.killed
    else:
        result = asyncio.run(call)
        assert result["complete"] is False
        assert result["error"] == ("ValueError" if mode == "limit" else None)
        assert process.killed is (mode == "limit")
        assert destination.read_bytes() == (b"" if mode == "limit" else b"opaque TAR bytes")
    assert calls == [("docker", "cp", "a" * 64 + ":/app", "-")]
    assert destination.with_suffix(".stderr.txt").read_bytes() == b"copy diagnostic"


@pytest.mark.parametrize(
    "exception,expected_status,code",
    [
        (None, "completed", None),
        ("AgentTimeoutError", "timeout", None),
        ("ApiUsageLimitError", "infra_failure", "subscription_exhausted"),
    ],
)
def test_original_reward_and_failure_status_remain_separate(exception, expected_status, code):
    result = SimpleNamespace(
        exception_info=SimpleNamespace(exception_type=exception) if exception else None,
        verifier_result=SimpleNamespace(rewards={"reward": 1}),
    )
    row = transfer.summarize_result(
        {},
        result,
        agent_started=True,
        stopped={"primary_output_complete": True, "all_outputs_complete": True},
        usage={
            "child_usage_complete": True,
            "runtime_valid": True,
            "entrypoint_load_observed": True,
            "workflow_exposure_verified": True,
            "native_agent_stopped": True,
            "execution_boundary_complete": True,
        },
    )
    assert row["upstream_reward"] == 1
    assert row["functional_success"] is True
    assert row["status"] == expected_status
    assert row["error_code"] == code
    assert row["runtime_evidence_complete"] is True
    assert row["artifact_capture_complete"] is True


def test_controller_deadline_is_timeout_even_if_harbor_observes_native_exit_first():
    result = SimpleNamespace(exception_info=None, verifier_result=SimpleNamespace(rewards={"reward": 1}))
    row = transfer.summarize_result(
        {},
        result,
        agent_started=True,
        stopped=None,
        usage={"agent_deadline_expired": True, "execution_boundary_complete": True},
    )
    assert row["status"] == "timeout"
    assert row["functional_success"] is True
    assert row["runtime_evidence_complete"] is False


@pytest.mark.parametrize(
    "rewards", [None, {"reward": float("nan")}, {"reward": 0.5}, {"other": 1}, {"reward": 1, "other": 0}]
)
def test_unrecognized_rewards_are_ungraded_not_guessed(rewards):
    result = SimpleNamespace(exception_info=None, verifier_result=SimpleNamespace(rewards=rewards))
    row = transfer.summarize_result({}, result, agent_started=True, stopped=None, usage={})
    assert row["upstream_reward"] is None
    assert row["functional_success"] is None
    assert row["runtime_evidence_complete"] is False
    assert row["artifact_capture_complete"] is False


def test_service_contract_is_frozen_in_preparation_and_cannot_be_rewritten(fixture):
    destination, prepared = prepare(fixture)
    manifest = prepared["manifest"]
    assert manifest["service_contracts"] == transfer.SERVICE_CONTRACTS
    assert manifest["service_contracts"]["kv-store-grpc"] == [{"script": "/app/server.py", "tcp_port": 5328}]
    assert all(
        not contract for name, contract in manifest["service_contracts"].items() if name != "kv-store-grpc"
    )
    manifest["service_contracts"]["kv-store-grpc"] = [{"script": "/tmp/writer", "tcp_port": 80}]
    # Rehashing a new envelope does not authorize a different background-service contract.
    path = destination / "preparation.json"
    path.write_bytes(transfer._canonical(manifest))
    with pytest.raises(ValueError, match="required-service"):
        transfer.validate_prepared(
            destination,
            transfer._file_hash(path),
            upstream=fixture.upstream,
            evalopt_skill=fixture.skill,
            runner=fixture.runtime.run,
        )


@pytest.mark.parametrize("expired", [False, True])
def test_unresolved_execution_boundary_never_exposes_a_reward(expired):
    result = SimpleNamespace(exception_info=None, verifier_result=SimpleNamespace(rewards={"reward": 1}))
    value = transfer.summarize_result(
        {},
        result,
        agent_started=True,
        stopped=None,
        usage={"agent_deadline_expired": expired, "execution_boundary_complete": False},
    )
    assert value["upstream_reward"] is None
    assert value["functional_success"] is None
    assert value["execution_boundary_complete"] is False
    assert value["runtime_evidence_complete"] is False
    assert value["status"] == ("timeout" if expired else "agent_failure")
    assert value["error_code"] is None


@pytest.mark.parametrize("expired", [False, True])
def test_unresolved_execution_boundary_blocks_harbor_verifier(tmp_path, monkeypatch, expired):
    from runtime import harbor_campaign

    async def exposure(*_args):
        return {"verified_before_agent": True}

    async def identity(*_args):
        return {"baseline": {}, "service_contracts": []}

    class Guard:
        stop_started_at = "fixture"

        def __init__(self, *_args):
            self.expired = expired

        async def finish(self):
            return {
                "confirmed": True,
                "boundary_confirmed": False,
                "issues": [{"kind": "unclassified_new_process"}],
                "controller_wall_seconds": 0.01,
            }

        async def close(self):
            pass

    class Trial:
        verifier_calls = 0

        def __init__(self):
            self.hooks = {}
            self.paths = SimpleNamespace(agent_dir=tmp_path / "unused-agent-logs")
            self.agent_environment = None
            self.agent = SimpleNamespace(_build_register_skills_command=lambda: "register")

        @classmethod
        async def create(cls, _config):
            return cls()

        def add_hook(self, event, callback):
            self.hooks[event] = callback

        async def run(self):
            await self.hooks["start"](None)
            try:
                await self.hooks["end"](None)
            except transfer.ExecutionBoundaryError as exc:
                return SimpleNamespace(
                    exception_info=SimpleNamespace(exception_type=type(exc).__name__), verifier_result=None
                )
            Trial.verifier_calls += 1
            raise AssertionError("verifier must not execute after an unresolved boundary")

    monkeypatch.setitem(
        sys.modules,
        "harbor.models.trial.config",
        SimpleNamespace(TrialConfig=SimpleNamespace(model_validate=lambda value: value)),
    )
    monkeypatch.setitem(
        sys.modules,
        "harbor.trial.hooks",
        SimpleNamespace(TrialEvent=SimpleNamespace(AGENT_START="start", AGENT_END="end")),
    )
    monkeypatch.setitem(sys.modules, "harbor.trial.trial", SimpleNamespace(Trial=Trial))
    monkeypatch.setattr(transfer, "verify_harbor_version", lambda: "0.24.0")
    prepared = {
        "image_lock": {"images": {"build-pmars": {"local_reference": "fixture", "image_id": "fixture"}}},
        "catalog": {"selection": {"selected": [{"task_id": "build-pmars", "agent_seconds": 900}]}},
        "service_contracts": {"build-pmars": []},
    }
    monkeypatch.setattr(transfer, "validate_prepared", lambda *_args, **_kwargs: prepared)
    monkeypatch.setattr(transfer, "validate_runtime_preflight", lambda *_args: {})
    monkeypatch.setattr(transfer, "trial_configuration", lambda *_args: {"agent": {"skills": []}})
    monkeypatch.setattr(transfer, "_inspect", lambda *_args: {"Id": "fixture"})
    monkeypatch.setattr(harbor_campaign, "subscription_environment", lambda: None)
    monkeypatch.setattr(transfer, "verify_workflow_exposure", exposure)
    monkeypatch.setattr(transfer, "record_native_identity", identity)
    monkeypatch.setattr(transfer, "NativeStopGuard", Guard)
    directory = tmp_path / "trial"
    summary = asyncio.run(
        transfer.execute_transfer_trial(
            {"stage": "transfer", "task_id": "build-pmars", "arm": "C"},
            prepared_root=tmp_path,
            preparation_sha256="fixture",
            directory=directory,
            upstream=tmp_path,
            evalopt_skill=tmp_path,
            runtime_preflight=tmp_path,
        )
    )
    assert Trial.verifier_calls == 0
    assert summary["upstream_reward"] is None
    assert summary["execution_boundary_complete"] is False
    assert summary["status"] == ("timeout" if expired else "agent_failure")
    assert summary["error_code"] is None
    assert (directory / "native-stop.json").is_file()
    assert (directory / "native-stop-failure.json").is_file()
    assert not (directory / "stopped").exists()


@pytest.mark.parametrize("mode", ["clean", "fork", "reuse", "persistent", "wrong_service", "nested_native"])
def test_execution_cutoff_rechecks_process_identity_and_fails_closed(tmp_path, mode):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable for offline process control")
    script = (
        transfer.NODE_RUNTIME
        + r"""
const assert=require('node:assert/strict'), mode=process.argv[1];
const identity={native:[{device:'1',inode:'2'}],node:{device:'1',inode:'3'},launcher:'/fixture/codex.js',
 baseline:{'10':'baseline'},service_contracts:[{script:'/app/server.py',tcp_port:5328}]};
const row=(pid,ppid,started,executable=identity.node)=>({pid,ppid,pgid:pid,sid:pid,started,state:'S',executable,argv:['fixture']});
let rows=[row(10,1,'baseline'),row(101,1,'native',identity.native[0]),row(102,101,'tool'),row(200,1,'service')];
if(mode==='nested_native')rows.push(row(103,102,'child-native',identity.native[0]));
const signals=[];let injected=false;
(async()=>{
 const result=await stopExecution(identity,{
  controllerPid:900,scan:()=>rows.map(item=>({...item})),reread:pid=>rows.find(item=>item.pid===pid),sleep:async()=>{},
  serviceMatch:info=>mode!=='wrong_service'&&info.pid===200,
  signal:(pid,name)=>{
   signals.push([pid,name]);const item=rows.find(item=>item.pid===pid);
   if(mode==='fork'&&!injected&&name==='SIGSTOP'){injected=true;rows.push(row(103,102,'fork'));}
   if(mode==='reuse'&&!injected&&pid===102&&name==='SIGSTOP'){injected=true;item.started='reused';return;}
   if(name==='SIGSTOP'&&mode!=='persistent')item.state='T';
   if(name==='SIGKILL')rows=rows.filter(item=>item.pid!==pid);
   if(name==='SIGCONT')item.state='R';
  },
 });
 assert.equal(result.confirmed,true);
 assert.equal(result.boundary_confirmed,['clean','fork','nested_native'].includes(mode),JSON.stringify(result));
 assert.ok(rows.some(item=>item.pid===10),'baseline survives');
 assert.ok(!signals.some(([pid])=>pid===10),'baseline never signaled');
 assert.equal(rows.some(item=>[101,102,103].includes(item.pid)),false,'all tool work removed');
 if(['clean','fork','nested_native'].includes(mode))assert.deepEqual(signals.filter(([,name])=>name==='SIGCONT'),[[200,'SIGCONT']]);
 else assert.ok(!signals.some(([,name])=>name==='SIGCONT'),'ambiguous boundary never resumes service for verifier');
 if(mode==='wrong_service')assert.ok(result.issues.some(issue=>issue.kind==='unclassified_new_process'));
 if(mode==='persistent')assert.ok(result.issues.some(issue=>issue.kind==='freeze_did_not_quiesce'));
 console.log('cutoff controls passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
"""
    )
    result = subprocess.run([node, "-e", script, mode], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "cutoff controls passed"
