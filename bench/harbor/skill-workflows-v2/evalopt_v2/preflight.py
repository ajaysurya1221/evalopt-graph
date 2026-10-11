"""Read-only version, subscription and native runtime identity checks.

No model request, purchase, auth mutation or alternate billing route is made.
Only sanitized permission/identity projections leave this module.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import selectors
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

import tomllib

from .framing import SCHEMA, decode_jsonl, strict_json
from .records import canonical, digest

UPSTREAM_COMMIT = "b0618bc436ad893b3c5e84e55fba86586d34a404"
MODEL, EFFORT, CLI, HARBOR = "gpt-6-astra", "ultra", "0.154.0", "0.24.0"
IMAGE = re.compile(r"sha256:[0-9a-f]{64}\Z")


class PreDispatchInfrastructureError(RuntimeError):
    """Only a read-only Docker transport failure before any container creation."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason
        self.proof = {
            "phase": "read_only_image_preflight",
            "containers_created": False,
            "agent_dispatched": False,
        }


def minimal_environment():
    return {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}


def auth_path():
    home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
    path = home / "auth.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1024 * 1024:
        raise ValueError("chatgpt_auth_unavailable")
    data = strict_json(path.read_bytes())
    if (
        not isinstance(data, dict)
        or data.get("auth_mode") != "chatgpt"
        or not isinstance(data.get("tokens"), dict)
        or not all(
            isinstance(data["tokens"].get(key), str) and data["tokens"][key]
            for key in ("access_token", "refresh_token")
        )
        or data.get("OPENAI_API_KEY")
    ):
        raise ValueError("chatgpt_auth_required")
    return path


def require_versions():
    import platform

    if platform.python_implementation() != "CPython" or platform.python_version() != "3.13.12":
        raise ValueError("controller_version_mismatch")
    if importlib.metadata.version("harbor") != HARBOR:
        raise ValueError("harbor_version_mismatch")
    result = subprocess.run(
        ["codex", "--version"], env=minimal_environment(), capture_output=True, timeout=10, check=True
    )
    if result.stdout.decode().strip() != "codex-cli " + CLI:
        raise ValueError("codex_version_mismatch")
    return {"controller": "CPython 3.13.12", "harbor": HARBOR, "codex": CLI}


def image_identity(image):
    if not isinstance(image, str) or not IMAGE.fullmatch(image):
        raise ValueError("image_must_be_full_local_id")
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", "--format", "{{.Id}}", image],
            capture_output=True,
            timeout=15,
            check=True,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PreDispatchInfrastructureError("docker_read_only_transport_unavailable") from None
    except subprocess.CalledProcessError as exc:
        diagnostic = (exc.stderr or b"").lower()
        transport = (
            b"cannot connect to the docker daemon",
            b"error during connect",
            b"context deadline exceeded",
        )
        if any(pattern in diagnostic for pattern in transport):
            raise PreDispatchInfrastructureError("docker_read_only_transport_unavailable") from None
        raise ValueError("required_local_image_inspection_failed") from None
    if result.stdout.decode().strip() != image:
        raise ValueError("image_identity_mismatch")
    return image


def native_config(path):
    raw = Path(path).read_bytes()
    config = tomllib.loads(raw.decode())
    if (
        config.get("model") != MODEL
        or config.get("model_reasoning_effort") != EFFORT
        or config.get("forced_login_method") != "chatgpt"
        or config.get("web_search") != "disabled"
        or config.get("check_for_update_on_startup") is not False
    ):
        raise ValueError("native_config_identity_mismatch")
    agents = config.get("agents", {})
    if canonical(agents) != canonical(
        {
            "enabled": True,
            "max_concurrent_threads_per_session": 2,
            "max_depth": 1,
            "default_subagent_model": MODEL,
            "default_subagent_reasoning_effort": EFFORT,
        }
    ):
        raise ValueError("native_delegation_config_mismatch")
    if config.get("features") != {
        "multi_agent": True,
        "multi_agent_v2": False,
        "apps": False,
        "skill_mcp_dependency_install": False,
    } or config.get("analytics") != {"enabled": False}:
        raise ValueError("native_features_config_mismatch")
    if set(config) != {
        "model",
        "model_reasoning_effort",
        "forced_login_method",
        "web_search",
        "check_for_update_on_startup",
        "agents",
        "features",
        "analytics",
    }:
        raise ValueError("unregistered_native_config")
    return config, hashlib.sha256(raw).hexdigest()


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True, timeout=10).stdout


def _upstream_bundle(upstream):
    """Bind the roster and every injected byte to Git, including ignored files.

    Git status alone does not cover ignored dependencies. Walking each complete
    skill tree also rejects untracked files, symlinks and empty extra directories.
    """
    root = Path(upstream).resolve()
    if _git(root, "rev-parse", "HEAD").decode().strip() != UPSTREAM_COMMIT:
        raise ValueError("upstream_commit_mismatch")
    entries = {}
    for row in _git(root, "ls-tree", "-rz", UPSTREAM_COMMIT).split(b"\x00"):
        if row:
            header, name = row.split(b"\t", 1)
            mode, kind, oid = header.decode().split()
            entries[name.decode("utf-8")] = (mode, kind, oid)

    def checked_file(name):
        mode, kind, oid = entries.get(name, (None, None, None))
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("unsupported_upstream_file")
        path = root / name
        if any(parent.is_symlink() for parent in (path, *path.parents) if parent != root):
            raise ValueError("upstream_symlink")
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or bool(info.st_mode & 0o111) != (mode == "100755"):
            raise ValueError("upstream_file_mode_changed")
        raw = path.read_bytes()
        if hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() != oid:
            raise ValueError("upstream_file_changed")
        return raw

    plugin = strict_json(checked_file(".claude-plugin/plugin.json"))
    paths = plugin.get("skills") if isinstance(plugin, dict) else None
    if not isinstance(paths, list) or len(paths) != 27:
        raise ValueError("complete_upstream_bundle_required")
    result, trees = {}, {}
    for name in paths:
        if not isinstance(name, str):
            raise ValueError("invalid_skill_path")
        path = root / name
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or path.is_symlink() or path.name in result:
            raise ValueError("invalid_skill_roster")
        relative = resolved.relative_to(root).as_posix()
        pinned = {key: value for key, value in entries.items() if key.startswith(relative + "/")}
        if relative + "/SKILL.md" not in pinned:
            raise ValueError("invalid_skill_roster")
        expected = set()
        for key in pinned:
            local = Path(key).relative_to(relative)
            expected.add(local.as_posix())
            expected.update(p.as_posix() for p in local.parents if p != Path("."))
            checked_file(key)
        actual = {p.relative_to(resolved).as_posix() for p in resolved.rglob("*")}
        if actual != expected:
            raise ValueError("upstream_tree_changed")
        result[path.name], trees[path.name] = resolved, pinned
    return root, result, trees


def export_upstream_skills(upstream, destination):
    """Export verified commit blobs, not a second mutable working-tree copy."""
    root, sources, trees = _upstream_bundle(upstream)
    destination = Path(destination)
    if any(destination.iterdir()):
        raise ValueError("upstream_export_not_empty")
    for name, pinned in trees.items():
        relative_root = sources[name].relative_to(root)
        for relative, (mode, _, oid) in sorted(pinned.items()):
            target = destination / name / Path(relative).relative_to(relative_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as output:
                output.write(_git(root, "cat-file", "blob", oid))
            target.chmod(0o755 if mode == "100755" else 0o644)


def skill_sources(arm, upstream, skill_c, skill_d):
    if arm == "A":
        return {}
    if arm in {"C", "D"}:
        path = Path(skill_c if arm == "C" else skill_d).resolve()
        if not (path / "SKILL.md").is_file():
            raise ValueError("candidate_skill_missing")
        return {"eval-opt-v2": path}
    if arm != "B":
        raise ValueError("unknown_arm")
    return _upstream_bundle(upstream)[1]


def permission_from_response(response):
    value = (
        response.get("result", {}).get("ordinaryUsageAllowed")
        if isinstance(response, dict) and isinstance(response.get("result"), dict)
        else None
    )
    return {
        "schema_version": SCHEMA,
        "kind": "subscription_permission",
        "ordinary_usage_allowed": value is True,
        "state": "allowed" if value is True else "exhausted" if value is False else "unavailable",
    }


def subscription_permission(*, timeout=30):
    """Fresh native app-server permission. Unknown always denies admission."""
    try:
        source = auth_path()
        with tempfile.TemporaryDirectory(prefix="evalopt-v2-permission-") as temporary:
            home = Path(temporary).resolve()
            shutil.copyfile(source, home / "auth.json")
            (home / "auth.json").chmod(0o600)
            (home / "config.toml").write_text('forced_login_method = "chatgpt"\n')
            env = minimal_environment() | {"CODEX_HOME": str(home)}
            process = subprocess.Popen(
                ["codex", "app-server"],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            deadline, buffer = time.monotonic() + timeout, b""
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ)

            def send(value):
                process.stdin.write(json.dumps(value).encode() + b"\n")
                process.stdin.flush()

            def receive(wanted):
                nonlocal buffer
                while time.monotonic() < deadline:
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        row = strict_json(line)
                        if isinstance(row, dict) and row.get("id") == wanted:
                            return row
                    if len(buffer) > 1024 * 1024:
                        raise ValueError("permission_response_oversized")
                    if selector.select(max(0, deadline - time.monotonic())):
                        chunk = os.read(process.stdout.fileno(), 65536)
                        if not chunk:
                            raise ValueError("permission_connection_closed")
                        buffer += chunk
                raise TimeoutError("permission_timeout")

            try:
                send(
                    {
                        "id": 0,
                        "method": "initialize",
                        "params": {"clientInfo": {"name": "evalopt-v2-permission", "version": "1"}},
                    }
                )
                if "result" not in receive(0):
                    return permission_from_response({})
                send({"method": "initialized"})
                send({"id": 1, "method": "account/rateLimits/read"})
                return permission_from_response(receive(1))
            finally:
                selector.close()
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
    except (OSError, ValueError, TimeoutError, subprocess.SubprocessError):
        return permission_from_response({})


def runtime_observations(files):
    versions, models, efforts, hashes = set(), set(), set(), []
    contexts = 0
    for raw in files.values():
        framed = decode_jsonl(raw)
        hashes.append(framed["source_sha256"])
        rows = [item["value"] for item in framed["records"]]
        if not rows or rows[0].get("type") != "session_meta":
            raise ValueError("runtime_owner_metadata_missing")
        metadata = rows[0].get("payload")
        if not isinstance(metadata, dict) or not isinstance(metadata.get("cli_version"), str):
            raise ValueError("runtime_version_malformed")
        versions.add(metadata["cli_version"])
        owner_contexts = 0
        for row in rows:
            if row.get("type") == "turn_context":
                payload = row.get("payload", {})
                if (
                    not isinstance(payload, dict)
                    or not isinstance(payload.get("model"), str)
                    or not isinstance(payload.get("effort"), str)
                ):
                    raise ValueError("runtime_context_malformed")
                models.add(payload.get("model"))
                efforts.add(payload.get("effort"))
                owner_contexts += 1
        if owner_contexts == 0:
            raise ValueError("runtime_context_missing")
        contexts += owner_contexts
    verified = bool(files) and versions == {CLI} and models == {MODEL} and efforts == {EFFORT}
    return {
        "schema_version": SCHEMA,
        "kind": "runtime_identity",
        "verified": verified,
        "cli_versions": sorted(str(x) for x in versions),
        "models": sorted(str(x) for x in models),
        "efforts": sorted(str(x) for x in efforts),
        "context_count": contexts,
        "source_hashes": sorted(hashes),
        "source_digest": digest(sorted(hashes)),
    }
