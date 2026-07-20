"""Removed local SWE-bench-shaped runner; use the official Docker evaluator."""


def _removed(*_args, **_kwargs):
    raise RuntimeError("local SWE-bench grading was removed; use the official Docker harness")


load_instances = load_swebench_tasks = materialize = prep_swebench = swebench_local_grade = _removed
