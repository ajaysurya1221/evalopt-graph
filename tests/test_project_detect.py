"""Project detection tests (pure stdlib, filesystem fixtures)."""

from __future__ import annotations

import json

from evalopt_graph import configured_gates, detect_project


def test_detect_python_with_tests(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='x'\n[tool.ruff]\n[tool.mypy]\n[build-system]\nrequires=['hatchling']\n"
    )
    (tmp_path / "tests").mkdir()
    p = detect_project(str(tmp_path))
    assert p["type"] == "python"
    assert p["has_tests"] is True
    assert p["commands"]["test"] == "python -m pytest -q"
    assert p["commands"]["lint"] == "ruff check ."
    assert p["commands"]["typecheck"] == "mypy ."
    assert p["commands"]["build"] == "python -m build"
    assert set(configured_gates(p)) == {"tests", "lint", "typecheck", "build"}


def test_detect_javascript_npm(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "jest", "lint": "eslint .", "build": "webpack"}})
    )
    (tmp_path / "package-lock.json").write_text("{}")
    p = detect_project(str(tmp_path))
    assert p["type"] == "javascript"
    assert p["package_manager"] == "npm"
    assert p["commands"]["test"] == "npm test"
    assert p["commands"]["lint"] == "npm run lint"
    assert p["commands"]["build"] == "npm run build"


def test_detect_typescript_pnpm(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps({"devDependencies": {"typescript": "^5"}, "scripts": {"test": "vitest"}})
    )
    (tmp_path / "tsconfig.json").write_text("{}")
    (tmp_path / "pnpm-lock.yaml").write_text("")
    p = detect_project(str(tmp_path))
    assert p["type"] == "typescript"
    assert p["package_manager"] == "pnpm"
    assert p["commands"]["test"] == "pnpm test"
    # no explicit typecheck script, but TS => tsc --noEmit inferred
    assert "tsc --noEmit" in p["commands"]["typecheck"]


def test_detect_rust(tmp_path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname='x'\n")
    p = detect_project(str(tmp_path))
    assert p["type"] == "rust"
    assert p["commands"]["test"] == "cargo test"
    assert "clippy" in p["commands"]["lint"]


def test_detect_go(tmp_path):
    (tmp_path / "go.mod").write_text("module x\n")
    p = detect_project(str(tmp_path))
    assert p["type"] == "go"
    assert p["commands"]["test"] == "go test ./..."


def test_detect_ruby_rspec(tmp_path):
    (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\n")
    (tmp_path / "spec").mkdir()
    p = detect_project(str(tmp_path))
    assert p["type"] == "ruby"
    assert p["commands"]["test"] == "bundle exec rspec"


def test_detect_unknown(tmp_path):
    p = detect_project(str(tmp_path))
    assert p["type"] == "unknown"
    assert configured_gates(p) == []
    assert p["notes"]
