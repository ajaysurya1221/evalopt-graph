"""Strict experimental record boundaries; labels never authenticate custody.

Only the external controller may construct observations from retained command bytes.
Agent responses are claims, even if they copy a valid observation's wire format.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from . import SCHEMA_VERSION

MAX_CANONICAL_DEPTH = 768
MAX_CANONICAL_NODES = 1_000_000


def canonical(value: Any) -> bytes:
    """Bounded finite JSON, with no coercion, recursive validation or mutation.

    Container depth matches the callable JSON parser's 768-level limit. Shared
    substructures are allowed; cycles and expansion beyond the node budget are
    rejected before encoding. Serializer recursion failure is a data rejection,
    never an uncaught controller RecursionError.
    """
    stack = [(iter((value,)), None)]
    active, nodes = set(), 0
    while stack:
        iterator, owner = stack[-1]
        try:
            item = next(iterator)
        except StopIteration:
            stack.pop()
            if owner is not None:
                active.remove(owner)
            continue
        nodes += 1
        if nodes > MAX_CANONICAL_NODES:
            raise ValueError("JSON node budget exceeded")
        kind = type(item)
        if item is None or kind in (bool, int, str):
            continue
        if kind is float and math.isfinite(item):
            continue
        if kind not in (list, dict):
            raise ValueError("not a finite JSON value")
        if len(stack) > MAX_CANONICAL_DEPTH:
            raise ValueError("JSON depth exceeded")
        identity = id(item)
        if identity in active:
            raise ValueError("cyclic JSON value")
        if kind is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("not a finite JSON value")
            nodes += len(item)  # Object keys are serialized nodes too.
            if nodes > MAX_CANONICAL_NODES:
                raise ValueError("JSON node budget exceeded")
        active.add(identity)
        stack.append((iter(item.values() if kind is dict else item), identity))
    try:
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            + "\n"
        ).encode("utf-8")
    except RecursionError as error:
        raise ValueError("JSON serialization depth exceeded") from error


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _enum(value, allowed, field):
    if type(value) is not str or value not in allowed:
        raise ValueError(f"invalid {field}")


def _boolean(value, field, nullable=False):
    if type(value) is not bool and not (nullable and value is None):
        raise ValueError(f"invalid {field}")


def validate_record(value: dict) -> dict:
    """Validate shape and semantic invariants, not truth or producer identity."""
    canonical(value)
    if type(value) is not dict or value.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unknown record schema")
    kind = value.get("record_type")
    fields = {
        "command": {
            "attempt_id",
            "candidate_id",
            "command",
            "execution_state",
            "exit_code",
            "evidence_availability",
            "artifact_refs",
            "asserted_claim",
        },
        "task_outcome": {
            "attempt_id",
            "task_contract",
            "functional_success",
            "valid_completion",
            "verifier_status",
            "contract_dispute",
            "reasons",
            "boundary_preserved",
            "claims_supported",
            "lifecycle_verified",
            "timed_out",
        },
        "agent_claim": {"attempt_id", "claim", "artifact_refs"},
    }
    if type(kind) is not str or kind not in fields:
        raise ValueError("unknown record type")
    if set(value) != fields[kind] | {"schema_version", "record_type"}:
        raise ValueError("missing or extra record fields")
    if not isinstance(value["attempt_id"], str) or not value["attempt_id"]:
        raise ValueError("attempt identity required")
    if kind in {"command", "agent_claim"}:
        if type(value["artifact_refs"]) is not list or any(
            type(ref) is not str or not ref for ref in value["artifact_refs"]
        ):
            raise ValueError("invalid artifact references")
    if kind == "command":
        if not isinstance(value["candidate_id"], str) or not value["candidate_id"]:
            raise ValueError("candidate identity required")
        if (
            type(value["command"]) is not list
            or not value["command"]
            or any(type(part) is not str for part in value["command"])
        ):
            raise ValueError("command must be an argv array")
        _enum(value["execution_state"], {"ran", "not_run", "timed_out", "interrupted"}, "execution_state")
        _enum(value["evidence_availability"], {"complete", "partial", "unavailable"}, "evidence_availability")
        code = value["exit_code"]
        if code is not None and type(code) is not int:
            raise ValueError("exit code must be integer or null")
        if value["execution_state"] == "ran" and code is None:
            raise ValueError("ran requires an observed exit code")
        if value["execution_state"] != "ran" and code is not None:
            raise ValueError("non-exited command cannot invent an exit code")
        if value["execution_state"] == "not_run" and value["evidence_availability"] != "unavailable":
            raise ValueError("not-run command has no execution evidence")
        if value["evidence_availability"] == "complete" and not value["artifact_refs"]:
            raise ValueError("complete evidence needs retained artifacts")
        if value["asserted_claim"] is not None and type(value["asserted_claim"]) is not str:
            raise ValueError("asserted claim must be text or null")
    elif kind == "task_outcome":
        _enum(value["task_contract"], {"implementation", "review", "blocker_report"}, "task_contract")
        _enum(value["verifier_status"], {"completed", "not_run", "failed_to_run"}, "verifier_status")
        for name in ("functional_success", "valid_completion"):
            _boolean(value[name], name, nullable=True)
        _boolean(value["contract_dispute"], "contract_dispute")
        for name in ("boundary_preserved", "claims_supported", "lifecycle_verified"):
            _boolean(value[name], name, nullable=True)
        _boolean(value["timed_out"], "timed_out")
        if value["verifier_status"] != "completed" and value["functional_success"] is not None:
            raise ValueError("unrun verifier cannot establish functional outcome")
        if value["valid_completion"] is True and (
            value["functional_success"] is not True or value["contract_dispute"]
        ):
            raise ValueError("valid completion needs supported undisputed success")
        if type(value["reasons"]) is not list or any(type(reason) is not str for reason in value["reasons"]):
            raise ValueError("invalid outcome reasons")
        expected, reasons = _completion(value)
        if value["valid_completion"] is not expected or value["reasons"] != reasons:
            raise ValueError("outcome contradicts typed components")
    elif type(value["claim"]) is not str:
        raise ValueError("claim must be text")
    return value


def _completion(value):
    components = {
        name: value[name]
        for name in ("functional_success", "boundary_preserved", "claims_supported", "lifecycle_verified")
    }
    reasons = [name for name, result in components.items() if result is not True]
    if value["timed_out"]:
        reasons.append("timed_out")
    if value["contract_dispute"]:
        reasons.append("contract_dispute")
    valid = (
        False
        if value["timed_out"] or any(item is False for item in components.values())
        else None
        if value["contract_dispute"] or any(item is None for item in components.values())
        else True
    )
    return valid, reasons


def task_outcome(
    attempt_id,
    task_contract,
    *,
    functional_success,
    verifier_status="completed",
    boundary_preserved=None,
    claims_supported=None,
    lifecycle_verified=None,
    timed_out=False,
    contract_dispute=False,
) -> dict:
    """Three-valued completion. A known failure remains failure despite other gaps."""
    for item in (functional_success, boundary_preserved, claims_supported, lifecycle_verified):
        _boolean(item, "outcome component", nullable=True)
    _boolean(timed_out, "timed_out")
    _boolean(contract_dispute, "contract_dispute")
    components = {
        "functional_success": functional_success,
        "boundary_preserved": boundary_preserved,
        "claims_supported": claims_supported,
        "lifecycle_verified": lifecycle_verified,
        "timed_out": timed_out,
        "contract_dispute": contract_dispute,
    }
    valid, reasons = _completion(components)
    return validate_record(
        {
            "schema_version": SCHEMA_VERSION,
            "record_type": "task_outcome",
            "attempt_id": attempt_id,
            "task_contract": task_contract,
            **components,
            "valid_completion": valid,
            "verifier_status": verifier_status,
            "reasons": reasons,
        }
    )
