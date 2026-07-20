"""Removed local experiment runner.

Harbor owns tasks, trials, isolation, artifacts, retries, and aggregation. Deterministic mechanism
checks remain ordinary tests; this module exists for one compatibility cycle only.
"""


def _removed(*_args, **_kwargs):
    raise RuntimeError("evalopt's local benchmark runner was removed; use the pinned Harbor adapter")


bench_ab = load_fixture_tasks = run_suite = run_config = grade = _removed
