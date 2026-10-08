"""Read included-usage permission without starting a model or changing billing."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


def permission_from_response(result: dict) -> dict:
    allowed = result.get("ordinaryUsageAllowed")
    return {
        "schema_version": "evalopt.subscription-permission.v1",
        "ordinary_usage_allowed": allowed is True,
        "state": "allowed" if allowed is True else ("exhausted" if allowed is False else "unavailable"),
    }


def read_subscription_permission(executable: str = "codex") -> dict:
    """Pinned app-server read; retain no account IDs, balances, tokens or reset IDs."""
    auth = Path.home() / ".codex" / "auth.json"
    if not auth.is_file():
        return permission_from_response({})
    version = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, timeout=10, check=False
    )
    if version.returncode or version.stdout.strip() != "codex-cli 0.154.0":
        return permission_from_response({})
    with tempfile.TemporaryDirectory(prefix="evalopt-quota-") as temporary:
        root = Path(temporary)
        shutil.copyfile(auth, root / "auth.json")
        (root / "auth.json").chmod(0o600)
        (root / "config.toml").write_text('forced_login_method = "chatgpt"\n[analytics]\nenabled = false\n')
        env = {key: os.environ[key] for key in ("PATH", "HOME", "LANG", "TMPDIR") if key in os.environ}
        env["CODEX_HOME"] = str(root)
        process = subprocess.Popen(
            [executable, "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
            text=True,
            bufsize=1,
        )
        deadline = time.monotonic() + 30

        def exchange(message):
            process.stdin.write(json.dumps(message) + "\n")
            process.stdin.flush()
            while time.monotonic() < deadline:
                ready, _, _ = select.select([process.stdout], [], [], max(0, deadline - time.monotonic()))
                if not ready:
                    break
                line = process.stdout.readline()
                if not line:
                    break
                response = json.loads(line)
                if response.get("id") == message["id"]:
                    return response.get("result", {})
            return {}

        try:
            initialized = exchange(
                {
                    "id": 0,
                    "method": "initialize",
                    "params": {"clientInfo": {"name": "evalopt-included-usage-check", "version": "1"}},
                }
            )
            if not initialized:
                return permission_from_response({})
            process.stdin.write(json.dumps({"method": "initialized"}) + "\n")
            process.stdin.flush()
            return permission_from_response(exchange({"id": 1, "method": "account/rateLimits/read"}))
        except (OSError, ValueError, BrokenPipeError):
            return permission_from_response({})
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    print(json.dumps(read_subscription_permission(), sort_keys=True))
