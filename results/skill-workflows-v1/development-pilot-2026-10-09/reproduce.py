#!/usr/bin/env python3
"""Offline arithmetic and evidence replay; never execute stopped candidate code."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import stat
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

PILOT_BUNDLE = "9a487b2185886e3ad0e3bbbc1ff1d60500c4c2bfcf14385d07e49e0745b4fd6b"
ARCHIVE_BUNDLE = "69d0c6594ecdf533be7aff81204512788820140d4255efb6adf001d66ee38630"
OVERHEAD_BUNDLE = "99da26670bf4d5676fa5af0fe37d33f4a26137577e80c2896c7fded5fb516d4a"
AMENDMENT = "29c2c08cdd2599546d104ec0fb2c02211323c29d11f5f0f8a6d5240c0906e5cd"
ORIGINAL_EXPORT = "7c4bc4b91d4535491d9197711a2c3fc83e35f0931542a395a24ac61dfcdb340b"
COUNTERS = ("input_tokens", "output_tokens", "model_calls", "tool_calls")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    require(stat.S_ISREG(path.lstat().st_mode), "nonregular evidence file")
    return path.read_bytes()


def parse(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def number(value):
        result = float(value)
        require(math.isfinite(result), "nonfinite JSON number")
        return result

    def constant(_value):
        raise ValueError("nonfinite JSON constant")

    return json.loads(read(path), object_pairs_hook=pairs, parse_float=number, parse_constant=constant)


def files(root, *, ignore_cache=False):
    require(root.is_dir() and not root.is_symlink(), "missing or symlink evidence directory")
    result = {}
    for path in sorted(root.rglob("*")):
        if ignore_cache and "__pycache__" in path.relative_to(root).parts:
            continue
        mode = path.lstat().st_mode
        require(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "nonregular evidence node")
        if stat.S_ISREG(mode):
            result[path.relative_to(root).as_posix()] = read(path)
    return result


def verify_checksums(root, schema, *, expected=None):
    payloads = files(root)
    require("CHECKSUMS.json" in payloads, "final outer checksums are unavailable")
    envelope = parse(root / "CHECKSUMS.json")
    require(
        isinstance(envelope, dict)
        and set(envelope) == {"schema_version", "bundle_id", "files"}
        and envelope["schema_version"] == schema,
        "invalid checksum envelope",
    )
    actual = {
        name: {"sha256": sha(raw), "size": len(raw)}
        for name, raw in payloads.items()
        if name != "CHECKSUMS.json"
    }
    require(canonical(envelope["files"]) == canonical(actual), "checksum or file roster changed")
    require(envelope["bundle_id"] == sha(canonical(actual)), "checksum bundle identity changed")
    require(expected is None or envelope["bundle_id"] == expected, "unexpected retained bundle")
    return envelope["bundle_id"]


def tree_identity(root):
    manifest = {name: sha(raw) for name, raw in files(root, ignore_cache=True).items()}
    return sha(json.dumps(manifest, sort_keys=True).encode())


def verify_overhead(root, source):
    overhead = root / "overhead"
    verify_checksums(overhead, "evalopt.overhead-draft-checksums.v1", expected=OVERHEAD_BUNDLE)
    ledger = parse(overhead / "overhead-ledger.json")
    probes = parse(overhead / "capability-probes.json")["probes"]
    rows = ledger["records"]
    require(len({row["record_id"] for row in rows}) == len(rows), "duplicate overhead record")
    require(len({probe["probe_id"] for probe in probes}) == len(probes), "duplicate probe")
    by_id = {row["record_id"]: row for row in rows}
    provenance = ledger["provenance"]
    capability = provenance["capability_source"]
    raw = read(overhead / "capability-probes.json")
    require(sha(raw) == capability["sha256"], "capability source changed")
    require(
        read(source / "bench/harbor/skill-workflows-v1/evidence/capability-probes.json") == raw,
        "capability evidence differs from trusted checkout",
    )
    totals, seconds, complete, unknown = dict.fromkeys(COUNTERS, 0), Decimal(0), 0, 0
    for index, probe in enumerate(probes):
        row = by_id[probe["probe_id"]]
        require(row["kind"] == "capability_probe", "probe kind changed")
        require(row["source_pointer"] == f"/probes/{index}", "probe source pointer changed")
        if probe["usage"] is None:
            require(
                row["accounting_status"] == "unavailable"
                and row["dispatch_status"] == "unknown"
                and row["exact_usage"] is None,
                "missing probe telemetry must remain unavailable with unknown dispatch",
            )
            unknown += 1
            continue
        events = probe["usage_events"]
        parents = [event for event in events if event["parent_id"] is None]
        require(len(parents) == 1, "probe requires one parent")
        parent = parents[0]
        ids = {event["agent_id"] for event in events}
        require(len(ids) == len(events) and set(parent["roster"]) == ids, "invalid probe roster")
        require(probe["usage"]["agent_count"] == len(events), "probe agent count changed")
        for event in events:
            require(event["complete"] is True and event["scope"] == "agent_exclusive", "incomplete probe")
            require(all(type(event[key]) is int and event[key] >= 0 for key in COUNTERS), "invalid counter")
            require(
                event is parent
                or (event["parent_id"] == parent["agent_id"] and event["roster"] == [event["agent_id"]]),
                "unexpected child ancestry or copied parent history",
            )
        measured = {key: sum(event[key] for event in events) for key in COUNTERS}
        require(all(measured[key] == probe["usage"][key] for key in COUNTERS), "probe arithmetic differs")
        require(parent["wall_seconds"] == probe["usage"]["wall_seconds"], "parent wall interval differs")
        exact_usage = {**measured, "parent_wall_seconds": str(Decimal(str(parent["wall_seconds"])))}
        require(
            canonical(row["exact_usage"]) == canonical(exact_usage)
            and row["accounting_status"] == "complete"
            and row["dispatch_status"] == "confirmed_by_retained_complete_telemetry"
            and row["private_summary_sha256"] == probe["private_summary_sha256"],
            "complete overhead row differs from exclusive events",
        )
        for key in COUNTERS:
            totals[key] += measured[key]
        seconds += Decimal(exact_usage["parent_wall_seconds"])
        complete += 1
    original = provenance["original_attempt"]
    finish_raw, manifest_raw = (
        read(overhead / original["finish_file"]),
        read(overhead / original["manifest_file"]),
    )
    require(
        sha(finish_raw) == original["finish_sha256"] and sha(manifest_raw) == original["manifest_sha256"],
        "original attempt identity changed",
    )
    finish, manifest = parse(overhead / original["finish_file"]), parse(overhead / original["manifest_file"])
    bindings = [item for item in manifest["artifacts"] if item["path"] == "finish.json"]
    require(
        len(bindings) == 1
        and bindings[0]["sha256"] == sha(finish_raw)
        and bindings[0]["size"] == len(finish_raw),
        "original finish manifest binding changed",
    )
    require(finish["usage"]["accounting_status"] == "unavailable", "original unavailable usage changed")
    archived = list((root / "original-pilot-overhead/evidence/trials").glob("*/attempt-*/finish.json"))
    require(
        len(archived) == 1
        and read(archived[0]) == finish_raw
        and read(archived[0].parent / "manifest.json") == manifest_raw,
        "archived overhead attempt is not the same event",
    )
    repairs = [row for row in rows if row["kind"] == "development_repair_attempt"]
    require(len(repairs) == 1, "extra or missing development repair attempt")
    repair = repairs[0]
    require(
        repair["source_finish_sha256"] == sha(finish_raw)
        and repair["source_manifest_sha256"] == sha(manifest_raw)
        and repair["retained_status"] == finish["status"]
        and repair["dispatch_status"] == "confirmed_by_retained_attempt"
        and repair["accounting_status"] == "unavailable"
        and repair["exact_usage"] is None,
        "repair attempt ledger differs from archive",
    )
    mirror = provenance["readiness_mirror"]
    require(
        mirror["additional_counted_events"] == 0
        and mirror["mirrors_record_id"] == "preflight-native-04"
        and mirror["private_summary_sha256"] == by_id["preflight-native-04"]["private_summary_sha256"],
        "readiness probe was counted twice or changed",
    )
    expected = {
        "records": len(probes) + 1,
        "complete_capability_probes": complete,
        "retained_development_repair_attempts": 1,
        "unavailable_accounting_records": unknown + 1,
        "unknown_dispatch_records": unknown,
        "observed_complete_probe_totals": {**totals, "parent_wall_seconds": str(seconds)},
        "complete_total_for_all_listed_overhead": False,
        "efficiency_comparison_eligible": False,
        "dollar_cost": None,
    }
    require(
        len(rows) == len(probes) + 1 and canonical(ledger["summary"]) == canonical(expected),
        "overhead summary differs from retained events",
    )
    return expected


def reproduce(source):
    require(
        platform.python_implementation() == "CPython" and sys.version_info[:3] == (3, 13, 12),
        "CPython 3.13.12 is required",
    )
    require(sys.flags.isolated == 1, "run Python with -I to isolate imports")
    root = Path(__file__).resolve().parent
    require(
        (root / "regrade-receipt.json").is_file() and (root / "regrade/registration.json").is_file(),
        "registered regrade evidence is pending; complete release replay is unavailable",
    )
    bundle = verify_checksums(root, "evalopt.pilot-release-checksums.v1")
    source = source.resolve(strict=True)
    benchmark = source / "bench/harbor/skill-workflows-v1"
    registration = parse(root / "regrade/registration.json")
    receipt = parse(root / "regrade-receipt.json")
    require(
        sha(canonical(registration)) == receipt["registration_sha256"],
        "regrade registration differs from receipt",
    )
    pins = registration["source_pins"]
    require(
        tree_identity(benchmark) == pins["benchmark_source_sha256"],
        "use the exact trusted registered benchmark source",
    )
    require(
        sha(read(benchmark / "pilot_regrade.py")) == pins["controller_sha256"]
        and sha(read(benchmark / "runtime/regrade_bridge.py")) == pins["baseline_bridge_sha256"],
        "registered regrade controller changed",
    )
    lock = parse(root / "pilot/pilot/source-lock.json")
    require(
        tree_identity(source / "src/evalopt_graph") == lock["kernel_source_sha256"],
        "use the registered kernel source",
    )
    overhead = verify_overhead(root, source)
    # No artifact directory is importable. A fresh cache also excludes stale or poisoned bytecode.
    with tempfile.TemporaryDirectory(prefix="evalopt-public-replay-") as cache:
        sys.pycache_prefix = cache
        sys.dont_write_bytecode = True
        sys.path[:0] = [str(benchmark), str(source / "src")]
        import amended_publish
        import pilot_regrade
        import publish_bundle

        amended = amended_publish.verify_public_bundle(
            root / "pilot", amendment_sha256=AMENDMENT, bundle_id=PILOT_BUNDLE
        )
        archive = publish_bundle.verify_public_bundle(root / "original-pilot-overhead")
        require(
            archive["bundle_id"] == ARCHIVE_BUNDLE and archive["attempts_verified"] == 1,
            "original pilot archive identity changed",
        )
        regraded = pilot_regrade.verify_evidence(
            root / "regrade/registration.json",
            registration_sha256=receipt["registration_sha256"],
            evidence_sha256=receipt["evidence_sha256"],
            current_grading=registration["grading"]["current"],
        )
        require(
            canonical(regraded) == canonical(receipt), "regrade receipt differs from full evidence replay"
        )
        require(
            set(pilot_regrade.public_payloads(root / "regrade/registration.json"))
            == set(files(root / "regrade")),
            "nonpublic or unregistered regrade artifact",
        )
    resources = parse(root / "pilot/resource-report.json")
    require(
        receipt["pilot_export_id"] == ORIGINAL_EXPORT == resources["frozen_export_id"],
        "regrade points to a different original pilot export",
    )
    require(
        receipt["accounting_amendment_sha256"] == AMENDMENT
        and receipt["pilot_registration_sha256"] == resources["pilot_registration_sha256"]
        and receipt["schedule_sha256"] == resources["schedule_sha256"],
        "regrade and pilot identities differ",
    )
    for attempt in registration["attempts"]:
        trial = attempt["trial_id"]
        original_root = root / "pilot/pilot/evidence/trials" / trial / "attempt-1"
        regrade_root = root / "regrade/inputs" / trial
        for name, expected in attempt["original_files"].items():
            original_raw = read(original_root / name)
            require(
                sha(original_raw) == expected and read(regrade_root / name) == original_raw,
                "regrade inputs differ from the fixed original public pilot bundle",
            )
    outcomes = parse(root / "pilot/pilot/reports/outcomes.json")
    require(len(outcomes) == len({row["trial_id"] for row in outcomes}) == 36, "pilot denominator changed")
    original = {
        arm: {
            "scheduled": sum(row["arm"] == arm for row in outcomes),
            "valid_completion": sum(
                row["arm"] == arm and row["valid_completion"] is True for row in outcomes
            ),
        }
        for arm in "ABC"
    }
    require(
        all(row == {"scheduled": 12, "valid_completion": 12} for row in original.values()),
        "descriptive original pilot totals changed",
    )
    require(
        resources["efficiency_comparison_eligible"] is False,
        "partial accounting cannot support efficiency comparison",
    )
    return {
        "schema_version": "evalopt.pilot-release-replay.v1",
        "bundle_id": bundle,
        "original_pilot": original,
        "pilot_policy_decisions_replayed": amended["policy_decisions_replayed"],
        "regrade": receipt,
        "overhead": overhead,
        "candidate_execution_performed": False,
        "raw_native_log_replay": False,
        "independent_replication": False,
        "efficiency_comparison_eligible": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="trusted repository checkout matching registered source hashes",
    )
    args = parser.parse_args()
    try:
        print(json.dumps(reproduce(args.source), indent=2, sort_keys=True))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, f"Replay failed: {error}\n")


if __name__ == "__main__":
    main()
