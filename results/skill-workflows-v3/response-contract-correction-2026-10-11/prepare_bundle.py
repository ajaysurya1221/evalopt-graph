"""Regenerate only this prospective patch artifact from exact pinned Git objects."""

import difflib
import hashlib
import json
import subprocess
from pathlib import Path

BASE = "f36088d17adcbfdfe24ec2a15d1268fd539daae6"
PREFIX = "bench/harbor/skill-workflows-v3/"
BUNDLE = Path(__file__).resolve().parent


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


names = (
    subprocess.check_output(["git", "ls-tree", "-r", "--name-only", BASE, "--", PREFIX + "evalopt_v3"])
    .decode()
    .splitlines()
)
originals = {
    name: subprocess.check_output(["git", "show", BASE + ":" + name])
    for name in names
    if name.endswith(".py")
}
changes = {}
for short in [
    "grading.py",
    "reporting.py",
    "materialize.py",
    "response_contract.py",
    "test_response_contract.py",
]:
    name = PREFIX + ("tests/" if short.startswith("test_") else "evalopt_v3/") + short
    new = (BUNDLE / "payload" / short).read_bytes()
    old = originals.get(name)
    changes[name] = {
        "before_sha256": sha(old) if old else None,
        "after_sha256": sha(new),
        "payload": "payload/" + short,
    }
diffs = []
for name, change in sorted(changes.items()):
    old = originals.get(name)
    new = (BUNDLE / change["payload"]).read_bytes()
    diffs.extend(
        difflib.unified_diff(
            (old or b"").decode().splitlines(keepends=True),
            new.decode().splitlines(keepends=True),
            fromfile="a/" + name if old else "/dev/null",
            tofile="b/" + name,
        )
    )
patch = "".join(diffs).encode()
(BUNDLE / "response-contract.patch").write_bytes(patch)
manifest = dict(
    schema_version="evalopt.prospective-response-contract-fix.v1",
    base_commit=BASE,
    package_prefix=PREFIX,
    prospective_only=True,
    live_trials=0,
    base_source_sha256={name: sha(raw) for name, raw in originals.items()},
    changes=changes,
    patch_sha256=sha(patch),
)
(BUNDLE / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
