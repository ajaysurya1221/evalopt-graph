"""Reconstruct a trusted original baseline in a fresh isolated Python process.

No stopped candidate file is imported or executed. The original materializer may
resolve/tag the already pinned local images; it never starts a coding agent.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def tree_identity(root):
    files = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("trusted source must not contain symlinks")
        if path.is_file() and "__pycache__" not in path.parts:
            files[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def main():
    request = json.loads(sys.stdin.read())
    if sys.implementation.name != "cpython" or sys.version_info[:3] != (3, 13, 12):
        raise ValueError("regrade baseline bridge requires CPython3.13.12")
    source = Path(request["frozen_source"]).absolute()
    if any(path.is_symlink() for path in (source, *source.parents)):
        raise ValueError("trusted frozen source must not traverse symlinks")
    if tree_identity(source) != request["frozen_source_sha256"]:
        raise ValueError("original materializer source changed")
    sys.path[:0] = [str(source), str(source.parents[2] / "src")]
    from runtime.harbor_campaign import materialize
    from tasks.suite import load_task

    for name in ("runtime.harbor_campaign", "tasks.suite"):
        if not Path(sys.modules[name].__file__).resolve().is_relative_to(source):
            raise ValueError("baseline bridge imported an unfrozen implementation")
    result = materialize(
        load_task(request["task_id"]),
        Path(request["destination"]),
        agent_image=request["agent_image"],
        verifier_image=request["verifier_image"],
        arm=request["arm"],
    )
    Path(request["result"]).write_text(json.dumps({"initial_manifest": result}, sort_keys=True))


if __name__ == "__main__":
    main()
