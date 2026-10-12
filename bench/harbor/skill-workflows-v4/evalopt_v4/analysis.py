"""Pure difficulty-screen analysis. No comparative inference or model execution."""

from .records import digest
from .registration import difficulty_gate, schedule, validate_registration


def reconcile(tasks, rows, stage="difficulty"):
    expected = schedule(tasks, stage)
    by_id = {row["trial_id"]: row for row in expected}
    actual = {}
    disputed = set()
    for row in rows:
        key = row.get("trial_id")
        if key not in by_id or key in actual:
            raise ValueError("unknown or duplicate scheduled row")
        if digest({field: row.get(field) for field in by_id[key]}) != digest(by_id[key]):
            raise ValueError("row identity differs from schedule")
        value = row.get("valid_completion")
        if type(value) is not bool and value is not None:
            raise ValueError("completion must be boolean or null")
        functional = row.get("functional_success")
        if type(functional) is not bool and functional is not None:
            raise ValueError("functional outcome must be boolean or null")
        if type(row.get("contract_dispute", False)) is not bool:
            raise ValueError("invalid dispute flag")
        if row.get("contract_dispute"):
            disputed.add(row["task_id"])
        actual[key] = row
    resolved = []
    for expected_row in expected:
        row = dict(
            actual.get(
                expected_row["trial_id"],
                {**expected_row, "valid_completion": None, "missing_reason": "unstarted_or_missing"},
            )
        )
        row["reported_valid_completion"] = None if row["task_id"] in disputed else row["valid_completion"]
        row["reported_functional_success"] = (
            None if row["task_id"] in disputed else row.get("functional_success")
        )
        row["task_disputed"] = row["task_id"] in disputed
        resolved.append(row)
    return resolved


def report(tasks, rows, *, registration_record):
    validate_registration(registration_record, expected_sha256=registration_record["registration_sha256"])
    if tasks != registration_record["tasks"]:
        raise ValueError("analysis tasks differ from freeze")
    resolved = reconcile(tasks, rows, "difficulty")
    gate = difficulty_gate(tasks, rows, controls_passed=True)
    from .descriptive import outcomes

    return dict(
        schema_version="evalopt-workflows-v4/1",
        stage="difficulty",
        evidence_class="maintainer-run upstream-only difficulty screen",
        input_sha256=digest({"tasks": tasks, "rows": rows}),
        scheduled_rows=resolved,
        secondary_outcomes=outcomes(resolved),
        gate=gate,
        conclusion=gate["conclusion"],
        mechanism_claim_allowed=False,
        upgrade_claim_allowed=False,
        larger_benchmark_authorized=False,
    )
