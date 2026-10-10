"""Interpreter-boundary controls that also run throughout the portable kernel matrix."""

from __future__ import annotations

import importlib
import os
import runpy
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BENCH = Path(__file__).resolve().parents[1] / "bench/harbor/skill-workflows-v1"


@pytest.fixture
def controller(monkeypatch):
    monkeypatch.syspath_prepend(str(BENCH))
    return importlib.import_module("runtime.controller")


def test_exact_controller_identity_is_supported(controller, monkeypatch):
    monkeypatch.setattr(controller, "sys", SimpleNamespace(version_info=(3, 13, 12)))
    monkeypatch.setattr(controller.platform, "python_implementation", lambda: "CPython")
    assert controller.require_controller() == {"implementation": "CPython", "version": "3.13.12"}


@pytest.mark.parametrize(
    ("implementation", "version"),
    [("CPython", (3, 11, 16)), ("CPython", (3, 13, 11)), ("CPython", (3, 14, 0)), ("PyPy", (3, 13, 12))],
)
def test_other_controller_identities_fail(controller, monkeypatch, implementation, version):
    monkeypatch.setattr(controller, "sys", SimpleNamespace(version_info=version))
    monkeypatch.setattr(controller.platform, "python_implementation", lambda: implementation)
    with pytest.raises(ValueError, match="requires CPython 3.13.12"):
        controller.require_controller()


@pytest.mark.parametrize("version", [(3, 11, 16), (3, 14, 0)])
@pytest.mark.parametrize(
    "operation",
    ["prepare", "verify_campaign", "report", "freeze", "verify_heldout", "export", "verify_public"],
)
def test_wrong_interpreter_rejected_before_campaign_access(
    controller, monkeypatch, tmp_path, version, operation
):
    campaign = importlib.import_module("campaign")
    heldout = importlib.import_module("heldout_campaign")
    publication = importlib.import_module("publish_bundle")
    destination = tmp_path / "must-not-be-created"
    missing = tmp_path / "does-not-exist"
    calls = {
        "prepare": lambda: campaign.prepare(destination, missing, "agent", "verifier", missing, missing),
        "verify_campaign": lambda: campaign._verify_campaign(destination, missing),
        "report": lambda: campaign.report(destination),
        "freeze": lambda: heldout.freeze(
            destination, missing, "a" * 64, missing, missing, missing, "agent", "verifier", missing, missing
        ),
        "verify_heldout": lambda: heldout.verify_registration(destination, missing, "a" * 64),
        "export": lambda: publication.export_public_bundle(missing, destination),
        "verify_public": lambda: publication.verify_public_bundle(destination),
    }
    monkeypatch.setattr(controller, "sys", SimpleNamespace(version_info=version))
    with pytest.raises(ValueError, match="requires CPython 3.13.12"):
        calls[operation]()
    assert list(tmp_path.iterdir()) == []


def test_collection_gate_does_not_import_unsupported_workflow_modules(tmp_path):
    (tmp_path / "test_stable.py").write_text("def test_stable(): assert True\n")
    (tmp_path / "test_skill_workflow_probe.py").write_text(
        "raise RuntimeError('unsupported workflow module must never import')\n"
    )
    script = """
import runpy, sys, types, pytest
scope = runpy.run_path(sys.argv[1])
hook = scope['pytest_pycollect_makemodule']
def unsupported():
    raise ValueError('wrong interpreter')
hook.__globals__['_require_controller'] = unsupported
plugin = types.SimpleNamespace(pytest_pycollect_makemodule=hook)
raise SystemExit(pytest.main([sys.argv[2], '-q', '-rs', '-p', 'no:cacheprovider'], plugins=[plugin]))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, str(Path(__file__).with_name("conftest.py")), str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed, 1 skipped" in result.stdout
    assert "workflow benchmark tests require CPython 3.13.12" in result.stdout


def test_collection_gate_preserves_supported_and_stable_modules(monkeypatch):
    hook = runpy.run_path(str(Path(__file__).with_name("conftest.py")))["pytest_pycollect_makemodule"]
    monkeypatch.setitem(hook.__globals__, "_require_controller", lambda: None)
    assert hook(Path("test_skill_workflow_probe.py"), None) is None

    def unsupported():
        raise ValueError("wrong interpreter")

    monkeypatch.setitem(hook.__globals__, "_require_controller", unsupported)
    assert hook(Path("test_kernel_characterization.py"), None) is None
    assert hook(Path("test_benchmark_controller.py"), None) is None
