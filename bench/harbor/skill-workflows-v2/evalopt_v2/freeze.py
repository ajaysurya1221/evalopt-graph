"""Create and verify a controller-owned, self-contained campaign input freeze.

The review/control receipt records actual reviewed work; its hashes establish
which bytes were checked, not reviewer identity. It must originate outside the
candidate environment. Public reporting uses relative inventory names only.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from .ablation import derive_ablation, validate_pair
from .framing import strict_json
from .preflight import UPSTREAM_COMMIT, image_identity, skill_sources
from .preservation import verify as verify_preservation
from .records import digest
from .registration import development_gate, registration, validate_tasks
from .store import CampaignStore, exclusive_json, read_json, sync_directory


def tree_manifest(root):
    root = Path(root).absolute()
    if root.resolve() != root or not root.is_dir():
        raise ValueError("input tree must be a real directory")
    result = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in {".git", "__pycache__", ".pytest_cache", ".ruff_cache"} for part in rel.parts):
            continue
        metadata = path.lstat()
        if stat.S_ISDIR(metadata.st_mode):
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ValueError("input tree contains symlink or special node")
        result[rel.as_posix()] = {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "executable": bool(metadata.st_mode & stat.S_IXUSR),
        }
    if not result:
        raise ValueError("empty frozen input tree")
    return result


def copy_tree(source, destination):
    source, destination = Path(source).absolute(), Path(destination).absolute()
    before = tree_manifest(source)
    destination.mkdir()
    for name in before:
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, path)
    if before != tree_manifest(source) or before != tree_manifest(destination):
        raise ValueError("input changed while freezing")
    return before


def verify_harness_source_only(harness):
    """Reject unregistered executable caches in an already frozen harness.

    -B prevents cache writes, not reads. The launcher must perform its own
    equivalent check before importing any frozen harness module; this helper
    also protects subsequent verification and admission from injected caches.
    Working-source caches may be excluded when constructing the frozen copy.
    """
    harness = Path(harness).absolute()
    if harness.resolve() != harness or not harness.is_dir():
        raise ValueError("frozen harness must be a real directory")
    if any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"} for path in harness.rglob("*")):
        raise ValueError("frozen harness bytecode cache is not an admitted input")


def reviewed_inputs(harness, skill, tasks):
    return {
        "harness": digest(tree_manifest(harness)),
        "skill_c": digest(tree_manifest(skill)),
        "tasks": digest(tree_manifest(tasks)),
    }


def validate_admission(receipt, inputs):
    """Validate source-bound review/control data and the single revision limit.

    Retained previous rows are replayed for consistency. Their registration
    digest is an identifier, not authentication of the source report's custody.
    """
    if set(receipt) != {"schema_version", "inputs", "controls", "reviews", "development_round"}:
        raise ValueError("invalid offline admission receipt")
    if receipt["schema_version"] != "evalopt-workflows-v2/1" or receipt["inputs"] != inputs:
        raise ValueError("offline admission covers different bytes")
    controls = receipt["controls"]
    required = {
        "audited_regressions",
        "semantic",
        "framing_accounting",
        "lifecycle",
        "compatibility_reproduction",
    }
    if set(controls) != required:
        raise ValueError("all five control groups required")
    for result in controls.values():
        if (
            result.get("status") != "PASS"
            or result.get("skipped") != 0
            or not _sha(result.get("evidence_sha256"))
        ):
            raise ValueError("control group has not passed completely")
    reviews = receipt["reviews"]
    if set(reviews) != {"skill", "tasks", "grading_capture", "integration_analysis"}:
        raise ValueError("separated review coverage incomplete")
    for review in reviews.values():
        if review.get("verdict") != "ACCEPT" or not _sha(review.get("evidence_sha256")):
            raise ValueError("independent review has not accepted")

    round_ = receipt["development_round"]
    if (
        not isinstance(round_, dict)
        or set(round_) != {"revision", "previous"}
        or type(round_["revision"]) is not int
        or round_["revision"] not in (0, 1)
    ):
        raise ValueError("invalid development round")
    previous = round_["previous"]
    if round_["revision"] == 0:
        if previous is not None:
            raise ValueError("initial development round cannot have previous evidence")
    elif isinstance(previous, dict) and previous.get("status") == "stopped_incomplete":
        validate_stopped_incomplete(previous)
    else:
        if (
            not isinstance(previous, dict)
            or set(previous)
            != {"tasks", "rows", "controls_passed", "revision", "result", "registration_sha256"}
            or type(previous["revision"]) is not int
            or previous["revision"] != 0
            or not _sha(previous["registration_sha256"])
        ):
            raise ValueError("development revision requires the previous registered round")
        gate = development_gate(
            previous["tasks"],
            previous["rows"],
            controls_passed=previous["controls_passed"],
            revision=previous["revision"],
        )
        if gate["ready"] or gate["recorded"] != 48 or gate != previous["result"]:
            raise ValueError("revision requires a complete nonready development round")


def _keys(value, names):
    if not isinstance(value, dict) or set(value) != set(names.split()):
        raise ValueError("invalid stopped-incomplete evidence fields")


def _same(left, right):
    # JSON identity must distinguish true from 1, including nested schedule data.
    if digest(left) != digest(right):
        raise ValueError("stopped-incomplete evidence identity mismatch")


def validate_stopped_incomplete(previous):
    """Check a portable predecessor projection without changing its old gate.

    This is consistency replay, not authentication. The separately reviewed
    correspondence receipt must bind the supplied original replay, starts,
    final/failure byte hashes and private preservation seal before preparation.
    No private native filenames, raw logs, executable code or mutable paths are
    required here. Only the original revision-zero, sequential first-attempt
    prefix is supported; its unfinished attempt is never made a task result.
    """
    from .analysis import reconcile
    from .descriptive import outcomes
    from .registration import validate_registration

    _keys(
        previous,
        "status revision registration registration_sha256 replay replay_sha256 "
        "replay_source preservation partition started_attempts resumptions correspondence",
    )
    if (
        previous["status"] != "stopped_incomplete"
        or type(previous["revision"]) is not int
        or previous["revision"] != 0
    ):
        raise ValueError("stopped predecessor must be development revision zero")
    registered = previous["registration"]
    pin = previous["registration_sha256"]
    if not _sha(pin) or not isinstance(registered, dict):
        raise ValueError("original external registration pin required")
    validate_registration(registered, expected_sha256=pin)
    _same(registered, registration(registered["tasks"], "development", registered["identities"]))
    _same(pin, digest({key: value for key, value in registered.items() if key != "registration_sha256"}))
    source = previous["replay_source"]
    _keys(source, "source_sha256 controller_sha256 entrypoint_sha256")
    if (
        source["source_sha256"] != registered["identities"]["source"]
        or source["controller_sha256"] != registered["identities"]["controller"]
        or not _sha(source["entrypoint_sha256"])
    ):
        raise ValueError("replay source differs from original registered source")
    seal = previous["preservation"]
    _keys(seal, "file_count sha256")
    if type(seal["file_count"]) is not int or seal["file_count"] <= 0 or not _sha(seal["sha256"]):
        raise ValueError("original private preservation seal required")
    correspondence = previous["correspondence"]
    _keys(correspondence, "status evidence_sha256 scope")
    if (
        correspondence["status"] != "PASS"
        or not _sha(correspondence["evidence_sha256"])
        or correspondence["scope"] != "independently_reviewed_consistency_not_authentication"
    ):
        raise ValueError("reviewed private-artifact correspondence required")

    scheduled = registered["schedule"]
    ids = [row["trial_id"] for row in scheduled]
    partition = previous["partition"]
    _keys(partition, "finalized unfinalized unstarted")
    if any(not isinstance(value, list) for value in partition.values()):
        raise ValueError("partition lists required")
    count = len(partition["finalized"])
    if len(partition["unfinalized"]) != 1 or count >= len(ids):
        raise ValueError("one stopped, unfinished first attempt required")
    _same(
        partition,
        {"finalized": ids[:count], "unfinalized": ids[count : count + 1], "unstarted": ids[count + 1 :]},
    )
    ledger = previous["started_attempts"]
    if not isinstance(ledger, list) or len(ledger) != count + 1:
        raise ValueError("started-attempt ledger coverage differs from partition")
    resumptions = previous["resumptions"]
    if not isinstance(resumptions, list):
        raise ValueError("original subscription resumption list required")
    pauses = []
    rows = []
    metrics = {
        "valid_completion",
        "functional_success",
        "unsupported_success",
        "incorrect_refusal",
        "boundary_violation",
        "raw_valid_completion",
        "raw_functional_success",
    }
    for index, entry in enumerate(ledger):
        final = index < count
        _keys(
            entry,
            "trial_id start start_sha256 state "
            + ("final_sha256 outcome continuation" if final else "failure failure_sha256"),
        )
        row = scheduled[index]
        expected_start = {
            "row": row,
            "registration_sha256": pin,
            "attempt": 1,
            "attempt_id": row["trial_id"] + "--attempt-1",
        }
        _same(entry["start"], expected_start)
        if (
            entry["trial_id"] != row["trial_id"]
            or entry["state"] != ("finalized" if final else "unfinalized")
            or entry["start_sha256"] != digest(expected_start)
        ):
            raise ValueError("started-attempt identity or digest mismatch")
        if final:
            if not _sha(entry["final_sha256"]):
                raise ValueError("original final artifact byte hash required")
            continuation = entry["continuation"]
            if not isinstance(continuation, dict) or continuation.get("historical_delegation") not in {
                "verified",
                "unverified",
            }:
                raise ValueError("original continuation record required")
            paused = continuation.get("decision") == "stop"
            _same(
                continuation,
                {
                    "schema_version": "evalopt-workflows-v2/1",
                    "kind": "continuation",
                    "decision": "stop" if paused else "continue",
                    "reasons": ["subscription_permission_unavailable"] if paused else [],
                    "retry_authorized": False,
                    "task_success_inferred": False,
                    "historical_delegation": continuation["historical_delegation"],
                },
            )
            if paused:
                pauses.append(entry)
            outcome = entry["outcome"]
            required = set(row) | metrics | {"contract_dispute", "runtime_identity_verified"}
            if not isinstance(outcome, dict) or set(outcome) not in (required, required | {"missing_reason"}):
                raise ValueError("original finalized outcome projection required")
            _same({key: outcome[key] for key in row}, row)
            if any(type(outcome[key]) is not bool and outcome[key] is not None for key in metrics) or any(
                type(outcome[key]) is not bool for key in ("contract_dispute", "runtime_identity_verified")
            ):
                raise ValueError("invalid finalized outcome types")
            if outcome["valid_completion"] is None:
                reason = outcome.get("missing_reason")
                if (
                    not isinstance(reason, str)
                    or not reason
                    or any(c not in "abcdefghijklmnopqrstuvwxyz_" for c in reason)
                ):
                    raise ValueError("unknown finalized outcome requires static missing reason")
            elif "missing_reason" in outcome:
                raise ValueError("known finalized outcome cannot have missing reason")
            rows.append(outcome)
        else:
            failure = entry["failure"]
            _keys(failure, "kind error_type observed_at automatic_retry_allowed")
            if (
                failure["kind"] != "controller_failure"
                or failure["automatic_retry_allowed"] is not False
                or entry["failure_sha256"] != digest(failure)
            ):
                raise ValueError("retained nonretryable controller failure required")
            error = failure["error_type"]
            if not isinstance(error, str) or not error.isascii() or not error.isidentifier():
                raise ValueError("sanitized exception class required")
            try:
                observed = datetime.fromisoformat(failure["observed_at"])
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid controller failure timestamp") from exc
            if observed.utcoffset() is None:
                raise ValueError("controller failure timestamp requires timezone")

    if len(resumptions) != len(pauses):
        raise ValueError("every stopped subscription continuation requires its original resumption")
    for resumption, entry in zip(resumptions, pauses, strict=True):
        _keys(resumption, "pause pause_sha256 resume resume_sha256")
        expected_pause = {
            "registration_sha256": pin,
            "stopped_trial_id": entry["trial_id"],
            "stopped_final_sha256": entry["final_sha256"],
            "permission": {
                "schema_version": "evalopt-workflows-v2/1",
                "kind": "subscription_permission",
                "ordinary_usage_allowed": False,
                "state": "exhausted",
            },
        }
        _same(resumption["pause"], expected_pause)
        _same(resumption["pause_sha256"], digest(expected_pause))
        expected_resume = {
            "registration_sha256": pin,
            "pause_sha256": digest(expected_pause),
            "permission": {
                "schema_version": "evalopt-workflows-v2/1",
                "kind": "subscription_permission",
                "ordinary_usage_allowed": True,
                "state": "allowed",
            },
        }
        _same(resumption["resume"], expected_resume)
        _same(resumption["resume_sha256"], digest(expected_resume))

    replay = previous["replay"]
    _keys(
        replay,
        "stage scheduled_rows secondary_outcomes gate conclusion resources kernel registration_sha256 retained_attempts finalized_rows unfinalized_trials controller_time",
    )
    if not _sha(previous["replay_sha256"]) or digest(replay) != previous["replay_sha256"]:
        raise ValueError("original frozen replay digest mismatch")
    resolved = reconcile(registered["tasks"], rows, "development")
    gate = development_gate(registered["tasks"], rows, controls_passed=True, revision=0)
    for key, expected in {
        "stage": "development",
        "conclusion": "development_only",
        "registration_sha256": pin,
        "scheduled_rows": resolved,
        "secondary_outcomes": outcomes(resolved),
        "gate": gate,
        "finalized_rows": count,
        "retained_attempts": count + 1,
        "unfinalized_trials": partition["unfinalized"],
    }.items():
        _same(replay[key], expected)
    if gate["ready"] or gate["recorded"] != count or gate["next"] != "development_revision":
        raise ValueError("stopped original round cannot pass or inflate its gate")
    _validate_stopped_report_counts(replay, scheduled[: count + 1], rows)
    return {
        "scheduled": len(ids),
        "finalized": count,
        "unfinalized": 1,
        "unstarted": len(ids) - count - 1,
        "gate": gate,
    }


def _validate_stopped_report_counts(replay, started, outcomes):
    """Check retained report denominators; counters remain supplied original evidence."""
    import math

    from .accounting import COUNTERS
    from .registration import ARMS

    def integer(value):
        return type(value) is int and value >= 0

    def duration(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0

    _keys(replay["resources"], " ".join(ARMS))
    for arm, bucket in replay["resources"].items():
        _keys(
            bucket,
            "attempts complete_usage_attempts partial_usage_attempts unavailable_usage_attempts exact_totals observed_lower_bounds agent_wall_seconds_observed agent_wall_seconds_known_attempts efficiency_claim_allowed",
        )
        counts = [
            bucket[key]
            for key in (
                "attempts",
                "complete_usage_attempts",
                "partial_usage_attempts",
                "unavailable_usage_attempts",
                "agent_wall_seconds_known_attempts",
            )
        ]
        if (
            not all(map(integer, counts))
            or counts[0] != sum(row["arm"] == arm for row in started)
            or sum(counts[1:4]) != counts[0]
            or counts[4] > counts[0]
            or bucket["efficiency_claim_allowed"] is not False
        ):
            raise ValueError("invalid original all-attempt resource denominator")
        if arm == started[-1]["arm"] and counts[3] < 1:
            raise ValueError("unfinished attempt consumption must remain unavailable")
        lower = bucket["observed_lower_bounds"]
        _keys(lower, " ".join(COUNTERS))
        if any(value is not None and not integer(value) for value in lower.values()) or (
            not sum(counts[1:3]) and any(value is not None for value in lower.values())
        ):
            raise ValueError("invalid original resource counters")
        expected_exact = lower if counts[0] and counts[1] == counts[0] else None
        _same(bucket["exact_totals"], expected_exact)
        seconds = bucket["agent_wall_seconds_observed"]
        if (counts[4] == 0 and seconds is not None) or (counts[4] > 0 and not duration(seconds)):
            raise ValueError("invalid original observed agent duration")
    _keys(replay["kernel"], "U M G")
    for bucket in replay["kernel"].values():
        _keys(
            bucket,
            "stopped_outputs accepted rejected incorrect_acceptance false_rejection abstained artifact_failures unknown_outcomes approval_coverage",
        )
        if (
            any(not integer(value) for key, value in bucket.items() if key != "approval_coverage")
            or bucket["stopped_outputs"] != len(outcomes)
            or bucket["unknown_outcomes"] != sum(row["valid_completion"] is None for row in outcomes)
            or sum(bucket[key] for key in ("accepted", "rejected", "abstained", "artifact_failures"))
            != len(outcomes)
            or bucket["incorrect_acceptance"] > bucket["accepted"]
            or bucket["false_rejection"] > bucket["rejected"]
        ):
            raise ValueError("invalid original kernel denominator")
        _same(bucket["approval_coverage"], bucket["accepted"] / len(outcomes) if outcomes else None)
    timing = replay["controller_time"]
    _keys(timing, "observed_seconds known_attempts retained_attempts scope")
    if (
        not integer(timing["known_attempts"])
        or timing["known_attempts"] > len(outcomes)
        or type(timing["retained_attempts"]) is not int
        or timing["retained_attempts"] != len(started)
        or timing["scope"] != "setup_agent_capture_visible_and_hidden_verification"
        or (timing["known_attempts"] == 0 and timing["observed_seconds"] is not None)
        or (timing["known_attempts"] > 0 and not duration(timing["observed_seconds"]))
    ):
        raise ValueError("invalid original controller-time denominator")


def _validate_stage_round(admission, stage, development_admission):
    if stage == "heldout" and (
        not isinstance(development_admission, dict)
        or type(development_admission.get("revision")) is not int
        or development_admission["revision"] != admission["development_round"]["revision"]
    ):
        raise ValueError("held-out admission uses a different development round")


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _preserved_kernel(kernel):
    kernel = Path(kernel).resolve()
    if kernel.name != "evalopt_graph" or kernel.parent.name != "src":
        raise ValueError("kernel must be the preserved repository src/evalopt_graph package")
    report = verify_preservation(kernel.parent.parent)
    if report.get("status") != "PASS":
        raise ValueError("kernel source repository failed v1 preservation")
    return kernel


def derive_identities(frozen, admission, manifest):
    """One definition for freeze creation and external-digest-bound verification."""
    frozen = Path(frozen)
    inputs = reviewed_inputs(frozen / "harness", frozen / "skill-c", frozen / "tasks")
    package = frozen / "harness/evalopt_v2"

    def subset(names):
        return digest({name: hashlib.sha256((package / name).read_bytes()).hexdigest() for name in names})

    environment = read_json(frozen / "environment.json")
    if set(environment) != {"agent_image", "verifier_image"} or any(
        not isinstance(value, str) or not value.startswith("sha256:") for value in environment.values()
    ):
        raise ValueError("invalid frozen image environment")
    images = [environment[key].removeprefix("sha256:") for key in ("agent_image", "verifier_image")]
    if not all(_sha(value) for value in images):
        raise ValueError("frozen image digests required")
    controller = ["harbor_bridge.py", "observe.py", "snapshot.py", "preflight.py", "campaign.py"]
    # Legacy freezes predate explicit network configuration. Their exact source
    # manifest and external registration still determine the original identity;
    # every new prepare requires and explicitly pins the new network module.
    if "harness/evalopt_v2/network.py" in manifest:
        controller.append("network.py")
    return {
        "tasks": inputs["tasks"],
        "skill_c": inputs["skill_c"],
        "skill_d": digest(tree_manifest(frozen / "skill-d")),
        "upstream": digest(tree_manifest(frozen / "upstream")),
        "agent_image": images[0],
        "verifier_image": images[1],
        "source": digest({"manifest": manifest, "admission": admission}),
        "grader": subset(["case_runner.py", "grading.py", "verifier.py", "verifier_container.py"]),
        "parser": subset(["framing.py", "accounting.py"]),
        "continuation_policy": subset(["lifecycle.py", "store.py", "campaign.py"]),
        "analysis": subset(["analysis.py", "descriptive.py", "registration.py"]),
        "controller": subset(controller),
    }


def verify_kernel_import(root):
    """Check kernel import custody after verify_frozen has checked the external pin.

    The launcher must prepend frozen/kernel before calling this function. This
    helper never silently swaps an already imported off-path package. It checks
    source origins and retained bytes, not arbitrary mutation of live Python
    objects by trusted controller code.
    """
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("kernel campaign path must be real")
    kernel = root / "frozen/kernel/evalopt_graph"
    manifest = read_json(root / "source-manifest.json")
    prefix = "kernel/evalopt_graph/"
    expected = {
        name.removeprefix(prefix): record for name, record in manifest.items() if name.startswith(prefix)
    }
    if not expected or tree_manifest(kernel) != expected:
        raise ValueError("frozen kernel source changed")
    # -B prevents writes but can still read existing pyc files. Reject these
    # before import rather than letting an unhashed cache choose executed code.
    if any(path.name == "__pycache__" or path.suffix in {".pyc", ".pyo"} for path in kernel.rglob("*")):
        raise ValueError("frozen kernel bytecode cache is not an admitted input")

    def check_module(name, module):
        relative = (
            "__init__.py"
            if name == "evalopt_graph"
            else name.removeprefix("evalopt_graph.").replace(".", "/") + ".py"
        )
        origin = kernel / relative
        spec = getattr(module, "__spec__", None)
        if (
            relative not in expected
            or getattr(module, "__file__", None) != str(origin)
            or spec is None
            or spec.name != name
            or spec.origin != str(origin)
            or origin.resolve() != origin
            or hashlib.sha256(origin.read_bytes()).hexdigest() != expected[relative]["sha256"]
        ):
            raise ValueError("loaded evalopt_graph module is outside frozen kernel or changed")
        if name == "evalopt_graph" and list(getattr(module, "__path__", ())) != [str(kernel)]:
            raise ValueError("kernel package search path escapes frozen source")

    for name, module in list(sys.modules.items()):
        if name == "evalopt_graph" or name.startswith("evalopt_graph."):
            check_module(name, module)
    spec = importlib.util.find_spec("evalopt_graph")
    if (
        spec is None
        or spec.origin != str(kernel / "__init__.py")
        or list(spec.submodule_search_locations or ()) != [str(kernel)]
    ):
        raise ValueError("kernel import does not resolve to frozen package")
    before = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        importlib.import_module("evalopt_graph")
    finally:
        sys.dont_write_bytecode = before
    checked = []
    for name, module in list(sys.modules.items()):
        if name == "evalopt_graph" or name.startswith("evalopt_graph."):
            check_module(name, module)
            checked.append(name)
    return {"status": "PASS", "package_sha256": digest(expected), "modules": sorted(checked)}


def prepare(
    destination,
    *,
    harness,
    skill_c,
    task_root,
    upstream,
    agent_image,
    verifier_image,
    admission,
    kernel,
    stage="development",
    development_admission=None,
):
    harness, skill_c, task_root, upstream = map(
        lambda value: Path(value).resolve(), (harness, skill_c, task_root, upstream)
    )
    if not (harness / "evalopt_v2/network.py").is_file():
        raise ValueError("new freezes require the reviewed network controller")
    kernel = _preserved_kernel(kernel)
    inputs = reviewed_inputs(harness, skill_c, task_root)
    validate_admission(admission, inputs)
    _validate_stage_round(admission, stage, development_admission)
    catalog = strict_json((task_root / "catalog.json").read_bytes())
    tasks = catalog["tasks"] if isinstance(catalog, dict) else catalog
    validate_tasks(tasks, stage)
    image_identity(agent_image)
    image_identity(verifier_image)
    # Validate exact upstream bytes before copying any input or creating a store.
    skill_sources("B", upstream, skill_c, skill_c)
    destination = Path(destination).absolute()
    if destination.exists() or destination.is_symlink() or destination.resolve() != destination:
        raise ValueError("fresh campaign destination required")
    with tempfile.TemporaryDirectory(prefix="evalopt-v2-freeze-", dir=destination.parent) as temporary:
        frozen = Path(temporary).resolve() / "frozen"
        frozen.mkdir()
        copy_tree(harness, frozen / "harness")
        verify_harness_source_only(frozen / "harness")
        copy_tree(skill_c, frozen / "skill-c")
        derive_ablation(frozen / "skill-c", frozen / "skill-d")
        copy_tree(task_root, frozen / "tasks")
        (frozen / "kernel").mkdir()
        copy_tree(kernel, frozen / "kernel/evalopt_graph")
        exclusive_json(
            frozen / "environment.json", {"agent_image": agent_image, "verifier_image": verifier_image}
        )
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        git = ["git", "-c", "core.hooksPath=/dev/null", "-c", "init.templateDir="]
        subprocess.run(
            [
                *git,
                "clone",
                "--quiet",
                "--no-hardlinks",
                "--no-checkout",
                str(upstream),
                str(frozen / "upstream"),
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=60,
        )
        subprocess.run(
            [
                *git,
                "-C",
                str(frozen / "upstream"),
                "sparse-checkout",
                "set",
                "--no-cone",
                "/skills/",
                "/.claude-plugin/",
                "/LICENSE",
            ],
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )
        # Freeze the entire plugin bundle and license from the pinned commit.
        # Non-cone patterns exclude unrelated root files (including upstream's
        # AGENTS.md symlink) without weakening any tree-manifest symlink rule.
        subprocess.run(
            [*git, "-C", str(frozen / "upstream"), "checkout", "--quiet", "--detach", UPSTREAM_COMMIT],
            env=env,
            check=True,
            capture_output=True,
            timeout=30,
        )
        skill_sources("B", frozen / "upstream", frozen / "skill-c", frozen / "skill-d")
        validate_pair(frozen / "skill-c", frozen / "skill-d")
        manifest = tree_manifest(frozen)
        if reviewed_inputs(harness, skill_c, task_root) != inputs:
            raise ValueError("reviewed inputs changed during freeze")
        _preserved_kernel(kernel)
        identities = derive_identities(frozen, admission, manifest)
        registered = registration(tasks, stage, identities, development_admission=development_admission)
        store = CampaignStore.create(destination, registered)
        os.rename(frozen, destination / "frozen")
        sync_directory(destination)
        exclusive_json(destination / "source-manifest.json", manifest)
        exclusive_json(destination / "admission.json", admission)
        receipt = {
            "registration_sha256": registered["registration_sha256"],
            "source_manifest_sha256": digest(manifest),
            "admission_sha256": digest(admission),
        }
        exclusive_json(destination / "freeze.json", receipt)
        verify_frozen(store.root, expected_sha256=registered["registration_sha256"])
        return receipt


def verify_frozen(root, *, expected_sha256):
    root = Path(root).absolute()
    verify_harness_source_only(root / "frozen/harness")
    store = CampaignStore(root, expected_sha256=expected_sha256)
    receipt = read_json(root / "freeze.json")
    manifest = read_json(root / "source-manifest.json")
    admission = read_json(root / "admission.json")
    if receipt != {
        "registration_sha256": expected_sha256,
        "source_manifest_sha256": digest(manifest),
        "admission_sha256": digest(admission),
    } or manifest != tree_manifest(root / "frozen"):
        raise ValueError("frozen campaign inputs changed")
    frozen = root / "frozen"
    validate_admission(admission, reviewed_inputs(frozen / "harness", frozen / "skill-c", frozen / "tasks"))
    _validate_stage_round(admission, store.registration["stage"], store.registration["development_admission"])
    validate_pair(frozen / "skill-c", frozen / "skill-d")
    skill_sources("B", frozen / "upstream", frozen / "skill-c", frozen / "skill-d")
    catalog = strict_json((frozen / "tasks/catalog.json").read_bytes())
    tasks = catalog["tasks"] if isinstance(catalog, dict) else catalog
    validate_tasks(tasks, store.registration["stage"])
    if tasks != store.registration["tasks"]:
        raise ValueError("frozen task catalog differs from registration")
    identities = derive_identities(frozen, admission, manifest)
    if identities != store.registration["identities"]:
        raise ValueError("frozen input identities differ from externally pinned registration")
    return store
