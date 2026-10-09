"""Lossless node metadata for stopped snapshots; never follow candidate links."""

from __future__ import annotations

import base64
import json
import os
import stat
from pathlib import Path


def encode_snapshot(root: Path) -> bytes:
    nodes = {}
    for current, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(current) / name
            info = path.lstat()
            node = {"mode": stat.S_IMODE(info.st_mode)}
            if stat.S_ISREG(info.st_mode):
                node.update(type="file", data=base64.b64encode(path.read_bytes()).decode())
            elif stat.S_ISDIR(info.st_mode):
                node.update(type="directory")
            elif stat.S_ISLNK(info.st_mode):
                node.update(type="symlink", target=os.readlink(path))
            else:
                node.update(type="special", device=info.st_rdev, file_type=stat.S_IFMT(info.st_mode))
            nodes[path.relative_to(root).as_posix()] = node
    return json.dumps({"schema_version": "evalopt.stopped-nodes.v1", "nodes": nodes}, sort_keys=True).encode()


def regular_snapshot(root: Path) -> bool:
    return all(stat.S_ISREG(p.lstat().st_mode) or stat.S_ISDIR(p.lstat().st_mode) for p in root.rglob("*"))


def terminal_status(exception_type: str | None, *, agent_started: bool, captured: bool, grade_exists: bool):
    # Harbor's pinned Codex adapter derives these from provider/runtime events,
    # excluding tool output and assistant prose from its error classifier.
    if exception_type in {"ApiUsageLimitError", "ApiRateLimitError"}:
        return "infra_failure", "subscription_exhausted"
    if exception_type == "AgentTimeoutError":
        return "timeout", None
    if exception_type == "NonZeroAgentExitCodeError":
        return "agent_failure", None
    if not agent_started:
        return "infra_failure", "container_start"
    # Unknown failures after dispatch are retained as agent failures until investigated,
    # never automatically retried as infrastructure.
    if exception_type and not captured:
        return "agent_failure", None
    if not captured:
        return "agent_failure", None
    if not grade_exists:
        return "infra_failure", "verifier_infrastructure"
    return ("agent_failure", None) if exception_type else ("completed", None)
