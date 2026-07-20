#!/usr/bin/env python3
"""Perform a bounded, clean PyPI install and run the installed-release verifier."""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--delay-seconds", type=int, default=10)
    args = parser.parse_args()
    if args.attempts < 1 or not 0 <= args.delay_seconds <= 30:
        raise SystemExit("attempts must be positive and delay must be between 0 and 30 seconds")

    with tempfile.TemporaryDirectory(prefix="evalopt-pypi-") as directory:
        environment = Path(directory) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True, timeout=60)
        python = environment / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
        command = [
            str(python),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "--no-cache-dir",
            "--no-deps",
            "--only-binary=:all:",
            "--retries=0",
            "--timeout=15",
            "--index-url=https://pypi.org/simple",
            f"evalopt-graph=={args.version}",
        ]
        last: subprocess.SubprocessError | None = None
        for attempt in range(1, args.attempts + 1):
            try:
                subprocess.run(command, check=True, timeout=30)
                last = None
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                last = exc
                if attempt < args.attempts:
                    print(f"PyPI install attempt {attempt} failed; retrying", file=sys.stderr)
                    time.sleep(args.delay_seconds)
        if last is not None:
            raise SystemExit(f"PyPI install failed after {args.attempts} attempts") from last
        subprocess.run(
            [
                str(python),
                str(ROOT / "scripts" / "verify_installed_release.py"),
                "--version",
                args.version,
            ],
            check=True,
            timeout=60,
        )
    print(f"PyPI evalopt-graph {args.version} installation verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
