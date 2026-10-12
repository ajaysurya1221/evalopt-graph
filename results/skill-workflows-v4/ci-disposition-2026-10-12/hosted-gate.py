"""Read-only, exact-head hosted-job gate; scan adjudication remains separate."""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path

REPO = "ajaysurya1221/evalopt-graph"
BRANCH = "feat/response-contract-difficulty-v4"
PR = 36
WORKFLOW_ID = 382086011
WORKFLOW = ".github/workflows/workflow-v4.yml"
SOURCE_PINS = {
    WORKFLOW: "b9933bfbe6ff4a84678ea531d52c691dcaef6c359896c4d77049b841773e9250",
    ".github/workflows/ci.yml": "85d5a3a9605aa0d3dc5dd51e5e9cd5cf5824c93654ce68e0d7aeac063cf95bf4",
}
PREFIX = "compatibility / "
SCANNER = PREFIX + "Gitleaks / full history"
AGGREGATE = PREFIX + "CI / required"
OFFLINE = "V4 controls and v1/v2/v3 preservation"
COMMON = [
    "Check out source",
    "Set up Python",
    "Install uv",
    "Sync locked development environment",
    "Run full test suite",
]
STEPS = {
    **{PREFIX + "Ubuntu / Python " + version: COMMON for version in ("3.10", "3.11", "3.12", "3.13", "3.14")},
    PREFIX + "macOS / Python 3.14": COMMON,
    PREFIX + "Workflow benchmark / CPython 3.13.12": [
        "Check out source",
        "Set up exact controller Python",
        "Install uv",
        "Sync locked development environment",
        "Require exact controller interpreter",
        "Run offline workflow controls",
        "Check benchmark controller sources",
        "Reproduce published workflow and transfer evidence",
        "Reproduce separate post-publication semantic audit",
    ],
    PREFIX + "Quality, demos, smoke, and artifacts": [
        "Check out source",
        "Set up Python",
        "Install uv",
        "Verify lock and sync environment",
        "Verify action pins and test floor",
        "Compile and lint",
        "Run deterministic demos",
        "Run offline smoke test",
        "Build distributions once",
        "Validate distributions",
        "Upload CI distributions",
    ],
    PREFIX + "Windows / clean wheel / Python 3.14": [
        "Check out verification script",
        "Set up Python",
        "Download wheel",
        "Install wheel without dependencies",
        "Verify exact API, serialization, and replay",
    ],
    OFFLINE: [
        "Check out full preservation history",
        "Set up exact controller Python",
        "Sync locked development tools",
        "Verify every original byte and mode",
        "Run independent v4 test process",
        "Check v4 source quality",
        "Reproduce immutable v2 public evidence",
        "Reproduce immutable v3 screen",
        "Reproduce v4 offline source correspondence",
        "Reproduce fixed v4 registration",
        "Reproduce completed v4 report when published",
    ],
    SCANNER: [
        "Check out full history",
        "Install checksum-pinned Gitleaks",
        "Scan every reachable commit for secrets",
    ],
    AGGREGATE: ["Require every CI lane"],
}
FAILED_STEP = {SCANNER: "Scan every reachable commit for secrets", AGGREGATE: "Require every CI lane"}


class GateBlocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise GateBlocked(reason)


def integer(value):
    return type(value) is int and value > 0


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(_):
        raise GateBlocked("nonfinite JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def run_identity(run, head):
    require(type(run) is dict, "invalid run record")
    for key in ("id", "run_attempt", "workflow_id"):
        require(integer(run.get(key)), "invalid run integer: " + key)
    expected = {
        "name": "Workflow v4",
        "workflow_id": WORKFLOW_ID,
        "path": WORKFLOW,
        "head_sha": head,
        "head_branch": BRANCH,
    }
    require(all(run.get(k) == v for k, v in expected.items()), "wrong workflow/head/branch")
    require(run.get("event") in ("push", "pull_request"), "unexpected run event")
    require(run.get("html_url") == f"https://github.com/{REPO}/actions/runs/{run['id']}", "run URL differs")
    pulls = run.get("pull_requests")
    require(
        type(pulls) is list
        and len(pulls) == 1
        and type(pulls[0].get("number")) is int
        and pulls[0]["number"] == PR,
        "run PR association differs",
    )
    return tuple(run.get(k) for k in ("id", "run_attempt", "workflow_id", "event", "status", "conclusion"))


def listed(record, head):
    require(
        type(record) is dict and type(record.get("total_count")) is int and record["total_count"] == 2,
        "run list missing, ambiguous or truncated",
    )
    runs = record.get("workflow_runs")
    require(type(runs) is list and len(runs) == 2, "run list incomplete")
    identities = [run_identity(run, head) for run in runs]
    require(
        len({v[0] for v in identities}) == 2 and {v[3] for v in identities} == {"push", "pull_request"},
        "duplicate run/event",
    )
    return {str(run["id"]): run for run in runs}


def evaluate(data, head):
    """Validate raw GitHub records; callers retain and authenticate acquisition custody."""
    require(type(head) is str and re.fullmatch(r"[0-9a-f]{40}", head), "invalid expected head")
    for suffix in ("before", "after"):
        branch = data["branch_" + suffix]
        require(
            branch.get("ref") == "refs/heads/" + BRANCH and branch.get("object", {}).get("sha") == head,
            "current public branch differs",
        )
        pull = data["pull_" + suffix]
        require(
            type(pull.get("number")) is int
            and pull["number"] == PR
            and pull.get("state") == "open"
            and pull.get("draft") is True
            and pull.get("head", {}).get("sha") == head
            and pull["head"].get("ref") == BRANCH
            and pull["head"].get("repo", {}).get("full_name") == REPO,
            "current draft PR identity differs",
        )
    before, after = listed(data["runs_before"], head), listed(data["runs_after"], head)
    require(set(before) == set(after) == set(data["details"]), "run roster drift")
    require(set(data["sources"]) == set(SOURCE_PINS), "workflow source roster differs")
    for path, expected in SOURCE_PINS.items():
        source = data["sources"][path]
        require(
            source.get("type") == "file"
            and source.get("path") == path
            and source.get("encoding") == "base64",
            "workflow source identity differs",
        )
        content = base64.b64decode("".join(source["content"].split()), validate=True)
        require(hashlib.sha256(content).hexdigest() == expected, "workflow source changed")
    result = []
    all_job_ids = set()
    for rid, original in before.items():
        current = data["details"][rid]["run"]
        require(
            run_identity(original, head) == run_identity(current, head) == run_identity(after[rid], head),
            "run attempt/status drift during acquisition",
        )
        require(
            current.get("status") == "completed" and current.get("conclusion") == "failure",
            "run incomplete or unexpected conclusion: " + current["event"],
        )
        payload = data["details"][rid]["jobs"]
        jobs = payload.get("jobs")
        require(
            type(payload.get("total_count")) is int
            and payload["total_count"] == len(STEPS)
            and type(jobs) is list
            and len(jobs) == len(STEPS),
            "job roster incomplete or ambiguous",
        )
        require(
            all(type(j) is dict for j in jobs) and {j.get("name") for j in jobs} == set(STEPS),
            "missing, duplicate or unknown job",
        )
        for job in jobs:
            name = job["name"]
            require(integer(job.get("id")) and job["id"] not in all_job_ids, "duplicate/invalid job identity")
            all_job_ids.add(job["id"])
            require(
                type(job.get("run_id")) is int
                and job["run_id"] == current["id"]
                and type(job.get("run_attempt")) is int
                and job["run_attempt"] == current["run_attempt"]
                and job.get("head_sha") == head,
                "job run/attempt/head differs",
            )
            require(
                job.get("status") == "completed"
                and job.get("conclusion") == ("failure" if name in FAILED_STEP else "success"),
                "job not in required completed state: " + name,
            )
            steps = job.get("steps")
            require(
                type(steps) is list and steps and all(type(s) is dict for s in steps), "missing step evidence"
            )
            names = [s.get("name") for s in steps]
            numbers = [s.get("number") for s in steps]
            required = set(STEPS[name]) | {"Set up job", "Complete job"}
            require(
                all(type(n) is str for n in names)
                and len(set(names)) == len(names)
                and required <= set(names)
                and all(integer(n) for n in numbers)
                and numbers == sorted(set(numbers)),
                "step roster invalid or incomplete",
            )
            for step in steps:
                require(
                    step.get("status") == "completed"
                    and step.get("conclusion")
                    == ("failure" if step["name"] == FAILED_STEP.get(name) else "success"),
                    "unexpected failed/skipped/pending step: " + name,
                )
        result.append(
            {
                "event": current["event"],
                "run_id": current["id"],
                "run_attempt": current["run_attempt"],
                "url": current["html_url"],
                "independent_jobs_succeeded": len(STEPS) - 2,
                "failed_jobs": [SCANNER, AGGREGATE],
            }
        )
    return {
        "status": "HOSTED_NONSECRET_LANES_ACCEPTED_PENDING_SCAN_ADJUDICATION",
        "head": head,
        "runs": sorted(result, key=lambda r: r["event"]),
        "ci_all_green": False,
        "scan_findings_adjudicated": False,
        "dispatch_authorized": False,
    }


def collect(head, output):
    started = time.monotonic()
    acquired = {}
    commands = []

    def get(name, endpoint):
        require(time.monotonic() - started <= 120, "observation interval exceeded")
        argv = ["gh", "api", f"repos/{REPO}/" + endpoint]
        call = subprocess.run(argv, capture_output=True, timeout=30, check=False)
        (output / (name + ".json")).write_bytes(call.stdout)
        (output / (name + ".stderr")).write_bytes(call.stderr)
        commands.append(
            {
                "argv": argv,
                "returncode": call.returncode,
                "stdout_sha256": hashlib.sha256(call.stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(call.stderr).hexdigest(),
            }
        )
        require(call.returncode == 0, "GitHub read failed: " + name)
        return strict(call.stdout)

    try:
        for suffix in ("before", "after"):
            acquired["branch_" + suffix] = get("branch_" + suffix, "git/ref/heads/" + BRANCH)
            acquired["pull_" + suffix] = get("pull_" + suffix, f"pulls/{PR}")
            acquired["runs_" + suffix] = get(
                "runs_" + suffix, f"actions/workflows/workflow-v4.yml/runs?head_sha={head}&per_page=100"
            )
            if suffix == "before":
                runs = listed(acquired["runs_before"], head)
                acquired["details"] = {}
                for rid, run in runs.items():
                    acquired["details"][rid] = {
                        "run": get("run_" + rid, "actions/runs/" + rid),
                        "jobs": get(
                            "jobs_" + rid,
                            f"actions/runs/{rid}/attempts/{run['run_attempt']}/jobs?per_page=100",
                        ),
                    }
                acquired["sources"] = {
                    p: get("source_" + str(i), f"contents/{p}?ref={head}") for i, p in enumerate(SOURCE_PINS)
                }
        require(time.monotonic() - started <= 120, "observation interval exceeded")
        result = evaluate(acquired, head)
    except (GateBlocked, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        result = {
            "status": "BLOCKED",
            "head": head,
            "reason": str(error),
            "error_type": type(error).__name__,
            "ci_all_green": False,
            "scan_findings_adjudicated": False,
            "dispatch_authorized": False,
        }
    result.update(
        {
            "schema_version": "evalopt.v4-hosted-ci-gate.v1",
            "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "observation_seconds": time.monotonic() - started,
            "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "commands": commands,
            "observed_job_states": {
                rid: [
                    {k: j.get(k) for k in ("name", "status", "conclusion")}
                    for j in evidence["jobs"].get("jobs", [])
                ]
                for rid, evidence in acquired.get("details", {}).items()
            },
        }
    )
    (output / "inputs.json").write_text(json.dumps(acquired, sort_keys=True, indent=2) + "\n")
    (output / "receipt.json").write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.expected_head), "invalid expected head")
    root = Path(__file__).resolve().parent
    require(
        args.output.is_absolute() and args.output == args.output.resolve() and args.output.parent == root,
        "output must be a new absolute direct child of this private helper directory",
    )
    args.output.mkdir(exist_ok=False)
    result = collect(args.expected_head, args.output)
    print(json.dumps({k: result[k] for k in ("status", "head", "dispatch_authorized")}, sort_keys=True))
    return 1 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
