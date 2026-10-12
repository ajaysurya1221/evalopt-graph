"""Deterministic fresh-task authoring. Never reads prior tasks or live scores."""

import copy
import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = []


def code(s):
    return textwrap.dedent(s).lstrip()


def dump(p, value):
    p.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def snapshot(root, name, files, spec):
    p = root / name
    p.mkdir(parents=True, exist_ok=True)
    for filename, contents in {**files, "SPEC.md": spec}.items():
        (p / filename).write_text(contents)


def author(
    identity,
    category,
    spec,
    source,
    reference,
    inputs,
    *,
    bugs=None,
    mutants=None,
    review=None,
    frozen=(),
    evidence=False,
    smoke=None,
):
    root = ROOT / "difficulty" / identity
    root.mkdir(parents=True, exist_ok=True)
    meta = dict(
        id=identity,
        category=category,
        split="difficulty",
        source_cluster=identity,
        evidence_opportunity=evidence,
    )
    CATALOG.append(meta)
    common = "\nAll input domains and required behavior are stated above. Preserve all arguments. Use Python standard library only, no package installation or network. The supplied verify.py is a frozen smoke check, not the complete contract. The controller reporting contract specifies phase-bound observations; never substitute an observation from another phase or invent an execution.\n"
    allowed = [] if review else [name for name in source if name not in frozen]
    boundary = (
        "\nAllowed content edits: "
        + (", ".join(allowed) if allowed else "none (review only)")
        + ". Change only the contents of those existing regular files. Preserve their modes. All other initial files, directories, modes, and Git metadata are frozen; incidental stat-cache refresh is handled by the common controller contract. Do not create, remove or rename workspace files. Put temporary probes under /tmp.\n"
    )
    spec = spec.strip() + common + boundary
    ref = code(reference)
    ns = {}
    exec(compile(ref, "<authored-reference>", "exec"), ns)
    cases = []
    for i, value in enumerate(inputs, 1):
        request = dict(module="service", function="solve", args=[copy.deepcopy(value)])
        try:
            expected = dict(kind="return", value=ns["solve"](copy.deepcopy(value)))
        except ValueError:
            expected = dict(kind="raise", builtin="ValueError")
        cases.append(dict(case_id=f"case-{i:02d}", request=request, expect=expected, preserve_args=True))
    if smoke is None:
        smoke = (
            "from service import solve\nassert isinstance(solve("
            + repr(inputs[0])
            + "), (dict, list, str))\n"
        )
    files = {**source, "verify.py": code(smoke)}
    candidate = {**files, **(bugs or {})}
    allowed = [name for name in source if name not in frozen]
    task = {
        **meta,
        "schema_version": "evalopt-workflows-v4/1",
        "task_id": identity,
        "attempt_id": "authored-control--" + identity,
        "task_contract": "review" if review else "implementation",
        "visible_command": ["python3", "-B", "verify.py"],
        "allowed_changes": [] if review else allowed,
        "cases": cases,
        "instruction": spec,
    }
    response = dict(status="completed", findings=[], blockers=[], checks=[])
    if review:
        domain = [case["request"] for case in cases]
        spec += (
            "\nReview all supplied workspace layers against benchmark-base. Do not modify any file or Git metadata. The finite witness domain is exactly these requests (without expected answers):\n"
            + json.dumps(domain, sort_keys=True)
            + "\nEach finding is {path:workspace-relative POSIX filename,symbol:unqualified function name,kind:incorrect-result|unexpected-exception|data-loss,witness:{module,function,args}}. The witness must equal a request in this finite domain and is data, never verifier code. Report demonstrated introduced contract violations: baseline satisfies the expectation and candidate violates it. Duplicate supported findings are neutral; unsupported findings and missed defects fail. Only the exact location/request bindings below count toward the named obligations. A different demonstrated in-domain counterexample may become a contract dispute rather than silently satisfying an obligation. Do not report stylistic preferences.\n"
        )
        bindings = [
            {
                "obligation": o["id"],
                "locations": o["supported_locations"],
                "requests": [c["request"] for c in cases if c["case_id"] in o["witness_case_ids"]],
            }
            for o in review["obligations"]
        ]
        spec += (
            "\nAccepted obligation/location/witness bindings (no expected answers):\n"
            + json.dumps(bindings, sort_keys=True)
            + "\n"
        )
        task["instruction"] = spec
        task.update(preserve_review_args=True, max_findings=12, defect_obligations=review["obligations"])
        response["findings"] = review["findings"]
        snapshot(root, "baseline", files, spec)
        snapshot(root, "clean", files, spec)
        if "layers" in review:
            task["workspace_layers"] = dict(
                baseline="baseline", committed="committed", index="index", workspace="agent"
            )
            snapshot(root, "committed", {**files, **review["layers"][0]}, spec)
            snapshot(root, "index", {**files, **review["layers"][1]}, spec)
        snapshot(root, "agent", candidate, spec)
        dump(root / "oracle_cases.json", [{"request": c["request"], "expect": c["expect"]} for c in cases])
    else:
        snapshot(root, "oracle", files, spec)
        snapshot(root, "agent", candidate, spec)
    review_mutants = {}
    if review:
        for identity, changes in review["isolated_mutations"].items():
            name = "defect-controls/" + identity
            snapshot(root, name, {**files, **changes}, spec)
            review_mutants[identity] = name
    names = [] if review else ["agent"]
    for index, changes in enumerate(mutants or [], 1):
        name = f"mutant-{index}"
        snapshot(root, name, {**files, **changes}, spec)
        names.append(name)
    (root / "reference.py").write_text(ref)
    dump(root / "task.json", task)
    dump(
        root / "controls.json",
        dict(
            positive_snapshot="agent" if review else "oracle",
            review_mutants=review_mutants,
            positive_response=response,
            negative_snapshots=names,
            initial_check_exit=0,
            positive_check_exit=1 if evidence else 0,
        ),
    )


for definition in sorted((ROOT / "definitions").glob("*.py")):
    exec(compile(definition.read_text(), definition.name, "exec"), {"code": code, "author": author})
dump(ROOT / "catalog.json", sorted(CATALOG, key=lambda item: item["id"]))
subprocess.run(
    [sys.executable, "-m", "ruff", "check", "--select", "I", "--fix", str(ROOT / "difficulty")],
    check=True,
    capture_output=True,
)
subprocess.run(
    [sys.executable, "-m", "ruff", "format", str(ROOT / "difficulty")], check=True, capture_output=True
)
dump(
    ROOT / "manifest.json",
    {
        "schema_version": "evalopt.v4-authored-task-manifest.v1",
        "task_ids": sorted(row["id"] for row in CATALOG),
        "registered_cases": sum(
            len(json.loads((ROOT / "difficulty" / row["id"] / "task.json").read_text())["cases"])
            for row in CATALOG
        ),
        "files": {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(ROOT.rglob("*"))
            if p.is_file() and p.name != "manifest.json" and "__pycache__" not in p.parts
        },
        "test_source_sha256": hashlib.sha256(
            (ROOT.parent / "tests/test_fresh_tasks.py").read_bytes()
        ).hexdigest(),
    },
)
print(json.dumps({"tasks": len(CATALOG), "stage": "difficulty", "model_calls": 0}))
