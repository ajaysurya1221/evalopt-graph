#!/usr/bin/env python3
"""Check prospective registration correspondence without candidate execution."""

import sys

if __name__ == "__main__" and (not sys.flags.isolated or not sys.flags.dont_write_bytecode):
    raise SystemExit("Run with python -I -B to exclude adjacent modules and bytecode writes.")

import hashlib
import json
import re
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("nonfinite JSON constant")

    require(path.is_file() and not path.is_symlink(), "regular artifact required")
    return json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=constant)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256((raw + "\n").encode()).hexdigest()


def main():
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    sums = read(here / "checksums.json")
    require(set(sums) == {p.name for p in here.iterdir()} - {"checksums.json"}, "packet roster differs")
    for name, expected in sums.items():
        require(Path(name).name == name and re.fullmatch(r"[0-9a-f]{64}", expected), "invalid checksum")
        require(sha(here / name) == expected, "public artifact checksum differs")
    manifest = read(here / "source-manifest.json")
    harness = repo / "bench/harbor/skill-workflows-v4"
    for prefix, local_root in (("harness", harness), ("kernel", repo / "src" / "evalopt_graph")):
        expected_files = {
            name.removeprefix(prefix + "/").removeprefix("evalopt_graph/" if prefix == "kernel" else "")
            for name in manifest
            if name.startswith(prefix + "/")
        }
        actual_files = {
            p.relative_to(local_root).as_posix()
            for p in local_root.rglob("*")
            if p.is_file()
            and not any(
                x in {".git", ".pytest_cache", ".ruff_cache"} for x in p.relative_to(local_root).parts
            )
        }
        require(actual_files == expected_files, "source roster differs from freeze")
    count = 0
    for name, expected in manifest.items():
        parts = Path(name).parts
        require(not Path(name).is_absolute() and ".." not in parts, "unsafe frozen path")
        if parts[0] == "harness":
            local = harness.joinpath(*parts[1:])
        elif parts[0] == "tasks":
            local = (harness / "tasks").joinpath(*parts[1:])
        elif parts[0] == "kernel":
            local = (repo / "src").joinpath(*parts[1:])
        else:
            continue  # Upstream/image identities remain declared freeze provenance.
        require(local.is_file() and not local.is_symlink(), "missing frozen source")
        require(sha(local) == expected["sha256"], "frozen source bytes differ")
        require(
            bool(local.stat().st_mode & 0o100) is expected["executable"],
            "frozen source executable bit differs",
        )
        count += 1
    require(count > 0, "empty source correspondence")
    require(
        not any(p.name == "__pycache__" or p.suffix in {".pyc", ".pyo"} for p in harness.rglob("*")),
        "unregistered bytecode",
    )
    registration = read(here / "registration.json")
    freeze = read(here / "freeze.json")
    pin = freeze["registration_sha256"]
    require(registration.get("registration_sha256") == pin, "registration pin differs")
    require(
        digest({key: value for key, value in registration.items() if key != "registration_sha256"}) == pin,
        "registration canonical identity differs",
    )
    require(digest(manifest) == freeze["source_manifest_sha256"], "frozen manifest digest differs")
    admission = read(here / "admission.json")
    require(digest(admission) == freeze["admission_sha256"], "admission digest differs")
    inputs = {
        label: digest(
            {
                name.removeprefix(label + "/"): value
                for name, value in manifest.items()
                if name.startswith(label + "/")
            }
        )
        for label in ("harness", "tasks")
    }
    require(
        registration["identities"]["source"] == digest({"manifest": manifest, "admission": admission}),
        "source identity differs",
    )
    require(registration["identities"]["tasks"] == inputs["tasks"], "task identity differs")
    require(
        digest(registration["tasks"]) == digest(read(harness / "tasks/catalog.json")),
        "registered task roster differs from frozen catalog",
    )
    subsets = {
        "grader": [
            "records.py",
            "reporting.py",
            "response_contract.py",
            "case_runner.py",
            "grading.py",
            "verifier.py",
            "verifier_container.py",
            "replay_grade.py",
        ],
        "parser": ["framing.py", "accounting.py"],
        "continuation_policy": ["lifecycle.py", "store.py", "campaign.py"],
        "analysis": ["analysis.py", "descriptive.py", "registration.py"],
        "controller": [
            "harbor_bridge.py",
            "observe.py",
            "snapshot.py",
            "preflight.py",
            "campaign.py",
            "network.py",
        ],
    }
    for label, names in subsets.items():
        require(
            registration["identities"][label]
            == digest({name: sha(harness / "evalopt_v4" / name) for name in names}),
            "source subset identity differs",
        )
    require(registration["stage"] == "difficulty" and len(registration["schedule"]) == 16, "wrong allocation")
    # Validate the complete source/registration/admission identity chain above
    # using stdlib only. No local implementation executes before its pinned
    # manifest and canonical registration have been checked.
    sys.path.insert(0, str(harness))
    from evalopt_v4.registration import validate_registration
    from evalopt_v4.freeze import validate_admission

    validate_registration(registration, expected_sha256=pin)
    validate_admission(admission, inputs)
    print(
        json.dumps(
            {
                "status": "PASS",
                "scheduled": 16,
                "registration_sha256": pin,
                "source_entries_checked": count,
                "scope": "preregistration correspondence; no candidate execution or live replication",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
