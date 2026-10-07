"""The README figures are generated, current, and show the README example's real output."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import re
import subprocess
import sys
from pathlib import Path

from evalopt_graph import kernel

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "docs" / "assets" / "src" / "make_figures.py"


def _generator():
    spec = importlib.util.spec_from_file_location("make_figures", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_committed_figures_match_the_generator() -> None:
    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_evidence_card_repeats_the_readme_example_output() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    example = re.search(r"```python\n(.*?)```", readme, re.DOTALL)
    assert example, "README has no python example"
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        exec(compile(example.group(1), "README.md", "exec"), {"__name__": "readme_example"})

    card = [f"{status} {reasons}" for _, status, reasons in _generator().CARD_ROWS]

    assert printed.getvalue().splitlines() == card
    assert "```text\n" + "\n".join(card) + "\n```" in readme


def test_boundary_figure_names_the_five_kernel_states_and_tested_reasons() -> None:
    figures = _generator()
    kernel_tests = (ROOT / "tests" / "test_kernel.py").read_text(encoding="utf-8")
    example_output = {(status, reasons) for _, status, reasons in figures.CARD_ROWS}

    assert {status for status, _ in figures.OUTCOMES} == kernel._DECISIONS
    assert len(figures.OUTCOMES) == len(kernel._DECISIONS)
    for status, reason in figures.OUTCOMES:
        in_kernel_tests = re.search(rf'"{status}",\s*"{re.escape(reason)}"', kernel_tests)
        in_example = (status, f"('{reason}',)") in example_output
        assert in_kernel_tests or in_example, (status, reason)
