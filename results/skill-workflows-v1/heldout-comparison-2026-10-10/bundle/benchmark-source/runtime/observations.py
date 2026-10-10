"""Read pinned native runtime telemetry without publishing conversation content."""

import inspect
import json
from pathlib import Path


def runtime_observations(sessions: Path, entrypoint: str | None) -> dict:
    contexts, versions, outputs = [], set(), []
    for path in sorted(sessions.rglob("*.jsonl")):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            payload = record.get("payload", {})
            if record.get("type") == "session_meta":
                versions.add(payload.get("cli_version"))
            elif record.get("type") == "turn_context":
                contexts.append((payload.get("model"), payload.get("effort")))
            elif record.get("type") == "response_item" and payload.get("type") in {
                "function_call_output",
                "custom_tool_call_output",
            }:
                outputs.append(str(payload.get("output", "")))
    return {
        "runtime_valid": (set(contexts) == {("gpt-6-astra", "ultra")} and versions == {"0.154.0"})
        if contexts
        else None,
        "returned_models": sorted({model for model, _ in contexts if isinstance(model, str)}),
        "returned_efforts": sorted({effort for _, effort in contexts if isinstance(effort, str)}),
        "cli_versions": sorted(v for v in versions if isinstance(v, str)),
        # This is a load observation, not authentication that instructions were obeyed.
        "entrypoint_load_observed": None
        if entrypoint is None
        else (f"name: {entrypoint}" in "\n".join(outputs).replace("\\n", "\n")),
    }


# Invoked only inside a disposable candidate container at AGENT_END. Preserve PID1
# and this controller command's ancestry, and stop lingering candidate processes
# before snapshot capture. No host process or other container is addressable here.
PROCESS_BASELINE = """import json, pathlib
result = {}
for path in pathlib.Path("/proc").glob("[0-9]*/stat"):
    try:
        result[path.parent.name] = path.read_text().rsplit(")", 1)[1].split()[19]
    except FileNotFoundError:
        pass
print(json.dumps(result))
"""


def quiesce_processes(read_processes, kill_process, baseline, keep, pause):
    for _ in range(32):
        live = [
            pid
            for pid, (started, state) in read_processes().items()
            if pid not in keep and state != "Z" and baseline.get(str(pid)) != started
        ]
        if not live:
            return
        for pid in live:
            try:
                kill_process(pid)
            except ProcessLookupError:
                pass
        pause()
    raise RuntimeError("candidate processes did not become quiescent")


STOP_CANDIDATE = (
    inspect.getsource(quiesce_processes)
    + """
import os, signal, time
keep = {1}
pid = os.getpid()
while pid > 1 and pid not in keep:
    keep.add(pid)
    with open(f"/proc/{pid}/status") as stream:
        pid = int(next(line.split()[1] for line in stream if line.startswith("PPid:")))
def read_processes():
    result = {}
    for name in os.listdir("/proc"):
        if name.isdigit():
            try:
                with open(f"/proc/{name}/stat") as stream:
                    fields = stream.read().rsplit(")", 1)[1].split()
                result[int(name)] = (fields[19], fields[0])
            except FileNotFoundError:
                pass
    return result
quiesce_processes(read_processes, lambda pid: os.kill(pid, signal.SIGKILL),
                  globals().get("BASELINE", {}), keep, lambda: time.sleep(0.01))
"""
)
