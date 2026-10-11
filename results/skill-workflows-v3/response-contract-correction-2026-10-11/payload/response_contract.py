"""Declared response envelope shared by prompt rendering and pure validation.

This module describes transport and task response shape, not check truth or
behavioral correctness. Controller evidence and semantic grading stay separate.
"""

from __future__ import annotations

import json

RESPONSE_FIELDS = ("status", "findings", "blockers", "checks")
STATUS_VALUES = ("completed", "blocked")
ARRAY_FIELDS = ("findings", "blockers", "checks")
CHECK_FIELDS = (
    "observation_id",
    "phase",
    "command",
    "execution_state",
    "exit_code",
    "evidence_availability",
)
COMPLETED_EMPTY_FIELDS = {
    "implementation": ("findings", "blockers"),
    "review": ("blockers",),
}


def envelope_valid(response, *, include_checks=True, strict=False):
    """Preserve the existing JSON envelope predicates, including strictness."""
    matches = (lambda value, kind: type(value) is kind) if strict else isinstance
    return (
        matches(response, dict)
        and matches(response.get("status"), str)
        and response["status"] in STATUS_VALUES
        and all(matches(response.get(key), list) for key in ARRAY_FIELDS if include_checks or key != "checks")
    )


def task_response_valid(response, contract, max_findings=16):
    """Task semantics can still be assessed when only check transport is malformed."""
    return envelope_valid(response, include_checks=False) and (
        contract != "review" or len(response["findings"]) <= max_findings
    )


def completed_payload_valid(response, contract):
    """Existing completed-task shape: issue summaries are not review findings."""
    return response["status"] == "completed" and not any(
        response[key] for key in COMPLETED_EMPTY_FIELDS[contract]
    )


def declared_contract(task):
    """Return machine-readable visible facts; no additional semantic requirements."""
    contract = task["task_contract"]
    if contract not in {"implementation", "review", "blocker_report"}:
        raise ValueError("unsupported task response contract")
    result = {
        "required": list(RESPONSE_FIELDS),
        "status": {"type": "string", "enum": list(STATUS_VALUES)},
        "arrays": list(ARRAY_FIELDS),
        "checks_exact_fields": list(CHECK_FIELDS),
        "additional_top_level_fields": "allowed; optional summary or validation_notes carry prose",
        "task_contract": contract,
        "max_findings": task.get("max_findings", 16),
    }
    if contract in COMPLETED_EMPTY_FIELDS:
        result["completed_requires_empty"] = list(COMPLETED_EMPTY_FIELDS[contract])
    else:
        result["blocker_report"] = {
            "status": "blocked",
            "findings": [],
            "blockers": [
                {
                    "resource": task["blocker_resource"],
                    "reason": "<nonempty explanation of the specified missing evidence>",
                }
            ],
            "required_evidence_availability": task["required_evidence_availability"],
        }
    return result


def response_contract_text(task):
    declared = declared_contract(task)
    text = (
        "Required final response envelope (all four keys must be present): "
        + json.dumps(
            {"required": declared["required"], "status": declared["status"], "arrays": declared["arrays"]},
            sort_keys=True,
        )
        + ". Use a status string from the declared enum; values such as repaired or success are invalid. "
        "Use JSON arrays for findings, blockers and checks, including [] when empty; do not omit empty arrays. "
        "The checks array must contain every supplied initial observation, in supplied order, with exactly these keys: "
        + ", ".join(declared["checks_exact_fields"])
        + ". Copy the supplied values exactly. "
    )
    if task["task_contract"] in COMPLETED_EMPTY_FIELDS:
        text += (
            "For a completed "
            + task["task_contract"]
            + ' task, use status="completed" and '
            + " and ".join(key + "=[]" for key in declared["completed_requires_empty"])
            + ". "
        )
    if task["task_contract"] == "implementation":
        text += "The findings array is reserved for review findings, not summaries of bugs you fixed. "
    elif task["task_contract"] == "review":
        text += (
            f"Use at most {declared['max_findings']} findings, each following the visible task's path/symbol/kind/witness contract. "
            "A clean review uses findings=[]. Do not use blocked to report ordinary discovered defects. "
        )
    else:
        text += (
            "The specified blocker-report outcome requires exactly one blockers object with resource and reason keys; resource must match exactly and reason must be a nonempty explanation. Required shape and evidence availability: "
            + json.dumps(declared["blocker_report"], sort_keys=True)
            + ". "
        )
    return text + (
        'Use status="blocked" only for an actual blocker; a solvable-task refusal is not success. '
        "Put explanations, fixed-bug summaries and checks you ran yourself in optional top-level summary or validation_notes fields. "
        "These prose fields do not replace the required envelope, controller checks or supported review witnesses. "
    )
