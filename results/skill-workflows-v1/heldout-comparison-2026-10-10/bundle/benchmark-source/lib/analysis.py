"""Prespecified task-first workflow analysis and descriptive stopped-output policy metrics.

Percentile paired cluster bootstrap is category-stratified. It is deliberately dependency
free so offline reproduction needs only Python and retained sanitized outcome records.
"""

from __future__ import annotations

import random
from collections import defaultdict
from statistics import mean

from .manifest import CATEGORIES

METRICS = (
    "valid_completion",
    "functional_success",
    "unsupported_success",
    "incorrect_refusal",
    "boundary_violation",
)
FAILURES = {"agent_failure", "timeout", "budget_exhausted"}


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low = int(index)
    fraction = index - low
    return ordered[low] * (1 - fraction) + ordered[min(low + 1, len(ordered) - 1)] * fraction


def _normalize(rows: list[dict], schedule: list[dict] | None) -> list[dict]:
    found = {}
    for row in rows:
        if row["trial_id"] in found:
            raise ValueError("duplicate outcome trial")
        found[row["trial_id"]] = row
        for metric in METRICS:
            if row.get(metric) is not None and type(row[metric]) is not bool:
                raise ValueError(f"{metric} must be boolean or null")
    if schedule is None:
        schedule = rows
    if len({row["trial_id"] for row in schedule}) != len(schedule):
        raise ValueError("duplicate scheduled trial")
    if set(found) - {row["trial_id"] for row in schedule}:
        raise ValueError("unscheduled outcome")
    result = []
    for scheduled in schedule:
        observed = found.get(scheduled["trial_id"], {})
        if observed and any(
            key not in observed or observed[key] != value for key, value in scheduled.items()
        ):
            raise ValueError("outcome identity differs from schedule")
        row = {**scheduled, **observed}
        row.setdefault("status", "missing")
        for metric in METRICS:
            row.setdefault(metric, None)
        if row["status"] in FAILURES:
            row["valid_completion"] = False
        if row["status"] not in {"completed", *FAILURES}:
            for metric in METRICS:
                row[metric] = None
        result.append(row)
    return result


def _pairs(
    rows: list[dict], metric: str, *, conservative: bool = False, ordinary: bool = False
) -> list[dict]:
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row["stage"] != "heldout" or row["arm"] not in {"B", "C"}:
            continue
        if ordinary and row["category"] not in CATEGORIES[:2]:
            continue
        grouped[row["task_id"]][row["arm"]].append(row)
    pairs = []
    clusters = {}
    for task_id, arms in sorted(grouped.items()):
        if set(arms) != {"B", "C"}:
            continue
        if any(
            len(values) != 3 or {item["repetition"] for item in values} != {1, 2, 3}
            for values in arms.values()
        ):
            raise ValueError("heldout task requires three unique repetitions per arm")
        first = arms["B"][0]
        if any(
            (row["cluster_id"], row["category"]) != (first["cluster_id"], first["category"])
            for values in arms.values()
            for row in values
        ):
            raise ValueError("task cluster/category changed across trials")
        if first["cluster_id"] in clusters and clusters[first["cluster_id"]] != first["category"]:
            raise ValueError("shared-source cluster crosses category strata; preregister another design")
        clusters[first["cluster_id"]] = first["category"]
        means = {}
        for arm in ("B", "C"):
            values = [row[metric] for row in arms[arm]]
            if conservative:
                values = [(arm == "B") if value is None else value for value in values]
            if any(value is None for value in values):
                break
            means[arm] = mean(values)
        if len(means) == 2:
            pairs.append(
                {
                    "task_id": task_id,
                    "cluster_id": first["cluster_id"],
                    "category": first["category"],
                    "difference": means["C"] - means["B"],
                }
            )
    return pairs


def _bootstrap(pairs: list[dict], *, resamples: int, seed: int) -> dict:
    strata: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in pairs:
        strata[row["category"]][row["cluster_id"]].append(row["difference"])
    base = {
        "tasks": len(pairs),
        "clusters": sum(len(value) for value in strata.values()),
        "categories": sorted(strata),
        "resamples": resamples,
        "seed": seed,
        "method": "paired category-stratified cluster percentile bootstrap",
    }
    if not strata or any(len(clusters) < 2 for clusters in strata.values()):
        return {
            **base,
            "difference": None if not pairs else mean(row["difference"] for row in pairs),
            "ci95": None,
            "one_sided_lower95": None,
            "degenerate": True,
            "sufficient": False,
        }
    point = mean(
        mean(value for values in clusters.values() for value in values) for clusters in strata.values()
    )
    rng = random.Random(seed)
    distributions = []
    prepared = [list(clusters.values()) for _, clusters in sorted(strata.items())]
    for _ in range(resamples):
        category_means = []
        for clusters in prepared:
            sampled = [clusters[rng.randrange(len(clusters))] for _ in clusters]
            category_means.append(
                sum(sum(values) for values in sampled) / sum(len(values) for values in sampled)
            )
        distributions.append(mean(category_means))
    degenerate = min(distributions) == max(distributions)
    return {
        **base,
        "difference": point,
        "ci95": [_quantile(distributions, 0.025), _quantile(distributions, 0.975)],
        "one_sided_lower95": _quantile(distributions, 0.05),
        "degenerate": degenerate,
        "sufficient": not degenerate,
    }


def _metric_summary(rows: list[dict], arm: str, metric: str) -> dict:
    selected = [row for row in rows if row["arm"] == arm]
    by_task = defaultdict(list)
    category = {}
    for row in selected:
        if row[metric] is not None:
            by_task[row["task_id"]].append(row[metric])
            category[row["task_id"]] = row["category"]
    strata = defaultdict(list)
    for task, values in by_task.items():
        strata[category[task]].append(mean(values))
    return {
        "category_macro_task_mean": mean(mean(values) for values in strata.values()) if strata else None,
        "observed_trials": sum(len(values) for values in by_task.values()),
        "scheduled_trials": len(selected),
        "missing_trials": sum(row[metric] is None for row in selected),
    }


def analyze_workflows(
    rows: list[dict], schedule: list[dict] | None = None, *, resamples: int = 20000, seed: int = 20261008
) -> dict:
    if type(resamples) is not int or resamples < 100:
        raise ValueError("at least 100 bootstrap resamples required")
    normalized = _normalize(rows, schedule)
    heldout = [row for row in normalized if row["stage"] == "heldout"]
    primary = _bootstrap(_pairs(heldout, "valid_completion"), resamples=resamples, seed=seed)
    conservative = _bootstrap(
        _pairs(heldout, "valid_completion", conservative=True), resamples=resamples, seed=seed
    )
    ordinary = _bootstrap(
        _pairs(heldout, "functional_success", ordinary=True, conservative=True),
        resamples=resamples,
        seed=seed,
    )
    combinations = {(row["task_id"], row["arm"], row["repetition"]) for row in heldout}
    full = schedule is not None and len(heldout) == 432 and len({row["task_id"] for row in heldout}) == 48
    full = (
        full
        and len(combinations) == 432
        and all(
            row["arm"] in {"A", "B", "C"}
            and type(row["repetition"]) is int
            and row["repetition"] in {1, 2, 3}
            for row in heldout
        )
    )
    full = full and all(
        len({row["task_id"] for row in heldout if row["category"] == category}) == 8
        for category in CATEGORIES
    )
    registered = full and seed == 20261008 and resamples == 20000

    def positive(result: dict) -> bool:
        return bool(
            result["sufficient"]
            and result["difference"] >= 0.10
            and result["ci95"][0] > 0
            and set(result["categories"]) == set(CATEGORIES)
        )

    scoped = registered and positive(primary) and positive(conservative)
    noninferior = bool(
        ordinary["sufficient"] and ordinary["tasks"] == 16 and ordinary["one_sided_lower95"] > -0.05
    )
    consistency = {}
    for arm in "ABC":
        tasks = defaultdict(list)
        for row in heldout:
            if row["arm"] == arm:
                tasks[row["task_id"]].append(row["valid_completion"])
        consistency[arm] = {
            "all_three_pass": sum(
                len(values) == 3 and all(value is True for value in values) for values in tasks.values()
            ),
            "scheduled_tasks": len(tasks),
            "complete_tasks": sum(
                len(values) == 3 and all(value is not None for value in values) for values in tasks.values()
            ),
        }
    usage = {}
    for arm in "ABC":
        entries = [row.get("usage") for row in heldout if row["arm"] == arm]
        complete = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("child_usage_complete") is True
        ]
        usage[arm] = {
            "accounted_trials": len(complete),
            "scheduled_trials": len(entries),
            "totals": {
                key: sum(entry[key] for entry in complete)
                for key in ("input_tokens", "output_tokens", "model_calls", "tool_calls", "wall_seconds")
            },
            "dollar_cost": None,
        }
    return {
        "schema_version": "evalopt.workflow-analysis.v1",
        "primary_contrast": "C_minus_B",
        "primary": primary,
        "conservative_missing_C_fail_B_pass": conservative,
        "ordinary_functional_noninferiority": ordinary,
        "registered_analysis_conditions": registered,
        "scoped_positive_headline_permitted": scoped,
        "overall_upgrade_permitted": scoped and noninferior,
        "verdict": "scoped_positive" if scoped else "inconclusive_or_no_registered_gain",
        "metrics": {
            arm: {metric: _metric_summary(heldout, arm, metric) for metric in METRICS} for arm in "ABC"
        },
        "all_three_consistency": consistency,
        "resources": usage,
        "resource_scope": "Final retained trial attempts only; report infrastructure retry resources separately.",
        "stage_summaries": {
            stage: {
                "scheduled_trials": len([row for row in normalized if row["stage"] == stage]),
                "metrics": {
                    arm: {
                        metric: _metric_summary(
                            [row for row in normalized if row["stage"] == stage], arm, metric
                        )
                        for metric in METRICS
                    }
                    for arm in ("BC" if stage == "transfer" else "ABC")
                },
            }
            for stage in ("pilot", "heldout", "transfer")
        },
        "limits": [
            "Maintainer-run authored study; not independent external validation.",
            "Observed 10 percentage point gain does not establish a true gain of that size.",
            "Model and tools are matched; tokens are measured, not matched.",
        ],
    }


def summarize_kernel(rows: list[dict]) -> dict:
    """Secondary descriptive rates, with explicit denominators and unavailable artifacts."""
    ids = [row["trial_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate stopped output in kernel summary")
    result = {}
    for policy in "UMG":
        counts = {
            "scheduled": len(rows),
            "accepted": 0,
            "incorrect_accepted": 0,
            "correct_rejected": 0,
            "hidden_incorrect": 0,
            "hidden_correct": 0,
            "abstentions": 0,
            "artifact_failures": 0,
            "replay_pass": 0,
            "replay_assessed": 0,
            "decision_available": 0,
            "paired_grade_available": 0,
        }
        for row in rows:
            item = row.get("policies", {}).get(policy)
            if row.get("artifact_valid") is not True or not isinstance(item, dict):
                counts["artifact_failures"] += 1
                continue
            if type(item.get("accepted")) is not bool:
                raise ValueError("policy acceptance must be boolean")
            counts["decision_available"] += 1
            accepted = item["accepted"]
            counts["accepted"] += accepted
            counts["abstentions"] += item.get("status") in {"UNVERIFIED", "UNSUPPORTED"}
            correct = row.get("valid_completion")
            if correct is not None:
                if type(correct) is not bool:
                    raise ValueError("hidden grade must be boolean or unavailable")
                counts["paired_grade_available"] += 1
                counts["hidden_correct"] += correct
                counts["hidden_incorrect"] += not correct
                counts["incorrect_accepted"] += accepted and not correct
                counts["correct_rejected"] += not accepted and correct
            replay = row.get("replay", {}).get(policy)
            if replay is not None:
                if type(replay) is not bool:
                    raise ValueError("replay status must be boolean or unavailable")
                counts["replay_assessed"] += 1
                counts["replay_pass"] += replay
        result[policy] = {
            **counts,
            "approval_coverage": counts["accepted"] / counts["scheduled"] if counts["scheduled"] else None,
            "incorrect_acceptance_rate": counts["incorrect_accepted"] / counts["hidden_incorrect"]
            if counts["hidden_incorrect"]
            else None,
            "false_rejection_rate": counts["correct_rejected"] / counts["hidden_correct"]
            if counts["hidden_correct"]
            else None,
            "replay_fidelity": counts["replay_pass"] / counts["replay_assessed"]
            if counts["replay_assessed"]
            else None,
        }
    return {
        "schema_version": "evalopt.kernel-secondary.v1",
        "policies": result,
        "claim": "Descriptive decisions on identical stopped outputs; no causal workflow or superiority claim.",
    }
