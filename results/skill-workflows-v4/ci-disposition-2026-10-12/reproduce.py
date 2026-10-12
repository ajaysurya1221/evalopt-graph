"""Replay sanitized nonsecret source correspondence, without running a scanner."""

import sys

if not sys.flags.isolated or not sys.flags.dont_write_bytecode:
    raise SystemExit("Run with python -I -B.")

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

CONTENT_PINS = {
    "README.md": "ad7648511907e15dcf081011ca835de659ccd90213fc039d2079276abb7bf189",
    "adjudicate.py": "44866981ce3277ca8e4558512eecc2fba291d61aa2840c50222e685d758dc3e5",
    "adjudicator-review.json": "ba3056c5b4fe55dc456b29d98ae4b6a494af5cd2645b0d38f2274ec3ad04d212",
    "diagnosis.json": "3ccdb27be0321b052a17bc693239b456fa07ae34943d1536235747af015b7fbc",
    "expected-findings.json": "943d01b687acbb2ca53d75951d4d51fa0f34f96ad1b79adb645c582b822c6c98",
    "historical-adjudication.json": "09782bc3e2b677d06b95b48e5eae8c48a480e001f297c4c0b12c66940749c159",
    "historical-hosted-status.json": "d1d8adda3799d3e86318c34429ff423a404403202a2aadd16efda2f4cd0187e6",
    "hosted-gate.py": "d4b2d8545d6bd195e5b9162d798d20026f0fab2d5ac812f85e99f5bfb48db32d",
    "hosted-review.json": "46afaf59ad247ed9e7d214b840d53f4366348dd53f03e0d35f754a5c4eb038bd",
    "operational-policy.json": "bfda412c444b51f22bd41551a3819928c52ae0201f5840f733beaa1759e3f620",
    "receipt.json": "b47b5a4b0678d46bac2999a2446386b0c168459ef4e00571442baa3e3b42a5c7",
}

HELPER_SHA = "44866981ce3277ca8e4558512eecc2fba291d61aa2840c50222e685d758dc3e5"


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[3])
    args = parser.parse_args()
    bundle = Path(__file__).resolve().parent
    helper = bundle / "adjudicate.py"
    require(not helper.is_symlink(), "helper symlink")
    require(hashlib.sha256(helper.read_bytes()).hexdigest() == HELPER_SHA, "helper changed")
    spec = importlib.util.spec_from_file_location("v4_nonsecret_source_correspondence", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checksums = module.strict(module.regular(bundle / "checksums.json"))
    require(
        type(checksums) is dict and set(checksums) == set(CONTENT_PINS) | {"reproduce.py"}, "checksum roster"
    )
    require(
        all(checksums[name] == digest for name, digest in CONTENT_PINS.items()),
        "pinned packet content changed",
    )
    actual = {p.name for p in bundle.iterdir()}
    require(actual == set(checksums) | {"checksums.json"}, "unexpected or missing packet file")
    for name, digest in checksums.items():
        require(type(name) is str and Path(name).name == name, "nonlocal packet path")
        require(type(digest) is str and len(digest) == 64, "checksum type")
        require(module.sha(module.regular(bundle / name)) == digest, "packet changed: " + name)
    expected = module.expected(bundle / "expected-findings.json")
    require(
        module.sha(module.regular(bundle / "diagnosis.json")) == module.DIAGNOSIS_SHA, "diagnosis changed"
    )
    policy = module.strict(module.regular(bundle / "operational-policy.json"))
    require(
        policy["claims"]["ci_all_green"] is False
        and policy["claims"]["future_exceptions_authorized"] is False
        and policy["claims"]["larger_benchmark_authorized"] is False
        and policy["claims"]["scanner_pass_claim"] is False
        and policy["known_findings"]["exact_fingerprints"] == sorted(x["Fingerprint"] for x in expected),
        "policy classification or limits changed",
    )
    projection = module.strict(module.regular(bundle / "historical-adjudication.json"))
    require(
        projection["status"] == "ACCEPT_KNOWN_NONSECRETS"
        and type(projection["original_scan_exit"]) is int
        and projection["original_scan_exit"] == 1
        and projection["clean_scan"] is False
        and projection["green_ci_claim"] is False
        and projection["head"] == module.HEAD
        and type(projection["finding_count"]) is int
        and projection["finding_count"] == 11,
        "historical classification or limits changed",
    )
    repo = args.repo.resolve(strict=True)

    def blob(commit, path):
        # Paths and commit are the pinned expected roster, not verifier code.
        return module.git(repo, "show", f"{commit}:{path}")

    findings = module.validate_projection(projection["findings"], expected, blob)
    print(
        json.dumps(
            {
                "status": "PASS_SOURCE_CORRESPONDENCE",
                "historical_findings": len(findings),
                "historical_scanner_exit": 1,
                "scope": "Sanitized immutable Git-source correspondence; retained scan execution is not independently reproduced or authenticated.",
                "scanner_executed": False,
                "ci_all_green": False,
                "dispatch_authorized": False,
                "candidate_execution": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
