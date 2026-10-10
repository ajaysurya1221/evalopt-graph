"""Controller-side collection and pure grading; expected values never enter a child."""

from __future__ import annotations

import hashlib
import math
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

from .case_runner import (
    CHILD,
    SCHEMA,
    canonical,
    digest,
    execute_process,
    run_case,
    snapshot_manifest,
    strict_json,
    validate_invocation,
    validate_request,
)
from .grading import evaluate_case, evaluate_witness, grade_task, validate_case
from .replay_grade import case_boundaries_confirmed


class CaseBoundaryError(OSError):
    """A case's descendants may still be running; no later case may start."""


class OracleDomainError(ValueError):
    """The data witness is outside the published finite review domain."""


def _duration(value):
    if type(value) not in {int, float} or not math.isfinite(value) or value <= 0:
        raise ValueError("invalid time budget")
    return value


def collect_cases(
    cases, invoke, *, total_seconds=120, case_seconds=5, clock=time.monotonic, record_sink=None
):
    """Invoke every case even after failures; explicitly record budget skips.

    ``invoke(request, timeout_seconds=..., deadline=...)`` must honor the absolute
    monotonic deadline, including setup. Safety closure may finish afterward.
    A sink failure propagates; evidence loss cannot be converted into success.
    """
    _duration(total_seconds)
    _duration(case_seconds)
    cases = strict_json(canonical(cases))
    ids = [validate_case(case)["case_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case identity")
    deadline = clock() + total_seconds
    result = []
    boundary_unknown = False
    for case in cases:
        request = strict_json(canonical(case["request"]))
        remaining = deadline - clock()
        if boundary_unknown or remaining <= 0:
            actual = {
                "schema_version": SCHEMA,
                "request": request,
                "state": "not_run",
                "reason": "prior_case_boundary_unconfirmed"
                if boundary_unknown
                else "verifier_budget_exhausted",
            }
        else:
            try:
                actual = invoke(
                    strict_json(canonical(request)),
                    timeout_seconds=min(remaining, case_seconds),
                    deadline=deadline - remaining + min(remaining, case_seconds),
                )
                validate_invocation(actual, request)
                actual = strict_json(canonical(actual))
            except CaseBoundaryError:
                boundary_unknown = True
                actual = {
                    "schema_version": SCHEMA,
                    "request": request,
                    "state": "not_run",
                    "reason": "case_boundary_unconfirmed",
                }
            except TimeoutError:
                actual = {
                    "schema_version": SCHEMA,
                    "request": request,
                    "state": "timeout",
                    "reason": "case_deadline",
                }
            except (OSError, ValueError, TypeError, RecursionError):
                actual = {
                    "schema_version": SCHEMA,
                    "request": request,
                    "state": "not_run",
                    "reason": "invoker_evidence_unavailable",
                }
        record = {
            "schema_version": SCHEMA,
            "record_type": "case_evidence",
            "case_id": case["case_id"],
            "invocation": actual,
            "evaluation": evaluate_case(case, actual),
        }
        if record_sink is not None:
            record_sink(strict_json(canonical(record)))
        result.append(record)
    return result


def collect_witnesses(
    task,
    baseline,
    candidate,
    findings,
    oracle,
    *,
    total_seconds=120,
    case_seconds=5,
    clock=time.monotonic,
    record_sink=None,
    invoke=None,
    trusted_fixture=False,
):
    """Run reported witnesses on real snapshots; the oracle runs only in the controller.

    ``oracle`` is trusted authored code returning {kind,value} or {kind,builtin}.
    It receives a copied request, not mutable expected objects shared with children.
    """
    _duration(total_seconds)
    _duration(case_seconds)
    if invoke is None:
        if trusted_fixture is not True:
            raise ValueError("a sandbox invoker is required outside authored local fixtures")

        def invoke(snapshot, request, **limits):
            return run_case(snapshot, request, trusted_fixture=True, **limits)

    if not isinstance(findings, list) or len(findings) > task.get("max_findings", 16):
        raise ValueError("finding roster exceeds declared limit")
    deadline = clock() + total_seconds
    manifests = snapshot_manifest(baseline), snapshot_manifest(candidate)
    records = []
    boundary_unknown = False
    for finding in strict_json(canonical(findings)):
        record = {"schema_version": SCHEMA, "record_type": "review_witness", "finding": finding}
        request = finding.get("witness") if isinstance(finding, dict) else None
        if boundary_unknown:
            record["not_executed_reason"] = "prior_case_boundary_unconfirmed"
            record.update(evaluate_witness(task, finding, record))
        elif not isinstance(request, dict):
            record.update(evaluate_witness(task, finding, record))
        elif request.get("kind") == "removed-required-test":
            record.update(baseline_manifest=manifests[0], candidate_manifest=manifests[1])
            record.update(evaluate_witness(task, finding, record))
        elif clock() >= deadline:
            record["not_executed_reason"] = "verifier_budget_exhausted"
            record.update(evaluate_witness(task, finding, record))
        else:
            try:
                request = validate_request(request)
                expected = strict_json(canonical(oracle(strict_json(canonical(request)))))
                validate_case(
                    {"case_id": "witness", "request": request, "expect": expected, "preserve_args": True}
                )
                record["expect"] = expected
                for label, snapshot in (("baseline", baseline), ("candidate", candidate)):
                    remaining = deadline - clock()
                    if remaining <= 0:
                        record[label] = {
                            "schema_version": SCHEMA,
                            "request": request,
                            "state": "not_run",
                            "reason": "verifier_budget_exhausted",
                        }
                    else:
                        record[label] = invoke(
                            snapshot,
                            strict_json(canonical(request)),
                            timeout_seconds=min(remaining, case_seconds),
                            deadline=deadline - remaining + min(remaining, case_seconds),
                        )
            except OracleDomainError:
                record["not_executed_reason"] = "witness_outside_published_domain"
            except CaseBoundaryError:
                boundary_unknown = True
                record["not_executed_reason"] = "case_boundary_unconfirmed"
            except (ValueError, TypeError, OSError, RecursionError):
                record["not_executed_reason"] = "witness_oracle_or_execution_unavailable"
            record.update(evaluate_witness(task, finding, record))
        if record_sink is not None:
            record_sink(strict_json(canonical(record)))
        records.append(record)
    return records


def _case_boundaries_confirmed(records, witnesses):
    """Summary of production containment, independent of functional grading."""
    return case_boundaries_confirmed(records, witnesses)


def verify_task(
    task,
    snapshot,
    response,
    observations,
    *,
    baseline=None,
    oracle=None,
    boundary_violations=(),
    total_seconds=120,
    case_seconds=5,
    record_sink=None,
    invoke=None,
    trusted_fixture=False,
    lifecycle_verified=None,
    timed_out=False,
):
    """Offline authored-fixture adapter. No model calls or policy decisions occur here."""
    records, witnesses = [], []
    if invoke is None:
        if trusted_fixture is not True:
            raise ValueError("a sandbox invoker is required outside authored local fixtures")

        def invoke(root, request, **limits):
            return run_case(root, request, trusted_fixture=True, **limits)

    if task["task_contract"] == "implementation":
        records = collect_cases(
            task["cases"],
            lambda request, **limits: invoke(snapshot, request, **limits),
            total_seconds=total_seconds,
            case_seconds=case_seconds,
            record_sink=record_sink,
        )
    elif task["task_contract"] == "review":
        if baseline is None or oracle is None:
            raise ValueError("review requires baseline and trusted oracle")
        findings = response.get("findings", []) if isinstance(response, dict) else []
        if not isinstance(findings, list) or len(findings) > task.get("max_findings", 16):
            findings = []
        witnesses = collect_witnesses(
            task,
            baseline,
            snapshot,
            findings,
            oracle,
            total_seconds=total_seconds,
            case_seconds=case_seconds,
            record_sink=record_sink,
            invoke=invoke,
        )
    grade = grade_task(
        task,
        response,
        observations,
        records,
        boundary_violations=boundary_violations,
        review_witnesses=witnesses,
        lifecycle_verified=lifecycle_verified,
        timed_out=timed_out,
    )
    return {
        "schema_version": SCHEMA,
        "record_type": "verification_bundle",
        "grade": grade,
        "case_records": records,
        "review_witnesses": witnesses,
        "case_boundary_confirmed": _case_boundaries_confirmed(records, witnesses),
    }


def finite_oracle(entries):
    """A trusted finite contract catalog, never forwarded to the candidate."""
    lookup = {}
    if not isinstance(entries, list):
        raise ValueError("oracle catalog must be a list")
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"request", "expect"}:
            raise ValueError("invalid oracle entry")
        validate_case({"case_id": "oracle", **entry, "preserve_args": True})
        key = canonical(entry["request"])
        if key in lookup:
            raise ValueError("duplicate oracle request")
        lookup[key] = canonical(entry["expect"])

    def oracle(request):
        try:
            return strict_json(lookup[canonical(validate_request(request))])
        except KeyError as error:
            raise OracleDomainError("witness outside the finite authored oracle") from error

    return oracle


def chroot_invoker(chroot_root="/candidate-root"):
    """Create the production invoker inside an already isolated Linux verifier.

    The caller supplies a container with network disabled and resource limits.
    This function does not start containers or mount host files. The rootfs must
    contain only its runtime, with trusted task/oracle/output files outside it.
    ``chroot`` plus dropping UID prevents candidate access to those files; it is
    not a substitute for the outer container boundary.
    """
    root = Path(chroot_root)
    if sys.platform != "linux" or os.geteuid() != 0:
        raise ValueError("production verifier requires Linux root before UID drop")
    if root.is_symlink() or root.resolve() != root or not (root / "usr/bin/python3").is_file():
        raise ValueError("invalid isolated runtime root")
    # No shared writable temporary directory is visible across calls. A case may
    # leave arbitrary files in /tmp; removing cross-case storage also eliminates
    # dependence on earlier witness inputs. Runtime tasks cannot use /proc here.
    for forbidden in ("trusted", "output", "snapshot", "proc", "dev"):
        if (root / forbidden).exists():
            raise ValueError("unexpected rootfs path could expose controller data")
    temporary = root / "tmp"
    if temporary.is_symlink() or (temporary.exists() and any(temporary.iterdir())):
        raise ValueError("isolated runtime tmp must start empty")
    if temporary.exists():
        temporary.chmod(0o555)

    def invoke(snapshot, request, *, timeout_seconds=5):
        request = validate_request(request)
        source = Path(snapshot)
        before = snapshot_manifest(source)
        if not (source / (request["module"] + ".py")).is_file():
            raise ValueError("requested module absent")
        with tempfile.TemporaryDirectory(prefix="case-", dir=root) as scratch:
            workspace = Path(scratch) / "workspace"
            shutil.copytree(source, workspace)
            if snapshot_manifest(workspace) != before or snapshot_manifest(source) != before:
                raise ValueError("snapshot changed while preparing isolated call")
            for node in workspace.rglob("*"):
                node.chmod(0o555 if node.is_dir() else 0o444)
            workspace.chmod(0o555)
            Path(scratch).chmod(0o555)
            relative = "/" + workspace.relative_to(root).as_posix()
            wrapper = "import os\nos.chdir(" + repr(relative) + ")\n" + CHILD
            argv = [
                "/usr/sbin/chroot",
                "--userspec=65534:65534",
                str(root),
                "/usr/bin/python3",
                "-I",
                "-B",
                "-c",
                wrapper,
            ]
            record = execute_process(
                request,
                argv,
                cwd=root,
                timeout_seconds=timeout_seconds,
                record={
                    "schema_version": SCHEMA,
                    "record_type": "case_invocation",
                    "request": request,
                    "candidate_id": digest(before),
                    "runner_sha256": hashlib.sha256(CHILD.encode()).hexdigest(),
                    "isolation": "chroot_unprivileged_requires_outer_case_container",
                },
            )
        if snapshot_manifest(source) != before:
            raise ValueError("original stopped snapshot changed")
        return record

    return invoke


def verify_container(
    task,
    snapshot,
    response,
    observations,
    *,
    output,
    baseline=None,
    oracle_cases=(),
    chroot_root="/candidate-root",
    boundary_violations=(),
    lifecycle_verified=None,
    timed_out=False,
    total_seconds=120,
    case_seconds=5,
):
    """Reject the obsolete shared-container entrypoint before executing cases.

    A shared chroot does not contain detached descendants between invocations.
    Use host verify_task with the fresh-container adapter and a durable sink.
    """
    output = Path(output)
    root = Path(chroot_root).resolve()
    if (
        not output.is_dir()
        or output.is_symlink()
        or output.resolve().is_relative_to(root)
        or any(output.iterdir())
    ):
        raise ValueError("output must be an empty controller directory outside chroot")
    raise ValueError(
        "whole-task shared verifier containers are not a per-case process boundary; "
        "use verify_task with verifier_container.docker_invoker"
    )


def main():
    """Fixed production mount contract; launch from a trusted package bootstrap."""
    control = strict_json(Path("/trusted/input.json").read_text(encoding="utf-8"))
    required = {
        "task",
        "response",
        "observations",
        "oracle_cases",
        "baseline_present",
        "boundary_violations",
        "lifecycle_verified",
        "timed_out",
        "total_seconds",
        "case_seconds",
    }
    if (
        not isinstance(control, dict)
        or set(control) != required
        or type(control["baseline_present"]) is not bool
    ):
        raise ValueError("invalid trusted verifier input")
    verify_container(
        control["task"],
        Path("/snapshot"),
        control["response"],
        control["observations"],
        output=Path("/output"),
        baseline=Path("/trusted/baseline") if control["baseline_present"] else None,
        **{key: control[key] for key in required - {"task", "response", "observations", "baseline_present"}},
    )


if __name__ == "__main__":
    main()
