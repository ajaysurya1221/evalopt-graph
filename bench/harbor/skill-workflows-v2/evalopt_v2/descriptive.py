"""Secondary outcome and resource summaries without efficiency inference.

Every scheduled row remains in the outcome denominator. Resource summaries use
every retained attempt, including classified infrastructure retries. Unknown
counters remain unknown; observed lower bounds never become estimated totals.
"""

from __future__ import annotations

import math

from .accounting import COUNTERS, validate_usage
from .registration import ARMS, CATEGORIES


def _counts(values):
    values = list(values)
    if any(type(value) is not bool and value is not None for value in values):
        raise ValueError("secondary outcomes must be boolean or null")
    true = sum(value is True for value in values)
    false = sum(value is False for value in values)
    return {"true": true, "false": false, "unknown": len(values) - true - false, "scheduled": len(values)}


def outcomes(resolved):
    """Input is the full, schedule-validated output from analysis.reconcile."""
    result = {}
    for arm in ARMS:
        selected = [row for row in resolved if row["arm"] == arm]
        result[arm] = {
            "functional_success": _counts(row["reported_functional_success"] for row in selected),
            "unsupported_success": _counts(
                None if row["task_disputed"] else row.get("unsupported_success") for row in selected
            ),
            "incorrect_refusal": _counts(
                None if row["task_disputed"] else row.get("incorrect_refusal") for row in selected
            ),
            "boundary_violation": _counts(row.get("boundary_violation") for row in selected),
            "categories": {
                category: _counts(
                    row["reported_valid_completion"] for row in selected if row["category"] == category
                )
                for category in CATEGORIES
            },
        }
    return result


def resources(schedule, attempts):
    """Validate attempt identity once, sum only authenticated-by-caller usage.

    Wire schemas verify arithmetic, not custody. The caller must first verify the
    retained controller manifest. This reducer never reads candidate artifacts.
    """
    registered = {row["trial_id"]: row for row in schedule}
    if len(registered) != len(schedule):
        raise ValueError("duplicate scheduled trial")
    seen = set()
    output = {}
    for arm in ARMS:
        output[arm] = {
            "attempts": 0,
            "complete_usage_attempts": 0,
            "partial_usage_attempts": 0,
            "unavailable_usage_attempts": 0,
            "exact_totals": None,
            "observed_lower_bounds": dict.fromkeys(COUNTERS),
            "agent_wall_seconds_observed": None,
            "agent_wall_seconds_known_attempts": 0,
            "efficiency_claim_allowed": False,
        }
    for attempt in attempts:
        trial_id = attempt.get("trial_id")
        number = attempt.get("attempt")
        if trial_id not in registered or type(number) is not int or number not in (1, 2):
            raise ValueError("unregistered attempt identity")
        key = trial_id, number
        if key in seen:
            raise ValueError("duplicate attempt would double count consumption")
        seen.add(key)
        usage = attempt["usage"]
        validate_usage(usage)
        bucket = output[registered[trial_id]["arm"]]
        bucket["attempts"] += 1
        bucket[f"{usage['accounting_status']}_usage_attempts"] += 1
        for counter in COUNTERS:
            value = usage["lower_bounds"][counter]
            if value is not None:
                previous = bucket["observed_lower_bounds"][counter]
                bucket["observed_lower_bounds"][counter] = (0 if previous is None else previous) + value
        seconds = attempt.get("agent_wall_seconds")
        if seconds is not None:
            if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
                raise ValueError("invalid observed duration")
            bucket["agent_wall_seconds_observed"] = (bucket["agent_wall_seconds_observed"] or 0) + seconds
            bucket["agent_wall_seconds_known_attempts"] += 1
    for bucket in output.values():
        if bucket["attempts"] and bucket["complete_usage_attempts"] == bucket["attempts"]:
            bucket["exact_totals"] = dict(bucket["observed_lower_bounds"])
    return output


def kernel_metrics(rows):
    """All supplied stopped outputs, with acceptance and abstention together.

    rows contain the immutable U/M/G decisions and subsequent hidden valid
    completion. A missing policy artifact counts as artifact failure, not reject.
    """
    result = {}
    seen = set()
    for row in rows:
        if row["trial_id"] in seen:
            raise ValueError("duplicate stopped output")
        seen.add(row["trial_id"])
        _counts([row["valid_completion"]])
    for policy in ("U", "M", "G"):
        bucket = dict.fromkeys(
            (
                "stopped_outputs",
                "accepted",
                "rejected",
                "incorrect_acceptance",
                "false_rejection",
                "abstained",
                "artifact_failures",
                "unknown_outcomes",
            ),
            0,
        )
        for row in rows:
            bucket["stopped_outputs"] += 1
            if row["valid_completion"] is None:
                bucket["unknown_outcomes"] += 1
            decisions = row.get("policies")
            if decisions is None or policy not in decisions:
                bucket["artifact_failures"] += 1
                continue
            accepted = decisions[policy].get("accepted")
            if type(accepted) is not bool:
                raise ValueError("invalid acceptance record")
            # Kernel abstention is represented by its existing UNVERIFIED or
            # UNSUPPORTED statuses; do not introduce a new stable status.
            if policy == "G" and decisions[policy].get("decision", {}).get("status") in {
                "UNVERIFIED",
                "UNSUPPORTED",
            }:
                if accepted:
                    raise ValueError("abstention cannot be acceptance")
                bucket["abstained"] += 1
            elif accepted:
                bucket["accepted"] += 1
                bucket["incorrect_acceptance"] += row["valid_completion"] is False
            else:
                bucket["rejected"] += 1
                bucket["false_rejection"] += row["valid_completion"] is True
        denominator = bucket["stopped_outputs"]
        bucket["approval_coverage"] = bucket["accepted"] / denominator if denominator else None
        result[policy] = bucket
    return result
