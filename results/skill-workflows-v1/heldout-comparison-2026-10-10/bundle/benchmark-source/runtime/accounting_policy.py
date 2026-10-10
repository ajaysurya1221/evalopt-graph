"""Explicit, source-bound partial-accounting policy for newly frozen campaigns.

This changes neither grading nor the stopped-output acceptance policy. Supplied
controller counters remain evidence, not authentication or recovered missing usage.
"""

from __future__ import annotations

import copy
from pathlib import Path

from lib.common import bytes_digest, digest, exact, is_digest, read_json
from runtime.controller import require_controller
from runtime.partial_accounting import derive_partial_usage

HERE = Path(__file__).resolve().parent
COUNTERS = ("input_tokens", "output_tokens", "model_calls", "tool_calls")
RULES = {
    "accepted_accounting": ["complete", "partial"],
    "required_provenance": "valid",
    "required_delegation_boundary": "verified",
    "runtime_valid_required": True,
    "partial_counts_are_lower_bounds": True,
    "partial_efficiency_comparisons": False,
}
DERIVED_KEYS = {
    "schema_version",
    "accounting_status",
    "provenance_status",
    "child_usage_complete",
    "lower_bounds",
    "completeness_reasons",
    "efficiency_eligible",
    "delegation_boundary_status",
    "agents",
    "complete_usage",
    "source_log_sha256",
}
INCOMPLETE_REASONS = {
    "owned_turn_start_missing",
    "owned_turn_end_missing",
    "owned_turn_aborted",
    "owned_turns_missing",
    "owned_turn_usage_missing",
    "owned_response_usage_missing",
}
REASONS = INCOMPLETE_REASONS | {
    "duplicate_json_field",
    "invalid_native_json",
    "native_log_directory_missing",
    "native_log_symlink",
    "native_log_not_regular",
    "missing_lifecycle_timestamp",
    "invalid_lifecycle_timestamp",
    "empty_native_log",
    "invalid_native_record",
    "invalid_native_turn_identity",
    "native_owner_metadata_missing",
    "duplicate_or_missing_native_owner",
    "unsupported_native_cli_version",
    "unknown_native_session_source",
    "delegation_depth_exceeded",
    "invalid_native_child_identity",
    "native_session_logs_missing",
    "native_parent_roster_invalid",
    "duplicate_native_child_path",
    "native_parent_or_depth_invalid",
    "ambiguous_native_turn_ownership",
    "unknown_copied_session_owner",
    "missing_native_response_identity",
    "duplicate_native_response_usage",
    "unattributable_native_response_turn",
    "invalid_native_token_counter",
    "unknown_native_token_counter",
    "missing_native_token_counter",
    "unattributable_copied_response_usage",
    "duplicate_or_unordered_native_start",
    "duplicate_native_turn_end",
    "unattributable_native_tool_call",
    "native_tool_after_turn_end",
    "duplicate_or_missing_native_tool_call",
    "duplicate_native_spawn_result",
    "unknown_native_spawn_result",
    "duplicate_or_invalid_spawned_child",
    "unresolved_native_spawn_roster",
    "native_end_precedes_start",
    "native_child_roster_mismatch",
    "native_child_concurrency_exceeded",
    "child_concurrency_unverified",
    "strict_parser_rejected_complete_evidence",
    "strict_parser_counter_mismatch",
    "native_logs_changed_during_derivation",
    "native_logs_unreadable",
}


def source_pins():
    return {
        "partial_parser_sha256": bytes_digest((HERE / "partial_accounting.py").read_bytes()),
        "strict_parser_sha256": bytes_digest((HERE.parent / "lib/accounting.py").read_bytes()),
        "admission_helper_sha256": bytes_digest(Path(__file__).read_bytes()),
    }


def build_policy(pilot_evidence, review_sha256):
    require_controller()
    accounting = pilot_evidence.get("accounting", {})
    if pilot_evidence.get("schema_version") != "evalopt.pilot-evidence.v2" or accounting.get(
        "rules_sha256"
    ) != digest(RULES):
        raise ValueError("campaign partial accounting requires reviewed pilot evidence v2")
    policy = {
        "schema_version": "evalopt.campaign-accounting-policy.v1",
        "rules": copy.deepcopy(RULES),
        "source_pins": source_pins(),
        "approval": {
            "pilot_registration_sha256": pilot_evidence["registration_sha256"],
            "pilot_review_sha256": review_sha256,
            "accounting_amendment_sha256": accounting["amendment_sha256"],
            "accounting_report_sha256": accounting["resource_report_sha256"],
        },
    }
    return validate_policy(policy)


def validate_policy(policy, expected_sha256=None):
    require_controller()
    exact(policy, {"schema_version", "rules", "source_pins", "approval"}, "accounting policy")
    if policy["schema_version"] != "evalopt.campaign-accounting-policy.v1" or digest(
        policy["rules"]
    ) != digest(RULES):
        raise ValueError("unsupported campaign accounting policy")
    if expected_sha256 is not None and (not is_digest(expected_sha256) or digest(policy) != expected_sha256):
        raise ValueError("accounting policy differs from frozen identity")
    if policy["source_pins"] != source_pins():
        raise ValueError("accounting policy implementation source changed")
    approval = exact(
        policy["approval"],
        {
            "pilot_registration_sha256",
            "pilot_review_sha256",
            "accounting_amendment_sha256",
            "accounting_report_sha256",
        },
        "accounting approval",
    )
    if any(not is_digest(value) for value in approval.values()):
        raise ValueError("accounting policy has unresolved approval identities")
    return policy


def read_accounting_policy(destination):
    """Legacy registrations have no accounting policy; v2 requires an exact lock entry."""
    destination = Path(destination)
    path = destination / "accounting-policy.json"
    freeze_path = destination / "freeze.json"
    freeze = read_json(freeze_path) if freeze_path.is_file() else {}
    if freeze.get("schema_version") != "evalopt.heldout-freeze.v2":
        if path.exists():
            raise ValueError("accounting policy is not registered by a heldout v2 freeze")
        return None
    if not is_digest(freeze.get("accounting_policy_sha256")):
        raise ValueError("heldout v2 freeze lacks its accounting policy identity")
    policy = validate_policy(read_json(path), freeze["accounting_policy_sha256"])
    lock = read_json(destination / "heldout-lock.json")
    if lock.get("accounting-policy.json") != bytes_digest(path.read_bytes()):
        raise ValueError("accounting policy is not bound to the heldout lock")
    evidence = read_json(destination / "pilot-evidence.json")
    review_path = destination / "pilot-review.json"
    review = read_json(review_path)
    accounting = exact(
        evidence.get("accounting"),
        {
            "amendment_sha256",
            "resource_report_sha256",
            "rules_sha256",
            "complete_final_attempts",
            "partial_final_attempts",
            "retained_attempts",
            "unavailable_attempts",
        },
        "reviewed pilot accounting evidence",
    )
    reviewed_accounting = exact(
        review.get("accounting"),
        {
            "amendment_sha256",
            "resource_report_sha256",
            "rules_sha256",
        },
        "pilot accounting review",
    )
    if (
        any(not is_digest(accounting[key]) for key in reviewed_accounting)
        or any(
            type(accounting[key]) is not int or accounting[key] < 0
            for key in (
                "complete_final_attempts",
                "partial_final_attempts",
                "retained_attempts",
                "unavailable_attempts",
            )
        )
        or accounting["complete_final_attempts"] + accounting["partial_final_attempts"] != 36
        or not 36 <= accounting["retained_attempts"] <= 72
        or accounting["unavailable_attempts"] != 0
        or type(evidence.get("scheduled_trials")) is not int
        or evidence["scheduled_trials"] != 36
    ):
        raise ValueError("pilot accounting coverage must represent all 36 reviewed outcomes")
    expected_approval = {
        "pilot_registration_sha256": evidence["registration_sha256"],
        "pilot_review_sha256": bytes_digest(review_path.read_bytes()),
        "accounting_amendment_sha256": evidence.get("accounting", {}).get("amendment_sha256"),
        "accounting_report_sha256": evidence.get("accounting", {}).get("resource_report_sha256"),
    }
    if (
        evidence.get("schema_version") != "evalopt.pilot-evidence.v2"
        or review.get("schema_version") != "evalopt.pilot-review.v2"
        or evidence["review_sha256"] != expected_approval["pilot_review_sha256"]
        or review["pilot_registration_sha256"] != evidence["registration_sha256"]
        or policy["approval"] != expected_approval
        or any(reviewed_accounting[key] != accounting[key] for key in reviewed_accounting)
        or evidence["accounting"].get("rules_sha256") != digest(RULES)
    ):
        raise ValueError("accounting policy approval differs from retained pilot review and evidence")
    return policy


def _counts(value, *, nullable=False):
    exact(value, set(COUNTERS), "accounting counters")
    if nullable and all(item is None for item in value.values()):
        return
    if any(type(item) is not int or item < 0 for item in value.values()):
        raise ValueError("invalid accounting counter")


def validate_derived(value):
    exact(value, DERIVED_KEYS, "derived accounting")
    if value["schema_version"] != "evalopt.partial-workflow-usage.v1" or value["accounting_status"] not in {
        "complete",
        "partial",
        "unavailable",
    }:
        raise ValueError("unsupported derived accounting status")
    if value["provenance_status"] not in {"valid", "invalid", "unavailable"} or value[
        "delegation_boundary_status"
    ] not in {"verified", "unverified", "invalid"}:
        raise ValueError("invalid accounting evidence status")
    if type(value["child_usage_complete"]) is not bool or type(value["efficiency_eligible"]) is not bool:
        raise ValueError("accounting completeness must be boolean")
    reasons = value["completeness_reasons"]
    hashes = value["source_log_sha256"]
    if (
        not isinstance(reasons, list)
        or any(not isinstance(item, str) or not item for item in reasons)
        or reasons != sorted(set(reasons))
        or not set(reasons) <= REASONS
    ):
        raise ValueError("invalid accounting incompleteness reasons")
    if (
        not isinstance(hashes, list)
        or hashes != sorted(hashes)
        or any(not is_digest(item) for item in hashes)
    ):
        raise ValueError("invalid native log identities")
    _counts(value["lower_bounds"], nullable=value["accounting_status"] == "unavailable")
    if value["accounting_status"] == "unavailable":
        if (
            value["provenance_status"] == "valid"
            or any(item is not None for item in value["lower_bounds"].values())
            or value["child_usage_complete"]
            or value["efficiency_eligible"]
            or value["complete_usage"] is not None
            or value["agents"] != []
            or not reasons
            or value["delegation_boundary_status"]
            != ("invalid" if value["provenance_status"] == "invalid" else "unverified")
        ):
            raise ValueError("unavailable accounting contradicts its evidence")
        return value
    if (
        value["provenance_status"] != "valid"
        or value["delegation_boundary_status"] == "invalid"
        or not hashes
        or len(set(hashes)) != len(hashes)
    ):
        raise ValueError("usable accounting lacks valid source provenance")
    agents = value["agents"]
    if not isinstance(agents, list) or len(agents) != len(hashes):
        raise ValueError("agent roster differs from retained native sources")
    combined_reasons = set()
    for index, agent in enumerate(agents):
        exact(
            agent,
            {"agent_id", "parent_id", "lower_bounds", "complete", "completeness_reasons"},
            "agent accounting",
        )
        if (
            agent["agent_id"] != f"agent-{index}"
            or agent["parent_id"] != (None if index == 0 else "agent-0")
            or type(agent["complete"]) is not bool
        ):
            raise ValueError("invalid sanitized agent accounting roster")
        _counts(agent["lower_bounds"])
        own_reasons = agent["completeness_reasons"]
        if (
            not isinstance(own_reasons, list)
            or any(not isinstance(item, str) or not item for item in own_reasons)
            or own_reasons != sorted(set(own_reasons))
            or not set(own_reasons) <= INCOMPLETE_REASONS
        ):
            raise ValueError("invalid agent accounting reasons")
        if agent["complete"] != (not own_reasons):
            raise ValueError("agent completeness contradicts its lifecycle reasons")
        no_response = agent["lower_bounds"]["model_calls"] == 0
        if no_response != ("owned_response_usage_missing" in own_reasons) or (
            no_response and any(agent["lower_bounds"][key] for key in ("input_tokens", "output_tokens"))
        ):
            raise ValueError("agent response counters contradict observed tokens or reasons")
        combined_reasons.update(own_reasons)
    if any(
        value["lower_bounds"][key] != sum(agent["lower_bounds"][key] for agent in agents) for key in COUNTERS
    ):
        raise ValueError("aggregate counters differ from exclusive per-agent counters")
    unclosed = any(
        set(agent["completeness_reasons"])
        & {"owned_turn_start_missing", "owned_turn_end_missing", "owned_turns_missing"}
        for agent in agents[1:]
    )
    if (value["delegation_boundary_status"] == "unverified") != unclosed:
        raise ValueError("delegation boundary contradicts child lifecycle evidence")
    if unclosed:
        combined_reasons.add("child_concurrency_unverified")
    if reasons != sorted(combined_reasons):
        raise ValueError("trial completeness reasons differ from exclusive agent evidence")
    if value["accounting_status"] == "partial":
        if (
            value["child_usage_complete"]
            or value["efficiency_eligible"]
            or value["complete_usage"] is not None
            or not reasons
        ):
            raise ValueError("partial accounting cannot claim complete usage")
        return value
    complete = exact(
        value["complete_usage"],
        {
            "schema_version",
            *COUNTERS,
            "wall_seconds",
            "agent_count",
            "aggregation",
            "child_usage_complete",
        },
        "complete accounting",
    )
    if (
        reasons
        or not value["child_usage_complete"]
        or not value["efficiency_eligible"]
        or not all(agent["complete"] for agent in agents)
        or value["delegation_boundary_status"] != "verified"
        or complete["schema_version"] != "evalopt.workflow-usage.v1"
        or complete["child_usage_complete"] is not True
        or complete["aggregation"] != "agent_exclusive"
        or type(complete["agent_count"]) is not int
        or complete["agent_count"] != len(agents)
        or any(
            type(complete[key]) is not int or complete[key] != value["lower_bounds"][key] for key in COUNTERS
        )
        or isinstance(complete["wall_seconds"], bool)
        or not isinstance(complete["wall_seconds"], int | float)
        or not 0 <= complete["wall_seconds"] < float("inf")
    ):
        raise ValueError("complete accounting contradicts retained counters or lifecycle")
    return value


def collect_usage(session_directory, policy):
    validate_policy(policy)
    derived = validate_derived(derive_partial_usage(session_directory))
    usage = dict(
        derived["complete_usage"]
        or {
            "child_usage_complete": False,
            "accounting_status": derived["accounting_status"],
            "raw_logs_retained": True,
        }
    )
    usage["accounting"] = {"policy_sha256": digest(policy), "derived": derived}
    return usage


def validated_projection(usage, expected_policy_sha256):
    if not isinstance(usage, dict):
        raise ValueError("accounting usage missing")
    nested = exact(usage.get("accounting"), {"policy_sha256", "derived"}, "registered accounting")
    if not is_digest(expected_policy_sha256) or nested["policy_sha256"] != expected_policy_sha256:
        raise ValueError("attempt accounting policy differs from campaign")
    derived = validate_derived(nested["derived"])
    if usage.get("child_usage_complete") is not derived["child_usage_complete"]:
        raise ValueError("usage completeness differs from registered projection")
    if derived["accounting_status"] == "complete":
        if digest({key: usage.get(key) for key in derived["complete_usage"]}) != digest(
            derived["complete_usage"]
        ):
            raise ValueError("top-level exact usage differs from registered projection")
    elif any(key in usage for key in (*COUNTERS, "wall_seconds")):
        raise ValueError("partial or unavailable usage cannot expose exact top-level counters")
    return derived


def continuation_reason(finish, policy):
    validate_policy(policy)
    usage = finish.get("usage")
    if usage is None:
        usage = {}
    if not isinstance(usage, dict):
        return "accounting_policy_evidence_requires_remediation"
    if "accounting" not in usage:
        try:
            validate_attempt(finish, policy)
        except (KeyError, TypeError, ValueError):
            return "accounting_policy_evidence_requires_remediation"
        if usage.get("runtime_valid") is False:
            return "runtime_identity_requires_remediation"
        # An approved absent-telemetry recovery remains unavailable; the scheduler
        # still requires its explicit infrastructure retry and fresh permission.
        return None
    if usage.get("runtime_valid") is not True:
        return "runtime_identity_requires_remediation"
    try:
        derived = validated_projection(usage, digest(policy))
    except (KeyError, TypeError, ValueError):
        return "accounting_policy_evidence_requires_remediation"
    if derived["provenance_status"] != "valid":
        return "accounting_provenance_requires_remediation"
    if derived["delegation_boundary_status"] != "verified":
        return "delegation_boundary_requires_remediation"
    if derived["accounting_status"] not in RULES["accepted_accounting"]:
        return "usage_accounting_requires_remediation"
    return None


def validate_usage(usage, policy):
    """Validate a retained projection without requiring continuation to be admissible."""
    validate_policy(policy)
    return validated_projection(usage, digest(policy))


def validate_attempt(record, policy):
    """Missing recovery/pre-agent infrastructure telemetry is unavailable, never zero.

    Context is collected from the verified immutable store, not from agent prose.
    This exception never grants runtime/provenance verification or permission to retry.
    """
    policy_sha256 = policy if isinstance(policy, str) else digest(validate_policy(policy))
    usage = record.get("usage")
    if usage is None:
        usage = {}
    if not isinstance(usage, dict):
        raise ValueError("invalid attempt usage record")
    if "accounting" in usage:
        return validated_projection(usage, policy_sha256)
    context = record.get("accounting_context")
    if (
        record.get("artifact_valid") is not True
        or record.get("status") != "infra_failure"
        or not isinstance(context, dict)
    ):
        raise ValueError("ordinary retained attempt lacks registered accounting")
    exact(context, {"stopped_output_retained", "grade_retained"}, "infrastructure accounting context")
    if any(type(value) is not bool for value in context.values()) or context["grade_retained"]:
        raise ValueError("graded attempt cannot omit registered accounting")
    if record.get("error_code") == "controller_interrupted":
        return None
    if record.get("error_code") == "container_start" and not context["stopped_output_retained"]:
        return None
    raise ValueError("missing accounting has no retained recovery or pre-agent classification")


def summarize_resources(attempts, schedule, policy_sha256):
    """Pure counter aggregation, including failed runtime attempts and retained retries."""
    require_controller()
    if not is_digest(policy_sha256):
        raise ValueError("resource accounting requires one frozen policy identity")
    tasks = {row["trial_id"]: row for row in schedule}
    if len(tasks) != len(schedule):
        raise ValueError("duplicate scheduled trial")
    seen, classified = set(), []
    for record in attempts:
        key = (record["trial_id"], record["attempt"])
        if key in seen or key[0] not in tasks or type(key[1]) is not int or key[1] not in {1, 2}:
            raise ValueError("duplicate or unscheduled resource attempt")
        seen.add(key)
        derived = validate_attempt(record, policy_sha256) if record.get("artifact_valid") is True else None
        classified.append((record, derived))
    arms = {}
    for arm in sorted({row["arm"] for row in schedule}):
        selected = [(row, value) for row, value in classified if tasks[row["trial_id"]]["arm"] == arm]
        known = [value for _, value in selected if value and value["provenance_status"] == "valid"]
        complete = [value for value in known if value["accounting_status"] == "complete"]
        partial = [value for value in known if value["accounting_status"] == "partial"]
        scheduled = [row for row in schedule if row["arm"] == arm]
        retained = {row["trial_id"] for row, _ in selected}
        arms[arm] = {
            "scheduled_trials": len(scheduled),
            "trials_with_attempts": len(retained),
            "trials_without_attempts": len(scheduled) - len(retained),
            "retained_attempts": len(selected),
            "complete_attempts": len(complete),
            "partial_attempts": len(partial),
            "unavailable_accounting_attempts": len(selected) - len(known),
            "runtime_unverified_attempts": sum(
                (row.get("usage") or {}).get("runtime_valid") is not True for row, _ in selected
            ),
            "observed_lower_bounds": {
                key: sum(value["lower_bounds"][key] for value in known) for key in COUNTERS
            },
            "partial_attempts_lower_bounds": {
                key: sum(value["lower_bounds"][key] for value in partial) for key in COUNTERS
            },
            "complete_attempts_exact_totals": {
                key: sum(value["complete_usage"][key] for value in complete)
                for key in (*COUNTERS, "wall_seconds")
            },
        }
    return {
        "schema_version": "evalopt.campaign-resource-accounting.v1",
        "policy_sha256": policy_sha256,
        "arms": arms,
        "efficiency_comparison_eligible": {row["trial_id"] for row in attempts} == set(tasks)
        and all(
            value is not None
            and value["efficiency_eligible"]
            and (row.get("usage") or {}).get("runtime_valid") is True
            for row, value in classified
        ),
        "scope": "all retained attempts including infrastructure retries; known counters from runtime-blocked attempts remain included; supplied controller counters are not authentication",
        "resource_semantics": "complete and partial observations contribute once to lower bounds; exact complete totals and partial-only bounds are components, not additional costs; missing usage is not zero",
        "dollar_cost": None,
    }
