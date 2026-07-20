from __future__ import annotations

import pytest

from evalopt_graph import swebench


def test_local_swebench_runner_is_removed() -> None:
    with pytest.raises(RuntimeError, match="official Docker harness"):
        swebench.load_instances("instances.json")


def test_local_swebench_grader_is_not_mistaken_for_official_evaluation() -> None:
    with pytest.raises(RuntimeError, match="official Docker harness"):
        swebench.swebench_local_grade("checkout", object())
