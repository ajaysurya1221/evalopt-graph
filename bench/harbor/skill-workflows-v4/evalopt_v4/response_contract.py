"""Declared response envelope shared by prompt rendering and pure validation.

This module describes transport and task response shape, not check truth or
behavioral correctness. Controller evidence and semantic grading stay separate.
"""

from __future__ import annotations

import json

from .case_runner import validate_request

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
FINDING_FIELDS = ("path", "symbol", "kind", "witness")
FINDING_KINDS = ("incorrect-result", "data-loss", "unexpected-exception", "test-coverage-loss")
BLOCKER_FIELDS = ("resource", "reason")
DECLARATION_START = "BEGIN RESPONSE CONTRACT JSON\n"
DECLARATION_END = "\nEND RESPONSE CONTRACT JSON"


def findings_assessable(response, max_findings=16):
    """Only the review payload, not unrelated reporting fields, enables scoring.

    Incorrect but well-shaped findings remain semantic failures. Missing or
    malformed findings remain unknown and cannot create measured difficulty.
    """
    if not isinstance(response, dict) or not isinstance(response.get("findings"), list):
        return False
    if len(response["findings"]) > max_findings:
        return False
    for finding in response["findings"]:
        if not isinstance(finding, dict) or any(
            not isinstance(finding.get(key), str) or not finding[key] for key in ("path", "symbol", "kind")
        ):
            return False
        witness = finding.get("witness")
        if not isinstance(witness, dict):
            return False
        if witness.get("kind") == "removed-required-test":
            if (
                set(witness) != {"kind", "path"}
                or not isinstance(witness["path"], str)
                or not witness["path"]
            ):
                return False
        else:
            try:
                validate_request(witness)
            except (ValueError, TypeError):
                return False
    return True


def blockers_assessable(response):
    return (
        isinstance(response, dict)
        and isinstance(response.get("findings"), list)
        and isinstance(response.get("blockers"), list)
        and all(
            isinstance(item, dict)
            and all(isinstance(item.get(key), str) and bool(item[key].strip()) for key in BLOCKER_FIELDS)
            for item in response["blockers"]
        )
    )


def response_contract_valid(response, task):
    """Declared shape only. Support, availability and behavioral truth are separate."""
    contract = task["task_contract"]
    if not envelope_valid(response, strict=True):
        return False
    if contract == "review" and not findings_assessable(response, task.get("max_findings", 16)):
        return False
    if contract == "review" and any(item["kind"] not in FINDING_KINDS for item in response["findings"]):
        return False
    if contract == "blocker_report":
        return (
            blockers_assessable(response)
            and response["status"] == "blocked"
            and response["findings"] == []
            and len(response["blockers"]) == 1
        )
    if response["status"] == "completed" and contract in COMPLETED_EMPTY_FIELDS:
        return completed_payload_valid(response, contract)
    return blockers_assessable(response)


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
    if type(task.get("max_findings", 16)) is not int or task.get("max_findings", 16) < 0:
        raise ValueError("invalid_task_finding_limit")
    result = {
        "required": list(RESPONSE_FIELDS),
        "status": {"type": "string", "enum": list(STATUS_VALUES)},
        "arrays": list(ARRAY_FIELDS),
        "checks_exact_fields": list(CHECK_FIELDS),
        "additional_top_level_fields": "allowed; optional summary or validation_notes carry prose",
        "task_contract": contract,
        "max_findings": task.get("max_findings", 16),
        "review_finding_required_fields": list(FINDING_FIELDS),
        "review_finding_kinds": list(FINDING_KINDS),
        "review_callable_witness": {
            "exact_fields": ["module", "function", "args"],
            "module_and_function": "top-level ASCII Python identifiers",
            "args": "JSON array, inside the visible finite witness domain",
            "canonical_request_max_utf8_bytes": 65536,
        },
        "review_structural_witness": {"kind": "removed-required-test", "path": "<required test path>"},
        "blocker_required_fields": list(BLOCKER_FIELDS),
        "extra_finding_and_blocker_fields": "allowed; do not change support or coverage",
        "review_preserve_arguments": task.get("preserve_review_args", True),
        "controller_only": [
            "post_stop observations and candidate manifests",
            "builtin exception-category membership from the trusted wrapper",
            "case and witness execution, coverage and frozen oracle results",
            "runtime identity, lifecycle, deadlines, capture and resource accounting",
        ],
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
            "Each finding requires nonempty path, symbol and kind strings and a witness object. "
            "Kinds are incorrect-result or data-loss for a wrong return, unexpected-exception for an unexpected raise, "
            "or test-coverage-loss for removal of a required test. Callable witnesses have exactly module, function and args; "
            "module/function are top-level ASCII Python identifiers, args is an array, and canonical UTF-8 request JSON is at most 65536 bytes. "
            "Use only the finite witness domain in SPEC.md. Locate the callable at module.py/function, or a responsible helper "
            "location allowed by the visible review contract. Required-test removal uses exactly "
            '{"kind":"removed-required-test","path":"<required test path>"} and finding symbol="<module>". '
            "Witnesses must demonstrate the baseline satisfied the contract and the candidate violates it; "
            "when argument preservation is required, mutation is a violation. "
            "Coverage is the union of demonstrated defect obligations: supported duplicates are neutral, "
            "unsupported extra findings fail, and a supported unmodeled defect yields a contract dispute, not an automatic pass. "
        )
    else:
        text += (
            "The specified blocker-report outcome requires exactly one blockers object with required resource and reason keys; resource must match exactly and reason must be a nonempty explanation. Additional object fields are allowed. Required shape and evidence availability: "
            + json.dumps(declared["blocker_report"], sort_keys=True)
            + ". "
        )
    return (
        text
        + (
            'Use status="blocked" only for an actual blocker; a solvable-task refusal is not success. '
            "Put explanations, fixed-bug summaries and checks you ran yourself in optional top-level summary or validation_notes fields. "
            "These prose fields do not replace the required envelope, controller checks or supported review witnesses. "
            "The host alone determines final execution, builtin exception membership, lifecycle, boundary and resource records; "
            "do not manufacture them in the response. The declaration below is normative alongside SPEC.md.\n"
        )
        + DECLARATION_START
        + json.dumps(declared, sort_keys=True)
        + DECLARATION_END
        + "\n"
    )
