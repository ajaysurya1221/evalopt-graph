"""Keep the portable kernel matrix separate from the pinned benchmark controller."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

_CONTROLLER = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1/runtime/controller.py"
_require_controller = runpy.run_path(str(_CONTROLLER))["require_controller"]
_REASON = (
    "workflow benchmark tests require CPython 3.13.12; "
    "the required Workflow benchmark CI lane runs these controls"
)


class _UnsupportedWorkflowModule(pytest.Module):
    def collect(self):
        pytest.skip(_REASON, allow_module_level=True)


def pytest_pycollect_makemodule(module_path: Path, parent):
    """Skip only benchmark modules, before imports or fixture creation, on other runtimes."""
    if module_path.name.startswith("test_skill_workflow_"):
        try:
            _require_controller()
        except ValueError:
            return _UnsupportedWorkflowModule.from_parent(parent, path=module_path)
    return None
