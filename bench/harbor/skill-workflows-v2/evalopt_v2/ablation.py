"""Derive the single-procedure D ablation without changing its invocation or tools.

Only skill bytes are read/written. This module does not install a skill, load a
candidate, run an agent, or import the frozen v1 benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import re
import stat
from pathlib import Path, PurePosixPath

NAME = "eval-opt-v2"
VERSION = "2.0.0"
MECHANISM = "typed-evidence-dispute"
START = b"<!-- evalopt-v2:typed-evidence-dispute:start -->\n"
END = b"<!-- evalopt-v2:typed-evidence-dispute:end -->\n"
PROCEDURE = "references/evidence-dispute.md"
ROUTE = (
    START
    + (
        b"- When a check, its evidence availability, or a proposed completion claim conflicts\n"
        b"  with the task contract, use the\n"
        b"  [typed evidence and dispute procedure](references/evidence-dispute.md).\n"
    )
    + END
)
COMMON = frozenset(
    {
        "SKILL.md",
        "agents/openai.yaml",
        "ATTRIBUTION.md",
        "LICENSE",
        "references/debugging.md",
        "references/review.md",
        "references/evidence-record.md",
    }
)
FULL = COMMON | {PROCEDURE}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def bundle_files(root: Path) -> dict[str, bytes]:
    """Read a regular-file-only skill tree, rejecting links and undeclared files."""
    root = Path(root)
    _require(stat.S_ISDIR(root.lstat().st_mode), "skill root must be a directory, not a link")
    files = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        _require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "unsupported skill node or symlink")
        if stat.S_ISDIR(mode):
            _require(
                path.relative_to(root).as_posix() in {"agents", "references"}, "unexpected skill directory"
            )
        if stat.S_ISREG(mode):
            files[path.relative_to(root).as_posix()] = path.read_bytes()
    return files


def _route(skill: bytes) -> tuple[int, int]:
    _require(skill.count(START) == skill.count(END) == 1, "one named procedure route required")
    start, end = skill.index(START), skill.index(END) + len(END)
    _require(start < end - len(END), "procedure route markers reversed")
    block = skill[start:end]
    _require(block == ROUTE, "route must be exactly the registered conditional instruction")
    outside = skill[:start] + skill[end:]
    _require(PROCEDURE.encode() not in outside, "procedure routed outside removable block")
    return start, end


def _validate(files: dict[str, bytes], *, full: bool):
    _require(
        isinstance(files, dict) and set(files) == (FULL if full else COMMON), "skill file roster differs"
    )
    for name, data in files.items():
        _require(isinstance(data, bytes) and data, "skill files must be nonempty bytes")
        _require(PurePosixPath(name).as_posix() == name, "noncanonical skill path")
        text = data.decode("utf-8")
        personal = ("/" + "Users/", "/" + "home/", "~" + "/", "C:" + "\\Users\\")
        _require(not any(prefix in text for prefix in personal), "personal path in skill bundle")
    skill = files["SKILL.md"].decode("utf-8")
    _require(skill.startswith("---\n") and "\n---\n" in skill[4:], "missing skill frontmatter")
    frontmatter = skill.split("---\n", 2)[1]
    _require(re.findall(r"^name: (.+)$", frontmatter, re.M) == [NAME], "invocation identity changed")
    _require(re.findall(r'^  version: "(.+)"$', frontmatter, re.M) == [VERSION], "skill version changed")
    _require(len(re.findall(r"^description: .+$", frontmatter, re.M)) == 1, "missing skill description")
    metadata = files["agents/openai.yaml"].decode("utf-8")
    _require(f"${NAME}" in metadata, "UI invocation differs from skill")
    if full:
        _route(files["SKILL.md"])
    else:
        _require(
            START not in files["SKILL.md"] and END not in files["SKILL.md"], "ablation retains route markers"
        )

    # Verify all local links without importing a Markdown/YAML dependency. These
    # controlled documents use ordinary inline links only, not executable helpers.
    links = {}
    for name, data in files.items():
        if not name.endswith(".md"):
            continue
        links[name] = []
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", data.decode("utf-8")):
            if target.startswith("https://"):
                continue
            target = target.split("#", 1)[0]
            _require(target and not target.startswith("/") and ":" not in target, "unsupported skill link")
            relative = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
            _require(relative in files, "missing local skill reference: " + relative)
            links[name].append(relative)
    reachable, queue = set(), ["SKILL.md"]
    while queue:
        name = queue.pop()
        if name not in reachable:
            reachable.add(name)
            queue.extend(links.get(name, []))
    _require(
        all(name in reachable for name in files if name.startswith("references/")), "unrouted skill reference"
    )


def derive_files(full: dict[str, bytes]) -> dict[str, bytes]:
    """Produce D from C, deleting only the named route and procedure-only file."""
    _validate(full, full=True)
    start, end = _route(full["SKILL.md"])
    ablated = {name: data for name, data in full.items() if name != PROCEDURE}
    ablated["SKILL.md"] = full["SKILL.md"][:start] + full["SKILL.md"][end:]
    _validate(ablated, full=False)
    return ablated


def _identity(files):
    nodes = {name: {"sha256": _sha(data), "size": len(data)} for name, data in sorted(files.items())}
    return {"files": nodes, "sha256": _sha(_canonical(nodes))}


def validate_files(full: dict[str, bytes], ablated: dict[str, bytes]) -> dict:
    """Reject any additional treatment difference, including an added instruction."""
    expected = derive_files(full)
    _validate(ablated, full=False)
    _require(ablated == expected, "ablation exceeds the single permitted procedure deletion")
    start, end = _route(full["SKILL.md"])
    return {
        "schema_version": "evalopt.skill-ablation.v1",
        "skill_name": NAME,
        "skill_version": VERSION,
        "mechanism": MECHANISM,
        "C": _identity(full),
        "D": _identity(ablated),
        "changed_files": ["SKILL.md"],
        "removed_files": [PROCEDURE],
        "removed_route_sha256": _sha(full["SKILL.md"][start:end]),
        "identical_files": sorted(COMMON - {"SKILL.md"}),
        "common_observation_schema_changed": False,
        "invocation_changed": False,
    }


def validate_pair(full: Path, ablated: Path) -> dict:
    return validate_files(bundle_files(full), bundle_files(ablated))


def derive_ablation(source: Path, destination: Path) -> dict:
    """Write only skill files to a fresh destination; never replace a prior bundle.

    If a write fails, the partial destination remains explicit and cannot be
    reused by this function. The caller owns any deliberate recovery decision.
    The returned manifest belongs outside either skill's injected context.
    """
    source, destination = Path(source), Path(destination)
    source_files = bundle_files(source)
    derived = derive_files(source_files)
    _require(not destination.exists() and not destination.is_symlink(), "ablation destination exists")
    _require(
        not destination.resolve().is_relative_to(source.resolve()), "destination cannot be inside source"
    )
    # Resolve the caller-owned parent (including platform temporary-root aliases)
    # while preserving exclusive creation of the new destination itself.
    destination = destination.parent.resolve(strict=True) / destination.name
    destination.mkdir()
    for name, data in sorted(derived.items()):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as handle:
            handle.write(data)
    _require(bundle_files(source) == source_files, "source changed during ablation")
    return validate_pair(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--verify", action="store_true", help="validate an existing pair without writing")
    args = parser.parse_args()
    result = (
        validate_pair(args.source, args.destination)
        if args.verify
        else derive_ablation(args.source, args.destination)
    )
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
