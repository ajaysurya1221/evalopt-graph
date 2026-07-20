#!/usr/bin/env python3
"""Reproducible production-complexity report for the kernelization contract."""

from __future__ import annotations

import argparse
import ast
import subprocess
from dataclasses import asdict, dataclass

PACKAGE = "src/evalopt_graph"


@dataclass(frozen=True)
class Counts:
    modules: int = 0
    physical_lines: int = 0
    public_functions: int = 0
    public_classes: int = 0
    methods: int = 0
    decision_branches: int = 0


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _sources(revision: str) -> dict[str, str]:
    paths = [
        path
        for path in _git("ls-tree", "-r", "--name-only", revision, "--", PACKAGE).splitlines()
        if path.endswith(".py")
    ]
    return {path: _git("show", f"{revision}:{path}") for path in paths}


def count(revision: str) -> Counts:
    values = Counts()
    totals = asdict(values)
    sources = _sources(revision)
    totals["modules"] = len(sources)
    for source in sources.values():
        totals["physical_lines"] += sum(
            bool(line.strip()) and not line.lstrip().startswith("#") for line in source.splitlines()
        )
        tree = ast.parse(source)
        totals["public_functions"] += sum(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
            for node in tree.body
        )
        totals["public_classes"] += sum(
            isinstance(node, ast.ClassDef) and not node.name.startswith("_") for node in tree.body
        )
        totals["methods"] += sum(
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            for item in node.body
        )
        totals["decision_branches"] += sum(
            isinstance(node, (ast.If, ast.IfExp, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler))
            for node in ast.walk(tree)
        )
        totals["decision_branches"] += sum(
            len(node.cases) for node in ast.walk(tree) if isinstance(node, ast.Match)
        )
    return Counts(**totals)


def raw_delta(baseline: str, target: str) -> tuple[int, int, int]:
    added = deleted = 0
    for line in _git("diff", "--numstat", baseline, target, "--", PACKAGE).splitlines():
        add, remove, _path = line.split("\t", 2)
        if add != "-":
            added += int(add)
            deleted += int(remove)
    return added, deleted, added - deleted


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--target", default="HEAD")
    args = parser.parse_args()
    baseline = count(args.baseline)
    target = count(args.target)
    added, deleted, net = raw_delta(args.baseline, args.target)
    result = {
        "baseline": args.baseline,
        "target": args.target,
        "raw_diff": {"added": added, "deleted": deleted, "net": net},
        "baseline_counts": asdict(baseline),
        "target_counts": asdict(target),
        "count_delta": {key: getattr(target, key) - getattr(baseline, key) for key in asdict(baseline)},
    }
    import json

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
