# Transfer image setup checks — 2026-10-09

**12/12 pinned images passed setup and configuration checks.** These controls ran zero model calls, agent trials, task trials, or verifier trials. They are preparation evidence for the Terminal-Bench feasibility subset, not workflow benchmark results.

Harbor **0.24.0** used its unmodified installation recipe for Codex **0.154.0**. Every image reported Node **22.23.3**, npm **10.9.9**, and `multi_agent=true` with the frozen configuration. Fresh `linux/amd64` containers ran sequentially with one CPU, 2 GiB RAM, and a 600-second installation/check budget each; cleanup and read-only verification had separately bounded overhead. Networking was detached before the feature query. No authentication, host mounts, Docker socket, or task startup was supplied. All probe containers were removed; the original images and prepared tasks were unchanged.

[setup-receipt.json](setup-receipt.json) records the frozen source, preparation, image lock, helper, result-summary and retained checksum identities, plus each image digest and retained result hash. A separate maintainer agent independently inspected the helper and retained evidence and accepted this setup-only scope. This is maintainer-agent review, not independent human replication.

The public package contains selected observations and identities. Private paths, contributor/account identifiers, raw logs, helper code and prepared task assets are excluded. The command below checks these public files and their counts; it cannot independently reproduce or authenticate the private container observations.

From the repository root:

```bash
python3 -B - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("results/skill-workflows-v1/transfer-readiness-2026-10-09")
checks = json.loads((root / "CHECKSUMS.json").read_bytes())
assert set(checks["files"]) == {"README.md", "setup-receipt.json"}
assert {p.name for p in root.iterdir()} == {*checks["files"], "CHECKSUMS.json"}
for name, expected in checks["files"].items():
    path = root / name
    assert path.is_file() and not path.is_symlink()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected
receipt = json.loads((root / "setup-receipt.json").read_bytes())
rows = receipt["images"]
assert len(rows) == len({row["task"] for row in rows}) == 12
assert all(row["setup_status"] == "passed" for row in rows)
observed = receipt["observations"]
assert observed["selected_images"] == observed["setup_passes"] == 12
for key in ("setup_failures", "model_calls", "agent_trials", "task_trials", "verifier_trials"):
    assert observed[key] == 0
print("Receipt integrity and 12 setup records verified; private executions not replayed.")
PY
```

These checks do not establish returned model identity, actual delegation/accounting behavior, required-service behavior, verifier execution, task success within original deadlines, agent efficiency, or workflow superiority. Transfer freeze and dispatch still require **all 432 scheduled primary trials to be terminal and accounted for**, with verified retained artifacts and a reproduced primary report; outcomes need not be successful. Frozen workflow identities and the registered accounting policy must also match.
