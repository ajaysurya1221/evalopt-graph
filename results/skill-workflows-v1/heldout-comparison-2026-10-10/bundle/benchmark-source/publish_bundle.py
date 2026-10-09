#!/usr/bin/env python3
"""Create or verify an offline public evidence candidate. Never uploads or redacts evidence."""

from __future__ import annotations

import argparse
import base64
import binascii
import fcntl
import hashlib
import importlib.util
import json
import re
import stat
import sys
import zlib
from collections import Counter
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

from lib.analysis import analyze_workflows, summarize_kernel
from lib.common import bytes_digest, canonical_bytes, digest, is_digest, read_json
from lib.manifest import build_schedule, validate_manifest
from lib.store import CampaignStore
from runtime.controller import require_controller

import evalopt_graph

HERE = Path(__file__).resolve().parent
REGISTRATION_FILES = (
    "manifest.json",
    "runtime.json",
    "readiness.json",
    "readiness-sources.json",
    "source-lock.json",
    "evidence/schedule.json",
)
PUBLIC_ROOT_FILES = {"manifest.json", "runtime.json", "source-lock.json", "registration-lock.json"}
REPORT_FILES = {"outcomes.json", "analysis.json", "kernel.json", "attempts.json", "scheduler-runs.json"}
ATTEMPT_FILES = {
    "start.json",
    "stopped.json",
    "visible.json",
    "controller-artifacts.json",
    "policies.json",
    "grade.json",
    "finish.json",
    "finalize.json",
    "manifest.json",
}
AGENT_FILES = {"snapshot.json", "node-manifest.json", "workflow-exposure.json"}
CONTROLLER_FILES = {"visible-check.json"}
MAX_GIT_OBJECT_BYTES = 16 * 1024 * 1024
SECRET_FIELDS = {
    "access_token",
    "refresh_token",
    "id_token",
    "api_key",
    "apikey",
    "client_secret",
    "openai_api_key",
    "anthropic_api_key",
    "github_token",
    "password",
    "private_key",
}
PRIVATE_ID_FIELDS = {"agent_nickname", "agent_path", "thread_id", "session_id", "parent_thread_id"}
PATTERNS = {
    "api_credential": re.compile(
        r"\b(?:sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16}|ASIA[A-Z0-9]{16})\b"
    ),
    "github_credential": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]*"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
    "bearer_credential": re.compile(
        r"(?i)\b(?:authorization[\"']?\s*[:=]\s*[\"']?\s*)?Bearer\s+[A-Za-z0-9._~+/-]{12,}"
    ),
    "personal_host_path": re.compile(
        r"(?:/"
        r"Users/[^/\s\"'\\]+(?:/|\b)|/"
        r"home/[^/\s\"'\\]+/|/"
        r"private/var/folders/[A-Za-z0-9/_-]+|(?i:[A-Za-z]:\\+Users\\+[^\\\s\"/]+\\+))",
    ),
    "credential_assignment": re.compile(
        r"(?i)\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|GITHUB_TOKEN|ACCESS_TOKEN|REFRESH_TOKEN|CLIENT_SECRET)\s*=\s*[\"']?[^\s\"']{8,}"
    ),
}


class PublicationError(ValueError):
    """The candidate requires explicit remediation; source evidence stays unchanged."""


def _safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise PublicationError("unsafe public artifact path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {".", "..", ""} for part in path.parts) or path.as_posix() != value:
        raise PublicationError("unsafe public artifact path")
    return path


def _safe_root(path):
    path = Path(path).absolute()
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise PublicationError("public export paths must not traverse symlinks")
    return path


def _read_regular(path):
    _safe_root(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        raise PublicationError("publication input must be a regular file")
    return path.read_bytes()


def _tree_identity(path):
    path = _safe_root(path)
    files = {}
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise PublicationError("frozen sources cannot contain symlinks")
        if item.is_file() and "__pycache__" not in item.parts:
            files[item.relative_to(path).as_posix()] = bytes_digest(_read_regular(item))
    return bytes_digest(json.dumps(files, sort_keys=True).encode())


def _scan_text(text, label):
    for kind, pattern in PATTERNS.items():
        if pattern.search(text):
            raise PublicationError(
                f"sensitive content ({kind}) in {label}; remediate explicitly, no bytes were redacted"
            )


def _scan_json(value, label, depth=0):
    if depth > 40:
        raise PublicationError(f"sensitive-content inspection depth exceeded in {label}")
    if isinstance(value, dict):
        for key, item in value.items():
            if key.casefold() in SECRET_FIELDS and isinstance(item, str) and item:
                raise PublicationError(
                    f"sensitive credential field in {label}; explicit remediation required"
                )
            if key in PRIVATE_ID_FIELDS and isinstance(item, str) and item:
                raise PublicationError(f"private runtime identity in {label}; explicit remediation required")
            _scan_text(key, label)
            _scan_json(item, label, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _scan_json(item, label, depth + 1)
    elif isinstance(value, str):
        _scan_text(value, label)
        try:
            nested = json.loads(value)
        except (ValueError, TypeError):
            return
        if nested != value:
            _scan_json(nested, label, depth + 1)


def _scan_bytes(data, label):
    text = data.decode("utf-8", errors="replace")
    _scan_text(text, label)
    if b"\x00" in data:
        for encoding in ("utf-16-le", "utf-16-be"):
            _scan_text(data.decode(encoding, errors="replace"), label)
    try:
        value = json.loads(text)
    except (ValueError, TypeError):
        return
    _scan_json(value, label)


def _scan_git_object(node_name, data, label):
    """Inspect bounded loose Git objects; unsupported storage never silently passes."""
    match = re.search(r"(?:^|/)\.git/objects/(.+)$", node_name)
    if match is None:
        return
    object_path = match.group(1)
    if not re.fullmatch(r"[0-9a-f]{2}/(?:[0-9a-f]{38}|[0-9a-f]{62})", object_path):
        raise PublicationError(f"unsupported Git object storage in {label}; explicit remediation required")
    decoder = zlib.decompressobj()
    try:
        decoded = decoder.decompress(data, MAX_GIT_OBJECT_BYTES + 1)
    except zlib.error:
        raise PublicationError(f"malformed compressed Git object in {label}") from None
    if (
        len(decoded) > MAX_GIT_OBJECT_BYTES
        or not decoder.eof
        or decoder.unconsumed_tail
        or decoder.unused_data
    ):
        raise PublicationError(f"uninspectable or oversized compressed Git object in {label}")
    header, separator, body = decoded.partition(b"\0")
    if not separator or not re.fullmatch(rb"(?:blob|tree|commit|tag) [0-9]+", header):
        raise PublicationError(f"invalid Git object header in {label}")
    if int(header.split(b" ")[1]) != len(body):
        raise PublicationError(f"invalid Git object length in {label}")
    object_id = object_path.replace("/", "")
    algorithm = hashlib.sha1 if len(object_id) == 40 else hashlib.sha256
    if algorithm(decoded).hexdigest() != object_id:
        raise PublicationError(f"Git object content differs from its path in {label}")
    _scan_bytes(decoded, f"{label} [decompressed Git object]")
    _scan_bytes(body, f"{label} [decompressed Git object body]")


def scan_public_file(name, data):
    """Scan raw data plus decoded captured file contents. Never print matched secrets."""
    _safe_relative(name)
    _scan_bytes(data, name)
    if PurePosixPath(name).name == "workflow-exposure.json":
        value = json.loads(data)
        if (
            not isinstance(value, dict)
            or set(value) != {"arm", "source_files", "verified_before_agent"}
            or value["arm"] not in {"A", "B", "C"}
            or value["verified_before_agent"] is not True
            or not isinstance(value["source_files"], dict)
        ):
            raise PublicationError("unsupported workflow exposure schema")
        for source_name, source_sha in value["source_files"].items():
            _safe_relative(source_name)
            if not is_digest(source_sha):
                raise PublicationError("invalid workflow exposure source identity")
    if PurePosixPath(name).name != "snapshot.json":
        return
    try:
        value = json.loads(data)
        if (
            set(value) != {"schema_version", "nodes"}
            or value["schema_version"] != "evalopt.stopped-nodes.v1"
            or not isinstance(value["nodes"], dict)
        ):
            raise PublicationError("unsupported captured snapshot schema")
        for index, (node_name, node) in enumerate(sorted(value["nodes"].items())):
            _safe_relative(node_name)
            if not isinstance(node, dict):
                raise PublicationError("invalid captured snapshot node")
            if node.get("type") == "file":
                decoded = base64.b64decode(node["data"], validate=True)
                label = f"{name} [decoded file {index}]"
                _scan_bytes(decoded, label)
                _scan_git_object(node_name, decoded, label)
            elif node.get("type") not in {"directory", "symlink", "special"}:
                raise PublicationError("unknown captured snapshot node type")
    except (KeyError, TypeError, ValueError, binascii.Error) as exc:
        if isinstance(exc, PublicationError):
            raise
        raise PublicationError(f"malformed captured snapshot in {name}") from None


@contextmanager
def _frozen_controller(campaign):
    lock = campaign / ".scheduler.lock"
    if not lock.exists():
        yield
        return
    with lock.open("r") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PublicationError("campaign controller is active; wait for its retained outcome") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _import_reporter(path, module_name):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise PublicationError("cannot load report reproduction implementation")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HERE))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def _load_frozen_reporter(source, source_lock):
    if _tree_identity(source) != source_lock["campaign_sha256"]:
        raise PublicationError("frozen campaign source identity differs from registration")
    if _tree_identity(source / "lib") != _tree_identity(HERE / "lib"):
        raise PublicationError("reproduce with the registered benchmark library version")
    kernel = Path(evalopt_graph.__file__).resolve().parent
    if _tree_identity(kernel) != source_lock["kernel_source_sha256"]:
        raise PublicationError("installed kernel differs from frozen campaign source")
    return _import_reporter(source / "campaign.py", "evalopt_frozen_publication_report")


def _read_only_store(root, schedule):
    """Use the verified reader methods without creating scratch files in frozen evidence."""
    expected = {
        "schema_version": "evalopt.workflow-schedule.v1",
        "schedule": schedule,
        "schedule_sha256": digest(schedule),
    }
    if json.loads(_read_regular(root / "schedule.json")) != expected:
        raise PublicationError("invalid retained schedule registration")
    if len({row["trial_id"] for row in schedule}) != len(schedule):
        raise PublicationError("duplicate public trial")
    store = object.__new__(CampaignStore)
    store.root = _safe_root(root)
    store.schedule_sha256 = digest(schedule)
    store.trials = {row["trial_id"]: row for row in schedule}
    return store


def _registered_schedule(manifest, registration):
    if (
        not isinstance(registration, dict)
        or set(registration) != {"schema_version", "schedule", "schedule_sha256"}
        or registration["schema_version"] != "evalopt.workflow-schedule.v1"
    ):
        raise PublicationError("invalid schedule registration schema")
    schedule = registration["schedule"]
    stages = {row["stage"] for row in schedule}
    if "transfer" in stages:
        raise PublicationError(
            "external transfer requires its separate publication schema; no U/M/G is implied"
        )
    expected = [
        row
        for stage in ("pilot", "heldout")
        if stage in stages
        for row in build_schedule(manifest["tasks"], stage)
    ]
    if not schedule or schedule != expected or registration["schedule_sha256"] != digest(schedule):
        raise PublicationError("schedule differs from frozen task manifest")
    return schedule


def _public_registration(directory):
    manifest = validate_manifest(read_json(directory / "manifest.json"))
    if any(
        not is_digest(value, 40 if name.endswith("_commit") else 64)
        for name, value in manifest["pins"].items()
    ):
        raise PublicationError("publication requires resolved source pins")
    lock = read_json(directory / "registration-lock.json")
    if set(lock) != set(REGISTRATION_FILES) or any(not is_digest(value) for value in lock.values()):
        raise PublicationError("invalid registration lock schema")
    for name in ("manifest.json", "runtime.json", "source-lock.json", "evidence/schedule.json"):
        if bytes_digest(_read_regular(directory / name)) != lock[name]:
            raise PublicationError("public artifact differs from retained registration")
    runtime = read_json(directory / "runtime.json")
    if digest(runtime) != manifest["pins"]["environment_sha256"]:
        raise PublicationError("runtime differs from registered environment")
    return manifest, _registered_schedule(manifest, read_json(directory / "evidence/schedule.json"))


def _require_pilot_publication(schedule):
    if any(row["stage"] != "pilot" for row in schedule):
        raise PublicationError(
            "use heldout_publish.py for complete held-out assets and release gates, or the separate transfer publisher"
        )


def _expected_reports(store, schedule, reporter, runs):
    rows, kernel_rows, attempts = reporter._report_rows(store, schedule)
    if any(row["status"] == "artifact_failure" for row in rows) or any(
        not row["artifact_valid"] for row in attempts
    ):
        raise PublicationError(
            "artifact integrity failed; cannot publish a rewritten or partial evidence set"
        )
    analysis = analyze_workflows(rows, schedule=schedule)
    analysis["all_attempt_resources"] = reporter._all_attempt_resources(attempts, schedule)
    stages = {row["stage"] for row in schedule}
    kernel_stage = "heldout" if "heldout" in stages else "pilot"
    ids = {row["trial_id"] for row in schedule if row["stage"] == kernel_stage}
    kernel = summarize_kernel([row for row in kernel_rows if row["trial_id"] in ids])
    kernel["scope"] = (
        "held-out stopped-output decisions"
        if kernel_stage == "heldout"
        else ("development diagnostics" if "pilot" in stages else "not applicable to external transfer")
    )
    return {
        "outcomes.json": rows,
        "analysis.json": analysis,
        "kernel.json": kernel,
        "attempts.json": attempts,
        "scheduler-runs.json": runs,
    }


def _select_reports(campaign, expected, export_id, schedule_sha256):
    expected_id = digest(expected)
    if export_id is not None and export_id != expected_id:
        raise PublicationError("selected report does not reproduce current frozen outcomes")
    source = campaign / "exports" / expected_id
    checksums = json.loads(_read_regular(source / "checksums.json"))
    if (
        checksums.get("schema_version") != "evalopt.report-export.v1"
        or checksums.get("schedule_sha256") != schedule_sha256
        or checksums.get("export_id") != expected_id
        or set(checksums.get("files", {})) != REPORT_FILES
    ):
        raise PublicationError("unsupported report export manifest")
    result = {}
    for name, value in expected.items():
        data = _read_regular(source / name)
        if data != canonical_bytes(value) + b"\n" or bytes_digest(data) != checksums["files"][name]:
            raise PublicationError("retained report differs from offline reproduction")
        result[f"reports/{name}"] = data
    result["reports/checksums.json"] = _read_regular(source / "checksums.json")
    return result, expected_id


def _evidence_files(campaign, store):
    evidence = campaign / "evidence"
    result = {"evidence/schedule.json": _read_regular(evidence / "schedule.json")}
    states = store.statuses()
    registered = set(store.trials)
    trials = evidence / "trials"
    if trials.exists() and any(
        path.name not in registered or not path.is_dir() or path.is_symlink() for path in trials.iterdir()
    ):
        raise PublicationError("unexpected trial entry in controller evidence")
    for state in states:
        trial_path = trials / state["trial_id"]
        if trial_path.exists() and any(
            item.name not in {"attempt-1", "attempt-2"} or not item.is_dir() for item in trial_path.iterdir()
        ):
            raise PublicationError("unexpected controller trial artifact")
        for attempt in range(1, state["attempts"] + 1):
            path = trials / state["trial_id"] / f"attempt-{attempt}"
            if not (path / "finish.json").is_file() or not (path / "manifest.json").is_file():
                raise PublicationError(
                    "started attempt is not finalized; finish or classify it before publication"
                )
            store.verify_attempt(state["trial_id"], attempt)
            for item in sorted(path.rglob("*")):
                if item.is_symlink():
                    raise PublicationError("symlink in retained evidence")
                if item.is_dir():
                    continue
                relative = item.relative_to(path).as_posix()
                allowed = (
                    relative in ATTEMPT_FILES
                    or (
                        relative.startswith("agent/")
                        and PurePosixPath(relative).name in AGENT_FILES
                        and len(PurePosixPath(relative).parts) == 2
                    )
                    or (
                        relative.startswith("controller/")
                        and PurePosixPath(relative).name in CONTROLLER_FILES
                        and len(PurePosixPath(relative).parts) == 2
                    )
                )
                if not allowed:
                    raise PublicationError(
                        "non-whitelisted or private artifact inside hash-bound evidence; explicit remediation required"
                    )
                name = item.relative_to(campaign).as_posix()
                result[name] = _read_regular(item)
    return result


def _claims(expected):
    rows = expected["outcomes.json"]
    scheduled = Counter(row["stage"] for row in rows)
    retained = Counter(row["stage"] for row in rows if row["status"] not in {"pending", "missing"})
    header = (
        "No comparative headline: development pilot evidence only."
        if not scheduled["heldout"]
        else (
            "Scoped positive-result rule met; claims remain limited to these registered conditions."
            if expected["analysis.json"]["scoped_positive_headline_permitted"]
            else "No registered positive-result headline is supported."
        )
    )
    return (
        f"# Claim-to-evidence table\n\n{header}\n\n"
        "| Claim | Evidence and limit |\n| --- | --- |\n"
        f"| Recorded workflow outcomes | {retained['pilot']} retained pilot outcomes across {scheduled['pilot']} scheduled trials; see reports/outcomes.json and evidence/. Agent execution is controller-recorded, not independently authenticated by hashes. |\n"
        f"| Held-out comparison | {retained['heldout']} retained outcomes across {scheduled['heldout']} scheduled trials; only the frozen analysis rules can permit a scoped comparison. |\n"
        f"| External transfer | {retained['transfer']} retained outcomes across {scheduled['transfer']} scheduled trials. Feasibility subset only; never an official leaderboard result. |\n"
        "| Acceptance decisions and conformance | reports/kernel.json and exact stopped-output policy records support replay. Replay checks supplied-input consistency, not real-world correctness. Authored offline controls remain a separate evidence class. |\n"
        "| Independent replication | Not established. This is a maintainer-run study with separated authoring and grading roles; it does not satisfy the independent-human external-validation protocol. |\n\n"
        "Resources for final trial attempts and all retained attempts are reported separately. Do not add these totals together. Tokens, calls and time are measured; no dollar cost is invented.\n"
    ).encode()


def export_public_bundle(campaign_directory, destination, *, frozen_source=None, export_id=None):
    require_controller()
    campaign = _safe_root(campaign_directory)
    destination = _safe_root(destination)
    source = _safe_root(frozen_source or HERE)
    if destination.exists() or destination.is_relative_to(campaign) or campaign.is_relative_to(destination):
        raise PublicationError("public bundle requires a fresh destination outside the campaign")
    with _frozen_controller(campaign):
        registration_lock = json.loads(_read_regular(campaign / "registration-lock.json"))
        actual = {name: bytes_digest(_read_regular(campaign / name)) for name in REGISTRATION_FILES}
        if registration_lock != actual:
            raise PublicationError("campaign registration changed")
        manifest = validate_manifest(json.loads(_read_regular(campaign / "manifest.json")))
        if any(
            not is_digest(value, 40 if name.endswith("_commit") else 64)
            for name, value in manifest["pins"].items()
        ):
            raise PublicationError("publication requires resolved source pins")
        source_lock = json.loads(_read_regular(campaign / "source-lock.json"))
        reporter = _load_frozen_reporter(source, source_lock)
        registration = json.loads(_read_regular(campaign / "evidence/schedule.json"))
        schedule = _registered_schedule(manifest, registration)
        _require_pilot_publication(schedule)
        store = _read_only_store(campaign / "evidence", schedule)
        payloads = _evidence_files(campaign, store)
        runs = []
        for path in sorted((campaign / "runs").glob("run-*")):
            if not (path / "end.json").is_file():
                raise PublicationError("scheduler invocation remains unfinished")
            runs.append(
                {
                    "run": path.name,
                    "start": json.loads(_read_regular(path / "start.json")),
                    "end": json.loads(_read_regular(path / "end.json")),
                    "subscription_permissions": [
                        json.loads(_read_regular(item)) for item in sorted(path.glob("permission-*.json"))
                    ],
                }
            )
        expected = _expected_reports(store, schedule, reporter, runs)
        reports, selected_id = _select_reports(campaign, expected, export_id, digest(schedule))
        payloads.update(reports)
        for name in PUBLIC_ROOT_FILES:
            payloads[name] = _read_regular(campaign / name)
        payloads["CLAIMS.md"] = _claims(expected)
        payloads["README.md"] = (
            b"# Reproducible eval-opt evidence candidate\n\n"
            b"This folder is an offline publication candidate. It has not been uploaded by the exporter.\n\n"
            b"Verify retained bytes, policy replay and outcome analysis with the registered source version and CPython 3.13.12 exactly:\n\n"
            b"```sh\npython bench/harbor/skill-workflows-v1/publish_bundle.py verify /path/to/public-bundle\n```\n\n"
            b"See CLAIMS.md for evidence limits. Private Harbor directories, raw conversations, authentication files and readiness-source host paths are excluded. Hash-bound evidence is copied without redaction. A sensitive-content finding prevents export and requires explicit remediation. The bounded scanner is not a proof that every possible secret has been recognized.\n"
        )
        payloads["PUBLICATION.json"] = (
            canonical_bytes(
                {
                    "schema_version": "evalopt.public-evidence.v1",
                    "report_export_id": selected_id,
                    "schedule_sha256": digest(schedule),
                    "source_lock_sha256": bytes_digest(payloads["source-lock.json"]),
                    "exporter_sha256": bytes_digest(Path(__file__).read_bytes()),
                    "redaction": "none",
                    "sensitive_scan": "bounded patterns plus decoded snapshot files; fail closed on findings",
                    "study_ownership": "maintainer-run",
                    "independent_replication": False,
                }
            )
            + b"\n"
        )
        for name, data in payloads.items():
            scan_public_file(name, data)
        checksums = {
            name: {"size": len(data), "sha256": bytes_digest(data)} for name, data in sorted(payloads.items())
        }
        payloads["CHECKSUMS.json"] = (
            canonical_bytes(
                {
                    "schema_version": "evalopt.public-checksums.v1",
                    "bundle_id": digest(checksums),
                    "files": checksums,
                }
            )
            + b"\n"
        )
        destination.mkdir(parents=True)
        for name, data in sorted(payloads.items()):
            target = destination / _safe_relative(name)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream:
                stream.write(data)
        return verify_public_bundle(destination)


def verify_public_bundle(directory):
    require_controller()
    directory = _safe_root(directory)
    checksum_bytes = _read_regular(directory / "CHECKSUMS.json")
    scan_public_file("CHECKSUMS.json", checksum_bytes)
    checksum = json.loads(checksum_bytes)
    if (
        not isinstance(checksum, dict)
        or set(checksum) != {"schema_version", "bundle_id", "files"}
        or checksum.get("schema_version") != "evalopt.public-checksums.v1"
        or not isinstance(checksum.get("files"), dict)
        or digest(checksum["files"]) != checksum.get("bundle_id")
    ):
        raise PublicationError("public checksum schema or identity is invalid")
    actual = set()
    for item in directory.rglob("*"):
        if item.is_symlink():
            raise PublicationError("symlink in public candidate")
        if not item.is_dir() and not stat.S_ISREG(item.lstat().st_mode):
            raise PublicationError("nonregular node in public candidate")
        if item.is_file() and item.relative_to(directory).as_posix() != "CHECKSUMS.json":
            actual.add(item.relative_to(directory).as_posix())
    if actual != set(checksum["files"]):
        raise PublicationError("public candidate contains unexpected or missing files")
    for name, record in checksum["files"].items():
        path = _safe_relative(name)
        parts = path.parts
        allowed = name in PUBLIC_ROOT_FILES | {"CLAIMS.md", "README.md", "PUBLICATION.json"}
        allowed = allowed or (
            len(parts) == 2 and parts[0] == "reports" and parts[1] in REPORT_FILES | {"checksums.json"}
        )
        allowed = allowed or name == "evidence/schedule.json"
        if (
            len(parts) in {5, 6}
            and parts[:2] == ("evidence", "trials")
            and parts[3] in {"attempt-1", "attempt-2"}
        ):
            allowed = (
                (len(parts) == 5 and parts[4] in ATTEMPT_FILES)
                or (len(parts) == 6 and parts[4] == "agent" and parts[5] in AGENT_FILES)
                or (len(parts) == 6 and parts[4] == "controller" and parts[5] in CONTROLLER_FILES)
            )
        if not allowed:
            raise PublicationError("non-whitelisted file in public candidate")
        data = _read_regular(directory / _safe_relative(name))
        if record != {"size": len(data), "sha256": bytes_digest(data)}:
            raise PublicationError("public artifact differs from retained checksum")
        scan_public_file(name, data)
    manifest, schedule = _public_registration(directory)
    _require_pilot_publication(schedule)
    store = _read_only_store(directory / "evidence", schedule)
    _evidence_files(directory, store)
    if _tree_identity(HERE / "lib") != manifest["pins"]["analysis_sha256"]:
        raise PublicationError("reproduce public analysis using the registered library version")
    if (
        _tree_identity(Path(evalopt_graph.__file__).resolve().parent)
        != read_json(directory / "source-lock.json")["kernel_source_sha256"]
    ):
        raise PublicationError("replay public decisions using the registered kernel source")
    verified = 0
    decisions = 0
    for state in store.statuses():
        for attempt in range(1, state["attempts"] + 1):
            replay = store.verify_attempt(state["trial_id"], attempt)
            if replay["kernel_replay"] is True:
                decisions += 3
            verified += 1
    reporter = _import_reporter(HERE / "campaign.py", "evalopt_public_verification_report")
    expected = _expected_reports(
        store, schedule, reporter, read_json(directory / "reports/scheduler-runs.json")
    )
    for name, value in expected.items():
        if _read_regular(directory / "reports" / name) != canonical_bytes(value) + b"\n":
            raise PublicationError("public report does not reproduce retained evidence")
    expected_report_checksums = {
        "schema_version": "evalopt.report-export.v1",
        "schedule_sha256": digest(schedule),
        "export_id": digest(expected),
        "files": {name: bytes_digest(canonical_bytes(value) + b"\n") for name, value in expected.items()},
    }
    if read_json(directory / "reports/checksums.json") != expected_report_checksums:
        raise PublicationError("retained report checksum envelope differs from reproduced reports")
    if _read_regular(directory / "CLAIMS.md") != _claims(expected):
        raise PublicationError("claim-to-evidence table differs from reproducible outcomes")
    publication = read_json(directory / "PUBLICATION.json")
    if (
        publication.get("schema_version") != "evalopt.public-evidence.v1"
        or publication.get("report_export_id") != digest(expected)
        or publication.get("schedule_sha256") != digest(schedule)
        or publication.get("source_lock_sha256")
        != bytes_digest(_read_regular(directory / "source-lock.json"))
        or publication.get("redaction") != "none"
        or publication.get("study_ownership") != "maintainer-run"
        or publication.get("independent_replication") is not False
    ):
        raise PublicationError("publication metadata differs from its evidence scope")
    return {
        "schema_version": "evalopt.public-verification.v1",
        "bundle_id": checksum["bundle_id"],
        "files": len(actual),
        "attempts_verified": verified,
        "policy_replay_verified": True if decisions else None,
        "policy_decisions_replayed": decisions,
        "analysis_reproduced": True,
        "sensitive_scan_passed": True,
        "network_publication_performed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--campaign", type=Path, required=True)
    export.add_argument("--destination", type=Path, required=True)
    export.add_argument("--frozen-source", type=Path)
    export.add_argument("--export-id")
    verify = commands.add_parser("verify")
    verify.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    result = (
        export_public_bundle(
            args.campaign, args.destination, frozen_source=args.frozen_source, export_id=args.export_id
        )
        if args.command == "export"
        else verify_public_bundle(args.directory)
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
