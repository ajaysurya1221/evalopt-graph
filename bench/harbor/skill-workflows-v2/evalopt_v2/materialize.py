"""Fresh task workspaces and real mixed Git layers, with no grader exposure."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from .case_runner import snapshot_manifest
from .framing import strict_json
from .git_index import workspace_manifest
from .records import digest
from .snapshot import response_transport_contract

COMMON = {
    "docs/agents/issue-tracker.md": "The supplied SPEC.md is the local issue. No external tracker is used.\n",
    "docs/agents/domain.md": "The supplied task contract defines the domain.\n",
    "GLOSSARY.md": "Use the vocabulary in SPEC.md.\n",
}


def _git(root, *argv):
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_ATTR_NOSYSTEM="1",
        GIT_AUTHOR_DATE="2000-01-01T00:00:00+00:00",
        GIT_COMMITTER_DATE="2000-01-01T00:00:00+00:00",
        GIT_OPTIONAL_LOCKS="0",
    )
    return subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "core.excludesFile=" + os.devnull,
            "-c",
            "core.attributesFile=" + os.devnull,
            "-c",
            "init.templateDir=",
            *argv,
        ],
        cwd=root,
        env=env,
        check=True,
        capture_output=True,
        timeout=20,
        umask=0o022,
    )


def _replace_owned_layer(source, target):
    snapshot_manifest(source)  # Refuse symlinks/special nodes before copying anything.
    if (source / ".git").exists():
        raise ValueError("authored layers must not supply Git metadata")
    # target is a fresh directory created by materialize; never a user checkout.
    for child in target.iterdir():
        if child.name != ".git":
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    shutil.copytree(source, target, dirs_exist_ok=True)
    for name, text in COMMON.items():
        output = target / name
        # Pin only newly created controller nodes, without changing authored
        # file/directory modes. Never alter the calling process's umask.
        missing = []
        parent = output.parent
        while not parent.exists():
            missing.append(parent)
            parent = parent.parent
        for parent in reversed(missing):
            parent.mkdir()
            parent.chmod(0o755)
        output.write_text(text)
        output.chmod(0o644)


def materialize(task_directory, destination, *, arm):
    if arm not in {"A", "B", "C", "D"}:
        raise ValueError("unknown workflow arm")
    source, target = Path(task_directory).resolve(), Path(destination).absolute()
    if target.exists() or target.is_symlink() or target.resolve() != target:
        raise ValueError("materialization requires a new real destination")
    task = strict_json((source / "task.json").read_bytes())
    if task["id"] != source.name or task["task_id"] != source.name:
        raise ValueError("task identity differs from directory")
    layers = task.get("workspace_layers")
    if layers is not None and layers != {
        "baseline": "baseline",
        "committed": "committed",
        "index": "index",
        "workspace": "agent",
    }:
        raise ValueError("unregistered workspace layers")
    target.mkdir(parents=True)
    initial_layer = source / ("baseline" if task["task_contract"] == "review" else "agent")
    _replace_owned_layer(initial_layer, target)
    _git(target, "init", "-q", "--initial-branch=benchmark")
    _git(target, "config", "user.name", "Benchmark Fixture")
    _git(target, "config", "user.email", "fixture@example.invalid")
    _git(target, "config", "core.filemode", "true")
    _git(target, "config", "index.version", "2")
    _git(target, "config", "core.hooksPath", "/dev/null")
    _git(target, "add", "-A")
    _git(target, "commit", "-qm", "Authored baseline")
    _git(target, "tag", "benchmark-base")
    if task["task_contract"] == "review":
        _replace_owned_layer(source / ("committed" if layers else "agent"), target)
        _git(target, "add", "-A")
        _git(target, "commit", "--allow-empty", "-qm", "Authored candidate")
        if layers:
            _replace_owned_layer(source / "index", target)
            _git(target, "add", "-A")
            _replace_owned_layer(source / "agent", target)
    entry = (
        "code-review"
        if task["task_contract"] == "review"
        else "implement"
        if task["category"] == "bounded-implementation"
        else "diagnosing-bugs"
    )
    invocation = (
        ""
        if arm == "A"
        else f"Use ${entry}. Read /root/.agents/skills/{entry}/SKILL.md before starting.\n"
        if arm == "B"
        else "Use $eval-opt-v2. Read /root/.agents/skills/eval-opt-v2/SKILL.md before starting.\n"
    )
    context = (
        "Work in /workspace. SPEC.md is the task specification and benchmark-base is the review base. "
        "The local issue tracker is configured in docs/agents/issue-tracker.md. Test seams in the specification are pre-agreed. "
        "If a workflow requires a Skill tool unavailable here, read that skill's SKILL.md and relevant references from /root/.agents/skills. "
        "You may use at most two concurrent native children, depth one, with the same model and effort. Do not invoke external agent CLIs. "
        "Return the response object as bare JSON in your final assistant message; do not create a response file. "
        + response_transport_contract(task.get("max_findings", 16))
        + "Incidental Git filesystem stat-cache refresh is ignored; staged objects, modes, flags and other Git metadata are protected. "
        "Temporary probes may use /tmp. Do not change model, effort, permissions, checks, or frozen task boundaries.\n\n"
    )
    manifest = workspace_manifest(target)
    return {
        "task": task,
        "arm": arm,
        "instruction": invocation + context + task["instruction"],
        "initial_manifest": manifest,
        "initial_sha256": digest(manifest),
        "git_status": _git(target, "status", "--porcelain=v1", "--untracked-files=all").stdout.decode(),
        "common_files": sorted(COMMON),
    }


def boundary_violations(initial, stopped, allowed_changes):
    allowed = set(allowed_changes)
    if any(
        not isinstance(name, str) or name.startswith(("/", ".git/")) or ".." in Path(name).parts
        for name in allowed
    ):
        raise ValueError("invalid owned path contract")
    violations = []
    for name in initial.keys() | stopped.keys():
        before, after = initial.get(name), stopped.get(name)
        if before == after:
            continue
        editable_content_only = (
            name in allowed
            and isinstance(before, dict)
            and isinstance(after, dict)
            and before.get("kind") == after.get("kind") == "file"
            and before.get("mode") == after.get("mode")
        )
        if not editable_content_only:
            violations.append(name)
    return sorted(violations)
