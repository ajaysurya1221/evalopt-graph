#!/usr/bin/env python3
"""Release a completed held-out evidence set and its sealed grading assets offline."""

from __future__ import annotations

import argparse
import base64
import json
import stat
from pathlib import Path

import campaign
import heldout_campaign
import publish_bundle as authored
from lib.analysis import analyze_workflows, summarize_kernel
from lib.common import bytes_digest, canonical_bytes, digest, exact, is_digest, read_json
from lib.store import TERMINAL
from runtime.controller import require_controller
from runtime.harbor_campaign import source_identity
from runtime.verify import strict_json
from tasks import suite

HELDOUT_FILES = set(heldout_campaign.HELDOUT_FILES) | {"heldout-lock.json"}
ROOT_FILES = authored.PUBLIC_ROOT_FILES | HELDOUT_FILES
REPORT_FILES = authored.REPORT_FILES
REPRO_KEYS = {
    "schema_version",
    "task_id",
    "split",
    "initial_manifest",
    "stopped_manifest",
    "response",
    "observations",
    "unsafe_snapshot",
    "hidden_test_passed",
    "hidden_case_records",
}
SCOPE = "maintainer-run held-out outcomes; pure grading replay from controller-supplied case replies; no independent candidate execution"


def _root_files(root):
    """Keep the legacy release roster exact; v2 additionally retains its policy."""
    frozen = read_json(root / "freeze.json")
    return ROOT_FILES | (
        {"accounting-policy.json"} if frozen.get("schema_version") == "evalopt.heldout-freeze.v2" else set()
    )


# Reviewed synthetic inputs, bound to the exact sealed fixture; never a general
# credential-field exemption. Actual file bytes are not changed by inspection.
SYNTHETIC_TASK = "redacted-structured-logging"
SYNTHETIC_PATH = "sealed-tasks/" + SYNTHETIC_TASK + "/hidden_cases.json"
SYNTHETIC_SHA256 = "6bdc567eec23f37494159ec358fa54351b1a55d18ef92f3180e26c465119b0b3"


def _field_values(value, prefix=""):
    found = {}
    if isinstance(value, dict):
        for key, child in value.items():
            pointer = prefix + "/" + key.replace("~", "~0").replace("/", "~1")
            if key.casefold() in authored.SECRET_FIELDS and isinstance(child, str) and child:
                found[pointer] = child
            found.update(_field_values(child, pointer))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.update(_field_values(child, prefix + "/" + str(index)))
    return found


def _inspect_fixture_fields(raw, allowed, label):
    value = json.loads(raw)
    matched = {}

    def project(item, pointer=""):
        if pointer in allowed and item == allowed[pointer]:
            matched[pointer] = bytes_digest(canonical_bytes(item))
            return None
        if isinstance(item, dict):
            return {
                key: project(child, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [project(child, pointer + "/" + str(index)) for index, child in enumerate(item)]
        return item

    inspected = project(value)
    # Generic secret/path patterns always inspect the original, unchanged bytes.
    authored._scan_text(raw.decode("utf-8", errors="replace"), label)
    if b"\0" in raw:
        for encoding in ("utf-16-le", "utf-16-be"):
            authored._scan_text(raw.decode(encoding, errors="replace"), label)
    authored._scan_json(inspected, label)
    return matched


def scan_heldout_payloads(payloads, schedule):
    source_raw = payloads.get(SYNTHETIC_PATH)
    source_matches = source_raw is not None and bytes_digest(source_raw) == SYNTHETIC_SHA256
    case_data = json.loads(source_raw) if source_matches else None
    allowed = {SYNTHETIC_PATH: _field_values(case_data)} if source_matches else {}
    by_trial = {row["trial_id"]: row for row in schedule}
    if source_matches:
        for name, raw in payloads.items():
            parts = Path(name).parts
            if (
                len(parts) != 5
                or parts[:2] != ("evidence", "trials")
                or parts[4] != "grade.json"
                or parts[2] not in by_trial
                or by_trial[parts[2]]["task_id"] != SYNTHETIC_TASK
            ):
                continue
            try:
                inputs = json.loads(raw)["grade"]["reproduction_inputs"]
                records = inputs["hidden_case_records"]
                if (
                    inputs["schema_version"] != "evalopt.grade-reproduction.v1"
                    or inputs["task_id"] != SYNTHETIC_TASK
                    or inputs["split"] != "heldout"
                    or not isinstance(records, list)
                    or len(records) > len(case_data)
                ):
                    continue
                fields = {}
                for index, record in enumerate(records):
                    case = case_data[index]
                    expected_request = {key: case[key] for key in ("module", "function", "args")}
                    if record.get("request") != expected_request:
                        fields = {}
                        break
                    prefix = "/grade/reproduction_inputs/hidden_case_records/" + str(index)
                    fields.update(_field_values(expected_request, prefix + "/request"))
                    fields.update(_field_values(case["args"], prefix + "/actual/args"))
                    if "result" in case:
                        fields.update(_field_values(case["result"], prefix + "/actual/result"))
                if fields:
                    allowed[name] = fields
            except (ValueError, KeyError, TypeError):
                continue
    files = {}
    for name, raw in payloads.items():
        if name in allowed:
            matched = _inspect_fixture_fields(raw, allowed[name], name)
            if matched:
                files[name] = {
                    "sha256": bytes_digest(raw),
                    "fields": [
                        {"json_pointer": pointer, "value_sha256": value}
                        for pointer, value in sorted(matched.items())
                    ],
                }
        else:
            authored.scan_public_file(name, raw)
    return {
        "schema_version": "evalopt.synthetic-fixture-allowances.v1",
        "source": {"task_id": SYNTHETIC_TASK, "path": SYNTHETIC_PATH, "sha256": SYNTHETIC_SHA256}
        if source_matches
        else None,
        "files": files,
        "review_reason": "registered recursive-redaction task uses known synthetic secret-field values; exact frozen cases and matching case provenance only",
        "scope": "exact reviewed synthetic JSON field values and matching task case replies only; generic text patterns remain active; exported bytes are unchanged",
    }


class GradeReplayError(RuntimeError):
    """A replay request differs from the retained verifier call sequence."""


def replay_grade(path, scheduled, task_root):
    grade = read_json(path / "grade.json")["grade"]
    inputs = exact(grade.get("reproduction_inputs"), REPRO_KEYS, "grade reproduction inputs")
    if (
        inputs["schema_version"] != "evalopt.grade-reproduction.v1"
        or inputs["task_id"] != scheduled["task_id"]
        or inputs["split"] != "heldout"
        or type(inputs["unsafe_snapshot"]) is not bool
        or type(inputs["hidden_test_passed"]) is not bool
        or not isinstance(inputs["hidden_case_records"], list)
    ):
        raise ValueError("invalid heldout grade reproduction identity")
    task = suite.load_task(scheduled["task_id"], task_root=task_root, split="heldout")
    if inputs["stopped_manifest"] != read_json(path / "agent/node-manifest.json"):
        raise ValueError("grade stopped-node inputs differ from retained controller snapshot")
    for name in ("initial_manifest", "stopped_manifest"):
        if not isinstance(inputs[name], dict) or any(
            not isinstance(k, str) or not isinstance(v, str) for k, v in inputs[name].items()
        ):
            raise ValueError("invalid node manifest in grade inputs")
    snapshot = read_json(path / "agent/snapshot.json")
    response = None
    node = snapshot["nodes"].get("response.json")
    if node is not None and node.get("type") == "file":
        try:
            response = strict_json(base64.b64decode(node["data"], validate=True))
        except (ValueError, TypeError):
            response = None
    if response != inputs["response"]:
        raise ValueError("grade response differs from frozen agent output")
    visible = read_json(path / "visible.json")
    gates = [gate for gate in visible["gates"] if gate["name"] == "visible_check"]
    if len(gates) != 1:
        raise ValueError("grade lacks one frozen visible observation")
    observation = {
        "command": task["visible_check"],
        "source": "controller",
        "outcome": {"PASS": "passed", "FAIL": "failed", "NOT_CONFIGURED": "unavailable"}[gates[0]["status"]],
    }
    if inputs["observations"] != [observation]:
        raise ValueError("grade observations differ from pre-grade controller evidence")
    records, consumed = inputs["hidden_case_records"], 0

    def recorded_invoke(request):
        nonlocal consumed
        if consumed >= len(records):
            raise GradeReplayError("recorded hidden case response missing")
        record = records[consumed]
        consumed += 1
        if not isinstance(record, dict) or record.get("request") != request:
            raise GradeReplayError("hidden case request or order differs")
        if set(record) == {"request", "error"} and record["error"] == "candidate_invocation_failed":
            raise ValueError("recorded candidate invocation failed")
        if set(record) != {"request", "actual"}:
            raise GradeReplayError("unsupported hidden case record")
        return record["actual"]

    hidden = (
        False
        if inputs["unsafe_snapshot"]
        else suite.evaluate_cases(task, recorded_invoke, task_root=task_root)
    )
    if consumed != len(records) or hidden is not inputs["hidden_test_passed"]:
        raise ValueError("recorded hidden case results do not reproduce grading input")
    reproduced = suite.grade_snapshot(
        task,
        inputs["initial_manifest"],
        inputs["stopped_manifest"],
        response,
        inputs["observations"],
        hidden_test_passed=hidden,
    )
    finish = read_json(path / "finish.json")
    if finish["status"] == "timeout":
        reproduced["valid_completion"] = False
    reproduced["boundary_violation"] = not reproduced["boundaries_preserved"]
    if {key: value for key, value in grade.items() if key != "reproduction_inputs"} != reproduced:
        raise ValueError("retained grade does not reproduce from supplied case replies")
    return True


def _check_heldout(root, registration_sha256, source):
    lock = read_json(root / "heldout-lock.json")
    if (
        not is_digest(registration_sha256)
        or digest(lock) != registration_sha256
        or lock != heldout_campaign._heldout_identity(root)
    ):
        raise authored.PublicationError("heldout lock differs from explicit registration identity")
    frozen = read_json(root / "freeze.json")
    if (
        frozen.get("schema_version") not in {"evalopt.heldout-freeze.v1", "evalopt.heldout-freeze.v2"}
        or frozen.get("scheduled_trials") != 432
        or frozen.get("seed") != 20261008
        or frozen.get("task_root") != "sealed-tasks"
    ):
        raise authored.PublicationError("heldout freeze scope changed")
    candidate = heldout_campaign.verify_sealed_tasks(
        root / "sealed-tasks", frozen["candidate_manifest_sha256"]
    )
    if candidate != read_json(root / "sealed-manifest.json") or suite.file_manifest(
        root / "sealed-tasks"
    ) != read_json(root / "sealed-snapshot.json"):
        raise authored.PublicationError("sealed task content, mode, or node identity changed")
    manifest, schedule = authored._public_registration(root)
    if len(schedule) != 432 or {row["stage"] for row in schedule} != {"heldout"}:
        raise authored.PublicationError("heldout publication requires all 432 registered trials")
    grader_sha = digest(
        {
            "suite": source_identity(source / "tasks"),
            "verifier": bytes_digest(authored._read_regular(source / "runtime/verify.py")),
        }
    )
    if grader_sha != manifest["pins"]["grader_sha256"]:
        raise authored.PublicationError("heldout grader source differs from registered identity")
    task_map = {task["id"]: task for task in candidate["tasks"]}
    for task in manifest["tasks"]:
        sealed = task_map.get(task["task_id"])
        if (
            sealed is None
            or task["task_sha256"] != digest(sealed["files"])
            or task["grader_sha256"] != grader_sha
            or task["category"] != sealed["category"].replace("-", "_")
            or task["cluster_id"] != sealed["source_family"]
        ):
            raise authored.PublicationError("heldout task or grading identities differ")
    if source_identity(source) != read_json(root / "source-lock.json")["campaign_sha256"]:
        raise authored.PublicationError("frozen benchmark source differs from registration")
    # Replay executes installed trusted code only, after comparing its grader and
    # analysis implementation with the source being released.
    for relative in ("tasks", "lib"):
        if source_identity(source / relative) != source_identity(authored.HERE / relative):
            raise authored.PublicationError("use the registered trusted grader and analysis source")
    review, pilot = read_json(root / "pilot-review.json"), read_json(root / "pilot-evidence.json")
    amended = frozen["schema_version"] == "evalopt.heldout-freeze.v2"
    review_checks = heldout_campaign.REVIEW_CHECKS_V2 if amended else heldout_campaign.REVIEW_CHECKS
    if (
        pilot["review_sha256"] != bytes_digest(authored._read_regular(root / "pilot-review.json"))
        or pilot["registration_sha256"] != review["pilot_registration_sha256"]
        or pilot["export_id"] != review["pilot_export_id"]
        or pilot["scheduled_trials"] != 36
        or review["verdict"] != "ready_for_heldout"
        or set(review["checks"]) != review_checks
        or not all(value is True for value in review["checks"].values())
    ):
        raise authored.PublicationError("retained pilot progression receipts disagree")
    store = authored._read_only_store(root / "evidence", schedule)
    if amended:
        from runtime.accounting_policy import validate_attempt

        if (
            review.get("schema_version") != "evalopt.pilot-review.v2"
            or pilot.get("schema_version") != "evalopt.pilot-evidence.v2"
        ):
            raise authored.PublicationError("accounting policy requires the amended pilot review")
        policy = heldout_campaign.read_accounting_policy(root)
        if policy is None:
            raise authored.PublicationError("amended heldout publication lacks its accounting policy")
        _, _, attempts = campaign._report_rows(store, schedule, accounting_policy=policy)
        for record in attempts:
            if record["artifact_valid"]:
                validate_attempt(record, policy)
    elif (root / "accounting-policy.json").exists():
        raise authored.PublicationError("legacy heldout registration cannot add an accounting policy")
    return manifest, schedule, store


def _unavailable(receipt, registration_sha256):
    if receipt is None:
        receipt = {
            "schema_version": "evalopt.heldout-unavailable.v1",
            "heldout_registration_sha256": registration_sha256,
            "trials": [],
        }
    exact(receipt, {"schema_version", "heldout_registration_sha256", "trials"}, "unavailable receipt")
    if (
        receipt["schema_version"] != "evalopt.heldout-unavailable.v1"
        or receipt["heldout_registration_sha256"] != registration_sha256
        or not isinstance(receipt["trials"], list)
    ):
        raise authored.PublicationError("unavailable evidence receipt has different registration")
    ids = set()
    for trial in receipt["trials"]:
        exact(trial, {"trial_id", "reason"}, "unavailable trial")
        if trial["trial_id"] in ids or not isinstance(trial["reason"], str) or not trial["reason"].strip():
            raise authored.PublicationError("duplicate unavailable trial or missing explicit reason")
        ids.add(trial["trial_id"])
    return receipt, ids


def _assessment(root, store, schedule, unavailable):
    accounting = heldout_campaign.read_accounting_policy(root)
    rows, kernel, attempts = campaign._report_rows(store, schedule, accounting_policy=accounting)
    states = {state["trial_id"]: state for state in store.statuses()}
    deficient, replayed = set(), 0
    for row in schedule:
        state = states[row["trial_id"]]
        if not state["attempts"]:
            deficient.add(row["trial_id"])
            continue
        for number in range(1, state["attempts"] + 1):
            path = store.root / "trials" / row["trial_id"] / f"attempt-{number}"
            try:
                store.verify_attempt(row["trial_id"], number)
                finish = read_json(path / "finish.json")
                if finish["status"] not in TERMINAL:
                    raise ValueError("unresolved outcome")
                if (path / "grade.json").is_file():
                    replay_grade(path, row, root / "sealed-tasks")
                    replayed += 1
                elif number == state["attempts"]:
                    raise ValueError("final attempt has no independent grade")
            except (OSError, ValueError, TypeError, KeyError, GradeReplayError):
                deficient.add(row["trial_id"])
    if unavailable != deficient:
        raise authored.PublicationError(
            "432 outcomes must be complete or exactly covered by an explicit unavailable-evidence receipt"
        )
    for row in rows:
        if row["trial_id"] in deficient:
            row.update(status="artifact_failure", **dict.fromkeys(campaign.METRICS))
    for row in kernel:
        if row["trial_id"] in deficient:
            row.update(valid_completion=None, artifact_valid=False)
    return rows, kernel, attempts, replayed


def _collect_evidence(root, store, unavailable):
    result = {"evidence/schedule.json": authored._read_regular(root / "evidence/schedule.json")}
    trial_root = root / "evidence/trials"
    if {path.name for path in (root / "evidence").iterdir()} - {"schedule.json", "trials"}:
        raise authored.PublicationError("unexpected controller evidence entry")
    if trial_root.exists() and any(
        path.name not in store.trials or path.is_symlink() or not path.is_dir()
        for path in trial_root.iterdir()
    ):
        raise authored.PublicationError("unscheduled heldout evidence")
    for state in store.statuses():
        trial = trial_root / state["trial_id"]
        if trial.exists() and any(
            path.name not in {"attempt-1", "attempt-2"} or path.is_symlink() or not path.is_dir()
            for path in trial.iterdir()
        ):
            raise authored.PublicationError("unexpected heldout attempt")
        for number in range(1, state["attempts"] + 1):
            path = trial / f"attempt-{number}"
            if state["trial_id"] not in unavailable:
                store.verify_attempt(state["trial_id"], number)
            for item in path.rglob("*"):
                if item.is_symlink() or (not item.is_dir() and not stat.S_ISREG(item.lstat().st_mode)):
                    raise authored.PublicationError("unsafe heldout evidence node")
                if item.is_dir():
                    continue
                relative = item.relative_to(path)
                parts = relative.parts
                allowed = relative.as_posix() in authored.ATTEMPT_FILES
                allowed |= len(parts) == 2 and parts[0] == "agent" and parts[1] in authored.AGENT_FILES
                allowed |= (
                    len(parts) == 2 and parts[0] == "controller" and parts[1] in authored.CONTROLLER_FILES
                )
                if not allowed:
                    raise authored.PublicationError("non-whitelisted heldout evidence")
                result[item.relative_to(root).as_posix()] = authored._read_regular(item)
    return result


def _asset_tree(source, prefix):
    data, nodes = {}, {}
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if "__pycache__" in relative.parts:
            continue
        name = (Path(prefix) / relative).as_posix()
        mode = stat.S_IMODE(path.lstat().st_mode)
        if path.is_symlink() or mode & ~0o777:
            raise authored.PublicationError("unsupported released asset node or permission")
        if path.is_dir():
            nodes[name] = {"type": "directory", "mode": mode}
        elif stat.S_ISREG(path.lstat().st_mode):
            raw = authored._read_regular(path)
            data[name] = raw
            nodes[name] = {"type": "file", "mode": mode, "size": len(raw), "sha256": bytes_digest(raw)}
        else:
            raise authored.PublicationError("special node in released grading assets")
    return data, nodes


def _runs(root):
    return [
        {
            "run": path.name,
            "start": read_json(path / "start.json"),
            "end": read_json(path / "end.json") if (path / "end.json").is_file() else None,
            "subscription_permissions": [read_json(item) for item in sorted(path.glob("permission-*.json"))],
        }
        for path in sorted((root / "runs").glob("run-*"))
    ]


def _reports(root, store, schedule, unavailable, runs):
    rows, kernel_rows, attempts, replayed = _assessment(root, store, schedule, unavailable)
    analysis = analyze_workflows(rows, schedule=schedule)
    accounting = heldout_campaign.read_accounting_policy(root)
    analysis["all_attempt_resources"] = campaign._all_attempt_resources(
        attempts, schedule, accounting_policy=accounting
    )
    analysis["declared_unavailable_trials"] = sorted(unavailable)
    kernel = summarize_kernel(kernel_rows)
    kernel["scope"] = "held-out stopped-output decisions"
    return {
        "outcomes.json": rows,
        "analysis.json": analysis,
        "kernel.json": kernel,
        "attempts.json": attempts,
        "scheduler-runs.json": runs,
    }, replayed


def _report_checksums(reports, schedule):
    return {
        "schema_version": "evalopt.heldout-report-export.v1",
        "export_id": digest(reports),
        "schedule_sha256": digest(schedule),
        "files": {name: bytes_digest(canonical_bytes(value) + b"\n") for name, value in reports.items()},
    }


def _claims(reports, replayed):
    available = sum(row["valid_completion"] is not None for row in reports["outcomes.json"])
    headline = (
        "Scoped positive-result rule met under the registered conditions."
        if reports["analysis.json"]["scoped_positive_headline_permitted"]
        else "No registered positive-result headline is supported."
    )
    resource_accounting = reports["analysis.json"]["all_attempt_resources"].get("registered_accounting")
    accounting_limit = (
        "\nRegistered accounting reports exact complete counters separately from observed partial lower bounds. "
        "Unavailable consumption is unknown, not zero; missing usage has no inferred upper bound. "
        "Incomplete accounting cannot support a resource-efficiency advantage claim. "
        "Public accounting replay uses supplied sanitized controller counters, not raw native logs.\n"
        if resource_accounting is not None
        else ""
    )
    return (
        f"# Held-out claim-to-evidence table\n\n{headline}\n\n"
        "| Claim | Evidence and limit |\n| --- | --- |\n"
        f"| Primary outcomes | {available} available outcomes across 432 scheduled trials. Every explicitly unavailable outcome is listed in UNAVAILABLE.json and enters conservative comparison bounds. |\n"
        "| Workflow comparison | reports/analysis.json applies the frozen task-level C-minus-B rules, ordinary-completion guardrail and unfavorable missing-outcome assignment. |\n"
        "| Acceptance kernel | reports/kernel.json reports acceptance, coverage, false rejection, abstention, artifact failures and replay together. Missing grades do not become evidence of correctness. |\n"
        f"| Grading replay | {replayed} retained grade records reproduce from controller-supplied hidden-case replies and frozen contracts. This is pure grading replay, not independent candidate execution. |\n"
        "| Independent replication | Not established. This is a maintainer-run study with separated authoring and grading roles; hashes establish content identity, not producer authentication. |\n"
        "| Authored controls and external transfer | Separate evidence classes, not established by this held-out package. |\n\n"
        "Sealed tasks, hidden cases, controls, reference assets and registered benchmark source are included for subsequent isolated verification. Their presence does not establish that a verifier was re-executed. "
        "Resources for final and all retained attempts are reported separately; do not add them together. No dollar costs are invented.\n"
        + accounting_limit
    ).encode()


def _readme():
    return (
        b"# Held-out reproducibility package\n\n"
        b"Use CPython 3.13.12 exactly and the registered benchmark source. This offline exporter has not uploaded this folder.\n\n"
        b"    python bench/harbor/skill-workflows-v1/heldout_publish.py verify /path/to/bundle\n\n"
        b"This verifies bytes, asset node modes, registration, policy decisions and pure grading from supplied hidden-case replies. "
        b"It does not run candidate code or establish independent replication. Missing evidence is listed explicitly in UNAVAILABLE.json and enters conservative bounds. "
        b"Sealed task contracts, hidden cases, controls and reference assets are released under sealed-tasks/. "
        b"benchmark-source/runtime/Verifier.Dockerfile, requirements.lock, verify.py and the tasks suite preserve the isolated grader implementation. "
        b"Any subsequent candidate execution must use the original isolated verifier environment, never import candidate code into the host.\n"
        b"SYNTHETIC_FIXTURE_ALLOWANCES.json identifies the exact reviewed fake redaction-test fields by source hash, JSON pointer and value hash. Generic text patterns still scan unchanged bytes. Extending a known synthetic lineage requires explicit review with a source-hash and reason receipt; scoring and attempt data must never be rewritten. Unresolved publication evidence stays explicitly unavailable and counted in conservative bounds.\n"
    )


def _metadata(reports, schedule, registration_sha256, replayed):
    result = {
        "schema_version": "evalopt.heldout-public-evidence.v1",
        "heldout_registration_sha256": registration_sha256,
        "report_export_id": digest(reports),
        "schedule_sha256": digest(schedule),
        "scope": SCOPE,
        "grade_records_replayed": replayed,
        "candidate_execution_performed": False,
        "independent_replication": False,
        "network_publication_performed": False,
    }
    accounting = reports["analysis.json"]["all_attempt_resources"].get("registered_accounting")
    if accounting is not None:
        result["accounting"] = {
            "policy_sha256": accounting["policy_sha256"],
            "efficiency_comparison_eligible": accounting["efficiency_comparison_eligible"],
            "raw_native_log_replay": False,
        }
    return result


def export_public_bundle(
    campaign_directory, destination, *, registration_sha256, frozen_source=None, unavailable_receipt=None
):
    require_controller()
    root, destination = authored._safe_root(campaign_directory), authored._safe_root(destination)
    source = authored._safe_root(frozen_source or authored.HERE)
    if destination.exists() or destination.is_relative_to(root) or root.is_relative_to(destination):
        raise authored.PublicationError("heldout export requires a fresh destination outside the campaign")
    with authored._frozen_controller(root):
        if read_json(root / "registration-lock.json") != campaign._registration_identity(root):
            raise authored.PublicationError("private heldout registration changed")
        _, schedule, store = _check_heldout(root, registration_sha256, source)
        receipt = read_json(unavailable_receipt) if unavailable_receipt is not None else None
        receipt, unavailable = _unavailable(receipt, registration_sha256)
        reports, replayed = _reports(root, store, schedule, unavailable, _runs(root))
        payloads = _collect_evidence(root, store, unavailable)
        assets = {}
        for origin, prefix in ((root / "sealed-tasks", "sealed-tasks"), (source, "benchmark-source")):
            files, nodes = _asset_tree(origin, prefix)
            payloads.update(files)
            assets.update(nodes)
        payloads.update({name: authored._read_regular(root / name) for name in _root_files(root)})
        payloads.update(
            {"reports/" + name: canonical_bytes(value) + b"\n" for name, value in reports.items()}
        )
        payloads["reports/checksums.json"] = canonical_bytes(_report_checksums(reports, schedule)) + b"\n"
        payloads["ASSETS.json"] = (
            canonical_bytes({"schema_version": "evalopt.heldout-assets.v1", "nodes": assets}) + b"\n"
        )
        payloads["UNAVAILABLE.json"] = canonical_bytes(receipt) + b"\n"
        payloads["CLAIMS.md"], payloads["README.md"] = _claims(reports, replayed), _readme()
        payloads["PUBLICATION.json"] = (
            canonical_bytes(_metadata(reports, schedule, registration_sha256, replayed)) + b"\n"
        )
        allowances = scan_heldout_payloads(payloads, schedule)
        payloads["SYNTHETIC_FIXTURE_ALLOWANCES.json"] = canonical_bytes(allowances) + b"\n"
        authored.scan_public_file(
            "SYNTHETIC_FIXTURE_ALLOWANCES.json", payloads["SYNTHETIC_FIXTURE_ALLOWANCES.json"]
        )
        checksums = {
            name: {"size": len(raw), "sha256": bytes_digest(raw)} for name, raw in sorted(payloads.items())
        }
        payloads["CHECKSUMS.json"] = (
            canonical_bytes(
                {
                    "schema_version": "evalopt.heldout-public-checksums.v1",
                    "bundle_id": digest(checksums),
                    "files": checksums,
                }
            )
            + b"\n"
        )
        destination.mkdir(parents=True)
        for name, record in sorted(assets.items()):
            if record["type"] == "directory":
                (destination / name).mkdir(parents=True, exist_ok=True)
        for name, raw in sorted(payloads.items()):
            path = destination / authored._safe_relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(raw)
            if name in assets:
                path.chmod(assets[name]["mode"])
        for name, record in assets.items():
            if record["type"] == "directory":
                (destination / name).chmod(record["mode"])
        return verify_public_bundle(destination)


def verify_public_bundle(directory):
    require_controller()
    root = authored._safe_root(directory)
    checksum_raw = authored._read_regular(root / "CHECKSUMS.json")
    authored.scan_public_file("CHECKSUMS.json", checksum_raw)
    checksums = json.loads(checksum_raw)
    if (
        not isinstance(checksums, dict)
        or set(checksums) != {"schema_version", "bundle_id", "files"}
        or checksums["schema_version"] != "evalopt.heldout-public-checksums.v1"
        or not isinstance(checksums["files"], dict)
        or digest(checksums["files"]) != checksums["bundle_id"]
    ):
        raise authored.PublicationError("invalid heldout public checksum envelope")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink() or (not path.is_dir() and not stat.S_ISREG(path.lstat().st_mode)):
            raise authored.PublicationError("unsafe public heldout node")
        if path.is_file() and path != root / "CHECKSUMS.json":
            actual.add(path.relative_to(root).as_posix())
    if actual != set(checksums["files"]):
        raise authored.PublicationError("unexpected or missing heldout publication files")
    asset_manifest = read_json(root / "ASSETS.json")
    exact(asset_manifest, {"schema_version", "nodes"}, "released asset manifest")
    if asset_manifest["schema_version"] != "evalopt.heldout-assets.v1":
        raise authored.PublicationError("unsupported released asset manifest")
    actual_assets = {}
    for prefix in ("sealed-tasks", "benchmark-source"):
        _, nodes = _asset_tree(root / prefix, prefix)
        actual_assets.update(nodes)
    if actual_assets != asset_manifest["nodes"]:
        raise authored.PublicationError("released asset bytes, nodes or modes changed")
    payloads = {}
    for name, record in checksums["files"].items():
        parts = authored._safe_relative(name).parts
        allowed = name in _root_files(root) | {
            "ASSETS.json",
            "SYNTHETIC_FIXTURE_ALLOWANCES.json",
            "UNAVAILABLE.json",
            "CLAIMS.md",
            "README.md",
            "PUBLICATION.json",
            "evidence/schedule.json",
        }
        allowed |= name in actual_assets and actual_assets[name]["type"] == "file"
        allowed |= len(parts) == 2 and parts[0] == "reports" and parts[1] in REPORT_FILES | {"checksums.json"}
        if (
            len(parts) in {5, 6}
            and parts[:2] == ("evidence", "trials")
            and parts[3] in {"attempt-1", "attempt-2"}
        ):
            allowed |= len(parts) == 5 and parts[4] in authored.ATTEMPT_FILES
            allowed |= len(parts) == 6 and parts[4] == "agent" and parts[5] in authored.AGENT_FILES
            allowed |= len(parts) == 6 and parts[4] == "controller" and parts[5] in authored.CONTROLLER_FILES
        if not allowed:
            raise authored.PublicationError("non-whitelisted heldout public file")
        raw = authored._read_regular(root / name)
        if record != {"size": len(raw), "sha256": bytes_digest(raw)}:
            raise authored.PublicationError("heldout public artifact changed")
        payloads[name] = raw
    publication = read_json(root / "PUBLICATION.json")
    registration_sha256 = publication["heldout_registration_sha256"]
    _, schedule, store = _check_heldout(root, registration_sha256, root / "benchmark-source")
    allowances = scan_heldout_payloads(payloads, schedule)
    if read_json(root / "SYNTHETIC_FIXTURE_ALLOWANCES.json") != allowances:
        raise authored.PublicationError(
            "synthetic fixture allowance differs from exact source and case provenance"
        )
    receipt, unavailable = _unavailable(read_json(root / "UNAVAILABLE.json"), registration_sha256)
    _collect_evidence(root, store, unavailable)
    reports, replayed = _reports(
        root, store, schedule, unavailable, read_json(root / "reports/scheduler-runs.json")
    )
    for name, value in reports.items():
        if authored._read_regular(root / "reports" / name) != canonical_bytes(value) + b"\n":
            raise authored.PublicationError("heldout analysis does not reproduce registered evidence")
    if read_json(root / "reports/checksums.json") != _report_checksums(reports, schedule):
        raise authored.PublicationError("heldout report checksum envelope differs")
    if (
        authored._read_regular(root / "CLAIMS.md") != _claims(reports, replayed)
        or authored._read_regular(root / "README.md") != _readme()
        or publication != _metadata(reports, schedule, registration_sha256, replayed)
    ):
        raise authored.PublicationError("heldout publication claims differ from evidence")
    return {
        "schema_version": "evalopt.heldout-public-verification.v1",
        "bundle_id": checksums["bundle_id"],
        "scheduled_trials": 432,
        "declared_unavailable_trials": len(unavailable),
        "released_tasks": 48,
        "grade_records_replayed": replayed,
        "policy_analysis_reproduced": True,
        "candidate_execution_performed": False,
        "independent_replication": False,
        "sensitive_scan_passed": True,
        "network_publication_performed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--campaign", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    export.add_argument("--registration-sha256", required=True)
    export.add_argument("--frozen-source", type=Path)
    export.add_argument("--unavailable-receipt", type=Path)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    result = (
        export_public_bundle(
            args.campaign,
            args.destination,
            registration_sha256=args.registration_sha256,
            frozen_source=args.frozen_source,
            unavailable_receipt=args.unavailable_receipt,
        )
        if args.command == "export"
        else verify_public_bundle(args.directory)
    )
    print(canonical_bytes(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
