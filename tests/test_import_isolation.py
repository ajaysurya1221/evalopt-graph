from __future__ import annotations

import json
import subprocess
import sys


def test_package_root_exports_only_stable_kernel_and_keeps_hosts_unloaded() -> None:
    code = """
import json
import sys
import evalopt_graph
excluded = [
    'evalopt_graph.graph',
    'evalopt_graph.cli',
    'evalopt_graph.providers',
    'evalopt_graph.bench',
    'evalopt_graph.swebench',
    'evalopt_graph.harbor_adapter',
    'evalopt_graph.evidence_adapters',
    'langgraph',
]
print(json.dumps({'exports': evalopt_graph.__all__, 'loaded': [x for x in excluded if x in sys.modules]}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert len(result["exports"]) == 10
    assert result["loaded"] == []
