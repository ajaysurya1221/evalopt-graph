#!/usr/bin/env python3
"""Verify published offline receipts and bytes; never execute candidate code.

This establishes retained-record correspondence, not independent rerunning of
Docker controls, models, private transcripts, or authorship authentication.
"""

from __future__ import annotations

import sys

if __name__ == "__main__" and (not sys.flags.isolated or not sys.flags.dont_write_bytecode):
    raise SystemExit("Run with python -I -B to exclude adjacent modules and bytecode writes.")

import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

SCHEMA = "evalopt-workflows-v4/offline-package/1"
BASE = "d8e6903df1aa12d35e1f7356200609617060baed"
SOURCE_ROOTS = (
    "bench/harbor/skill-workflows-v4",
    "skills/eval-opt-v4",
    "src/evalopt_graph",
)
EXTRA_SOURCE = ".github/workflows/workflow-v4.yml"
FILES = {
    "README.md",
    "controls.json",
    "reviews.json",
    "compatibility.json",
    "task-controls.json",
    "preservation.json",
    "sources.json",
    "reproduce.py",
}
HEX = re.compile(r"[0-9a-f]{64}")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def reject_constant(_value):
    raise ValueError("non-finite JSON")


def read(path, maximum=16 * 1024**2):
    if path.resolve() != path.absolute() or not path.is_file() or path.stat().st_size > maximum:
        raise ValueError("missing, aliased or oversized file")
    return path.read_bytes()


def load(path):
    try:
        return json.loads(read(path), object_pairs_hook=pairs, parse_constant=reject_constant)
    except (RecursionError, UnicodeError) as error:
        raise ValueError("invalid JSON encoding or nesting") from error


def relative(name):
    if type(name) is not str or not name or "\\" in name:
        raise ValueError("invalid relative path")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name or any(part in (".", "..") for part in path.parts):
        raise ValueError("unsafe relative path")
    return name


def digest_string(value):
    if type(value) is not str or HEX.fullmatch(value) is None:
        raise ValueError("invalid SHA-256")
    return value


def source_inventory(repo):
    result = {}
    paths = [repo / EXTRA_SOURCE]
    for root_name in SOURCE_ROOTS:
        root = repo / root_name
        if root.resolve() != root.absolute() or not root.is_dir():
            raise ValueError("source root missing or aliased")
        for path in root.rglob("*"):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.is_symlink():
                raise ValueError("source symlink")
            if path.is_file():
                paths.append(path)
    for path in sorted(paths):
        name = str(path.relative_to(repo))
        result[name] = {"sha256": sha(read(path)), "executable": bool(path.stat().st_mode & stat.S_IXUSR)}
    return result


def verify_preservation(repo, record):
    if record["base_commit"] != BASE or record["status"] != "PASS" or record["violations"] != []:
        raise ValueError("preservation did not pass")
    entries = record["inventory"]
    if type(entries) is not list or len(entries) != record["baseline_files"] or len(entries) != 9513:
        raise ValueError("preservation roster changed")
    if sha(canonical(entries)) != record["baseline_inventory_sha256"]:
        raise ValueError("preservation inventory identity changed")
    names = set()
    for entry in entries:
        if type(entry) is not dict or set(entry) != {"path", "mode", "git_blob"}:
            raise ValueError("invalid preservation entry")
        name = relative(entry["path"])
        if name in names or re.fullmatch(r"[0-9a-f]{40}", entry["git_blob"]) is None:
            raise ValueError("duplicate or invalid preservation identity")
        names.add(name)
        path = repo / name
        if path.parent.resolve() != path.parent:
            raise ValueError("preserved parent alias")
        if entry["mode"] == "120000":
            if not path.is_symlink():
                raise ValueError("preserved symlink changed")
            raw, mode = os.readlink(path).encode(), "120000"
        else:
            raw = read(path, maximum=64 * 1024**2)
            mode = "100755" if path.stat().st_mode & stat.S_IXUSR else "100644"
        actual = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        if mode != entry["mode"] or actual != entry["git_blob"]:
            raise ValueError("preserved bytes or Git mode changed: " + name)


def shape(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise ValueError("unexpected public record fields")


def nonnegative(value):
    if type(value) is not int or value < 0:
        raise ValueError("nonnegative integer required")


def verify_run(run, *, admitted):
    shape(
        run,
        {
            "id",
            "status",
            "scope",
            "name_projection",
            "models_invoked",
            "cases",
            "counts",
            "junit_total",
            "reported_subtests",
            "private_artifact_sha256",
        },
    )
    if any(type(run[key]) is not str or not run[key] for key in ("id", "scope", "name_projection")):
        raise ValueError("invalid control description")
    shape(run["counts"], {"records", "failures", "errors", "skips"})
    artifacts = run["private_artifact_sha256"]
    if type(artifacts) is not dict or set(artifacts) not in ({"xml"}, {"xml", "log"}):
        raise ValueError("missing or unknown control artifact")
    if (
        type(run["models_invoked"]) is not int
        or run["models_invoked"] != 0
        or run["status"] != ("PASS" if admitted else "HISTORICAL_NOT_ADMISSION")
    ):
        raise ValueError("invalid offline evidence scope")
    cases = run["cases"]
    if type(cases) is not list or not cases:
        raise ValueError("missing retained case roster")
    identities = set()
    for case in cases:
        if set(case) != {"class", "name", "outcome"} or any(type(case[k]) is not str for k in case):
            raise ValueError("invalid case projection")
        identity = (case["class"], case["name"])
        if identity in identities or case["outcome"] not in {"passed", "failed", "error", "skipped"}:
            raise ValueError("duplicate case or unknown outcome")
        identities.add(identity)
    counts = {
        "records": len(cases),
        **{
            key: sum(c["outcome"] == value for c in cases)
            for key, value in (("failures", "failed"), ("errors", "error"), ("skips", "skipped"))
        },
    }
    if (
        any(type(value) is not int or value < 0 for value in run["counts"].values())
        or type(run["reported_subtests"]) is not int
        or run["reported_subtests"] < 0
        or type(run["junit_total"]) is not int
        or run["junit_total"] != len(cases) + run["reported_subtests"]
        or counts != run["counts"]
        or (admitted and any(counts[key] for key in ("failures", "errors", "skips")))
    ):
        raise ValueError("control counts or results disagree")
    for value in run["private_artifact_sha256"].values():
        digest_string(value)
    return counts


def verify_controls(record):
    shape(
        record,
        {
            "schema_version",
            "live_model_trials",
            "source_inventory_sha256",
            "scope",
            "runs",
            "historical_runs",
            "complete_process_sha256",
        },
    )
    for key in ("source_inventory_sha256", "complete_process_sha256"):
        digest_string(record[key])
    if any(type(record[key]) is not list for key in ("runs", "historical_runs")):
        raise ValueError("control groups must be lists")
    if (
        record["schema_version"] != SCHEMA
        or type(record["live_model_trials"]) is not int
        or record["live_model_trials"] != 0
    ):
        raise ValueError("offline scope changed")
    seen = set()
    for admitted, runs in ((True, record["runs"]), (False, record["historical_runs"])):
        for run in runs:
            if run["id"] in seen:
                raise ValueError("duplicate offline run identity")
            seen.add(run["id"])
            verify_run(run, admitted=admitted)
    if not any(run["id"] == "complete-suite" for run in record["runs"]):
        raise ValueError("complete suite receipt missing")
    return next(run["counts"] for run in record["runs"] if run["id"] == "complete-suite")


def verify_compatibility(record):
    shape(
        record,
        {
            "schema_version",
            "candidate_execution_performed",
            "scope",
            "public_replays",
            "legacy_kernel_checks",
        },
    )
    if record["schema_version"] != SCHEMA or record["candidate_execution_performed"] is not False:
        raise ValueError("compatibility scope changed")
    counts = verify_run(record["legacy_kernel_checks"], admitted=False)
    if counts["failures"] or counts["errors"]:
        raise ValueError("legacy compatibility has failures")
    replays = record["public_replays"]
    if set(replays) != {
        "v1-heldout",
        "v1-transfer",
        "v1-semantic-audit",
        "v2-development-revision",
        "v3-difficulty",
    }:
        raise ValueError("compatibility replay roster changed")
    for identity, item in replays.items():
        if set(item) != {"retained_output_sha256", "result"}:
            raise ValueError("invalid replay receipt")
        digest_string(item["retained_output_sha256"])
        result = item["result"]
        if identity == "v1-heldout":
            valid = (
                result.get("schema_version") == "evalopt.heldout-release-replay.v1"
                and result.get("candidate_execution_performed") is False
                and result.get("heldout", {}).get("policy_analysis_reproduced") is True
            )
        elif identity == "v1-transfer":
            valid = (
                result.get("schema_version") == "evalopt.transfer-release-replay.v1"
                and result.get("candidate_execution_performed") is False
                and result.get("transfer", {}).get("reward_analysis_reproduced") is True
            )
        elif identity == "v1-semantic-audit":
            valid = (
                result.get("schema_version") == "evalopt.semantic-audit-reproduction.v1"
                and result.get("reproduction_executes_candidates") is False
                and set(result.get("outputs", {})) == {"report.json", "row-ledger.json"}
            )
        else:
            valid = result.get("status") == "PASS"
        if not valid:
            raise ValueError("public compatibility replay failed: " + identity)


def verify_task_controls(record, sources, repo):
    shape(
        record,
        {
            "status",
            "models_invoked",
            "failures",
            "errors",
            "skips",
            "task_manifest_sha256",
            "controls_passed",
            "registered_cases",
            "tasks",
            "retained_receipt_sha256",
            "retained_acceptance_sha256",
            "scope",
            "retained_artifact_sha256",
            "prior_offline_failure",
        },
    )
    for key in ("models_invoked", "failures", "errors", "skips", "controls_passed", "registered_cases"):
        nonnegative(record[key])
    for key in ("task_manifest_sha256", "retained_receipt_sha256", "retained_acceptance_sha256"):
        digest_string(record[key])
    shape(record["retained_artifact_sha256"], {"summary.json", "sources-before.json", "sources-after.json"})
    for value in record["retained_artifact_sha256"].values():
        digest_string(value)
    prior = record["prior_offline_failure"]
    shape(
        prior,
        {
            "candidate_executions",
            "classification",
            "disposition",
            "exact_absence_receipt_sha256",
            "log_sha256",
            "ownership_sha256",
        },
    )
    nonnegative(prior["candidate_executions"])
    if prior["candidate_executions"] != 0:
        raise ValueError("prior setup unexpectedly executed candidate")
    for key in ("exact_absence_receipt_sha256", "log_sha256", "ownership_sha256"):
        digest_string(prior[key])
    if type(record["tasks"]) is not list:
        raise ValueError("task roster must be a list")
    for task in record["tasks"]:
        shape(
            task,
            {"task_id", "passed", "checks", "case_count", "source_sha256", "isolation", "models_invoked"},
        )
        for key in ("passed", "case_count", "models_invoked"):
            nonnegative(task[key])
        digest_string(task["source_sha256"])
        if (
            type(task["checks"]) is not list
            or not task["checks"]
            or any(type(c) is not str or not c for c in task["checks"])
            or len(set(task["checks"])) != len(task["checks"])
        ):
            raise ValueError("invalid task control roster")
    if (
        record["status"] != "PASS"
        or record["models_invoked"] != 0
        or any(record[k] for k in ("failures", "errors", "skips"))
    ):
        raise ValueError("authored controls did not pass")
    if len(record["tasks"]) != 8 or len({t["task_id"] for t in record["tasks"]}) != 8:
        raise ValueError("authored task roster changed")
    if sum(t["passed"] for t in record["tasks"]) != record["controls_passed"]:
        raise ValueError("authored control total changed")
    manifest = "bench/harbor/skill-workflows-v4/tasks/manifest.json"
    if sources[manifest]["sha256"] != record["task_manifest_sha256"]:
        raise ValueError("authored task manifest changed")
    if sum(t["case_count"] for t in record["tasks"]) != record["registered_cases"]:
        raise ValueError("registered case total changed")
    for task in record["tasks"]:
        task_root = repo / "bench/harbor/skill-workflows-v4/tasks/difficulty" / relative(task["task_id"])
        contract = load(task_root / "task.json")
        if len(contract["cases"]) != task["case_count"] or contract["task_id"] != task["task_id"]:
            raise ValueError("registered task cases changed")
        snapshot = {}
        for path in sorted(task_root.rglob("*")):
            info = path.lstat()
            name = path.relative_to(task_root).as_posix()
            if stat.S_ISDIR(info.st_mode):
                snapshot[name] = {"kind": "directory", "mode": stat.S_IMODE(info.st_mode)}
            elif stat.S_ISREG(info.st_mode):
                raw = read(path)
                snapshot[name] = {
                    "kind": "file",
                    "mode": stat.S_IMODE(info.st_mode),
                    "size": len(raw),
                    "sha256": sha(raw),
                }
            else:
                raise ValueError("nonregular authored source")
        if sha(canonical(snapshot)) != task["source_sha256"]:
            raise ValueError("authored task source identity differs from executed controls")
        if (
            task["isolation"] != "docker"
            or task["models_invoked"] != 0
            or task["passed"] != len(task["checks"])
        ):
            raise ValueError("authored task checks changed")


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    if {p.name for p in here.iterdir()} != FILES | {"checksums.json"}:
        raise ValueError("unexpected public packet files")
    sums = load(here / "checksums.json")
    if set(sums) != FILES:
        raise ValueError("public checksum roster changed")
    for name, expected in sums.items():
        if sha(read(here / name)) != digest_string(expected):
            raise ValueError("public artifact checksum changed")
    sources = load(here / "sources.json")
    shape(sources, {"schema_version", "files"})
    if sources["schema_version"] != SCHEMA or canonical(sources["files"]) != canonical(
        source_inventory(repo)
    ):
        raise ValueError("reviewed source inventory changed")
    preservation = load(here / "preservation.json")
    verify_preservation(repo, preservation)
    controls = load(here / "controls.json")
    counts = verify_controls(controls)
    if controls["source_inventory_sha256"] != sha(read(here / "sources.json")):
        raise ValueError("control source inventory changed")
    task_controls = load(here / "task-controls.json")
    verify_task_controls(task_controls, sources["files"], repo)
    reviews = load(here / "reviews.json")
    if reviews["schema_version"] != SCHEMA or not reviews["reviews"]:
        raise ValueError("review roster missing")
    expected_review_ids = {
        "semantic-reporting",
        "runtime-freeze",
        "integration-analysis",
        "task-six-families",
        "task-two-families",
    }
    if (
        len(reviews["reviews"]) != len(expected_review_ids)
        or {r["id"] for r in reviews["reviews"]} != expected_review_ids
    ):
        raise ValueError("review identity roster differs")
    for review in reviews["reviews"]:
        if review["verdict"] != "ACCEPT" or not review["source_sha256"]:
            raise ValueError("review did not accept")
        for name, expected in review["source_sha256"].items():
            if (
                name not in sources["files"]
                and name != "results/skill-workflows-v4/difficulty-registration-2026-10-12/reproduce.py"
            ):
                raise ValueError("undeclared review source")
            if sha(read(repo / relative(name))) != digest_string(expected):
                raise ValueError("review source differs from tested source")
    compatibility = load(here / "compatibility.json")
    verify_compatibility(compatibility)
    print(
        json.dumps(
            {
                "status": "PASS",
                "scope": "published offline receipt and source correspondence",
                "complete_suite_junit_records": counts["records"],
                "authored_docker_checks": task_controls["controls_passed"],
                "preserved_baseline_files": preservation["baseline_files"],
                "candidate_execution_performed": False,
                "live_model_trials": 0,
                "independent_live_replication": False,
            },
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
