#!/usr/bin/env python3
"""U arm: retain the observation and accept without importing evalopt."""

import hashlib
import json
import sys
from pathlib import Path

source = Path(sys.argv[1])
raw = source.read_bytes()
payload = json.loads(raw)
canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
result = {
    "schema_version": "evalopt.harbor-decision.v1",
    "policy_acceptance": 1,
    "kernel": None,
    "run_identity": payload["run_identity"],
    "observation": payload,
    "observation_sha256": hashlib.sha256(canonical).hexdigest(),
    "observation_file_sha256": hashlib.sha256(raw).hexdigest(),
    "decision": {"status": "ACCEPTED", "reasons": ["ungoverned_completion"]},
}
Path(sys.argv[2]).write_text(json.dumps(result, sort_keys=True) + "\n")
