"""Recompute retained semantic grades without importing or executing candidates.

The caller first verifies the frozen task and retained-artifact manifests. This
module checks consistency against independently loaded per-case records; it is
not authentication against coordinated rewriting of all controller evidence.
"""

from __future__ import annotations

import re

from .case_runner import SCHEMA, validate_invocation, validate_request
from .grading import evaluate_witness, grade_task, validate_case
from .records import canonical, digest


def _same(left, right, reason):
    if canonical(left) != canonical(right):
        raise ValueError(reason)


def _oracle_lookup(entries):
    if not isinstance(entries, list):
        raise ValueError("replay requires the frozen review oracle catalog")
    lookup = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"request", "expect"}:
            raise ValueError("invalid frozen oracle entry")
        validate_case({"case_id": "oracle", **entry, "preserve_args": True})
        key = canonical(entry["request"])
        if key in lookup:
            raise ValueError("duplicate frozen oracle request")
        lookup[key] = entry["expect"]
    return lookup


def _invocation(record, request, manifest, seen_containers):
    validate_invocation(record, request)
    boundary = record.get("container_boundary")
    # A host TimeoutError has no observed execution identity. Retain that exact
    # evidence-poor failure without inventing identity or confirmed containment.
    host_timeout_gap = (
        set(record) == {"schema_version", "request", "state", "reason"}
        and record["state"] == "timeout"
        and record["reason"] == "case_deadline"
    )
    if (
        record["state"] != "not_run"
        and not host_timeout_gap
        or isinstance(boundary, dict)
        and boundary.get("status") == "confirmed"
    ) and "candidate_id" not in record:
        raise ValueError("executed invocation lacks snapshot identity")
    if "candidate_id" in record:
        if not isinstance(manifest, dict):
            raise ValueError("invocation replay requires its snapshot manifest")
        _same(record["candidate_id"], digest(manifest), "invocation snapshot identity changed")
    if "container_boundary" in record:
        if not isinstance(boundary, dict) or boundary.get("status") not in {
            "confirmed",
            "not_started",
            "unconfirmed",
        }:
            raise ValueError("invalid retained case boundary")
        if boundary["status"] == "confirmed":
            if not _confirmed_boundary(boundary):
                raise ValueError("confirmed case boundary lacks complete identity")
            identity = boundary["container_id"]
            if identity in seen_containers:
                raise ValueError("duplicate case container identity")
            seen_containers.add(identity)


def _confirmed_boundary(boundary):
    return (
        isinstance(boundary, dict)
        and set(boundary) == {"status", "container_id", "image_id", "case_label"}
        and boundary["status"] == "confirmed"
        and isinstance(boundary["container_id"], str)
        and re.fullmatch(r"[0-9a-f]{64}", boundary["container_id"]) is not None
        and isinstance(boundary["image_id"], str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", boundary["image_id"]) is not None
        and isinstance(boundary["case_label"], str)
        and re.fullmatch(r"[0-9a-f]{32}", boundary["case_label"]) is not None
    )


def case_boundaries_confirmed(records, witnesses):
    """Shared live/replay containment projection; skips cannot override uncertainty."""
    safe_skips = {"verifier_budget_exhausted", "witness_outside_published_domain", "case_setup_deadline"}
    invocations = [record["invocation"] for record in records]
    for witness in witnesses:
        reason = witness.get("not_executed_reason")
        if reason and reason not in safe_skips:
            return False
        invocations.extend(witness[label] for label in ("baseline", "candidate") if label in witness)
    for actual in invocations:
        safe_skip = actual.get("state") == "not_run" and actual.get("reason") in safe_skips
        if "container_boundary" not in actual:
            if safe_skip:
                continue
            return False
        boundary = actual["container_boundary"]
        if safe_skip and boundary == {"status": "not_started"}:
            continue
        if not _confirmed_boundary(boundary):
            return False
    return True


def replay_grade(
    task,
    verification,
    *,
    response,
    observations,
    visible_candidate_id,
    boundary_violations,
    lifecycle_verified,
    timed_out,
    retained_records,
    oracle_cases=None,
    baseline_manifest=None,
    candidate_manifest=None,
):
    """Return the reproduced grade, rejecting any retained-bundle disagreement.

    ``retained_records`` is the independently loaded, ordered case-NNNN.json
    roster. Manifests use case_runner.snapshot_manifest (raw file identities,
    including the raw Git index), not the normalized workspace boundary view.
    ``visible_candidate_id`` independently binds the normalized visible snapshot;
    it need not equal raw per-case snapshot digests. Review expectations come
    from the frozen oracle catalog. No path, command,
    candidate function or oracle function is accepted or executed here.
    """
    canonical([task, verification, response, observations, retained_records])
    if (
        not isinstance(visible_candidate_id, str)
        or re.fullmatch(r"[0-9a-f]{64}", visible_candidate_id) is None
    ):
        raise ValueError("expected visible snapshot identity is required")
    if not isinstance(observations, list) or len(observations) != 1 or not isinstance(observations[0], dict):
        raise ValueError("exactly one retained visible observation is required")
    _same(
        observations[0].get("candidate_id"),
        visible_candidate_id,
        "visible observation snapshot identity changed",
    )
    if not isinstance(verification, dict) or set(verification) != {
        "schema_version",
        "record_type",
        "grade",
        "case_records",
        "review_witnesses",
        "case_boundary_confirmed",
    }:
        raise ValueError("invalid verification bundle fields")
    if verification["schema_version"] != SCHEMA or verification["record_type"] != "verification_bundle":
        raise ValueError("invalid verification bundle schema")
    if type(verification["case_boundary_confirmed"]) is not bool:
        raise ValueError("case boundary summary must be boolean")
    if lifecycle_verified is not None and type(lifecycle_verified) is not bool:
        raise ValueError("invalid retained lifecycle status")
    if type(timed_out) is not bool:
        raise ValueError("invalid retained timeout status")
    if not isinstance(boundary_violations, (list, tuple)) or any(
        not isinstance(item, str) or not item for item in boundary_violations
    ):
        raise ValueError("invalid retained boundary violations")
    records, witnesses = verification["case_records"], verification["review_witnesses"]
    if not all(isinstance(value, list) for value in (records, witnesses, retained_records)):
        raise ValueError("retained record roster must be a list")
    _same(records + witnesses, retained_records, "bundle differs from retained per-case records")
    contract = task.get("task_contract")
    seen_containers = set()
    if contract == "implementation":
        if witnesses:
            raise ValueError("implementation has unexpected review witnesses")
        cases = task.get("cases")
        if not isinstance(cases, list) or len(cases) != len(records):
            raise ValueError("case roster incomplete")
        seen = set()
        for case, record in zip(cases, records, strict=True):
            validate_case(case)
            if not isinstance(record, dict) or set(record) != {
                "schema_version",
                "record_type",
                "case_id",
                "invocation",
                "evaluation",
            }:
                raise ValueError("invalid case evidence fields")
            if record["schema_version"] != SCHEMA or record["record_type"] != "case_evidence":
                raise ValueError("invalid case evidence schema")
            if record["case_id"] != case["case_id"] or case["case_id"] in seen:
                raise ValueError("case identity missing, duplicated or reordered")
            seen.add(case["case_id"])
            _invocation(record["invocation"], case["request"], candidate_manifest, seen_containers)
    elif contract == "review":
        if records:
            raise ValueError("review has unexpected implementation case records")
        lookup = _oracle_lookup(oracle_cases)
        findings = response.get("findings", []) if isinstance(response, dict) else []
        if not isinstance(findings, list) or len(findings) > task.get("max_findings", 16):
            findings = []
        if len(findings) != len(witnesses):
            raise ValueError("review witness roster incomplete")
        for finding, witness in zip(findings, witnesses, strict=True):
            if not isinstance(witness, dict) or not {
                "schema_version",
                "record_type",
                "finding",
                "supported",
                "obligation_ids",
                "reason",
            } <= set(witness) <= {
                "schema_version",
                "record_type",
                "finding",
                "supported",
                "obligation_ids",
                "reason",
                "expect",
                "baseline",
                "candidate",
                "baseline_manifest",
                "candidate_manifest",
                "not_executed_reason",
            }:
                raise ValueError("invalid review witness fields")
            if witness["schema_version"] != SCHEMA or witness["record_type"] != "review_witness":
                raise ValueError("invalid review witness schema")
            _same(witness["finding"], finding, "witness belongs to another finding")
            request = finding.get("witness") if isinstance(finding, dict) else None
            structural = isinstance(request, dict) and request.get("kind") == "removed-required-test"
            if structural:
                for label, manifest in (("baseline", baseline_manifest), ("candidate", candidate_manifest)):
                    key = label + "_manifest"
                    if key in witness:
                        if not isinstance(manifest, dict):
                            raise ValueError("structural replay requires retained snapshot manifests")
                        _same(witness[key], manifest, "structural witness manifest changed")
                if any(key in witness for key in ("expect", "baseline", "candidate")):
                    raise ValueError("structural witness contains callable evidence")
            else:
                if any(key in witness for key in ("baseline_manifest", "candidate_manifest")):
                    raise ValueError("callable witness contains structural evidence")
                if "expect" in witness:
                    key = canonical(validate_request(request))
                    if key not in lookup:
                        raise ValueError("witness expectation is outside the frozen oracle")
                    _same(witness["expect"], lookup[key], "witness expectation differs from frozen oracle")
                if witness.get("not_executed_reason") == "witness_outside_published_domain":
                    if canonical(validate_request(request)) in lookup:
                        raise ValueError("in-domain witness falsely reported outside the oracle")
                for label, manifest in (("baseline", baseline_manifest), ("candidate", candidate_manifest)):
                    if label in witness:
                        if "expect" not in witness:
                            raise ValueError("invoked review witness lacks frozen expectation")
                        _invocation(witness[label], request, manifest, seen_containers)
            try:
                evaluated = evaluate_witness(task, finding, witness)
            except (KeyError, TypeError) as error:
                raise ValueError("witness evidence incomplete or malformed") from error
            _same(evaluated, {key: witness[key] for key in evaluated}, "witness verdict is not reproducible")
    elif contract == "blocker_report":
        if records or witnesses:
            raise ValueError("blocker report has unexpected execution records")
    else:
        raise ValueError("unsupported replay task contract")
    _same(
        verification["case_boundary_confirmed"],
        case_boundaries_confirmed(records, witnesses),
        "case boundary summary is not reproducible",
    )
    reproduced = grade_task(
        task,
        response,
        observations,
        records,
        boundary_violations=boundary_violations,
        review_witnesses=witnesses,
        lifecycle_verified=lifecycle_verified,
        timed_out=timed_out,
    )
    _same(reproduced, verification["grade"], "retained semantic grade is not reproducible")
    return reproduced
