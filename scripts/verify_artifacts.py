#!/usr/bin/env python3
"""Inspect release archives for package shape, hygiene, and dependency invariants."""

from __future__ import annotations

import argparse
import email
import re
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

ALLOWED_SDIST_ROOTS = {
    ".gitignore",
    "CHANGELOG.md",
    "CODE_OF_CONDUCT.md",
    "CONTRIBUTING.md",
    "LICENSE",
    "PKG-INFO",
    "README.md",
    "SECURITY.md",
    "bench",
    "claude_assets",
    "docs",
    "pyproject.toml",
    "scripts",
    "src",
    "tests",
}
FORBIDDEN_COMPONENTS = {
    ".backups",
    ".context",
    ".evalopt",
    ".git",
    ".github",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "runs",
}
PERSONAL_MARKERS = tuple(
    "".join(parts).encode()
    for parts in (
        ("/Users/", "ajay/"),
        ("evalopt-graph-", "template"),
        ("conductor/", "workspaces"),
        ("~/", "Developer/"),
    )
)


def fail(message: str) -> None:
    raise AssertionError(message)


def check_common(path: PurePosixPath, data: bytes | None = None) -> None:
    if any(part in FORBIDDEN_COMPONENTS for part in path.parts):
        fail(f"forbidden artifact path: {path}")
    name = path.name.casefold()
    if name == ".env" or name.startswith(".env.") or name.endswith((".pyc", ".pyo")):
        fail(f"environment or cache file in artifact: {path}")
    if data is not None and b"\x00" not in data[:8192]:
        for marker in PERSONAL_MARKERS:
            if marker in data:
                fail(f"personal workspace marker {marker!r} in {path}")


def verify_wheel(wheel: Path, version: str) -> None:
    with zipfile.ZipFile(wheel) as archive:
        names = [PurePosixPath(name) for name in archive.namelist() if not name.endswith("/")]
        package_files = [path for path in names if path.parts[0] == "evalopt_graph"]
        dist_info_roots = {path.parts[0] for path in names if path.parts[0].endswith(".dist-info")}
        if not package_files:
            fail("wheel does not contain evalopt_graph")
        if len(dist_info_roots) != 1:
            fail(f"wheel must contain exactly one dist-info directory: {dist_info_roots!r}")
        dist_info = next(iter(dist_info_roots))
        for path in names:
            check_common(path, archive.read(str(path)))
            if path.parts[0] not in {"evalopt_graph", dist_info}:
                fail(f"wheel contains non-package payload: {path}")
        required = {"METADATA", "RECORD", "WHEEL"}
        present = {path.name for path in names if path.parts[0] == dist_info}
        if not required <= present:
            fail(f"wheel metadata missing {sorted(required - present)}")
        if not any(
            path.parts[0] == dist_info and "licenses" in path.parts and path.name == "LICENSE"
            for path in names
        ):
            fail("wheel does not carry the MIT LICENSE as license metadata")

        metadata_path = next(path for path in names if path.parts == (dist_info, "METADATA"))
        metadata = email.message_from_bytes(archive.read(str(metadata_path)))
        if metadata["Name"] != "evalopt-graph" or metadata["Version"] != version:
            fail("wheel name/version metadata does not match the release")
        if metadata["License-Expression"] != "MIT":
            fail("wheel does not declare the MIT SPDX license expression")
        if metadata["Description-Content-Type"] != "text/markdown" or not metadata.get_payload().strip():
            fail("wheel metadata does not contain the Markdown README")
        if metadata["Requires-Python"] != ">=3.10":
            fail("wheel Python requirement does not match the supported range")
        runtime = [
            requirement
            for requirement in metadata.get_all("Requires-Dist", [])
            if not re.search(r"\bextra\s*==", requirement)
        ]
        if runtime:
            fail(f"wheel declares runtime dependencies: {runtime!r}")


def verify_sdist(sdist: Path, version: str) -> None:
    with tarfile.open(sdist, "r:gz") as archive:
        members = [member for member in archive.getmembers() if member.isfile()]
        roots = {PurePosixPath(member.name).parts[0] for member in members}
        if len(roots) != 1:
            fail(f"sdist must have one archive root: {roots!r}")
        archive_root = next(iter(roots))
        paths: dict[PurePosixPath, bytes] = {}
        for member in members:
            full = PurePosixPath(member.name)
            relative = PurePosixPath(*full.parts[1:])
            extracted = archive.extractfile(member)
            data = extracted.read() if extracted is not None else b""
            check_common(relative, data)
            if not relative.parts:
                continue
            if relative.parts[0] not in ALLOWED_SDIST_ROOTS:
                fail(f"sdist path is outside the explicit public allowlist: {relative}")
            if relative.parts[0] == "bench" and relative.parts[:2] != ("bench", "harbor"):
                fail(f"only Harbor conformance material may ship under bench/: {relative}")
            paths[relative] = data

        required = {
            PurePosixPath("LICENSE"),
            PurePosixPath("README.md"),
            PurePosixPath("pyproject.toml"),
            PurePosixPath("src/evalopt_graph/__init__.py"),
        }
        missing = required - paths.keys()
        if missing:
            fail(f"sdist missing required public files: {sorted(map(str, missing))}")
        if not paths[PurePosixPath("README.md")].strip():
            fail("sdist README is empty")
        if b"Copyright (c) 2026 Ajay Surya Senthilrajan" not in paths[PurePosixPath("LICENSE")]:
            fail("sdist LICENSE is not the expected MIT license")
        expected_root = f"evalopt_graph-{version}"
        if archive_root != expected_root:
            fail(f"sdist root is {archive_root!r}, expected {expected_root!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dist", type=Path)
    parser.add_argument("--version", default="0.1.0")
    args = parser.parse_args()
    wheels = sorted(args.dist.glob("*.whl"))
    sdists = sorted(args.dist.glob("*.tar.gz"))
    # uv owns this exact output-directory marker. It is not part of either archive and
    # upload-artifact is explicitly configured to exclude hidden files.
    unexpected = sorted(
        path.name
        for path in args.dist.iterdir()
        if path.is_file() and path not in {*wheels, *sdists} and path.name != ".gitignore"
    )
    if len(wheels) != 1 or len(sdists) != 1 or unexpected:
        fail(
            f"expected one wheel and one sdist, found wheels={wheels}, sdists={sdists}, "
            f"unexpected={unexpected}"
        )
    verify_wheel(wheels[0], args.version)
    verify_sdist(sdists[0], args.version)
    print(f"verified wheel and sdist hygiene for evalopt-graph {args.version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
