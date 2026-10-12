# Actual hosted bundle qualification before publication

Root downloaded release-bundle11777777419 from run38317836286 attempt1, source8c8b7f4583a161947578fdd62d4c6658a1956f55 at annotated v0.1.1. The four draft GitHub assets were independently downloaded to a new directory and compared byte for byte with the workflow bundle. Exactly two distributions and two evidence assets were present. This report does not claim public PyPI publication.

| File | Bytes | SHA256 |
|---|---:|---|
| evalopt_graph-0.1.1-py3-none-any.whl | 137354 | `d6cffc1a0f1b56b087805ee18662d11863d6063b231b2d8e97d64a3430c8e739` |
| evalopt_graph-0.1.1.tar.gz | 382132 | `2c49351a7c6343b31faf3b9ff2c7359cc51a41f6249559c31f388be600facf10` |
| SHA256SUMS.txt | 196 | `7d7661547846d824f0709288d4730a73352903a4e58e9e63e6a68bfd7ca52e22` |
| evalopt-graph-0.1.1.spdx.json | 4232 | `9dee6be448e411d3190ea8ae25eb4fef2801feaa8dcdbd9065628c04ea95ff29` |

The checksum manifest names exactly the two distributions and matches their locally computed digests. Pinned Twine6.2.0 and verify_artifacts.py passed on the actual hosted files. A clean offline CPython3.13.12 virtual environment outside the source checkout installed only the hosted wheel with --no-deps. The exact ten-export/version/serialization/replay installed-release smoke passed, and the resolved import path was under that environment's site-packages. These checks are distinct from the earlier local candidate, whose timestamp-dependent archive bytes differ.

Native gh attestation verify passed for both distributions with repository and signer-workflow restrictions, exact source/signing commit, refs/tags/v0.1.1 and hosted-runner requirement. Root inspected the verified certificate source, signer, ref, workflow and invocation38317836286/attempt1. The provenance predicate is SLSA v1. The SPDX predicate is https://spdx.dev/Document/v2.3 and its parsed JSON exactly equals the downloaded SPDX asset. After inspecting that exact returned URI, root also ran both verifications with the explicit versioned v2.3 filter; both passed. Earlier unversioned Document-filter outputs remain retained.

Each signed statement additionally includes a .gitignore subject digest matching the single byte star, alongside both distribution digests. The hidden marker was not uploaded in the release bundle or GitHub assets. Root has not recovered its actual hosted file bytes and does not claim it as a release asset. The SPDX document is an archive-level inventory of two distributions, not a complete dependency or source-file SBOM.

Two exploratory root assertions failed before the final binding summary: an assumed newline in the marker content, and an assumed unversioned returned SPDX URI. Direct inspection corrected those assumptions. None of the original native verification results, signed predicates, artifacts or release source was repaired or replaced. The failures and corrected analysis are disclosed in private root-metadata-analysis-note.txt.

A fresh versioned PyPI query returned HTTP404 before approval, so version0.1.1 had not been published at that observation. Source/main CI, all twelve predecessor workflow jobs, actual-byte independent reviews, current native deployment eligibility and later public-channel verification are separate gates. Raw command arguments, exits, UTC timestamps, outputs, downloaded bytes and hashes are retained privately under artifacts/10-hosted; this summary is the public evidence pointer, not the raw evidence itself.
