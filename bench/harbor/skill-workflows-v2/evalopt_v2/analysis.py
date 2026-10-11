"""Pure registered analysis. Unknown outcomes never disappear from denominators."""

from __future__ import annotations

import random
from collections import defaultdict
from fractions import Fraction

from .records import digest
from .registration import ARMS, CATEGORIES, ORDINARY, SEED, schedule, validate_registration, validate_tasks


def reconcile(tasks, rows, stage="heldout"):
    expected = schedule(tasks, stage)
    by_id = {row["trial_id"]: row for row in expected}
    actual = {}
    disputed = set()
    for row in rows:
        key = row.get("trial_id")
        if key not in by_id or key in actual:
            raise ValueError("unknown or duplicate scheduled row")
        if any(row.get(field) != value for field, value in by_id[key].items()):
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


def _quantile(values, probability):
    values = sorted(values)
    index = (len(values) - 1) * probability
    lo = int(index)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (index - lo) * (values[hi] - values[lo])


def _contrast(tasks, rows, comparator, *, unfavorable, categories, resamples, metric="valid_completion"):
    selected = sorted((task for task in tasks if task["category"] in categories), key=lambda task: task["id"])
    lookup = defaultdict(list)
    for row in rows:
        lookup[row["task_id"], row["arm"]].append(row[f"reported_{metric}"])
    strata = {category: defaultdict(list) for category in categories}
    incomplete = False
    for task in selected:
        values = []
        for arm in ("C", comparator):
            attempts = lookup[task["id"], arm]
            if any(value is None for value in attempts):
                incomplete = True
                if not unfavorable:
                    continue
            values.append(
                Fraction(
                    sum((False if arm == "C" else True) if value is None else value for value in attempts),
                    len(attempts),
                )
            )
        if len(values) == 2:
            strata[task["category"]][task["source_cluster"]].append(values[0] - values[1])
    if incomplete and not unfavorable:
        return {"estimate_pp": None, "ci95_pp": None, "status": "missing_outcomes", "tasks": len(selected)}
    if any(len(clusters) < 2 for clusters in strata.values()):
        return {
            "estimate_pp": None,
            "ci95_pp": None,
            "status": "insufficient_clusters",
            "tasks": len(selected),
        }
    all_diffs = [value for clusters in strata.values() for values in clusters.values() for value in values]
    point = sum(all_diffs) / len(all_diffs)
    rng = random.Random(SEED)
    distribution = []
    for _ in range(resamples):
        weighted = Fraction(0)
        for clusters in strata.values():
            units = [clusters[key] for key in sorted(clusters)]
            draws = [rng.choice(units) for _ in units]
            sampled = [value for cluster in draws for value in cluster]
            original_n = sum(map(len, units))
            weighted += original_n * sum(sampled) / len(sampled)
        distribution.append(100 * weighted / len(all_diffs))
    ci = [_quantile(distribution, Fraction(1, 40)), _quantile(distribution, Fraction(39, 40))]
    return {
        "metric": metric,
        "estimate_pp": float(point * 100),
        "ci95_pp": list(map(float, ci)),
        "one_sided_lower95_pp": float(_quantile(distribution, Fraction(1, 20))),
        "status": "degenerate" if min(distribution) == max(distribution) else "estimated",
        "tasks": len(selected),
        "unfavorable_missing_assignment": unfavorable,
    }


def report(tasks, rows, *, registration_record, resamples=20000):
    validate_registration(registration_record, expected_sha256=registration_record["registration_sha256"])
    if registration_record["stage"] != "heldout" or tasks != registration_record["tasks"]:
        raise ValueError("analysis tasks differ from frozen registration")
    validate_tasks(tasks, "heldout")
    if resamples != 20000:
        raise ValueError("registered analysis requires 20000 resamples")
    resolved = reconcile(tasks, rows)
    contrasts = {}
    for comparator in ("D", "B"):
        contrasts[f"C-{comparator}"] = {
            "observed": _contrast(
                tasks, resolved, comparator, unfavorable=False, categories=CATEGORIES, resamples=resamples
            ),
            "unfavorable": _contrast(
                tasks, resolved, comparator, unfavorable=True, categories=CATEGORIES, resamples=resamples
            ),
            "ordinary": _contrast(
                tasks,
                resolved,
                comparator,
                unfavorable=False,
                categories=ORDINARY,
                resamples=resamples,
                metric="functional_success",
            ),
            "ordinary_unfavorable": _contrast(
                tasks,
                resolved,
                comparator,
                unfavorable=True,
                categories=ORDINARY,
                resamples=resamples,
                metric="functional_success",
            ),
        }

    def qualifies(contrast, threshold):
        for field in ("observed", "unfavorable"):
            item = contrast[field]
            if item["status"] != "estimated" or item["estimate_pp"] < threshold or item["ci95_pp"][0] <= 0:
                return False
        for field in ("ordinary", "ordinary_unfavorable"):
            item = contrast[field]
            if item["status"] != "estimated" or item["one_sided_lower95_pp"] <= -5:
                return False
        return True

    mechanism = qualifies(contrasts["C-D"], 5)
    upgrade = mechanism and qualifies(contrasts["C-B"], 10)
    arms = {}
    for arm in ARMS:
        selected = [row for row in resolved if row["arm"] == arm]
        passing = sum(row["reported_valid_completion"] is True for row in selected)
        missing = sum(row["reported_valid_completion"] is None for row in selected)
        arms[arm] = {
            "scheduled": len(selected),
            "valid": passing,
            "failed": len(selected) - passing - missing,
            "unknown": missing,
            "success_bounds": [passing / len(selected), (passing + missing) / len(selected)],
            "all_three_success_tasks": sum(
                all(
                    row["reported_valid_completion"] is True
                    for row in selected
                    if row["task_id"] == task["id"]
                )
                for task in tasks
            ),
            "all_three_unknown_tasks": sum(
                not any(
                    row["reported_valid_completion"] is False
                    for row in selected
                    if row["task_id"] == task["id"]
                )
                and any(
                    row["reported_valid_completion"] is None
                    for row in selected
                    if row["task_id"] == task["id"]
                )
                for task in tasks
            ),
        }
    from .descriptive import outcomes

    return {
        "schema_version": "evalopt-workflows-v2/1",
        "evidence_class": "maintainer-run authored study",
        "scheduled": len(resolved),
        "seed": SEED,
        "resamples": resamples,
        "input_sha256": digest({"tasks": tasks, "rows": rows}),
        "registration_sha256": registration_record["registration_sha256"],
        "arms": arms,
        "contrasts": contrasts,
        "mechanism_claim_allowed": mechanism,
        "upgrade_claim_allowed": upgrade,
        "conclusion": "scoped_upgrade" if upgrade else ("mechanism_benefit" if mechanism else "inconclusive"),
        "disputed_tasks": sorted({row["task_id"] for row in resolved if row["task_disputed"]}),
        "efficiency_claim_allowed": False,
        "secondary_outcomes": outcomes(resolved),
        "scheduled_rows": resolved,
    }
