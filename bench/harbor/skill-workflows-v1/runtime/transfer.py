"""Pinned Terminal-Bench feasibility transfer; original task/verifier semantics remain.

Importing, validating, or preparing tasks never pulls images or starts a model.
Image resolution is an explicit preflight operation. Raw stopped archives and
Harbor logs remain private pending sanitization; no archive is extracted here.
This stage does not run U/M/G or claim the authored suite's hidden-grader boundary.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import math
import os
import re
import shlex
import shutil
import stat
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import tomllib

HERE = Path(__file__).resolve().parent
BENCH = HERE.parent
SOURCE_PIN = "69671fbaac6d67a7ef0dfec016cc38a64ef7a77c"
UPSTREAM_PIN = "b0618bc436ad893b3c5e84e55fba86586d34a404"
HARBOR_VERSION = "0.24.0"
RUNTIME_SOURCE_FILES = (
    "runtime/transfer.py",
    "runtime/harbor_campaign.py",
    "runtime/observations.py",
    "runtime/readiness.py",
    "runtime/accounting_policy.py",
    "runtime/partial_accounting.py",
    "lib/__init__.py",
    "lib/accounting.py",
    "lib/common.py",
)
EVIDENCE_CLASS = "Terminal-Bench 2.0 feasibility subset; not an official leaderboard score"
# Classification is based on the pinned instructions, before outcomes. The four
# repair/recovery tasks use diagnosis; all remaining tasks request implementations.
ENTRYPOINTS = {
    "build-cython-ext": "diagnosing-bugs",
    "build-pmars": "implement",
    "cancel-async-tasks": "implement",
    "cobol-modernization": "implement",
    "custom-memory-heap-crash": "diagnosing-bugs",
    "fix-git": "diagnosing-bugs",
    "git-leak-recovery": "diagnosing-bugs",
    "headless-terminal": "implement",
    "kv-store-grpc": "implement",
    "make-doom-for-mips": "implement",
    "make-mips-interpreter": "implement",
    "polyglot-c-py": "implement",
}
EXTRA_CAPTURE = {
    "build-pmars": ["/usr/local/bin/pmars"],
    "build-cython-ext": ["/usr/local/lib/python3.13/site-packages/pyknotid"],
}
# Frozen from the original visible contracts, before any transfer outcomes. Only
# this task requires a live work-product service when its verifier starts.
SERVICE_CONTRACTS = {
    name: ([{"script": "/app/server.py", "tcp_port": 5328}] if name == "kv-store-grpc" else [])
    for name in ENTRYPOINTS
}
COMMON_CONTEXT = """

Workflow runtime context (the original task above remains authoritative):
The issue tracker is local Markdown, and the original task is the current issue.
The original task supplies all domain facts and pre-agreed test requirements.
No external issue service is needed. If a workflow refers to an unavailable Skill
API, invoke the named skill by reading its SKILL.md and relevant references.
Skills are installed under /root/.agents/skills. One parent and at most two
concurrent native child agents are available, with delegation depth one and the
same model and reasoning effort. Do not launch external agent CLIs or change
runtime settings. Preserve the original task's required background services.
"""

# Node is installed by Harbor's Codex setup, unlike Python in several original
# transfer images. These controller commands read files/kernel /proc metadata
# and signal candidate processes. They install no dependency or task change.
NODE_RUNTIME = r"""
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
function fileHash(filename) {
  const hash = crypto.createHash('sha256');
  const fd = fs.openSync(filename, 'r');
  const chunk = Buffer.alloc(1024 * 1024);
  try { let count; while ((count = fs.readSync(fd, chunk)) > 0) hash.update(chunk.subarray(0, count)); }
  finally { fs.closeSync(fd); }
  return hash.digest('hex');
}
function inode(filename) {
  const info = fs.statSync(filename, {bigint: true});
  return {device: String(info.dev), inode: String(info.ino)};
}
function sameInode(left, right) {
  return left.device === right.device && left.inode === right.inode;
}
function regularFiles(root) {
  const files = [];
  function visit(directory) {
    for (const name of fs.readdirSync(directory).sort()) {
      const filename = path.join(directory, name), info = fs.lstatSync(filename);
      if (info.isDirectory()) visit(filename);
      else if (info.isFile()) files.push(filename);
      else throw new Error('unsupported node in trusted runtime source');
    }
  }
  visit(root);
  return files;
}
function skillFiles(root) {
  return Object.fromEntries(regularFiles(root).map(filename => [path.relative(root, filename), fileHash(filename)]));
}
function isElf(filename) {
  const fd = fs.openSync(filename, 'r'), header = Buffer.alloc(4);
  try { fs.readSync(fd, header); } finally { fs.closeSync(fd); }
  return header.equals(Buffer.from([127, 69, 76, 70]));
}
function collectRuntime(launcher) {
  launcher = fs.realpathSync(launcher);
  let binaries;
  if (isElf(launcher)) binaries = [launcher];
  else {
    // Pinned npm Codex places its native executable under the package's vendor
    // tree or optional platform package. Never scan the task workspace or /proc.
    const root = path.dirname(path.dirname(launcher));
    if (path.basename(launcher) !== 'codex.js' || path.basename(root) !== 'codex')
      throw new Error('unrecognized Codex launcher layout');
    binaries = regularFiles(root).filter(filename => path.basename(filename) === 'codex' && isElf(filename));
  }
  if (!binaries.length) throw new Error('native Codex executable unavailable');
  return {
    launcher, launcher_sha256: fileHash(launcher),
    node: {...inode(process.execPath), path: process.execPath, sha256: fileHash(process.execPath)},
    native: binaries.map(filename => ({...inode(filename), path: filename, sha256: fileHash(filename)})),
  };
}
function processInfo(pid) {
  try {
    const root = '/proc/' + pid;
    const fields = fs.readFileSync(root + '/stat', 'utf8').split(/\) /).at(-1).trim().split(/\s+/);
    if (fields[0] === 'Z') return null;
    return {pid, state: fields[0], ppid: Number(fields[1]), pgid: Number(fields[2]),
      sid: Number(fields[3]), started: fields[19], executable: inode(root + '/exe'),
      argv: fs.readFileSync(root + '/cmdline').toString().split('\0').filter(Boolean)};
  } catch (error) {
    if (['ENOENT', 'ESRCH'].includes(error.code)) return null;
    throw error;
  }
}
function isNativeAgent(info, identity) {
  if (!info || info.pid <= 1 || info.pid === process.pid) return false;
  if (identity.native.some(binary => sameInode(info.executable, binary))) return true;
  // Node may run a work-product server too: match only the exact Codex launcher,
  // never the interpreter alone, process names, parentage, or process groups.
  if (!sameInode(info.executable, identity.node) || !info.argv[1]) return false;
  try { return fs.realpathSync(info.argv[1]) === identity.launcher; }
  catch (error) { if (error.code === 'ENOENT') return false; throw error; }
}
function agentProcesses(identity) {
  return fs.readdirSync('/proc').filter(name => /^[0-9]+$/.test(name))
    .map(name => processInfo(Number(name))).filter(info => isNativeAgent(info, identity));
}
async function stopNative(identity, operations = {}) {
  const scan = operations.scan || (() => agentProcesses(identity));
  const reread = operations.reread || processInfo;
  const kill = operations.kill || (pid => process.kill(pid, 'SIGKILL'));
  const sleep = operations.sleep || (() => new Promise(resolve => setTimeout(resolve, 25)));
  const started = Date.now(), signaled = [];
  for (let iteration = 0; iteration < 80; iteration++) {
    const running = scan();
    if (!running.length) return {confirmed: true, signaled, wall_seconds: (Date.now() - started) / 1000};
    for (const info of running) {
      const current = reread(info.pid);
      if (!isNativeAgent(current, identity) || current.started !== info.started) continue;
      // Kill only this proven executable identity, with no shutdown handler that
      // could cascade into task services. Native child agents share this runtime.
      try { kill(info.pid); signaled.push({pid: info.pid, started: info.started}); }
      catch (error) { if (error.code !== 'ESRCH') throw error; }
    }
    await sleep();
  }
  throw new Error('native Codex processes remained after bounded stop');
}
function processSnapshot() {
  return fs.readdirSync('/proc').filter(name => /^[0-9]+$/.test(name))
    .map(name => processInfo(Number(name))).filter(Boolean);
}
function ancestors(info, rows) {
  const result = new Set(), byPid = new Map(rows.map(row => [row.pid, row]));
  let parent = info.ppid;
  while (parent > 1 && !result.has(parent)) {
    result.add(parent); parent = byPid.get(parent)?.ppid || 0;
  }
  return result;
}
function ownsListener(info, port) {
  const sockets = new Set();
  for (const version of ['tcp', 'tcp6']) {
    for (const line of fs.readFileSync('/proc/net/' + version, 'utf8').trim().split('\n').slice(1)) {
      const parts = line.trim().split(/\s+/);
      if (parts[3] === '0A' && parseInt(parts[1].split(':').at(-1), 16) === port) sockets.add(parts[9]);
    }
  }
  for (const name of fs.readdirSync('/proc/' + info.pid + '/fd')) {
    try {
      const target = fs.readlinkSync('/proc/' + info.pid + '/fd/' + name);
      if (/^socket:\[[0-9]+\]$/.test(target) && sockets.has(target.slice(8, -1))) return true;
    } catch (error) { if (!['ENOENT', 'ESRCH'].includes(error.code)) throw error; }
  }
  return false;
}
function matchesService(info, contract) {
  // argv alone is insufficient: require the original script and that process's
  // kernel-owned listener. Ambiguous launch forms remain unavailable evidence.
  const root = '/proc/' + info.pid;
  const cwd = fs.readlinkSync(root + '/cwd');
  const script = info.argv.slice(1).some(arg => {
    if (arg.startsWith('-')) return false;
    try { return fs.realpathSync(path.resolve(cwd, arg)) === contract.script; }
    catch (error) { if (['ENOENT', 'ENOTDIR'].includes(error.code)) return false; throw error; }
  });
  return script && ownsListener(info, contract.tcp_port);
}
async function stopExecution(identity, operations = {}) {
  if (!identity.baseline || !Array.isArray(identity.service_contracts))
    throw new Error('missing registered process baseline or service contract');
  const scan = operations.scan || processSnapshot, reread = operations.reread || processInfo;
  const signal = operations.signal || ((pid, name) => process.kill(pid, name));
  const sleep = operations.sleep || (() => new Promise(resolve => setTimeout(resolve, 10)));
  const serviceMatch = operations.serviceMatch || matchesService;
  const controllerPid = operations.controllerPid || process.pid;
  const started = Date.now(), frozen = new Map(), issues = [], signaled = [], services = [];
  const transport = new Map(), pausedTransport = new Map();
  let quiet = false;
  function same(left, right) { return left && right && left.pid === right.pid && left.started === right.started; }
  function send(row, name) {
    const current = reread(row.pid);
    if (!current) return;
    if (!same(row, current)) { issues.push({kind:'pid_reused',pid:row.pid}); return; }
    try { signal(row.pid, name); }
    catch (error) { if (error.code !== 'ESRCH') throw error; }
  }
  function excluded(row, rows) {
    const controller = rows.find(item => item.pid === controllerPid);
    return row.pid <= 1 || row.pid === controllerPid || (controller && ancestors(controller, rows).has(row.pid))
      || identity.baseline[String(row.pid)] === row.started || same(transport.get(row.pid), row);
  }
  // Freeze every new candidate process before classifying it. This preserves
  // ancestry/group evidence and closes ordinary fork races; stopped tools cannot
  // create new writers while their native parent is being killed.
  for (let sweep = 0; sweep < 32; sweep++) {
    const rows = scan(), natives = rows.filter(row => isNativeAgent(row, identity));
    const nativeIds = new Set(natives.map(row => row.pid));
    const controller = rows.find(row => row.pid === controllerPid);
    const controllerParents = controller ? ancestors(controller, rows) : new Set();
    for (const native of natives) {
      const parents = ancestors(native, rows);
      for (const row of rows) {
        if (parents.has(row.pid) && !nativeIds.has(row.pid)
            && ![...ancestors(row,rows)].some(pid => nativeIds.has(pid))) {
          transport.set(row.pid, row);
          if (row.pid > 1 && row.pid !== controllerPid && !controllerParents.has(row.pid)
              && identity.baseline[String(row.pid)] !== row.started) {
            // Hold Harbor's outer launch shell until cutoff checks finish, so
            // its normal post-run log copy cannot race this candidate census.
            pausedTransport.set(row.pid,row); send(row,'SIGSTOP');
          }
        }
        // Pinned Harbor's sole sibling pipeline process writes the agent log.
        if (parents.has(row.ppid) && row.pgid === native.pgid
            && ![...ancestors(row,rows)].some(pid => nativeIds.has(pid))
            && path.basename(row.argv[0] || '') === 'tee'
            && row.argv.length === 2 && row.argv[1] === '/logs/agent/codex.txt') transport.set(row.pid, row);
      }
    }
    let pending = false;
    for (const row of rows) {
      if (excluded(row, rows)) continue;
      const key = row.pid + ':' + row.started;
      if ([...frozen.values()].some(previous => previous.pid === row.pid && previous.started !== row.started))
        issues.push({kind:'pid_reused',pid:row.pid});
      if (!frozen.has(key)) frozen.set(key, {...row,
        native: isNativeAgent(row, identity),
        tool: [...ancestors(row, rows)].some(pid => nativeIds.has(pid))});
      if (!['T','t'].includes(row.state)) { pending = true; send(row, 'SIGSTOP'); }
    }
    if (!pending) { quiet = true; break; }
    await sleep();
  }
  if (!quiet) issues.push({kind:'freeze_did_not_quiesce'});
  const currentRows = scan();
  for (const row of frozen.values()) {
    const current = currentRows.find(item => same(row, item));
    if (!current) continue;
    let allowedService = false;
    if (!row.native && !row.tool) {
      allowedService = identity.service_contracts.some(contract => serviceMatch(current, contract));
    }
    if (allowedService) services.push(current);
    else {
      if (!row.native && !row.tool) issues.push({kind:'unclassified_new_process',pid:row.pid,started:row.started,
        ppid:row.ppid,pgid:row.pgid,sid:row.sid});
      send(current, 'SIGKILL'); signaled.push({pid:row.pid,started:row.started,kind:row.native?'native':'tool_or_unclassified'});
    }
  }
  // Require every remaining new process to be the exact retained service. Never
  // convert a surviving/respawned process or a reused PID into a success record.
  let confirmed = false;
  for (let sweep = 0; sweep < 32; sweep++) {
    const rows = scan();
    const remaining = rows.filter(row => !excluded(row, rows) && !services.some(service => same(service,row)));
    if (!remaining.length) { confirmed = true; break; }
    for (const row of remaining) {
      issues.push({kind:'surviving_or_new_process',pid:row.pid,started:row.started}); send(row,'SIGKILL');
    }
    await sleep();
  }
  if (!confirmed) issues.push({kind:'termination_did_not_quiesce'});
  // Required services resume only after the complete cutoff has been established.
  // On failure the container will be discarded without running the verifier.
  if (!issues.length && confirmed) for (const service of services) send(service, 'SIGCONT');
  for (const row of pausedTransport.values()) send(row,'SIGCONT');
  return {confirmed, boundary_confirmed:confirmed && !issues.length, signaled, issues,
    services_preserved:services.map(({pid,started,pgid,sid})=>({pid,started,pgid,sid})),
    frozen_processes:[...frozen.values()].map(({pid,started,ppid,pgid,sid,native,tool})=>({pid,started,ppid,pgid,sid,native,tool})),
    wall_seconds:(Date.now()-started)/1000};
}
"""


def _node_command(script: str, *, launcher_argument: bool = False) -> str:
    command = "if [ -s ~/.nvm/nvm.sh ]; then . ~/.nvm/nvm.sh; fi; node -e " + shlex.quote(
        NODE_RUNTIME + "\n" + script
    )
    if launcher_argument:
        command += ' "$(command -v codex)"'
    return command


def expected_skill_files(skills: list[str]) -> dict:
    expected = {}
    for source in map(Path, skills):
        for filename in source.rglob("*"):
            if filename.is_symlink():
                raise ValueError("workflow source may not contain symlinks")
            if filename.is_file():
                expected[f"{source.name}/{filename.relative_to(source).as_posix()}"] = _file_hash(filename)
    return expected


async def verify_workflow_exposure(
    environment, skills: list[str], arm: str, registration_command: str
) -> dict:
    expected = expected_skill_files(skills)
    # Native Codex registers skills inside run(), after Harbor's AGENT_START.
    # First authenticate the injected bytes, then execute that exact pinned
    # registration command early and verify its result. The later native copy
    # remains unchanged and copies these same bytes again.
    injected = await environment.exec(
        _node_command("console.log(JSON.stringify(skillFiles('/harbor/skills')));"), timeout_sec=15
    )
    if injected.return_code != 0 or json.loads(injected.stdout) != expected:
        raise RuntimeError("injected workflow bytes differ from the assigned arm")
    if not registration_command:
        raise RuntimeError("pinned native Codex skill registration command is missing")
    registered = await environment.exec(registration_command, timeout_sec=15)
    if registered.return_code != 0:
        raise RuntimeError("controller could not register the verified workflow bytes")
    script = "console.log(JSON.stringify({injected:skillFiles('/harbor/skills'),registered:skillFiles('/root/.agents/skills')}));"
    result = await environment.exec(_node_command(script), timeout_sec=15)
    if result.return_code != 0:
        raise RuntimeError("controller could not inspect workflow exposure")
    actual = json.loads(result.stdout)
    if actual != {"injected": expected, "registered": expected}:
        raise RuntimeError("injected or registered workflow bytes differ from the assigned arm")
    return {"arm": arm, "source_files": expected, "verified_before_agent": True, "producer": "controller"}


async def record_native_identity(environment, service_contracts: list[dict]) -> dict:
    script = (
        "const identity=collectRuntime(process.argv[1]); if(agentProcesses(identity).length) throw new Error('preexisting native agent'); "
        "identity.baseline=Object.fromEntries(processSnapshot().map(row=>[String(row.pid),row.started])); "
        "identity.service_contracts="
        + json.dumps(service_contracts)
        + "; console.log(JSON.stringify(identity));"
    )
    result = await environment.exec(_node_command(script, launcher_argument=True), timeout_sec=20)
    if result.return_code != 0:
        raise RuntimeError("controller could not pin the native Codex executable")
    identity = json.loads(result.stdout)
    if not identity.get("native") or not identity.get("node") or not identity.get("launcher"):
        raise RuntimeError("native Codex identity is incomplete")
    return identity


async def stop_native_agent(environment, identity: dict) -> dict:
    started = time.monotonic()
    script = (
        "stopExecution("
        + json.dumps(identity)
        + ").then(result=>console.log(JSON.stringify(result))).catch(error=>{console.error(error.message);process.exitCode=1;});"
    )
    result = await environment.exec(_node_command(script), timeout_sec=10)
    if result.return_code != 0:
        raise RuntimeError("native Codex termination was not confirmed; verifier must not run")
    observed = json.loads(result.stdout)
    if observed.get("confirmed") is not True:
        raise RuntimeError("native Codex termination was not confirmed; verifier must not run")
    return {**observed, "controller_wall_seconds": time.monotonic() - started, "producer": "controller"}


class ExecutionBoundaryError(RuntimeError):
    """Candidate processes could not be separated from required task services."""


class NativeStopGuard:
    """Stop at the original deadline even while Harbor cancellation is cleaning up.

    The end hook reuses a deadline stop instead of killing the runtime twice.
    Required services are retained only through the frozen service contract and
    controller-owned process/listener evidence.
    """

    def __init__(self, environment, identity: dict, seconds: float, *, stop=stop_native_agent):
        self.environment, self.identity, self.seconds, self.stop = environment, identity, seconds, stop
        self.expired = False
        self.result = None
        self.started = time.monotonic()
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.stop_started_at = None
        self.task = asyncio.create_task(self._deadline())

    async def _stop(self, reason: str):
        self.stop_started_at = datetime.now(timezone.utc).isoformat()
        observed = await self.stop(self.environment, self.identity)
        self.result = {
            **observed,
            "reason": reason,
            "termination_started_at": self.stop_started_at,
            "termination_finished_at": datetime.now(timezone.utc).isoformat(),
            "agent_phase_started_at": self.started_at,
            "agent_deadline_seconds": self.seconds,
            "agent_phase_elapsed_seconds": time.monotonic() - self.started,
        }
        return self.result

    async def _deadline(self):
        await asyncio.sleep(self.seconds)
        self.expired = True
        return await self._stop("original_agent_deadline")

    async def finish(self):
        if self.expired:
            return await self.task
        await self.close()
        return await self._stop("agent_end")

    async def close(self):
        if not self.task.done():
            self.task.cancel()
        try:
            await self.task
        except asyncio.CancelledError:
            pass


def _bytes_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_hash(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def _canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _write_once(path: Path, value) -> None:
    with path.open("xb") as stream:
        stream.write(_canonical(value))


def _run(argv: list[str]):
    return subprocess.run(argv, text=True, capture_output=True, timeout=600, check=True)


def runtime_sources(root: Path = BENCH) -> dict:
    """Bind the adapter and every shared local helper used by this execution path."""
    return {name: _file_hash(root / name) for name in RUNTIME_SOURCE_FILES}


def verify_harbor_version() -> str:
    version = importlib.metadata.version("harbor")
    if version != HARBOR_VERSION:
        raise ValueError("transfer execution requires exactly Harbor 0.24.0")
    return version


def _git_pin(repository: Path, pin: str, runner=_run) -> None:
    head = runner(["git", "-C", str(repository), "rev-parse", "HEAD"]).stdout.strip()
    dirty = runner(["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=all"]).stdout
    if head != pin or dirty:
        raise ValueError("source checkout must be clean at its registered commit")


def tree_manifest(root: Path) -> dict:
    """Bind modes and bytes without following source symlinks."""
    result = {}
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(directory) / name
            info = path.lstat()
            item = {"mode": stat.S_IMODE(info.st_mode)}
            if stat.S_ISLNK(info.st_mode):
                item.update(type="symlink", target=os.readlink(path))
            elif stat.S_ISREG(info.st_mode):
                item.update(type="file", size=info.st_size, sha256=_file_hash(path))
            elif stat.S_ISDIR(info.st_mode):
                item.update(type="directory")
            else:
                raise ValueError("unsupported node in trusted task definition")
            result[path.relative_to(root).as_posix()] = item
    return result


def validate_selection(source: Path, selection: dict, *, runner=_run) -> dict:
    """Reproduce metadata-only selection and retain every exclusion reason."""
    _git_pin(source, SOURCE_PIN, runner)
    eligible, excluded = [], []
    for path in sorted(source.glob("*/task.toml")):
        data = tomllib.loads(path.read_text())
        metadata, environment = data["metadata"], data["environment"]
        reasons = []
        if metadata.get("category") not in {"software-engineering", "debugging"}:
            reasons.append("category")
        if environment.get("cpus", 1) > 1:
            reasons.append("cpu")
        if environment.get("memory") != "2G":
            reasons.append("memory")
        if environment.get("gpus", 0) != 0:
            reasons.append("gpu")
        if data["agent"]["timeout_sec"] > 1800 or data["verifier"]["timeout_sec"] > 1800:
            reasons.append("timeout")
        if set(metadata.get("tags", [])) & {"ocr", "images", "no-verified-solution"}:
            reasons.append("excluded_tag")
        if reasons:
            excluded.append({"task_id": path.parent.name, "reasons": reasons})
            continue
        eligible.append(
            {
                "task_id": path.parent.name,
                "category": metadata["category"],
                "agent_seconds": data["agent"]["timeout_sec"],
                "verifier_seconds": data["verifier"]["timeout_sec"],
                "image_source": environment.get("docker_image"),
                "task_toml_sha256": _bytes_hash(path.read_bytes()),
            }
        )
    if (
        selection.get("source_commit") != SOURCE_PIN
        or selection.get("eligible") != eligible
        or selection.get("selected") != eligible[:12]
        or [row["task_id"] for row in eligible[:12]] != list(ENTRYPOINTS)
    ):
        raise ValueError("selection differs from the registered score-blind twelve-task subset")
    return {
        "selection": selection,
        "excluded": excluded,
        "eligible_not_selected": [row["task_id"] for row in eligible[12:]],
        "entrypoints": ENTRYPOINTS.copy(),
    }


def _inspect(reference: str, runner=_run) -> dict:
    result = json.loads(runner(["docker", "image", "inspect", reference]).stdout)
    if not isinstance(result, list) or len(result) != 1:
        raise ValueError("ambiguous Docker image identity")
    return result[0]


def resolve_image_lock(
    source: Path, selection: dict, *, pull: bool = False, platform: str = "linux/amd64", runner=_run
) -> dict:
    """Explicit preflight: inspect local images; pull only when explicitly requested.

    Both arms use each task's original image and network configuration. No image
    build fallback, task substitution, dependency stripping, or model run occurs.
    """
    catalog = validate_selection(source, selection, runner=runner)
    images = {}
    for row in selection["selected"]:
        reference = row["image_source"]
        if not isinstance(reference, str) or not reference:
            raise ValueError("selected task lacks its registered prebuilt image")
        if pull:
            runner(["docker", "pull", "--platform", platform, reference])
        info = _inspect(reference, runner)
        actual_platform = info.get("Os", "") + "/" + info.get("Architecture", "")
        if actual_platform != platform or not re.fullmatch(r"sha256:[0-9a-f]{64}", info.get("Id", "")):
            raise ValueError("image platform or content identity does not match preflight")
        repository = reference.rsplit(":", 1)[0].removeprefix("docker.io/")
        digests = [
            item
            for item in info.get("RepoDigests", [])
            if isinstance(item, str)
            and item.split("@", 1)[0].removeprefix("docker.io/") == repository
            and re.fullmatch(r".+@sha256:[0-9a-f]{64}", item)
        ]
        if not digests:
            raise ValueError("image has no retained upstream repository digest")
        local = "evalopt-transfer-pin:" + info["Id"].split(":", 1)[1]
        runner(["docker", "tag", info["Id"], local])
        if _inspect(local, runner)["Id"] != info["Id"]:
            raise ValueError("local pin does not resolve to inspected image")
        images[row["task_id"]] = {
            "source_image": reference,
            "repository_digest": sorted(digests)[0],
            "image_id": info["Id"],
            "local_reference": local,
            "platform": actual_platform,
        }
    return {
        "schema_version": "evalopt.transfer-images.v1",
        "evidence_class": EVIDENCE_CLASS,
        "source_commit": SOURCE_PIN,
        "catalog": catalog,
        "images": images,
        "agent_trials": 0,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }


def _replace_image(original: bytes, source_image: str, locked: str) -> bytes:
    data = tomllib.loads(original.decode())
    if data["environment"].get("docker_image") != source_image:
        raise ValueError("source image differs from selected task")
    text = original.decode()
    pattern = re.compile(r'(?m)^docker_image\s*=\s*"' + re.escape(source_image) + r'"\s*$')
    updated, count = pattern.subn('docker_image = "' + locked + '"', text)
    if count != 1:
        raise ValueError("cannot unambiguously pin original task image")
    expected = json.loads(json.dumps(data))
    expected["environment"]["docker_image"] = locked
    if tomllib.loads(updated) != expected:
        raise ValueError("pinning changed upstream task semantics")
    return updated.encode()


def _bundle_sources(upstream: Path, evalopt_skill: Path, *, runner=_run) -> dict:
    from runtime.harbor_campaign import source_identity, upstream_skills

    _git_pin(upstream, UPSTREAM_PIN, runner)
    paths = upstream_skills(upstream)
    if not {"implement", "diagnosing-bugs", "code-review"} <= {path.name for path in paths}:
        raise ValueError("complete upstream entrypoints are missing")
    if not (evalopt_skill / "SKILL.md").is_file():
        raise ValueError("portable eval-opt skill missing")
    return {
        "upstream": source_identity(upstream / "skills"),
        "evalopt": source_identity(evalopt_skill),
    }


def prepare_transfer(
    source: Path,
    selection: dict,
    image_lock: dict,
    destination: Path,
    *,
    upstream: Path,
    evalopt_skill: Path,
    runner=_run,
) -> dict:
    """Prepare reviewable B/C task copies without Docker execution or model calls."""
    catalog = validate_selection(source, selection, runner=runner)
    if image_lock.get("catalog") != catalog or set(image_lock.get("images", {})) != set(ENTRYPOINTS):
        raise ValueError("image lock does not bind this complete selection")
    bundles = _bundle_sources(upstream, evalopt_skill, runner=runner)
    for row in selection["selected"]:
        image = image_lock["images"][row["task_id"]]
        identity = image.get("image_id", "")
        if (
            not re.fullmatch(r"sha256:[0-9a-f]{64}", identity)
            or image.get("local_reference") != "evalopt-transfer-pin:" + identity.removeprefix("sha256:")
            or image.get("source_image") != row["image_source"]
            or not re.fullmatch(r".+@sha256:[0-9a-f]{64}", image.get("repository_digest", ""))
        ):
            raise ValueError("unresolved or inconsistent image lock")
    destination.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(HERE / "codex.toml", destination / "codex.toml")
    tasks = {}
    for row in selection["selected"]:
        name = row["task_id"]
        original = source / name
        original_manifest = tree_manifest(original)
        arms = {}
        for arm in ("B", "C"):
            target = destination / arm / name
            shutil.copytree(original, target, symlinks=True)
            entry = ENTRYPOINTS[name] if arm == "B" else "eval-opt"
            invocation = f"\nUse ${entry}. Read /root/.agents/skills/{entry}/SKILL.md before starting.\n"
            (target / "instruction.md").write_bytes(
                (original / "instruction.md").read_bytes() + COMMON_CONTEXT.encode() + invocation.encode()
            )
            (target / "task.toml").write_bytes(
                _replace_image(
                    (original / "task.toml").read_bytes(),
                    row["image_source"],
                    image_lock["images"][name]["local_reference"],
                )
            )
            manifest = tree_manifest(target)
            changed = {
                key
                for key in original_manifest.keys() | manifest.keys()
                if original_manifest.get(key) != manifest.get(key)
            }
            if changed != {"instruction.md", "task.toml"}:
                raise ValueError("preparation changed an upstream environment, solution, or verifier file")
            arms[arm] = {"tree": manifest, "entrypoint": entry}
        tasks[name] = {"original_tree": original_manifest, "arms": arms}
    manifest = {
        "schema_version": "evalopt.transfer-preparation.v1",
        "evidence_class": EVIDENCE_CLASS,
        "source_commit": SOURCE_PIN,
        "upstream_commit": UPSTREAM_PIN,
        "catalog": catalog,
        "image_lock": image_lock,
        "skill_sources": bundles,
        "runtime_sources": runtime_sources(),
        "harbor_version": HARBOR_VERSION,
        "config_sha256": _bytes_hash((destination / "codex.toml").read_bytes()),
        "model": "gpt-6-astra",
        "reasoning_effort": "ultra",
        "codex_version": "0.154.0",
        "max_capture_bytes": 10 * 1024**3,
        "capture_paths": {name: ["/app", *EXTRA_CAPTURE.get(name, [])] for name in ENTRYPOINTS},
        "service_contracts": json.loads(json.dumps(SERVICE_CONTRACTS)),
        "verifier_semantics": "upstream unchanged; shared environment and required services preserved",
        "raw_artifacts_publication_ready": False,
        "tasks": tasks,
    }
    _write_once(destination / "preparation.json", manifest)
    return {
        "preparation_sha256": _bytes_hash((destination / "preparation.json").read_bytes()),
        "manifest": manifest,
    }


def validate_prepared(
    root: Path, expected_sha256: str, *, upstream: Path, evalopt_skill: Path, runner=_run
) -> dict:
    raw = (root / "preparation.json").read_bytes()
    if _bytes_hash(raw) != expected_sha256:
        raise ValueError("preparation differs from the externally frozen identity")
    manifest = json.loads(raw)
    if manifest.get("source_commit") != SOURCE_PIN or set(manifest.get("tasks", {})) != set(ENTRYPOINTS):
        raise ValueError("prepared task set differs from registered transfer")
    if manifest.get("service_contracts") != SERVICE_CONTRACTS:
        raise ValueError("required-service contracts differ from the frozen original tasks")
    if (
        manifest.get("runtime_sources") != runtime_sources()
        or manifest.get("harbor_version") != HARBOR_VERSION
    ):
        raise ValueError("transfer adapter, shared runtime helper, or Harbor pin changed after preparation")
    if _bytes_hash((root / "codex.toml").read_bytes()) != manifest["config_sha256"]:
        raise ValueError("prepared runtime configuration changed")
    if _bundle_sources(upstream, evalopt_skill, runner=runner) != manifest["skill_sources"]:
        raise ValueError("workflow bundle changed after transfer preparation")
    for name, task in manifest["tasks"].items():
        for arm in ("B", "C"):
            if tree_manifest(root / arm / name) != task["arms"][arm]["tree"]:
                raise ValueError("prepared upstream task or verifier changed")
    return manifest


def validate_runtime_preflight(preflight: Path, prepared: dict) -> dict:
    """Reproduce the shared native capability probe; never trust a ready flag alone.

    This validates Codex/skill/accounting capabilities, not every transfer image.
    Actual returned model/CLI/child telemetry is additionally checked per trial.
    """
    from lib.accounting import parse_native_usage, summarize_usage
    from runtime.readiness import REQUIRED

    probe = json.loads((preflight / "summary.json").read_text())
    if not all(probe.get("checks", {}).get(name) is True for name in REQUIRED):
        raise ValueError("native subscription/skill/accounting preflight incomplete")
    if (
        probe.get("config_sha256") != prepared["config_sha256"]
        or probe.get("skill_sources") != prepared["skill_sources"]
    ):
        raise ValueError("native preflight has different configuration or workflow sources")
    usage = summarize_usage(parse_native_usage(preflight / "sessions"))
    if usage != probe.get("usage") or usage["agent_count"] != 3:
        raise ValueError("native preflight child accounting cannot be reproduced")
    return {"probe_sha256": _bytes_hash((preflight / "summary.json").read_bytes()), "usage": usage}


def trial_configuration(
    row: dict, prepared_root: Path, output: Path, upstream: Path, evalopt_skill: Path
) -> dict:
    from runtime.harbor_campaign import upstream_skills

    if (
        row.get("stage") != "transfer"
        or row.get("arm") not in {"B", "C"}
        or row.get("task_id") not in ENTRYPOINTS
    ):
        raise ValueError("transfer supports exactly registered B/C tasks")
    skills = [str(path) for path in upstream_skills(upstream)] if row["arm"] == "B" else [str(evalopt_skill)]
    return {
        "task": {"path": str(prepared_root / row["arm"] / row["task_id"])},
        "trial_name": "harbor-transfer-" + uuid.uuid4().hex[:16],
        "trials_dir": str(output),
        "agent": {
            "name": "codex",
            "model_name": "gpt-6-astra",
            "skills": skills,
            "kwargs": {"version": "0.154.0", "config": str(prepared_root / "codex.toml")},
            # The host subscription_environment sets the auth-file switch.
            # Harbor treats AUTH-named agent.env values as secrets and would
            # replace every "1" in native JSON telemetry if supplied here.
        },
        "environment": {"type": "docker", "delete": True},
        # Deliberately no resource/network/agent-timeout/verifier overrides.
    }


async def _archive_container_path(container: str, source: str, destination: Path, maximum: int) -> dict:
    """Stream Docker's tar to a controller-owned file; never unpack candidate names."""
    started = time.monotonic()
    process = await asyncio.create_subprocess_exec(
        "docker",
        "cp",
        f"{container}:{source}",
        "-",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stderr_task = asyncio.create_task(process.stderr.read())
    size, written, digest = 0, 0, hashlib.sha256()
    error = None
    try:
        with destination.open("xb") as stream:
            while True:
                remaining = 120 - (time.monotonic() - started)
                chunk = await asyncio.wait_for(
                    process.stdout.read(1024 * 1024), timeout=max(remaining, 0.001)
                )
                if not chunk:
                    break
                size += len(chunk)
                if size > maximum:
                    raise ValueError("stopped archive exceeds registered capture limit")
                stream.write(chunk)
                written += len(chunk)
                digest.update(chunk)
        await asyncio.wait_for(process.wait(), timeout=max(120 - (time.monotonic() - started), 0.001))
    except (TimeoutError, ValueError, OSError) as exc:
        error = type(exc).__name__
    finally:
        # Cancellation must not leave docker cp streaming after the trial ends.
        if process.returncode is None:
            process.kill()
        await process.wait()
        stderr = await stderr_task
        if stderr:
            destination.with_suffix(".stderr.txt").write_bytes(stderr)
    return {
        "source": source,
        "path": destination.name,
        "bytes": written,
        "sha256": digest.hexdigest(),
        "returncode": process.returncode,
        "complete": error is None and process.returncode == 0,
        "error": error,
    }


async def capture_stopped(
    environment, directory: Path, paths: list[str], maximum: int, *, archive=_archive_container_path
) -> dict:
    """Pause for capture and resume required services before the upstream verifier.

    No STOP_CANDIDATE or process killing: kv-store-grpc requires its server alive.
    No command executes inside the paused container and no hidden grader is read.
    """
    directory.mkdir(parents=True, exist_ok=False)
    identity = await environment._run_docker_compose_command(["ps", "-q", "main"])
    container = identity.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{12,64}", container):
        raise ValueError("ambiguous candidate container identity")
    await environment._run_docker_compose_command(["pause"])
    records = []
    try:
        for index, path in enumerate(paths):
            records.append(await archive(container, path, directory / f"output-{index}.tar", maximum))
    finally:
        await environment._run_docker_compose_command(["unpause"])
    result = {
        "schema_version": "evalopt.transfer-stopped.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "producer": "controller",
        "artifacts": records,
        "primary_output_complete": bool(records) and records[0]["complete"],
        "all_outputs_complete": bool(records) and all(record["complete"] for record in records),
        "required_services_preserved": True,
        "publication_ready": False,
    }
    _write_once(directory / "stopped.json", result)
    return result


def summarize_result(row: dict, result, *, agent_started: bool, stopped: dict | None, usage: dict) -> dict:
    exception = result.exception_info.exception_type if result.exception_info else None
    rewards = result.verifier_result.rewards if result.verifier_result else None
    # Original Terminal-Bench tasks emit reward. Unknown/multiple metrics remain
    # ungraded instead of inventing a success rule from whichever value is largest.
    reward = rewards.get("reward") if isinstance(rewards, dict) and set(rewards) == {"reward"} else None
    if type(reward) not in (int, float) or not math.isfinite(reward) or reward not in (0, 1):
        reward = None
    boundary_complete = usage.get("execution_boundary_complete") is True
    if not boundary_complete:
        reward = None
    captured = stopped is not None and stopped.get("all_outputs_complete") is True
    if exception in {"ApiUsageLimitError", "ApiRateLimitError"}:
        status, error_code = "infra_failure", "subscription_exhausted"
    elif exception == "AgentTimeoutError" or usage.get("agent_deadline_expired") is True:
        status, error_code = "timeout", None
    elif not agent_started:
        status, error_code = "infra_failure", "container_start"
    elif not boundary_complete:
        status, error_code = "agent_failure", None
    elif exception:
        status, error_code = "agent_failure", None
    elif reward is None:
        status, error_code = "infra_failure", "verifier_infrastructure"
    else:
        status, error_code = "completed", None
    # Transfer reports the original verifier's reward even if the agent stopped
    # at its time limit. Never replace upstream scoring with authored-suite rules.
    success = None if reward is None else bool(reward)
    return {
        **row,
        "schema_version": "evalopt.transfer-trial.v1",
        "evidence_class": EVIDENCE_CLASS,
        "status": status,
        "error_code": error_code,
        "upstream_reward": reward,
        "functional_success": success,
        "execution_boundary_complete": boundary_complete,
        "artifact_capture_complete": captured,
        "usage": usage,
        "runtime_evidence_complete": usage.get("child_usage_complete") is True
        and usage.get("runtime_valid") is True
        and usage.get("workflow_exposure_verified") is True
        and usage.get("native_agent_stopped") is True
        and boundary_complete
        and usage.get("entrypoint_load_observed") is True,
        "verifier_semantics": "original shared verifier",
        "raw_artifacts_publication_ready": False,
    }


async def execute_transfer_trial(
    row: dict,
    *,
    prepared_root: Path,
    preparation_sha256: str,
    directory: Path,
    upstream: Path,
    evalopt_skill: Path,
    runtime_preflight: Path,
    accounting_policy: dict | None = None,
    runner=_run,
) -> dict:
    """One fresh transfer attempt; scheduler owns admission/retry/quota pauses.

    ``directory`` must be a new controller-only attempt directory. No automatic
    retry, credit purchase, model substitution, or API fallback is implemented.
    """
    harbor_version = verify_harbor_version()
    from harbor.models.trial.config import TrialConfig
    from harbor.trial.hooks import TrialEvent
    from harbor.trial.trial import Trial
    from lib.accounting import parse_native_usage, summarize_usage
    from runtime.harbor_campaign import subscription_environment
    from runtime.observations import runtime_observations

    if accounting_policy is not None:
        from runtime import accounting_policy as accounting

        accounting.validate_policy(accounting_policy)

    prepared = validate_prepared(
        prepared_root, preparation_sha256, upstream=upstream, evalopt_skill=evalopt_skill, runner=runner
    )
    readiness = validate_runtime_preflight(runtime_preflight, prepared)
    config_dict = trial_configuration(row, prepared_root, directory, upstream, evalopt_skill)
    image = prepared["image_lock"]["images"][row["task_id"]]
    if _inspect(image["local_reference"], runner)["Id"] != image["image_id"]:
        raise ValueError("local task image changed after preflight")
    subscription_environment()
    directory.mkdir(parents=True, exist_ok=False)
    _write_once(
        directory / "start.json",
        {
            "row": row,
            "preparation_sha256": preparation_sha256,
            "harbor_version": harbor_version,
            "readiness": readiness,
            "image": image,
            "started_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    trial = await Trial.create(TrialConfig.model_validate(config_dict))
    started, stopped, exposure, native_identity, native_stop, guard = False, None, None, None, None, None
    agent_start_observed = False

    async def on_start(_event):
        nonlocal started, exposure, native_identity, guard, agent_start_observed
        agent_start_observed = True
        exposure = await verify_workflow_exposure(
            trial.agent_environment,
            config_dict["agent"]["skills"],
            row["arm"],
            trial.agent._build_register_skills_command(),
        )
        _write_once(directory / "workflow-exposure.json", exposure)
        native_identity = await record_native_identity(
            trial.agent_environment, prepared["service_contracts"][row["task_id"]]
        )
        _write_once(directory / "native-identity.json", native_identity)
        deadline = next(
            task["agent_seconds"]
            for task in prepared["catalog"]["selection"]["selected"]
            if task["task_id"] == row["task_id"]
        )
        guard = NativeStopGuard(trial.agent_environment, native_identity, deadline)
        started = True

    async def on_stop(_event):
        nonlocal stopped, native_stop
        # Harbor's cancelled docker-exec client does not prove that the native
        # runtime or its tools inside the container exited. Freeze and terminate
        # owned work, preserving only the registered detached task service.
        end_hook_at = datetime.now(timezone.utc).isoformat()
        try:
            native_stop = await guard.finish()
            _write_once(directory / "native-stop.json", {**native_stop, "agent_end_hook_at": end_hook_at})
            if native_stop.get("boundary_confirmed") is not True:
                raise ExecutionBoundaryError("outstanding candidate work prevents original-verifier scoring")
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            _write_once(
                directory / "native-stop-failure.json",
                {
                    "error_type": type(exc).__name__,
                    "agent_end_hook_at": end_hook_at,
                    "termination_started_at": guard.stop_started_at,
                },
            )
            raise  # A possibly live agent must never run alongside the verifier.
        try:
            stopped = await capture_stopped(
                trial.agent_environment,
                directory / "stopped",
                prepared["capture_paths"][row["task_id"]],
                prepared["max_capture_bytes"],
            )
        except (OSError, ValueError, RuntimeError, TimeoutError) as exc:
            # Keep the original verifier runnable even when evidence capture fails.
            _write_once(directory / "capture-failure.json", {"error_type": type(exc).__name__})

    trial.add_hook(TrialEvent.AGENT_START, on_start)
    trial.add_hook(TrialEvent.AGENT_END, on_stop)
    try:
        result = await trial.run()
    finally:
        if guard is not None:
            try:
                await guard.close()
            except (OSError, ValueError, RuntimeError, TimeoutError):
                pass  # The end hook retains the stop failure and blocks verification.
    sessions = trial.paths.agent_dir / "sessions"
    if accounting_policy is not None:
        usage = accounting.collect_usage(sessions, accounting_policy)
        usage["agent_started"] = agent_start_observed
    else:
        try:
            usage = summarize_usage(parse_native_usage(sessions))
        except (ValueError, KeyError, OSError):
            usage = {
                "child_usage_complete": False,
                "accounting_status": "unavailable",
                "raw_logs_retained": True,
            }
    entry = ENTRYPOINTS[row["task_id"]] if row["arm"] == "B" else "eval-opt"
    try:
        usage.update(runtime_observations(sessions, entry))
    except (ValueError, OSError):
        usage["runtime_valid"] = False
    usage["workflow_exposure_verified"] = bool(exposure and exposure.get("verified_before_agent"))
    usage["native_agent_stopped"] = bool(native_stop and native_stop.get("confirmed"))
    usage["execution_boundary_complete"] = bool(native_stop and native_stop.get("boundary_confirmed"))
    usage["agent_deadline_expired"] = bool(guard and guard.expired)
    if native_stop:
        usage["native_stop_wall_seconds"] = native_stop["controller_wall_seconds"]
    summary = summarize_result(row, result, agent_started=started, stopped=stopped, usage=usage)
    _write_once(directory / "result.json", summary)
    _write_once(
        directory / "artifacts.json",
        {
            "producer": "controller",
            "publication_ready": False,
            "note": "Raw logs and archives require sanitization; archive contents were never extracted.",
            "tree": tree_manifest(directory),
        },
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    resolve = sub.add_parser("resolve-images", help="explicit image preflight; no model calls")
    resolve.add_argument("--source", type=Path, required=True)
    resolve.add_argument("--selection", type=Path, default=BENCH / "transfer-selection.json")
    resolve.add_argument("--output", type=Path, required=True)
    resolve.add_argument(
        "--pull", action="store_true", help="explicitly pull the twelve registered original images"
    )
    resolve.add_argument("--platform", default="linux/amd64")
    args = parser.parse_args()
    lock = resolve_image_lock(
        args.source, json.loads(args.selection.read_text()), pull=args.pull, platform=args.platform
    )
    _write_once(args.output, lock)
