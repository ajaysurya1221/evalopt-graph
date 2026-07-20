from __future__ import annotations

import pytest

from evalopt_graph import bench
from evalopt_graph.cli import main


def test_local_experiment_runner_is_removed() -> None:
    with pytest.raises(RuntimeError, match="Harbor"):
        bench.run_suite([])


def test_legacy_bench_cli_points_to_external_harness(capsys) -> None:
    assert main(["bench"]) == 2
    assert "official Docker harness" in capsys.readouterr().err
