#!/usr/bin/env python3
"""Check portable registration records without candidate execution."""
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def digest(value):
    return hashlib.sha256((json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    for name, expected in read(here / "checksums.json").items():
        assert Path(name).name == name
        assert hashlib.sha256((here / name).read_bytes()).hexdigest() == expected
    old = read(here.parent / "development-registration-2026-10-11/registration.json")
    new = read(here / "registration.json")
    freeze = read(here / "freeze.json")
    pin = new.pop("registration_sha256")
    assert digest(new) == pin == freeze["registration_sha256"]
    assert digest(read(here / "admission.json")) == freeze["admission_sha256"]
    assert digest(read(here / "source-manifest.json")) == freeze["source_manifest_sha256"]
    comparison = read(here / "comparability.json")
    assert comparison["registration_sha256"] == pin
    assert comparison["prior_registration_sha256"] == old["registration_sha256"]
    assert comparison["status"] == "PASS"
    assert new["schedule"] == old["schedule"] and len(new["schedule"]) == 48
    assert new["runtime"] == old["runtime"]
    changed = [key for key, value in new["identities"].items() if old["identities"][key] != value]
    assert set(changed) == set(comparison["changed_identities"]) == {"source", "controller"}
    for key, value in comparison["unchanged_identities"].items():
        assert new["identities"][key] == old["identities"][key] == value
    assert comparison["development_revision"] == 1 and comparison["old_attempts_imported"] is False
    assert comparison["live_trials_started"] == 0
    print(json.dumps({"status": "PASS", "scheduled": 48, "registration_sha256": pin, "scope": "preregistration consistency; no live model replication"}, sort_keys=True))


if __name__ == "__main__":
    main()
