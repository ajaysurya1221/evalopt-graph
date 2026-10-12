#!/usr/bin/env python3
"""Private exact-finding adjudication; original stock scanner failure is retained."""

import sys

if __name__ == "__main__" and (not sys.flags.isolated or not sys.flags.dont_write_bytecode):
    raise SystemExit("Run with python -I -B.")

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import stat
import subprocess
from pathlib import Path

HEAD = "49a379c7001b5b156f9f75b358da03a4367b252e"
SCANNER_SHA = "f414bc2fb952be6c9072b75cb411e3368614ef4b16d48dbd9ad238034afd2302"
CONFIG_SHA = "be739780ff6fb9d3eee469a149acb6a56ac3c00586fe45ac90b6eeeef748f96a"
DIAGNOSIS_SHA = "3ccdb27be0321b052a17bc693239b456fa07ae34943d1536235747af015b7fbc"
EXPECTED_SHA = "943d01b687acbb2ca53d75951d4d51fa0f34f96ad1b79adb645c582b822c6c98"
GIT_SHA = "34129c71a01a74f7f3b2443521519b2e5447553fa187f5fcafaaf8c42cc192e2"
SCHEMA = "evalopt-ci-adjudication/1"
COMMAND = [
    "gitleaks",
    "git",
    "--redact=100",
    "--no-color",
    "--no-banner",
    "--config",
    ".gitleaks.toml",
    "--log-opts=--all",
    "--report-format",
    "json",
    "--report-path",
    "<report>",
    ".",
]
FIELDS = {
    "Author",
    "Commit",
    "Date",
    "Description",
    "Email",
    "EndColumn",
    "EndLine",
    "Entropy",
    "File",
    "Fingerprint",
    "Link",
    "Match",
    "Message",
    "RuleID",
    "Secret",
    "StartColumn",
    "StartLine",
    "SymlinkFile",
    "Tags",
}

PROJECTION_FIELDS = {
    "Fingerprint",
    "Commit",
    "File",
    "StartLine",
    "EndLine",
    "StartColumn",
    "EndColumn",
    "RuleID",
    "classification",
    "matched_line_sha256",
    "retained_file_sha256",
    "source_file",
    "source_git_blob",
}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    ).encode()


def digest(value):
    return sha(canonical(value))


def regular(path, limit=16 * 1024 * 1024):
    path = Path(path)
    require(path.resolve(strict=True) == path and stat.S_ISREG(path.stat().st_mode), "regular_file_required")
    require(path.stat().st_size <= limit, "artifact_size_bound")
    return path.read_bytes()


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, "duplicate_json_key")
            out[key] = value
        return out

    def invalid(_):
        raise ValueError("nonfinite_json")

    try:
        return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    except (RecursionError, UnicodeError) as error:
        raise ValueError("malformed_json") from error


def write(path, value):
    with path.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def environment():
    # No credential/config hooks or inherited Gitleaks ignore/baseline settings.
    return {
        "PATH": "/usr/bin:/bin",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "LC_ALL": "C",
    }


def git(repo, *args):
    result = subprocess.run(
        [
            "/usr/bin/git",
            "--no-replace-objects",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=/dev/null",
            "-C",
            str(repo),
            *args,
        ],
        env=environment(),
        capture_output=True,
        timeout=30,
        check=False,
    )
    require(result.returncode == 0, "git_read_failed")
    return result.stdout


def state(repo, scanner, *, expected_head, expected_scope_sha256):
    repo = Path(repo).absolute()
    scanner = Path(scanner).resolve(strict=True)
    require(repo.resolve(strict=True) == repo and repo.is_dir(), "real_repo_required")
    require(
        type(expected_head) is str and re.fullmatch("[0-9a-f]{40}", expected_head) is not None,
        "external_head_pin_required",
    )
    require(
        type(expected_scope_sha256) is str
        and re.fullmatch("[0-9a-f]{64}", expected_scope_sha256) is not None,
        "external_scope_pin_required",
    )
    require(sha(regular(Path("/usr/bin/git"))) == GIT_SHA, "git_binary_changed")
    require(sha(regular(scanner, 64 * 1024 * 1024)) == SCANNER_SHA, "scanner_binary_changed")
    version = subprocess.run(
        [str(scanner), "version"], env=environment(), capture_output=True, timeout=10, check=False
    )
    require(version.returncode == 0 and version.stdout.strip() == b"8.30.1", "scanner_version_changed")
    require(git(repo, "rev-parse", "HEAD").decode().strip() == expected_head, "wrong_head")
    require(git(repo, "rev-parse", "--is-shallow-repository").strip() == b"false", "shallow_history")
    require(git(repo, "status", "--porcelain") == b"", "dirty_public_checkout")
    require(
        not (repo / ".gitleaksignore").exists() and not (repo / ".gitleaksignore").is_symlink(),
        "unexpected_ignore_file",
    )
    config = regular(repo / ".gitleaks.toml")
    require(sha(config) == CONFIG_SHA, "scanner_configuration_changed")
    commits = sorted(git(repo, "rev-list", "--all").decode().splitlines())
    require(
        len(commits) == len(set(commits))
        and HEAD in commits
        and expected_head in commits
        and digest(commits) == expected_scope_sha256,
        "reachable_history_changed",
    )
    return {
        "head": expected_head,
        "git_binary_sha256": GIT_SHA,
        "scanner_version": "8.30.1",
        "scanner_binary_sha256": SCANNER_SHA,
        "config_sha256": CONFIG_SHA,
        "scope_sha256": expected_scope_sha256,
        "commits": len(commits),
    }


def expected(diagnosis):
    raw = regular(diagnosis)
    require(sha(raw) == EXPECTED_SHA, "expected_findings_pin_changed")
    value = strict(raw)
    require(
        value["source_diagnosis_sha256"] == DIAGNOSIS_SHA and len(value["findings"]) == 11,
        "expected_findings_shape",
    )
    return value["findings"]


def validate_findings(found, known, blob, *, normalized_projection=False):
    require(type(found) is list and len(found) == 11, "exact_finding_count_required")
    lookup = {x["Fingerprint"]: x for x in known}
    require(len(lookup) == 11, "duplicate_expected_finding")
    seen = set()
    result = []
    for item in found:
        require(
            type(item) is dict and set(item) == (PROJECTION_FIELDS if normalized_projection else FIELDS),
            "finding_shape",
        )
        fingerprint = item["Fingerprint"]
        require(
            type(fingerprint) is str and fingerprint in lookup and fingerprint not in seen,
            "unknown_or_duplicate_fingerprint",
        )
        seen.add(fingerprint)
        reference = lookup[fingerprint]
        for key in (
            "Commit",
            "File",
            "RuleID",
            "StartLine",
            "EndLine",
            "StartColumn",
            "EndColumn",
            "Fingerprint",
        ):
            require(
                type(item[key]) is type(reference[key]) and item[key] == reference[key],
                "immutable_finding_identity_changed",
            )
        require(
            item["Commit"] == HEAD
            and item["Fingerprint"]
            == f"{item['Commit']}:{item['File']}:{item['RuleID']}:{item['StartLine']}",
            "fingerprint_binding",
        )
        if normalized_projection:
            require(
                all(item[key] == reference[key] for key in PROJECTION_FIELDS), "projection_metadata_changed"
            )
        else:
            require(
                item["Secret"] == "REDACTED" and item["SymlinkFile"] == "",
                "redaction_or_symlink_contradiction",
            )
            require(
                type(item["StartColumn"]) is int
                and type(item["EndColumn"]) is int
                and 1 <= item["StartColumn"] <= item["EndColumn"],
                "column_shape",
            )
            require(type(item["Entropy"]) in (float, int) and math.isfinite(item["Entropy"]), "entropy_shape")
            require(type(item["Tags"]) in (list, type(None)), "tags_shape")
            require(
                all(
                    type(item[k]) is str
                    for k in (
                        "Author",
                        "Date",
                        "Description",
                        "Email",
                        "Link",
                        "Match",
                        "Message",
                        "RuleID",
                        "Secret",
                        "File",
                        "Commit",
                        "Fingerprint",
                        "SymlinkFile",
                    )
                ),
                "native_text_shape",
            )
        raw = blob(HEAD, item["File"])
        require(sha(raw) == reference["retained_file_sha256"], "historical_file_changed")
        lines = raw.decode().splitlines()
        line = lines[item["StartLine"] - 1]
        require(sha(line.encode()) == reference["matched_line_sha256"], "historical_line_changed")
        pairs = re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', line)
        source = blob(HEAD, reference["source_file"])
        require(
            hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
            == reference["source_git_blob"],
            "historical_source_blob_changed",
        )
        if reference["classification"] == "reproducible_source_sha256_not_credential":
            require(
                len(pairs) == 2 and re.fullmatch("[0-9a-f]{64}", pairs[1]) and sha(source) == pairs[1],
                "source_checksum_not_reproduced",
            )
            source_name = (
                pairs[0]
                if pairs[0].startswith("bench/")
                else "bench/harbor/skill-workflows-v4/tasks/" + pairs[0]
            )
            require(source_name == reference["source_file"], "source_path_binding")
            require(normalized_projection or item["Match"] == 'api.py": "REDACTED"', "redacted_match_changed")
        elif reference["classification"] == "synthetic_pytest_parameter_not_credential":
            token = "ghp_" + "SYNTHETIC" * 5
            require(
                len(pairs) == 2
                and pairs[0] == "name"
                and pairs[1]
                == "test_decoded_snapshot_sensitive_content_fails_before_destination_creation[" + token + "]",
                "synthetic_parameter_changed",
            )
            require(sha(source) == reference["source_file_sha256"], "synthetic_source_file_changed")
            require(
                source.decode().splitlines()[reference["source_line"] - 1].strip()
                == 'b"ghp_" + b"SYNTHETIC" * 5,',
                "synthetic_expression_changed",
            )
            require(normalized_projection or item["Match"] == "REDACTED", "redacted_match_changed")
        else:
            raise ValueError("unknown_classification")
        result.append({key: reference[key] for key in PROJECTION_FIELDS})
    require(seen == set(lookup), "missing_expected_finding")
    return sorted(result, key=lambda item: item["Fingerprint"])


def validate_projection(projected_findings, expected_findings, blob):
    """Pure source correspondence for explicitly sanitized findings.

    This reuses the exact occurrence/source proof. It does not authenticate or
    reproduce scanner execution, native report bytes, producer or CI status.
    """
    return validate_findings(projected_findings, expected_findings, blob, normalized_projection=True)


def validate_provenance(provenance, live, report_raw, log_raw):
    required = {
        "schema_version",
        "kind",
        "state",
        "command",
        "original_scan_exit",
        "report_sha256",
        "log_sha256",
        "helper_sha256",
        "started_at",
        "finished_at",
    }
    require(type(provenance) is dict and set(provenance) == required, "provenance_shape")
    require(
        provenance["schema_version"] == SCHEMA and provenance["kind"] == "stock_full_history_scan",
        "provenance_kind",
    )
    require(
        canonical(provenance["state"]) == canonical(live) and provenance["command"] == COMMAND,
        "scan_identity_changed",
    )
    require(
        type(provenance["original_scan_exit"]) is int and provenance["original_scan_exit"] == 1,
        "original_scanner_failure_required",
    )
    require(
        provenance["report_sha256"] == sha(report_raw) and provenance["log_sha256"] == sha(log_raw),
        "scan_artifacts_changed",
    )
    require(provenance["helper_sha256"] == sha(regular(Path(__file__).resolve())), "capture_helper_changed")
    start, end = (dt.datetime.fromisoformat(provenance[key]) for key in ("started_at", "finished_at"))
    require(
        start.tzinfo is not None
        and end.tzinfo is not None
        and start <= end <= dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=1),
        "scan_time_invalid",
    )
    require(
        re.search(rb"\b" + str(live["commits"]).encode() + rb" commits scanned\.", log_raw) is not None
        and re.search(rb"leaks found: 11\b", log_raw) is not None,
        "stock_log_scope_mismatch",
    )


def adjudicate(repo, scanner, bundle, diagnosis, *, expected_head, expected_scope_sha256):
    before = state(repo, scanner, expected_head=expected_head, expected_scope_sha256=expected_scope_sha256)
    bundle = Path(bundle).absolute()
    require(bundle.resolve(strict=True) == bundle and bundle.is_dir(), "real_bundle_required")
    report_raw = regular(bundle / "report.redacted.json")
    log_raw = regular(bundle / "scanner.redacted.log")
    provenance = strict(regular(bundle / "scan.json"))
    validate_provenance(provenance, before, report_raw, log_raw)
    findings = validate_findings(
        strict(report_raw),
        expected(Path(diagnosis).absolute()),
        lambda commit, path: git(repo, "show", commit + ":" + path),
    )
    require(
        state(repo, scanner, expected_head=expected_head, expected_scope_sha256=expected_scope_sha256)
        == before,
        "repo_or_scanner_changed_during_adjudication",
    )
    return {
        "schema_version": SCHEMA,
        "status": "ACCEPT_KNOWN_NONSECRETS",
        "original_scan_exit": 1,
        "clean_scan": False,
        "green_ci_claim": False,
        "finding_count": 11,
        "head": before["head"],
        "scope_sha256": before["scope_sha256"],
        "expected_findings_sha256": EXPECTED_SHA,
        "scan_receipt_sha256": digest(provenance),
        "diagnosis_sha256": DIAGNOSIS_SHA,
        "findings": findings,
        "scope": "Exact historical non-secret occurrences under retained controller custody; not a clean scan, authentication or proof of no other secrets.",
    }


def capture(repo, scanner, output, *, expected_head, expected_scope_sha256):
    repo = Path(repo).absolute()
    scanner = Path(scanner).resolve(strict=True)
    output = Path(output).absolute()
    before = state(repo, scanner, expected_head=expected_head, expected_scope_sha256=expected_scope_sha256)
    require(
        not output.exists()
        and not output.is_symlink()
        and output.parent.resolve(strict=True) == output.parent,
        "fresh_output_required",
    )
    output.mkdir(mode=0o700)
    report = output / "report.redacted.json"
    log = output / "scanner.redacted.log"
    command = [str(scanner), *COMMAND[1:]]
    command[command.index("<report>")] = str(report)
    start = dt.datetime.now(dt.timezone.utc).isoformat()
    with log.open("xb") as stream:
        completed = subprocess.run(
            command,
            cwd=repo,
            env=environment(),
            stdout=stream,
            stderr=subprocess.STDOUT,
            timeout=120,
            check=False,
        )
        stream.flush()
        os.fsync(stream.fileno())
    end = dt.datetime.now(dt.timezone.utc).isoformat()
    # Preserve original nonzero scan before adjudication; never relabel this exit.
    provenance = {
        "schema_version": SCHEMA,
        "kind": "stock_full_history_scan",
        "state": before,
        "command": COMMAND,
        "original_scan_exit": completed.returncode,
        "report_sha256": sha(regular(report)),
        "log_sha256": sha(regular(log)),
        "helper_sha256": sha(regular(Path(__file__).resolve())),
        "started_at": start,
        "finished_at": end,
    }
    write(output / "scan.json", provenance)
    require(
        state(repo, scanner, expected_head=expected_head, expected_scope_sha256=expected_scope_sha256)
        == before,
        "repo_or_scanner_changed_during_capture",
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["capture", "verify"])
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--scanner", type=Path, required=True)
    parser.add_argument("--diagnosis", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--expected-scope-sha256", required=True)
    args = parser.parse_args()
    pins = {"expected_head": args.expected_head, "expected_scope_sha256": args.expected_scope_sha256}
    bundle = capture(args.repo, args.scanner, args.bundle, **pins) if args.mode == "capture" else args.bundle
    result = adjudicate(args.repo, args.scanner, bundle, args.diagnosis, **pins)
    if args.mode == "capture":
        write(bundle / "adjudication.json", result)
    print(
        json.dumps(
            {
                "status": result["status"],
                "original_scan_exit": 1,
                "clean_scan": False,
                "green_ci_claim": False,
                "findings": 11,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "REJECT", "error_type": type(error).__name__}), file=sys.stderr)
        raise SystemExit(1) from None
