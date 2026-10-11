"""Fresh-process reproduction using explicit local inputs; never dispatch a model."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from evalopt_v2.framing import strict_json
from evalopt_v2.freeze import prepare, reviewed_inputs


@pytest.mark.skipif(
    not all(
        os.environ.get(name)
        for name in (
            "EVALOPT_V2_UPSTREAM_CONTROL",
            "EVALOPT_V2_AGENT_CONTROL_IMAGE",
            "EVALOPT_V2_DOCKER_CONTROL_IMAGE",
        )
    ),
    reason="explicit local upstream and two images required; no pulls or model calls",
)
def test_cli_freezes_then_reproduces_all_unstarted_rows_in_fresh_process(tmp_path):
    harness = Path(__file__).resolve().parents[1]
    source = harness.parents[2]
    skill, tasks = source / "skills/eval-opt-v2", harness / "tasks"
    # This receipt is deliberately synthetic fixture data, not an offline
    # readiness claim. This test invokes only prepare/replay, never run.
    receipt = {
        "schema_version": "evalopt-workflows-v2/1",
        "inputs": reviewed_inputs(harness, skill, tasks),
        "development_round": {"revision": 0, "previous": None},
        "controls": {
            name: {
                "status": "PASS",
                "skipped": 0,
                "evidence_sha256": "a" * 64,
                "scope": "synthetic-control-only",
            }
            for name in (
                "audited_regressions",
                "semantic",
                "framing_accounting",
                "lifecycle",
                "compatibility_reproduction",
            )
        },
        "reviews": {
            name: {"verdict": "ACCEPT", "evidence_sha256": "b" * 64, "scope": "synthetic-control-only"}
            for name in ("skill", "tasks", "grading_capture", "integration_analysis")
        },
    }
    root = tmp_path.resolve() / "synthetic-no-dispatch"
    frozen = prepare(
        root,
        harness=harness,
        skill_c=skill,
        task_root=tasks,
        kernel=source / "src/evalopt_graph",
        upstream=os.environ["EVALOPT_V2_UPSTREAM_CONTROL"],
        agent_image=os.environ["EVALOPT_V2_AGENT_CONTROL_IMAGE"],
        verifier_image=os.environ["EVALOPT_V2_DOCKER_CONTROL_IMAGE"],
        admission=receipt,
    )
    report = tmp_path / "report.json"
    command = [
        sys.executable,
        "-I",
        "-B",
        str(harness / "run.py"),
        "replay",
        "--campaign",
        str(root),
        "--registration-sha256",
        frozen["registration_sha256"],
        "--output",
        str(report),
    ]
    completed = subprocess.run(command, capture_output=True, timeout=90)
    assert completed.returncode == 0, completed.stderr.decode()
    value = strict_json(report.read_bytes())
    assert value["finalized_rows"] == value["retained_attempts"] == 0
    assert len(value["scheduled_rows"]) == 48
    assert all(row["reported_valid_completion"] is None for row in value["scheduled_rows"])
    assert value["gate"]["ready"] is False
    assert all(bucket["exact_totals"] is None for bucket in value["resources"].values())
    assert not any((root / "attempts").iterdir())
    assert not list((root / "frozen").rglob("*.pyc"))
    # Reproduction cannot silently overwrite an existing report.
    repeated = subprocess.run(command, capture_output=True, timeout=90)
    assert repeated.returncode != 0
