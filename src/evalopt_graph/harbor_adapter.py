"""Verifier-side JSON adapter for Harbor 0.18; Harbor remains the experiment runtime."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
from typing import Any

from .kernel import AcceptanceInput, GovernancePolicy, evaluate_acceptance

_POLICY_FIELDS = set(GovernancePolicy().to_dict())
_INPUT_FIELDS = set(AcceptanceInput(observed_at="1970-01-01T00:00:00+00:00").to_dict())
_IDENTITY_FIELDS = {"schema_version", "candidate_commit", "wheel_sha256", "policy_source_sha256"}
_TOP_FIELDS = {"schema_version", "run_identity", "policy", "acceptance_input"}


def _canonical_sha256(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def _is_hex(value: object, size: int) -> bool:
    return isinstance(value, str) and len(value) == size and all(c in "0123456789abcdef" for c in value)


def evaluate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Map a versioned visible-observation payload to one kernel decision artifact."""
    if payload.get("schema_version") != "evalopt.harbor-observation.v1":
        raise ValueError("unsupported Harbor observation schema")
    if set(payload) != _TOP_FIELDS:
        raise ValueError("Harbor observation contains unexpected fields")
    identity = payload.get("run_identity")
    if not isinstance(identity, dict) or set(identity) != _IDENTITY_FIELDS:
        raise ValueError("Harbor observation requires an exact run_identity object")
    if identity.get("schema_version") != "evalopt.run-identity.v1":
        raise ValueError("unsupported Harbor run identity schema")
    if not _is_hex(identity.get("candidate_commit"), 40) or any(
        not _is_hex(identity.get(field), 64) for field in ("wheel_sha256", "policy_source_sha256")
    ):
        raise ValueError("Harbor run identity contains an invalid digest")
    policy_value, input_value = payload.get("policy"), payload.get("acceptance_input")
    if not isinstance(policy_value, dict) or not isinstance(input_value, dict):
        raise ValueError("Harbor observation requires policy and acceptance_input objects")
    if set(policy_value) != _POLICY_FIELDS or set(input_value) != _INPUT_FIELDS:
        raise ValueError("Harbor observation has an inexact policy or input schema")
    if policy_value.get("schema_version") != "evalopt.governance-policy.v1":
        raise ValueError("unsupported nested governance policy schema")
    if input_value.get("schema_version") != "evalopt.acceptance-input.v1":
        raise ValueError("unsupported nested acceptance input schema")
    policy_data = dict(policy_value)
    for key in (
        "required_gates",
        "allowed_verifiers",
        "allowed_authority_policies",
        "authorized_record_sha256",
    ):
        if key in policy_data:
            policy_data[key] = tuple(
                tuple(item) if key == "allowed_verifiers" else item for item in policy_data[key]
            )
    policy = GovernancePolicy(**policy_data)
    input_ = AcceptanceInput.from_dict(input_value)
    decision = evaluate_acceptance(policy, input_)
    observation = json.loads(json.dumps(payload))
    return {
        "schema_version": "evalopt.harbor-decision.v1",
        "policy_acceptance": int(decision.status == "ACCEPTED"),
        "kernel": {"distribution": "evalopt-graph", "version": importlib.metadata.version("evalopt-graph")},
        "run_identity": dict(identity),
        "observation": observation,
        "observation_sha256": _canonical_sha256(observation),
        "policy_sha256": policy.digest,
        "input_sha256": input_.digest,
        "decision": decision.to_dict(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    source = Path(args.input).read_bytes()
    payload = json.loads(source)
    result = evaluate_payload(payload)
    result["observation_file_sha256"] = hashlib.sha256(source).hexdigest()
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
