"""Regression tests for the compact generated-conformance utility."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "provenance_benchmark.py"


def _module():
    spec = importlib.util.spec_from_file_location("provenance_benchmark", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_generated_conformance_corpus_is_deterministic_and_versioned() -> None:
    module = _module()
    first = module.generate_cases()
    second = module.generate_cases()

    assert first == second
    assert len(first) == 32
    assert sum(case.kind == "legacy" for case in first) == 12
    assert sum(case.kind == "adapter" for case in first) == 12
    assert sum(case.kind == "valid" for case in first) == 8
    assert {case.variant for case in first if case.kind == "legacy"} == set(module.LEGACY_VARIANTS)
    assert {case.variant for case in first if case.kind == "adapter"} == set(module.ADAPTER_VARIANTS)
    assert {case.variant for case in first if case.kind == "valid"} == set(module.VALID_VARIANTS)


def test_candidate_preserves_all_generated_conformance_outcomes() -> None:
    module = _module()

    summary = module.run_conformance()

    assert summary == {
        "schema_version": "evalopt.generated-conformance.v1",
        "seed": module.SEED,
        "legacy": {"attempts": 12, "rejected": 12},
        "adapter": {"attempts": 12, "passed": 12},
        "valid": {"attempts": 8, "passed": 8},
        "failures": [],
        "passed": True,
    }


def test_cli_writes_only_one_compact_summary_outside_repository(tmp_path: Path) -> None:
    output = tmp_path / "summary.json"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--out", str(output)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["passed"] is True
    assert list(tmp_path.iterdir()) == [output]


def test_utility_contains_no_experiment_harness_or_sealed_set_language() -> None:
    source = SCRIPT.read_text(encoding="utf-8").lower()

    assert "holdout" not in source
    assert "jsonschema" not in source
    assert "subprocess" not in source
    assert "rows.jsonl" not in source
    assert "trial_id" not in source
