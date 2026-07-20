#!/usr/bin/env python3
"""Generate a compact SPDX 2.3 JSON SBOM for the two release archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path, algorithm: str) -> str:
    hasher = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def creation_timestamp() -> str:
    """Return a reproducible SPDX timestamp when SOURCE_DATE_EPOCH is set."""
    raw_epoch = os.environ.get("SOURCE_DATE_EPOCH")
    moment = (
        datetime.fromtimestamp(int(raw_epoch), timezone.utc)
        if raw_epoch is not None
        else datetime.now(timezone.utc)
    )
    return moment.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()

    artifacts = sorted([*args.dist_dir.glob("*.whl"), *args.dist_dir.glob("*.tar.gz")])
    if len(artifacts) != 2:
        raise SystemExit(f"expected one wheel and one sdist, found {artifacts!r}")
    identity = hashlib.sha256("".join(digest(path, "sha256") for path in artifacts).encode()).hexdigest()
    files = []
    packages = []
    relationships = []
    for index, path in enumerate(artifacts, 1):
        file_id = f"SPDXRef-File-{index}"
        package_id = f"SPDXRef-Package-{index}"
        sha1 = digest(path, "sha1")
        sha256 = digest(path, "sha256")
        verification_code = hashlib.sha1(sha1.encode("ascii")).hexdigest()
        kind = "wheel" if path.suffix == ".whl" else "sdist"
        files.append(
            {
                "SPDXID": file_id,
                "fileName": f"./{path.name}",
                "checksums": [
                    {"algorithm": "SHA1", "checksumValue": sha1},
                    {"algorithm": "SHA256", "checksumValue": sha256},
                ],
                "fileTypes": ["ARCHIVE"],
                "licenseConcluded": "MIT",
                "copyrightText": "Copyright (c) 2026 Ajay Surya Senthilrajan",
            }
        )
        packages.append(
            {
                "SPDXID": package_id,
                "name": f"evalopt-graph-{kind}",
                "versionInfo": args.version,
                "packageFileName": path.name,
                "downloadLocation": f"https://pypi.org/project/evalopt-graph/{args.version}/#files",
                "filesAnalyzed": True,
                "packageVerificationCode": {"packageVerificationCodeValue": verification_code},
                "checksums": [{"algorithm": "SHA256", "checksumValue": sha256}],
                "licenseConcluded": "MIT",
                "licenseDeclared": "MIT",
                "copyrightText": "Copyright (c) 2026 Ajay Surya Senthilrajan",
                "supplier": "Person: Ajay Surya Senthilrajan",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:pypi/evalopt-graph@{args.version}",
                    }
                ],
            }
        )
        relationships.extend(
            [
                {
                    "spdxElementId": "SPDXRef-DOCUMENT",
                    "relationshipType": "DESCRIBES",
                    "relatedSpdxElement": package_id,
                },
                {
                    "spdxElementId": package_id,
                    "relationshipType": "CONTAINS",
                    "relatedSpdxElement": file_id,
                },
            ]
        )

    document = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"evalopt-graph-{args.version}-release",
        "documentNamespace": f"https://github.com/ajaysurya1221/evalopt-graph/releases/download/v{args.version}/spdx-{identity}",
        "creationInfo": {
            "created": creation_timestamp(),
            "creators": [
                "Tool: evalopt-release-automation/1",
                "Person: Ajay Surya Senthilrajan",
            ],
        },
        "documentDescribes": [package["SPDXID"] for package in packages],
        "packages": packages,
        "files": files,
        "relationships": relationships,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
