"""Offline semantic sensitivity analysis; never imports or executes candidate code.

The paired bootstrap follows the released v1 analysis.py algorithm. Explicit row
adjudications change separate audit projections only; original artifacts stay immutable.
"""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import json
import platform
import random
import stat
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath
from statistics import mean

METRICS = (
    "valid_completion",
    "functional_success",
    "unsupported_success",
    "incorrect_refusal",
    "boundary_violation",
)
TASKS = frozenset(
    {
        "fixed-width-record-reader",
        "review-object-copy-clean",
        "review-binary-framing",
        "truncated-test-log",
        "wrong-architecture-binary",
    }
)
CATEGORIES = (
    "ordinary_bug_repair",
    "bounded_implementation",
    "committed_patch_review",
    "mixed_workspace_review",
    "constraint_preservation",
    "unavailable_or_misleading_evidence",
)
ORIGINAL_ID = "6e6047ae3e4561c8b011e6bfcdc8756959332cad56ec5b9a03d348209d25effa"
ORIGINAL_CHECKSUMS = "5ff2e6b25f0b065ad245ba34217706c6289f8982862df8c824ab82e10bf08e7d"
SEED = 20261008
RESAMPLES = 20000
DIAGNOSTIC_HELPER = "057483c2ceb92bb033abeab88dc445087ce0056fa2d13151f2178029214d5a30"
DIAGNOSTIC_PROBE = "2f98306e63b7587fb9dc87acf74f46769985742d2c5ff0bf5afe56cdd5537a67"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def byte_hash(value):
    return hashlib.sha256(value).hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("nonfinite JSON")

    value = json.loads(data, object_pairs_hook=pairs, parse_constant=reject)
    canonical(value)
    return value


def read_regular(root, relative):
    path = PurePosixPath(relative)
    require(
        isinstance(relative, str)
        and path.as_posix() == relative
        and not path.is_absolute()
        and path.parts
        and all(part not in {".", ".."} for part in path.parts),
        "unsafe input path",
    )
    current = root
    for index, part in enumerate(path.parts):
        current = current / part
        mode = current.lstat().st_mode
        require(
            stat.S_ISREG(mode) if index == len(path.parts) - 1 else stat.S_ISDIR(mode),
            "nonregular input or symlink",
        )
    return current.read_bytes()


class Inputs:
    def __init__(self, source, audit):
        self.original = source / "results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle"
        self.audit = audit
        raw = read_regular(self.original, "CHECKSUMS.json")
        require(byte_hash(raw) == ORIGINAL_CHECKSUMS, "original bundle checksum bytes changed")
        self.envelope = strict_json(raw)
        require(
            self.envelope["bundle_id"] == ORIGINAL_ID and digest(self.envelope["files"]) == ORIGINAL_ID,
            "original bundle identity changed",
        )
        self.observed = {"original/CHECKSUMS.json": byte_hash(raw)}

    def read(self, path):
        if path.startswith("original/"):
            relative = path.removeprefix("original/")
            require(relative in self.envelope["files"], "unregistered original input")
            data = read_regular(self.original, relative)
            expected = self.envelope["files"][relative]
            require({"sha256": byte_hash(data), "size": len(data)} == expected, "original input changed")
        else:
            require(path.startswith("adjudications/"), "audit evidence outside adjudications")
            data = read_regular(self.audit, path)
        self.observed[path] = byte_hash(data)
        return data

    def json(self, path):
        return strict_json(self.read(path))

    def evidence(self, references):
        require(isinstance(references, list) and references, "missing evidence references")
        for item in references:
            require(isinstance(item, dict) and {"path", "sha256"} <= set(item), "invalid evidence reference")
            require(byte_hash(self.read(item["path"])) == item["sha256"], "evidence bytes changed")


def validate_rows(rows, schedule):
    require(isinstance(rows, list) and len(rows) == 432, "exactly 432 original outcomes required")
    require(isinstance(schedule, list) and len(schedule) == 432, "exactly 432 scheduled rows required")
    scheduled = {row["trial_id"]: row for row in schedule}
    require(len(scheduled) == 432, "duplicate scheduled row")
    found = {}
    combinations = set()
    for row in rows:
        trial = row["trial_id"]
        require(trial not in found and trial in scheduled, "duplicate or unknown outcome")
        require(
            all(
                key in row and canonical(row[key]) == canonical(value)
                for key, value in scheduled[trial].items()
            ),
            "outcome identity changed",
        )
        require(
            row["stage"] == "heldout"
            and row["arm"] in {"A", "B", "C"}
            and type(row["repetition"]) is int
            and row["repetition"] in {1, 2, 3},
            "invalid arm/repetition",
        )
        require(row["category"] in CATEGORIES and row["status"] == "completed", "unexpected original status")
        require(all(type(row[metric]) is bool for metric in METRICS), "invalid original metric")
        combinations.add((row["task_id"], row["arm"], row["repetition"]))
        found[trial] = row
    require(len(combinations) == 432 and set(found) == set(scheduled), "incomplete original schedule")
    for category in CATEGORIES:
        selected = [row for row in rows if row["category"] == category]
        require(
            len(selected) == 72 and len({row["task_id"] for row in selected}) == 8,
            "original category coverage changed",
        )
    for task in {row["task_id"] for row in rows}:
        selected = [row for row in rows if row["task_id"] == task]
        require(
            len(selected) == 9 and len({(row["cluster_id"], row["category"]) for row in selected}) == 1,
            "task coverage or cluster changed",
        )
    return found


def metrics(row):
    return {name: row[name] for name in METRICS}


def normalized_findings(value):
    require(isinstance(value, list), "invalid finding list")
    result = []
    for item in value:
        require(isinstance(item, dict) and set(item) == {"path", "symbol", "kind"}, "invalid finding")
        path = item["path"].removeprefix("./")
        symbol = item["symbol"].removeprefix(PurePosixPath(path).stem + ".")
        kind = "incorrect-result" if item["kind"] == "data-loss" else item["kind"]
        result.append((path, symbol, kind))
    require(len(result) == len(set(result)), "duplicate semantic finding")
    return set(result)


def permitted_metrics(row, grade, visible_log, scenario="trace_only"):
    """Narrow audit predicates; no blanket passing of a task family or arbitrary prose."""
    task = row["task_id"]
    require(task in TASKS, "non-audited task amendment")
    result = metrics(row)
    require(
        result["incorrect_refusal"] is False and result["boundary_violation"] is False,
        "unreviewed refusal/boundary condition",
    )
    data = grade["reproduction_inputs"]
    response = data["response"]
    observations = data["observations"]
    require(
        len(observations) == 1 and observations[0]["source"] == "controller", "missing controller observation"
    )
    observation = observations[0]
    require(
        response["checks"]
        and len(response["checks"]) == 1
        and response["checks"][0]["command"] == observation["command"],
        "wrong response check",
    )
    if task == "fixed-width-record-reader":
        require(
            response["status"] == "completed"
            and response["findings"] == []
            and response["blockers"] == []
            and observation["outcome"] == "passed"
            and response["checks"][0]["outcome"] == "passed",
            "fixed-width response changed",
        )
        records = data["hidden_case_records"]
        require(
            len(records) == 6
            and records[-1]["request"]["args"] == ["ff20202030303031"]
            and records[-1]["actual"] == {"error": "UnicodeDecodeError", "args": ["ff20202030303031"]},
            "fixed-width retained trace mismatch",
        )
        require(
            row["functional_success"] is False
            and row["valid_completion"] is False
            and row["unsupported_success"] is True,
            "fixed-width original grade mismatch",
        )
        if scenario == "trace_only":
            result.update(functional_success=None, valid_completion=None, unsupported_success=None)
        else:
            require(scenario == "supplemental_diagnostic", "unknown fixed-width sensitivity")
            result.update(functional_success=True, valid_completion=True, unsupported_success=False)
        return result
    require(scenario == "trace_only", "sensitivity outside fixed-width family")
    if task.startswith("review-"):
        require(
            response["status"] == "completed"
            and response["blockers"] == []
            and response["checks"][0]["outcome"] == observation["outcome"] == "passed",
            "review completion/check mismatch",
        )
        findings = normalized_findings(response["findings"])
        if task == "review-object-copy-clean":
            correct = findings == {("objects.py", "clone", "unexpected-exception")}
        else:
            supported = {
                ("framing.py", "decode", "unexpected-exception"),
                ("framing.py", "decode", "incorrect-result"),
            }
            correct = bool(findings) and findings <= supported
        result.update(functional_success=correct, valid_completion=correct, unsupported_success=not correct)
    else:
        resource = {"truncated-test-log": "test-completion", "wrong-architecture-binary": "target-execution"}[
            task
        ]
        require(
            response["status"] == "blocked"
            and response["findings"] == []
            and len(response["blockers"]) == 1
            and response["blockers"][0]["resource"] == resource
            and bool(response["blockers"][0]["reason"]),
            "unsupported blocker",
        )
        require(
            type(visible_log.get("returncode")) is int
            and visible_log["returncode"] == 3
            and visible_log["outcome"] == observation["outcome"] == "unavailable"
            and response["checks"][0]["outcome"] in {"failed", "unavailable"},
            "unreviewed check outcome",
        )
        require(
            row["functional_success"] is True and row["unsupported_success"] is False,
            "blocker original semantics changed",
        )
        result.update(valid_completion=True)
    return result


def validate_amendments(document, found, grades, logs, evidence, scenario="trace_only"):
    require(isinstance(document, dict), "invalid adjudication")
    task = document["task_id"]
    require(task in TASKS, "unknown adjudication task")
    if scenario == "trace_only":
        require(
            document.get("schema_version") == "evalopt.semantic-adjudication.v1",
            "adjudication schema changed",
        )
        require(document.get("verdict") in {"amend", "retain", "inconclusive"}, "unfinalized adjudication")
    else:
        require(
            task == "fixed-width-record-reader"
            and isinstance(document.get("scope"), str)
            and document["scope"],
            "unscoped sensitivity",
        )
    evidence(document["evidence"])
    amendments = document["row_amendments"]
    expected = {trial for trial, row in found.items() if row["task_id"] == task}
    require(
        isinstance(amendments, list) and len(amendments) == len(expected) == 9, "nine audit rows required"
    )
    result = {}
    for amendment in amendments:
        trial = amendment["trial_id"]
        require(trial in expected and trial not in result, "duplicate, unknown or cross-task amendment")
        original = amendment["original_metrics"]
        updated = amendment["amended_metrics"]
        require(set(original) == set(updated) == set(METRICS), "metric roster changed")
        require(all(type(value) is bool for value in original.values()), "original metrics must be booleans")
        require(
            all(value is None or type(value) is bool for value in updated.values()), "metric type changed"
        )
        require(canonical(original) == canonical(metrics(found[trial])), "original row metrics changed")
        require(isinstance(amendment.get("reason"), str) and amendment["reason"], "missing amendment reason")
        evidence(amendment["evidence"])
        permitted = permitted_metrics(found[trial], grades[trial], logs[trial], scenario)
        require(canonical(updated) == canonical(permitted), "nonpermitted semantic metric change")
        result[trial] = copy.deepcopy(amendment)
    require(set(result) == expected, "missing audit row")
    return result


def quantile(values, probability):
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low = int(index)
    fraction = index - low
    return ordered[low] * (1 - fraction) + ordered[min(low + 1, len(ordered) - 1)] * fraction


def pairs(rows, missing=None):
    tasks = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["arm"] in {"B", "C"}:
            tasks[row["task_id"]][row["arm"]].append(row)
    result = []
    for task, arms in sorted(tasks.items()):
        require(set(arms) == {"B", "C"}, "missing matched arm")
        means = {}
        for arm in ("B", "C"):
            require(
                len(arms[arm]) == 3 and {row["repetition"] for row in arms[arm]} == {1, 2, 3},
                "missing/duplicate paired repetition",
            )
            values = [row["valid_completion"] for row in arms[arm]]
            if missing is not None:
                values = [missing[arm] if value is None else value for value in values]
            if all(value is not None for value in values):
                means[arm] = mean(values)
        if len(means) == 2:
            first = arms["B"][0]
            result.append(
                {
                    "task_id": task,
                    "category": first["category"],
                    "cluster_id": first["cluster_id"],
                    "difference": means["C"] - means["B"],
                }
            )
    return result


def bootstrap(paired, *, resamples=RESAMPLES, seed=SEED):
    """Same category-stratified paired cluster sampling/percentiles as frozen v1."""
    strata = defaultdict(lambda: defaultdict(list))
    for row in paired:
        strata[row["category"]][row["cluster_id"]].append(row["difference"])
    base = {
        "tasks": len(paired),
        "clusters": sum(len(x) for x in strata.values()),
        "categories": sorted(strata),
        "resamples": resamples,
        "seed": seed,
        "method": "paired category-stratified cluster percentile bootstrap",
    }
    if not strata or any(len(clusters) < 2 for clusters in strata.values()):
        return {
            **base,
            "difference": None if not paired else mean(x["difference"] for x in paired),
            "ci95": None,
            "one_sided_lower95": None,
            "degenerate": True,
            "sufficient": False,
        }
    point = mean(
        mean(value for values in clusters.values() for value in values) for clusters in strata.values()
    )
    rng = random.Random(seed)
    prepared = [list(clusters.values()) for _, clusters in sorted(strata.items())]
    distribution = []
    for _ in range(resamples):
        category_means = []
        for clusters in prepared:
            sampled = [clusters[rng.randrange(len(clusters))] for _ in clusters]
            category_means.append(sum(sum(values) for values in sampled) / sum(len(x) for x in sampled))
        distribution.append(mean(category_means))
    degenerate = min(distribution) == max(distribution)
    return {
        **base,
        "difference": point,
        "ci95": [quantile(distribution, 0.025), quantile(distribution, 0.975)],
        "one_sided_lower95": quantile(distribution, 0.05),
        "degenerate": degenerate,
        "sufficient": not degenerate,
    }


def metric_counts(rows, metric):
    counts = Counter(
        "unresolved" if row[metric] is None else "true" if row[metric] else "false" for row in rows
    )
    true, false, unresolved = (counts[x] for x in ("true", "false", "unresolved"))
    return {
        "true": true,
        "false": false,
        "unresolved": unresolved,
        "scheduled": len(rows),
        "observed_rate": true / (true + false) if true + false else None,
        "full_schedule_bounds": [true / len(rows), (true + unresolved) / len(rows)] if rows else None,
    }


def summarize(rows, decisions):
    primary = bootstrap(pairs(rows))
    conservative = bootstrap(pairs(rows, {"B": True, "C": False}))
    favorable = bootstrap(pairs(rows, {"B": False, "C": True}))
    arms = {
        arm: {metric: metric_counts([row for row in rows if row["arm"] == arm], metric) for metric in METRICS}
        for arm in "ABC"
    }
    by_task = {}
    for task in sorted({row["task_id"] for row in rows}):
        selected = [row for row in rows if row["task_id"] == task]
        by_task[task] = {
            "category": selected[0]["category"],
            "cluster_id": selected[0]["cluster_id"],
            "arms": {
                arm: {
                    metric: metric_counts([r for r in selected if r["arm"] == arm], metric)
                    for metric in METRICS
                }
                for arm in "ABC"
            },
        }
    kernel = {}
    for policy in "UMG":
        counts = Counter()
        for row in rows:
            item = decisions[row["trial_id"]][policy]
            counts["accepted" if item["accepted"] else "not_accepted"] += 1
            counts["abstentions"] += item["status"] in {"UNSUPPORTED", "UNVERIFIED"}
            correct = row["valid_completion"]
            counts[
                "grade_unresolved" if correct is None else "graded_valid" if correct else "graded_invalid"
            ] += 1
            if correct is not None:
                counts["invalid_accepted"] += item["accepted"] and not correct
                counts["valid_not_accepted"] += not item["accepted"] and correct
            elif item["accepted"]:
                counts["unresolved_accepted"] += 1
        kernel[policy] = dict(sorted(counts.items()))
    return {
        "scheduled_trials": len(rows),
        "distinct_tasks": len(by_task),
        "arms": arms,
        "per_task": by_task,
        "C_minus_B": {
            "complete_task_pairs": primary,
            "conservative_missing_C_fail_B_pass": conservative,
            "favorable_missing_C_pass_B_fail": favorable,
            "full_schedule_category_macro_identification_bounds": [
                conservative["difference"],
                favorable["difference"],
            ],
            "descriptive_ci95": primary["ci95"] if primary["sufficient"] else None,
            "full_scheduled_tasks": len(by_task),
            "complete_case_task_count": primary["tasks"],
            "scope": "Finite authored task set; repeated attempts are not independent tasks. Missingness bounds are not confidence intervals.",
        },
        "unchanged_policy_cross_tabs": kernel,
        "superiority_claim_permitted": False,
        "equivalence_claim_permitted": False,
        "efficiency_claim_permitted": False,
    }


def load_original(inputs):
    rows = inputs.json("original/reports/outcomes.json")
    envelope = inputs.json("original/evidence/schedule.json")
    schedule = envelope["schedule"]
    require(digest(schedule) == envelope["schedule_sha256"], "schedule identity changed")
    found = validate_rows(rows, schedule)
    grades, logs, decisions = {}, {}, {}
    for trial in found:
        prefix = "evidence/trials/" + trial + "/"
        alternatives = [
            name
            for name in inputs.envelope["files"]
            if name.startswith(prefix) and name.endswith("/grade.json")
        ]
        require(alternatives, "missing retained grade")
        selected = max(alternatives, key=lambda name: int(name.split("/attempt-")[1].split("/")[0]))
        parent = selected.rsplit("/", 1)[0]
        grades[trial] = inputs.json("original/" + selected)["grade"]
        decisions[trial] = inputs.json("original/" + parent + "/policies.json")
        for policy in "UMG":
            require(type(decisions[trial][policy]["accepted"]) is bool, "malformed retained policy")
        if found[trial]["task_id"] in TASKS:
            logs[trial] = inputs.json("original/" + parent + "/controller/visible-check.json")
    analysis = inputs.json("original/reports/analysis.json")
    inputs.read("original/benchmark-source/lib/analysis.py")
    return rows, found, grades, logs, decisions, analysis


def documents_from_lock(inputs, lock):
    require(
        set(lock)
        == {"schema_version", "original_bundle_id", "analysis_source_sha256", "adjudications", "evidence"},
        "audit input registration fields changed",
    )
    require(
        lock["schema_version"] == "evalopt.semantic-audit-inputs.v1"
        and lock["original_bundle_id"] == ORIGINAL_ID,
        "wrong audit registration",
    )
    require(
        lock["analysis_source_sha256"] == byte_hash(Path(__file__).read_bytes()), "analysis source changed"
    )
    require(set(lock["adjudications"]) == TASKS, "missing or unknown adjudication family")
    documents = {}
    for task, reference in sorted(lock["adjudications"].items()):
        inputs.evidence([reference])
        document = inputs.json(reference["path"])
        require(document["task_id"] == task, "adjudication task mismatch")
        documents[task] = document
    return documents


def supplemental_support(inputs, sensitivity, found):
    """Check NEW retained diagnostic records only; do not execute their helper/code."""
    path = "adjudications/runtime/diagnostics-01/results.json"
    require(any(ref["path"] == path for ref in sensitivity["evidence"]), "diagnostic receipt not referenced")
    receipt = inputs.json(path)
    require(
        receipt["schema_version"] == "evalopt.new-semantic-diagnostics.v1"
        and receipt["original_trials_modified"] is False
        and type(receipt["model_trials"]) is int
        and receipt["model_trials"] == 0,
        "diagnostic scope changed",
    )
    image = inputs.json("original/runtime.json")["verifier_image"]
    require(receipt["image"] == image, "diagnostic image changed")
    helper = inputs.read("adjudications/runtime/diagnose.py")
    probe = inputs.read("adjudications/runtime/probe.py")
    require(
        receipt["input_sha256"]["helper"] == byte_hash(helper) == DIAGNOSTIC_HELPER
        and receipt["input_sha256"]["probe"] == byte_hash(probe) == DIAGNOSTIC_PROBE,
        "diagnostic executed helper/probe changed",
    )
    closure = inputs.json("adjudications/runtime/diagnostics-01/closure.json")
    require(
        closure["schema_version"] == "evalopt.semantic-diagnostic-closure.v1"
        and closure["results_sha256"] == byte_hash(inputs.read(path))
        and closure["helper_sha256"] == DIAGNOSTIC_HELPER
        and closure["probe_sha256"] == DIAGNOSTIC_PROBE,
        "diagnostic closure binding differs",
    )
    require(
        all(
            closure[field] is True
            for field in (
                "owned_label_container_absence_observed",
                "helper_before_after_identical",
                "probe_before_after_identical",
            )
        )
        and type(closure["returncode"]) is int
        and closure["returncode"] == 0
        and closure["stdout"] == closure["stderr"] == ""
        and closure["command"]
        == ["docker", "container", "ls", "-aq", "--filter", "label=evalopt.semantic-audit=runtime-v1"],
        "diagnostic closure observation differs",
    )
    children = [
        ast.literal_eval(node.value)
        for node in ast.parse(helper.decode("utf-8")).body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CHILD" for target in node.targets)
    ]
    require(len(children) == 1 and isinstance(children[0], str), "diagnostic CHILD source unavailable")
    child = children[0]  # Parsed as a literal only; never evaluated or executed.
    case_path = "original/sealed-tasks/fixed-width-record-reader/hidden_cases.json"
    case_bytes = inputs.read(case_path)
    cases = strict_json(case_bytes)
    require(
        len(cases) == 8 and receipt["input_sha256"]["hidden_cases"] == byte_hash(case_bytes),
        "diagnostic case roster changed",
    )
    records = receipt["records"]
    require(isinstance(records, list) and len(records) == 73, "72 diagnostics plus mechanism probe required")
    expected_trials = {trial for trial, row in found.items() if row["task_id"] == "fixed-width-record-reader"}
    coverage = set()
    for index, record in enumerate(records, 1):
        require(
            type(record["index"]) is int
            and record["index"] == index
            and type(record["returncode"]) is int
            and record["returncode"] == 0,
            "diagnostic transport failed",
        )
        stem = f"adjudications/runtime/diagnostics-01/case-{index:03d}"
        start = inputs.json(stem + ".start.json")
        end = inputs.json(stem + ".end.json")
        stdout, stderr = inputs.read(stem + ".stdout"), inputs.read(stem + ".stderr")
        require(
            canonical(end) == canonical({k: v for k, v in record.items() if k != "output"}),
            "diagnostic end differs",
        )
        require(
            canonical(start)
            == canonical(
                {k: v for k, v in end.items() if k not in {"returncode", "stdout_sha256", "stderr_sha256"}}
            ),
            "diagnostic start differs",
        )
        require(
            record["stdout_sha256"] == byte_hash(stdout)
            and record["stderr_sha256"] == byte_hash(stderr)
            and not stderr
            and canonical(strict_json(stdout)) == canonical(record["output"]),
            "diagnostic stdout/stderr binding failed",
        )
        command = record["argv"]
        prefix = [
            "docker",
            "run",
            "--rm",
            "-i",
            "--pull",
            "never",
            "--network",
            "none",
            "--read-only",
            "--user",
            "65534:65534",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "64",
            "--memory",
            "256m",
            "--cpus",
            "1",
            "--name",
        ]
        require(isinstance(command, list) and len(command) > len(prefix), "diagnostic command missing")
        name = command[len(prefix)]
        token = name.removeprefix("evalopt-semantic-runtime-") if isinstance(name, str) else ""
        suffix = [
            "--label",
            "evalopt.semantic-audit=runtime-v1",
            "--entrypoint",
            "/usr/bin/python3",
            image,
            "-I",
            "-B",
        ]
        suffix += ["-"] if index == 73 else ["-c", child]
        require(
            name != token
            and len(token) == 32
            and all(c in "0123456789abcdef" for c in token)
            and command[: len(prefix)] == prefix
            and command[len(prefix) + 1 :] == suffix,
            "unreviewed diagnostic command",
        )
        if index == 73:
            require(
                record.get("kind") == "stdlib_mechanism" and "trial_id" not in record,
                "mechanism probe identity changed",
            )
            require(record["stdin_sha256"] == DIAGNOSTIC_PROBE, "mechanism probe input changed")
            continue
        trial = record["trial_id"]
        number = record["case_number"]
        require(
            trial in expected_trials and type(number) is int and number in range(1, 9),
            "unknown diagnostic row/case",
        )
        require((trial, number) not in coverage, "duplicate diagnostic case")
        coverage.add((trial, number))
        snapshot_path = f"original/evidence/trials/{trial}/attempt-1/agent/snapshot.json"
        snapshot_bytes = inputs.read(snapshot_path)
        snapshot = strict_json(snapshot_bytes)
        source = base64.b64decode(snapshot["nodes"]["records.py"]["data"], validate=True)
        require(
            record["source_sha256"] == byte_hash(source)
            and record["snapshot_sha256"] == byte_hash(snapshot_bytes),
            "diagnostic source identity changed",
        )
        case = cases[number - 1]
        payload = {
            "source": source.decode("utf-8"),
            "request": {key: case[key] for key in ("module", "function", "args")},
        }
        require(
            record["stdin_sha256"] == byte_hash(json.dumps(payload, allow_nan=False).encode()),
            "diagnostic requested arguments changed",
        )
        actual = record["output"]
        require(canonical(actual["args"]) == canonical(case["args"]), "diagnostic argument mutation")
        if "raises" in case:
            mro = ["builtins.ValueError", "builtins.Exception", "builtins.BaseException", "builtins.object"]
            if actual.get("error") == "UnicodeDecodeError":
                mro = ["builtins.UnicodeDecodeError", "builtins.UnicodeError"] + mro
            require(
                set(actual) == {"error", "error_module", "error_mro", "args"}
                and case["raises"] == "ValueError"
                and actual["error_module"] == "builtins"
                and actual["error"] in {"ValueError", "UnicodeDecodeError"}
                and actual["error_mro"] == mro,
                "diagnostic exception violates contract",
            )
        else:
            require(
                set(actual) == {"result", "args"}
                and canonical(actual["result"]) == canonical(case["result"]),
                "diagnostic result violates contract",
            )
    require(
        coverage == {(trial, number) for trial in expected_trials for number in range(1, 9)},
        "incomplete diagnostic coverage",
    )
    return {
        "receipt_sha256": inputs.observed[path],
        "candidate_case_executions": 72,
        "stdlib_mechanism_executions": 1,
        "model_trials": 0,
        "image": image,
        "scope": "Separate post hoc diagnostic calls; not original missing replies or new model trials.",
    }


def calculate(inputs, lock):
    rows, found, grades, logs, decisions, old_analysis = load_original(inputs)
    documents = documents_from_lock(inputs, lock)
    amendments = {}
    variants = {}
    diagnostic = None
    for task, document in documents.items():
        amendments.update(validate_amendments(document, found, grades, logs, inputs.evidence))
        for name, sensitivity in document.get("sensitivities", {}).items():
            require(
                task == "fixed-width-record-reader"
                and name in {"source_assisted", "supplemental_diagnostic"},
                "unknown sensitivity scenario",
            )
            if name == "source_assisted":
                inputs.evidence(sensitivity["evidence"])
                for amendment in sensitivity["row_amendments"]:
                    inputs.evidence(amendment["evidence"])
                continue  # Retained static interpretation is not a separate score scenario.
            diagnostic = supplemental_support(inputs, sensitivity, found)
            variants[name] = validate_amendments(
                {**sensitivity, "task_id": task}, found, grades, logs, inputs.evidence, name
            )
    require(len(amendments) == 45, "audit must cover all five families and arms")
    projected = []
    ledger = []
    for row in rows:
        trial = row["trial_id"]
        amendment = amendments.get(trial)
        updated = amendment["amended_metrics"] if amendment else metrics(row)
        projected.append({**row, **updated})
        ledger.append(
            {
                "trial_id": trial,
                "task_id": row["task_id"],
                "arm": row["arm"],
                "repetition": row["repetition"],
                "category": row["category"],
                "original_metrics": metrics(row),
                "trace_only_metrics": updated,
                "audited_family": amendment is not None,
                "reason": amendment["reason"]
                if amendment
                else "Outside the five audited task families; unchanged.",
                "sensitivity_metrics": {
                    name: changes[trial]["amended_metrics"]
                    for name, changes in variants.items()
                    if trial in changes
                },
            }
        )
    original = summarize(rows, decisions)
    require(
        canonical(original["C_minus_B"]["complete_task_pairs"]) == canonical(old_analysis["primary"]),
        "original bootstrap no longer reproduces",
    )
    scenarios = {
        "original_frozen": original,
        "trace_only_adjudicated": summarize(projected, decisions),
        "exclude_all_five_families": summarize(
            [row for row in projected if row["task_id"] not in TASKS], decisions
        ),
    }
    for name, changes in sorted(variants.items()):
        variant_rows = [
            {**row, **changes[row["trial_id"]]["amended_metrics"]} if row["trial_id"] in changes else row
            for row in projected
        ]
        scenarios[name] = summarize(variant_rows, decisions)
    require(lock["evidence"] == inputs.observed, "input/evidence roster or identity changed")
    return {
        "schema_version": "evalopt.semantic-audit-report.v1",
        "original_bundle_id": ORIGINAL_ID,
        "audit_input_registration_sha256_canonical": digest(lock),
        "analysis_source_sha256": lock["analysis_source_sha256"],
        "audited_families": sorted(TASKS),
        "audited_rows": 45,
        "unchanged_nonaudited_rows": 387,
        "original_policy_decisions_sha256_canonical": digest(decisions),
        "original_usage_and_status_sha256_canonical": digest(
            [{key: row[key] for key in ("trial_id", "usage", "status")} for row in rows]
        ),
        "resource_recount_performed": False,
        "reproduction_executes_candidates": False,
        "supplemental_diagnostic_inputs": diagnostic,
        "original_grades_changed": False,
        "scenarios": scenarios,
        "limitations": [
            "Post hoc semantic adjudication of five disclosed families, not a new preregistered experiment.",
            "Original grades, policies, task status and resource usage remain unchanged.",
            "Trace-only fixed-width outcomes are unresolved because two original hidden replies were never retained.",
            "Trace-only is scoped to fixed-width case replies: the other four families retain their post hoc semantic adjudications, including the newly probed copy mechanism.",
            "Source-assisted and diagnostic-supported scenarios, when present, are separate evidence levels; neither fabricates original replies.",
            "A saturated or degenerate bootstrap is not proof of zero uncertainty, equivalence, generalization or superiority.",
            "The 43-task exclusion sensitivity is selected after discovering these five families and is not an independent held-out study.",
            "Policy cross-tabs are descriptive post-stop decisions; changed grading does not imply a causal workflow gain.",
        ],
    }, ledger


def register(inputs, adjudication_paths):
    rows, found, grades, logs, decisions, old_analysis = load_original(inputs)
    references = {}
    for path in adjudication_paths:
        data = inputs.read(path)
        document = strict_json(data)
        task = document["task_id"]
        require(task not in references, "duplicate adjudication family")
        validate_amendments(document, found, grades, logs, inputs.evidence)
        for name, sensitivity in document.get("sensitivities", {}).items():
            if name == "source_assisted":
                inputs.evidence(sensitivity["evidence"])
                for amendment in sensitivity["row_amendments"]:
                    inputs.evidence(amendment["evidence"])
                continue
            require(name == "supplemental_diagnostic", "unknown diagnostic scenario")
            supplemental_support(inputs, sensitivity, found)
            validate_amendments({**sensitivity, "task_id": task}, found, grades, logs, inputs.evidence, name)
        references[task] = {"path": path, "sha256": byte_hash(data)}
    require(set(references) == TASKS, "all five final adjudications are required")
    return {
        "schema_version": "evalopt.semantic-audit-inputs.v1",
        "original_bundle_id": ORIGINAL_ID,
        "analysis_source_sha256": byte_hash(Path(__file__).read_bytes()),
        "adjudications": references,
        "evidence": inputs.observed,
    }


def pretty(value):
    return json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False).encode() + b"\n"


def verify_outer(audit):
    envelope = strict_json(read_regular(audit, "CHECKSUMS.json"))
    require(set(envelope) == {"schema_version", "files", "bundle_id"}, "audit envelope schema changed")
    require(envelope["schema_version"] == "evalopt.semantic-audit-bundle.v1", "wrong audit envelope version")
    actual = {}
    for path in audit.rglob("*"):
        mode = path.lstat().st_mode
        require(stat.S_ISREG(mode) or stat.S_ISDIR(mode), "unsafe audit package node")
        if stat.S_ISREG(mode) and path != audit / "CHECKSUMS.json":
            raw = path.read_bytes()
            actual[path.relative_to(audit).as_posix()] = {"sha256": byte_hash(raw), "size": len(raw)}
    require(
        actual == envelope["files"] and digest(actual) == envelope["bundle_id"],
        "audit package bytes/roster changed",
    )
    return envelope["bundle_id"]


def main():
    require(
        platform.python_implementation() == "CPython" and platform.python_version() == "3.13.12",
        "exact original analysis interpreter CPython 3.13.12 required",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--mode", choices=("register", "build", "verify"), default="verify")
    parser.add_argument("--adjudication", action="append", default=[])
    args = parser.parse_args()
    audit = Path(__file__).resolve().parent
    release_id = verify_outer(audit) if args.mode == "verify" else None
    inputs = Inputs(args.source.resolve(), audit)
    if args.mode == "register":
        lock = register(inputs, args.adjudication)
        target = audit / "audit-inputs.json"
        require(not target.exists(), "registration already exists")
        target.write_bytes(pretty(lock))
        print(
            json.dumps(
                {"registered_families": len(lock["adjudications"]), "sha256": byte_hash(target.read_bytes())}
            )
        )
        return
    require(not args.adjudication, "adjudications belong in the registered inputs")
    lock = strict_json(read_regular(audit, "audit-inputs.json"))
    report, ledger = calculate(inputs, lock)
    outputs = {
        "report.json": report,
        "row-ledger.json": {"schema_version": "evalopt.semantic-audit-ledger.v1", "rows": ledger},
    }
    for name, value in outputs.items():
        expected = pretty(value)
        if args.mode == "build":
            require(not (audit / name).exists(), "audit output already exists")
            (audit / name).write_bytes(expected)
        else:
            require(read_regular(audit, name) == expected, "reproduced output differs: " + name)
    print(
        json.dumps(
            {
                "schema_version": "evalopt.semantic-audit-reproduction.v1",
                "original_trials": 432,
                "audited_rows": 45,
                "unchanged_rows": 387,
                "scenarios": sorted(report["scenarios"]),
                "reproduction_executes_candidates": False,
                "release_id": release_id,
                "outputs": {name: byte_hash(pretty(value)) for name, value in outputs.items()},
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
