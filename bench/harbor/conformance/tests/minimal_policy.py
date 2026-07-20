#!/usr/bin/env python3
"""Reviewable M arm: no evalopt import and no model-controlled authority."""

import hashlib
import json
import sys
from pathlib import Path

TOP_FIELDS = {"schema_version", "run_identity", "policy", "acceptance_input"}
POLICY_FIELDS = set(
    "schema_version required_gates minimum_trust quality_threshold require_evaluator "
    "max_evidence_age_seconds required_claim_ids disqualified_claim_ids allowed_verifiers "
    "allowed_authority_policies authorized_record_sha256".split()
)
INPUT_FIELDS = set(
    "schema_version observed_at gate_results criteria claims contradictions attestations assessments "
    "tests_weakened evaluator_score".split()
)
IDENTITY_FIELDS = {"schema_version", "candidate_commit", "wheel_sha256", "policy_source_sha256"}


def _hex(value, size):
    return isinstance(value, str) and len(value) == size and all(c in "0123456789abcdef" for c in value)


def _exact(value, fields, schema):
    return isinstance(value, dict) and set(value) == fields and value.get("schema_version") == schema


source = Path(sys.argv[1])
raw = source.read_bytes()
payload = json.loads(raw)
policy = payload.get("policy")
observation = payload.get("acceptance_input")
identity = payload.get("run_identity")
valid = bool(
    payload.get("schema_version") == "evalopt.harbor-observation.v1"
    and set(payload) == TOP_FIELDS
    and _exact(policy, POLICY_FIELDS, "evalopt.governance-policy.v1")
    and _exact(observation, INPUT_FIELDS, "evalopt.acceptance-input.v1")
    and observation.get("tests_weakened") is False
    and _exact(identity, IDENTITY_FIELDS, "evalopt.run-identity.v1")
    and _hex(identity.get("candidate_commit"), 40)
    and all(_hex(identity.get(field), 64) for field in ("wheel_sha256", "policy_source_sha256"))
)
policy = policy if isinstance(policy, dict) else {}
observation = observation if isinstance(observation, dict) else {}
gate_rows = observation.get("gate_results", ())
try:
    gates = dict(gate_rows)
except (TypeError, ValueError):
    gates = {}
required = policy.get("required_gates", ())
accepted = valid and len(gates) == len(gate_rows) and all(gates.get(gate) == "PASS" for gate in required)
result = {
    "schema_version": "evalopt.harbor-decision.v1",
    "policy_acceptance": int(accepted),
    "run_identity": identity,
    "observation": payload,
    "observation_sha256": hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest(),
    "observation_file_sha256": hashlib.sha256(raw).hexdigest(),
    "decision": {"status": "ACCEPTED" if accepted else "UNVERIFIED", "reasons": ["minimal_policy"]},
}
Path(sys.argv[2]).write_text(json.dumps(result, sort_keys=True) + "\n")
