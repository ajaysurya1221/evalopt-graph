#!/usr/bin/env python3
"""Offline transfer evidence projection. Does not publish raw archives or run verifiers."""

from __future__ import annotations

import argparse
import json
import stat
from pathlib import Path

import publish_bundle as authored
import transfer_campaign
from lib.common import bytes_digest, canonical_bytes, digest, is_digest, read_json
from runtime.controller import require_controller
from runtime.harbor_campaign import source_identity
from transfer_store import TransferStore

ROOT_FILES = {
    "manifest.json",
    "preparation.json",
    "readiness.json",
    "source-lock.json",
    "registration-lock.json",
    "primary-evidence.json",
}
REPORT_FILES = {"outcomes.json", "analysis.json", "attempts.json", "scheduler-runs.json"}
ATTEMPT_FILES = {"start.json", "transfer-result.json", "finish.json", "finalize.json", "manifest.json"}
SCOPE = "controller-retained original verifier rewards; raw archives and trajectories excluded; no independent verifier reproduction or U/M/G"


def _root_files(manifest):
    return ROOT_FILES | (
        {"accounting-policy.json"}
        if manifest.get("schema_version") == "evalopt.transfer-campaign.v2"
        else set()
    )


def _registration(directory, *, private):
    manifest = read_json(directory / "manifest.json")
    registered_files = transfer_campaign.registered_files(manifest)
    registration = read_json(directory / "registration-lock.json")
    if set(registration) != set(registered_files) or any(
        not is_digest(value) for value in registration.values()
    ):
        raise authored.PublicationError("unsupported transfer registration lock")
    names = (
        registered_files
        if private
        else tuple((_root_files(manifest) - {"registration-lock.json"}) | {"evidence/schedule.json"})
    )
    for name in names:
        if bytes_digest(authored._read_regular(directory / name)) != registration[name]:
            raise authored.PublicationError("transfer registration changed")
    prepared = read_json(directory / "preparation.json")
    if bytes_digest(authored._read_regular(directory / "preparation.json")) != manifest["preparation_sha256"]:
        raise authored.PublicationError("transfer preparation identity changed")
    schedule = transfer_campaign.validate_manifest(manifest, prepared)
    transfer_campaign.validate_primary_receipt(
        read_json(directory / "primary-evidence.json"), manifest, prepared
    )
    expected = {
        "schema_version": "evalopt.workflow-schedule.v1",
        "schedule": schedule,
        "schedule_sha256": digest(schedule),
    }
    if read_json(directory / "evidence/schedule.json") != expected:
        raise authored.PublicationError("transfer schedule changed")
    lock = read_json(directory / "source-lock.json")
    if lock["campaign_sha256"] != source_identity(transfer_campaign.ROOT) or lock[
        "library_sha256"
    ] != source_identity(transfer_campaign.ROOT / "lib"):
        raise authored.PublicationError(
            "use the registered transfer source and Python version for reproduction"
        )
    store = object.__new__(TransferStore)
    store.root = authored._safe_root(directory / "evidence")
    store.schedule_sha256 = digest(schedule)
    store.trials = {row["trial_id"]: row for row in schedule}
    store.accounting_policy = transfer_campaign.read_accounting_policy(directory, manifest)
    return schedule, store


def _evidence(directory, store):
    result = {"evidence/schedule.json": authored._read_regular(directory / "evidence/schedule.json")}
    root = directory / "evidence"
    if {path.name for path in root.iterdir()} - {"schedule.json", "trials"}:
        raise authored.PublicationError("unexpected transfer evidence entry")
    trials = root / "trials"
    if trials.exists() and any(
        path.name not in store.trials or not path.is_dir() or path.is_symlink() for path in trials.iterdir()
    ):
        raise authored.PublicationError("unscheduled transfer evidence")
    for state in store.statuses():
        trial = trials / state["trial_id"]
        if trial.exists() and any(
            path.name not in {"attempt-1", "attempt-2"} or not path.is_dir() or path.is_symlink()
            for path in trial.iterdir()
        ):
            raise authored.PublicationError("unexpected transfer attempt")
        for attempt in range(1, state["attempts"] + 1):
            path = trial / f"attempt-{attempt}"
            if not (path / "finish.json").is_file() or not (path / "manifest.json").is_file():
                raise authored.PublicationError("transfer attempt is not finalized")
            store.verify_attempt(state["trial_id"], attempt)
            for item in path.iterdir():
                if (
                    item.name not in ATTEMPT_FILES
                    or item.is_symlink()
                    or not stat.S_ISREG(item.lstat().st_mode)
                ):
                    raise authored.PublicationError("private or non-whitelisted transfer evidence artifact")
                result[item.relative_to(directory).as_posix()] = authored._read_regular(item)
    return result


def _runs(directory):
    result = []
    for path in sorted((directory / "runs").glob("run-*")):
        if not (path / "end.json").is_file():
            raise authored.PublicationError("transfer scheduler run remains unfinished")
        result.append(
            {
                "run": path.name,
                "start": read_json(path / "start.json"),
                "end": read_json(path / "end.json"),
                "subscription_permissions": [
                    read_json(item) for item in sorted(path.glob("permission-*.json"))
                ],
            }
        )
    return result


def _report_checksums(payloads, schedule):
    return {
        "schema_version": "evalopt.transfer-export.v1",
        "export_id": digest(payloads),
        "schedule_sha256": digest(schedule),
        "files": {name: bytes_digest(canonical_bytes(value) + b"\n") for name, value in payloads.items()},
    }


def _claims(payloads):
    rows = payloads["outcomes.json"]
    available = sum(row["upstream_reward"] is not None for row in rows)
    accounting_scope = ""
    if payloads["analysis.json"]["schema_version"] == "evalopt.transfer-report.v2":
        accounting_scope = (
            "| Registered resource accounting | The primary study's identical accounting policy governs source-bound sanitized counters. "
            "Complete observations and partial lower bounds are reported separately; partial usage cannot support efficiency comparisons. "
            "Public reproduction checks retained counter arithmetic, not raw native logs or independent authentication. |\n"
            "| Execution boundary | Partial usage approval does not establish process termination or verifier isolation. "
            "Runtime admissibility requires native stop, execution boundary and workflow exposure; runtime evidence completeness remains false for partial usage. |\n"
        )
    return (
        "# Transfer claim-to-evidence table\n\n"
        "No primary upgrade headline follows from this feasibility subset.\n\n"
        "| Claim | Evidence and limit |\n| --- | --- |\n"
        f"| Original verifier rewards | {available} available rewards across {len(rows)} scheduled B/C trials; reports/outcomes.json preserves rewards even after timeouts. |\n"
        "| Transfer scope | Terminal-Bench 2.0 feasibility subset only; not an official leaderboard score. Original task/verifier limits and services are required. |\n"
        "| Reproduction | Checksums, attempt integrity, registered schedule and reward aggregation reproduce from this folder. Original verifiers and private stopped archives are not re-executed. |\n"
        "| Acceptance kernel | Not applicable. This stage has no U/M/G decisions and no authored-suite hidden grade. |\n"
        "| Independent replication | Not established. Controller records are a maintainer-run study; hashes establish content identity, not authorship or independent correctness. |\n"
        "| Authored controls and live comparison | Not contained in this transfer evidence class. Refer to separately scoped authored-suite artifacts. |\n"
        + accounting_scope
        + "\n"
        "All-attempt resources include original and infrastructure retry attempts once each. Missing rewards and incomplete runtime/capture evidence remain visible. No dollar costs are invented.\n"
    ).encode()


def _metadata(payloads, schedule):
    version_two = payloads["analysis.json"]["schema_version"] == "evalopt.transfer-report.v2"
    result = {
        "schema_version": "evalopt.transfer-public-evidence." + ("v2" if version_two else "v1"),
        "report_export_id": digest(payloads),
        "schedule_sha256": digest(schedule),
        "scope": SCOPE,
        "raw_archives_included": False,
        "independent_replication": False,
        "network_publication_performed": False,
    }
    if version_two:
        result.update(
            accounting_policy_sha256=payloads["analysis.json"]["accounting_policy_sha256"],
            accounting_reproduction="retained source-bound counter arithmetic; no raw native log replay or independent authentication",
            efficiency_comparison_eligible=payloads["analysis.json"]["all_attempt_resources"][
                "registered_accounting"
            ]["efficiency_comparison_eligible"],
        )
    return result


def _readme():
    return (
        b"# Transfer evidence candidate\n\n"
        b"This offline candidate contains allowlisted controller reward projections and retained identities. "
        b"Raw stopped archives, private paths, authentication and trajectories are excluded. The projection is "
        b"explicitly recorded in each retained transfer result; no hash-bound artifact is silently redacted.\n\n"
        b"Verify with the registered source and CPython 3.13.12 exactly:\n\n"
        b"    python bench/harbor/skill-workflows-v1/transfer_publish.py verify /path/to/bundle\n\n"
        b"The bounded sensitive-content scanner is a publication check, not a proof that every possible secret has been detected. See CLAIMS.md for reproduction limits.\n"
    )


def export_public_bundle(directory, destination):
    require_controller()
    directory, destination = authored._safe_root(directory), authored._safe_root(destination)
    if destination.exists() or destination.is_relative_to(directory) or directory.is_relative_to(destination):
        raise authored.PublicationError("transfer publication needs a fresh destination outside the campaign")
    with authored._frozen_controller(directory):
        schedule, store = _registration(directory, private=True)
        payloads = _evidence(directory, store)
        reports = transfer_campaign.report_payloads(store, schedule, _runs(directory))
        if any(not row["artifact_valid"] for row in reports["attempts.json"]):
            raise authored.PublicationError("invalid transfer artifacts cannot be published")
        export = directory / "exports" / digest(reports)
        expected_checksums = _report_checksums(reports, schedule)
        if read_json(export / "checksums.json") != expected_checksums:
            raise authored.PublicationError("transfer report checksum envelope differs")
        for name, value in reports.items():
            raw = authored._read_regular(export / name)
            if raw != canonical_bytes(value) + b"\n":
                raise authored.PublicationError("transfer report does not reproduce retained rewards")
            payloads["reports/" + name] = raw
        payloads["reports/checksums.json"] = authored._read_regular(export / "checksums.json")
        payloads.update(
            {
                name: authored._read_regular(directory / name)
                for name in _root_files(read_json(directory / "manifest.json"))
            }
        )
        payloads["CLAIMS.md"], payloads["README.md"] = _claims(reports), _readme()
        payloads["PUBLICATION.json"] = canonical_bytes(_metadata(reports, schedule)) + b"\n"
        for name, data in payloads.items():
            authored.scan_public_file(name, data)
        checksums = {
            name: {"size": len(data), "sha256": bytes_digest(data)} for name, data in sorted(payloads.items())
        }
        payloads["CHECKSUMS.json"] = (
            canonical_bytes(
                {
                    "schema_version": "evalopt.transfer-public-checksums.v1",
                    "bundle_id": digest(checksums),
                    "files": checksums,
                }
            )
            + b"\n"
        )
        destination.mkdir(parents=True)
        for name, data in sorted(payloads.items()):
            path = destination / authored._safe_relative(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(data)
        return verify_public_bundle(destination)


def verify_public_bundle(directory):
    require_controller()
    directory = authored._safe_root(directory)
    checksum_raw = authored._read_regular(directory / "CHECKSUMS.json")
    authored.scan_public_file("CHECKSUMS.json", checksum_raw)
    checksum = json.loads(checksum_raw)
    if (
        not isinstance(checksum, dict)
        or set(checksum) != {"schema_version", "bundle_id", "files"}
        or checksum["schema_version"] != "evalopt.transfer-public-checksums.v1"
        or not isinstance(checksum["files"], dict)
        or digest(checksum["files"]) != checksum["bundle_id"]
    ):
        raise authored.PublicationError("invalid transfer public checksum envelope")
    actual = set()
    for item in directory.rglob("*"):
        if item.is_symlink() or (not item.is_dir() and not stat.S_ISREG(item.lstat().st_mode)):
            raise authored.PublicationError("unsafe node in transfer public candidate")
        if item.is_file() and item != directory / "CHECKSUMS.json":
            actual.add(item.relative_to(directory).as_posix())
    if actual != set(checksum["files"]):
        raise authored.PublicationError("unexpected or missing public transfer files")
    root_files = _root_files(read_json(directory / "manifest.json"))
    for name, record in checksum["files"].items():
        parts = authored._safe_relative(name).parts
        allowed = name in root_files | {
            "CLAIMS.md",
            "README.md",
            "PUBLICATION.json",
            "evidence/schedule.json",
        }
        allowed |= len(parts) == 2 and parts[0] == "reports" and parts[1] in REPORT_FILES | {"checksums.json"}
        allowed |= (
            len(parts) == 5
            and parts[:2] == ("evidence", "trials")
            and parts[3] in {"attempt-1", "attempt-2"}
            and parts[4] in ATTEMPT_FILES
        )
        if not allowed:
            raise authored.PublicationError("non-whitelisted transfer publication file")
        raw = authored._read_regular(directory / name)
        if record != {"size": len(raw), "sha256": bytes_digest(raw)}:
            raise authored.PublicationError("transfer public artifact changed")
        authored.scan_public_file(name, raw)
    schedule, store = _registration(directory, private=False)
    _evidence(directory, store)
    reports = transfer_campaign.report_payloads(
        store, schedule, read_json(directory / "reports/scheduler-runs.json")
    )
    if any(not row["artifact_valid"] for row in reports["attempts.json"]):
        raise authored.PublicationError("transfer attempt integrity failed")
    for name, value in reports.items():
        if authored._read_regular(directory / "reports" / name) != canonical_bytes(value) + b"\n":
            raise authored.PublicationError("transfer report does not reproduce retained rewards")
    if read_json(directory / "reports/checksums.json") != _report_checksums(reports, schedule):
        raise authored.PublicationError("transfer report checksum envelope differs")
    if (
        authored._read_regular(directory / "CLAIMS.md") != _claims(reports)
        or authored._read_regular(directory / "README.md") != _readme()
        or read_json(directory / "PUBLICATION.json") != _metadata(reports, schedule)
    ):
        raise authored.PublicationError("transfer publication scope differs from evidence")
    return {
        "schema_version": "evalopt.transfer-public-verification.v1",
        "bundle_id": checksum["bundle_id"],
        "files": len(actual),
        "attempts_verified": len(reports["attempts.json"]),
        "reward_analysis_reproduced": True,
        "policy_replay": "not applicable; no U/M/G",
        "original_verifier_reexecuted": False,
        "raw_archives_included": False,
        "sensitive_scan_passed": True,
        "network_publication_performed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--campaign", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    result = (
        export_public_bundle(args.campaign, args.destination)
        if args.command == "export"
        else verify_public_bundle(args.directory)
    )
    print(canonical_bytes(result).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
