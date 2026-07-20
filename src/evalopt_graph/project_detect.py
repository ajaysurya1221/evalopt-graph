"""Project type detection and command inference (pure stdlib, no network)."""

from __future__ import annotations

import json
import os
from typing import Any


def _exists(repo: str, *names: str) -> bool:
    return any(os.path.isfile(os.path.join(repo, n)) for n in names)


def _read_json(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _js_package_manager(repo: str) -> str:
    if _exists(repo, "pnpm-lock.yaml"):
        return "pnpm"
    if _exists(repo, "yarn.lock"):
        return "yarn"
    if _exists(repo, "bun.lockb"):
        return "bun"
    return "npm"


def _js_run(pm: str, script: str) -> str:
    if pm == "npm":
        return f"npm run {script}"
    if pm == "bun":
        return f"bun run {script}"
    return f"{pm} {script}"  # pnpm/yarn: `pnpm test`, `yarn lint`


def detect_project(repo_path: str) -> dict[str, Any]:
    """Return a project profile: type, package manager, and inferred gate commands.

    Commands are inferred from the project's own manifests/scripts where possible and fall back
    to ecosystem conventions. Unknown gates are ``None`` (skipped, not failed).
    """
    repo = os.path.abspath(repo_path)
    profile: dict[str, Any] = {
        "type": "unknown",
        "package_manager": None,
        "has_tests": False,
        "commands": {"test": None, "lint": None, "typecheck": None, "build": None},
        "docker": detect_docker(repo),
        "notes": [],
    }
    cmds = profile["commands"]

    # ---- JavaScript / TypeScript ----
    if _exists(repo, "package.json"):
        pkg = _read_json(os.path.join(repo, "package.json"))
        scripts = pkg.get("scripts", {}) or {}
        deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})}
        is_ts = _exists(repo, "tsconfig.json") or "typescript" in deps
        profile["type"] = "typescript" if is_ts else "javascript"
        pm = _js_package_manager(repo)
        profile["package_manager"] = pm
        if "test" in scripts:
            cmds["test"] = _js_run(pm, "test") if pm != "npm" else "npm test"
            profile["has_tests"] = True
        if "lint" in scripts:
            cmds["lint"] = _js_run(pm, "lint")
        if "typecheck" in scripts:
            cmds["typecheck"] = _js_run(pm, "typecheck")
        elif is_ts:
            cmds["typecheck"] = "npx --no-install tsc --noEmit"
        if "build" in scripts:
            cmds["build"] = _js_run(pm, "build")
        return profile

    # ---- Python ----
    if _exists(repo, "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt"):
        profile["type"] = "python"
        profile["package_manager"] = "uv" if _exists(repo, "uv.lock") else "pip"
        py = ""
        pp = os.path.join(repo, "pyproject.toml")
        if os.path.isfile(pp):
            try:
                py = open(pp, encoding="utf-8").read()
            except Exception:
                py = ""
        has_tests = os.path.isdir(os.path.join(repo, "tests")) or "pytest" in py
        profile["has_tests"] = has_tests
        cmds["test"] = "python -m pytest -q" if has_tests else None
        if "[tool.ruff" in py or _exists(repo, "ruff.toml", ".ruff.toml"):
            cmds["lint"] = "ruff check ."
        if "[tool.mypy" in py or _exists(repo, "mypy.ini"):
            cmds["typecheck"] = "mypy ."
        elif "[tool.pyright" in py or "[tool.basedpyright" in py:
            cmds["typecheck"] = "basedpyright"
        if "[build-system]" in py:
            cmds["build"] = "python -m build"
        return profile

    # ---- Rust ----
    if _exists(repo, "Cargo.toml"):
        profile.update(type="rust", package_manager="cargo", has_tests=True)
        cmds.update(test="cargo test", lint="cargo clippy -- -D warnings", build="cargo build")
        return profile

    # ---- Go ----
    if _exists(repo, "go.mod"):
        profile.update(type="go", package_manager="go", has_tests=True)
        cmds.update(test="go test ./...", lint="go vet ./...", build="go build ./...")
        return profile

    # ---- Java / Kotlin ----
    if _exists(repo, "pom.xml"):
        profile.update(type="java-maven", package_manager="maven", has_tests=True)
        cmds.update(test="mvn -q test", build="mvn -q package")
        return profile
    if _exists(repo, "build.gradle", "build.gradle.kts", "gradlew"):
        profile.update(type="java-gradle", package_manager="gradle", has_tests=True)
        gw = "./gradlew" if _exists(repo, "gradlew") else "gradle"
        cmds.update(test=f"{gw} test", build=f"{gw} build")
        return profile

    # ---- Ruby ----
    if _exists(repo, "Gemfile"):
        profile.update(type="ruby", package_manager="bundler", has_tests=True)
        rspec = os.path.isdir(os.path.join(repo, "spec"))
        cmds["test"] = "bundle exec rspec" if rspec else "bundle exec rake test"
        if _exists(repo, ".rubocop.yml"):
            cmds["lint"] = "bundle exec rubocop"
        return profile

    profile["notes"].append("No known project manifest detected; ask for a test command if needed.")
    return profile


def configured_gates(profile: dict[str, Any]) -> list[str]:
    """Gates that actually have a command for this project (others are skipped, not failed)."""
    cmds = profile.get("commands", {}) or {}
    return [g for g in ("tests", "lint", "typecheck", "build") if cmds.get("test" if g == "tests" else g)]


def detect_docker(repo_path: str) -> dict[str, Any]:
    """Detect Docker affordances in a repo (used to decide reproducible containerized verification)."""
    repo = os.path.abspath(repo_path)
    dockerfile = _exists(repo, "Dockerfile") or any(
        n.startswith("Dockerfile") for n in (os.listdir(repo) if os.path.isdir(repo) else [])
    )
    compose = _exists(repo, "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
    devcontainer = _exists(repo, ".devcontainer.json") or os.path.isfile(
        os.path.join(repo, ".devcontainer", "devcontainer.json")
    )
    return {
        "dockerfile": bool(dockerfile),
        "compose": bool(compose),
        "devcontainer": bool(devcontainer),
        "available": bool(dockerfile or compose or devcontainer),
    }


def should_use_docker(
    profile: dict[str, Any], *, docker_enabled: str = "auto", native_dependency_failure: bool = False
) -> bool:
    """Decide whether to prefer containerized verification.

    ``docker_enabled``: 'true' forces on, 'false' forces off, 'auto' (default) turns on only when
    the repo declares Docker (Dockerfile/compose/devcontainer) or the native env failed to set up.
    """
    if str(docker_enabled).lower() == "false":
        return False
    if str(docker_enabled).lower() == "true":
        return True
    d = profile.get("docker", {}) or {}
    return bool(d.get("available") or native_dependency_failure)
