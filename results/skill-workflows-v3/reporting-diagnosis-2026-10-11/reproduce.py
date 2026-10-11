"""Reproduce a bounded diagnosis projection without candidate or harness execution."""

import hashlib
import json
from pathlib import Path

TASKS = {
    "atomic-migration-batches": "ordinary-bug-repair",
    "calendar-override-expansion": "ordinary-bug-repair",
    "cyclic-module-exports": "bounded-implementation",
    "incremental-build-invalidation": "bounded-implementation",
    "media-range-precedence": "committed-patch-review",
    "replica-placement-quorums": "mixed-workspace-review",
    "snapshot-delta-compatibility": "constraint-preservation",
    "stale-vector-distance-fixture": "unavailable-or-misleading-evidence",
}
OBLIGATIONS = {
    "media-range-precedence": {"applicable-range-precedence", "parameter-applicability"},
    "replica-placement-quorums": {
        "zero-capacity-eligibility",
        "physical-node-uniqueness",
        "failure-domain-diversity",
    },
}
FIELDS = {
    "trial_id",
    "task_id",
    "category",
    "repetition",
    "task_contract",
    "response_keys",
    "missing_required_envelope_fields",
    "status_value",
    "status_enum_valid",
    "findings_count",
    "checks_exact_supplied_initial_projection",
    "initial_exit_code",
    "post_stop_exit_code",
    "phase_ids_valid_and_distinct",
    "native_prompt_exact_match",
    "native_final_response_exact_match",
    "response_transport",
    "declared_envelope_in_prompt",
    "official_functional_success",
    "official_claims_supported",
    "official_unsupported_success",
    "official_valid_completion",
    "additional_implementation_empty_findings_condition",
    "review_evidence",
}
RESPONSE_KEYS = {
    "changes",
    "changed_files",
    "checks",
    "commit",
    "findings",
    "legacy_check",
    "notes",
    "review",
    "reviews",
    "scope",
    "spec",
    "standards",
    "status",
    "summary",
    "validation",
    "blockers",
}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def hexsha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def canonical(value):
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("nonfinite JSON")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def reduce(inputs):
    need(
        set(inputs) == {"schema_version", "registration_sha256", "source_diagnosis_sha256", "rows"},
        "input fields",
    )
    need(inputs["schema_version"] == "evalopt.v3.reporting-diagnosis-projection.v1", "input schema")
    need(all(hexsha(inputs[k]) for k in ("registration_sha256", "source_diagnosis_sha256")), "input pins")
    need(type(inputs["rows"]) is list and len(inputs["rows"]) == 16, "all 16 rows required")
    seen = set()
    summaries = []
    for row in inputs["rows"]:
        need(type(row) is dict and set(row) == FIELDS, "row fields")
        task = row["task_id"]
        need(task in TASKS and row["category"] == TASKS[task], "task/category")
        need(type(row["repetition"]) is int and row["repetition"] in (1, 2), "repetition")
        expected_id = f"difficulty--{task}--r{row['repetition']}--B"
        need(row["trial_id"] == expected_id and expected_id not in seen, "trial identity")
        seen.add(expected_id)
        is_review = task in OBLIGATIONS
        need(row["task_contract"] == ("review" if is_review else "implementation"), "task contract")
        keys = row["response_keys"]
        need(
            type(keys) is list and keys == sorted(set(keys)) and set(keys) <= RESPONSE_KEYS,
            "response key allowlist",
        )
        missing = sorted({"status", "findings", "blockers", "checks"} - set(keys))
        need(sorted(row["missing_required_envelope_fields"]) == missing, "missing fields")
        need(row["status_value"] in (None, "completed", "repaired"), "bounded observed status")
        need(("status" in keys) == (row["status_value"] is not None), "status presence")
        need(row["status_enum_valid"] is (row["status_value"] in ("completed", "blocked")), "status validity")
        need(type(row["findings_count"]) is int and 0 <= row["findings_count"] <= 12, "findings count")
        for field in FIELDS - {
            "trial_id",
            "task_id",
            "category",
            "repetition",
            "task_contract",
            "response_keys",
            "missing_required_envelope_fields",
            "status_value",
            "findings_count",
            "initial_exit_code",
            "post_stop_exit_code",
            "response_transport",
            "review_evidence",
        }:
            need(type(row[field]) is bool, "boolean field")
        for field in ("initial_exit_code", "post_stop_exit_code"):
            need(type(row[field]) is int and row[field] in (0, 1), "observed check exit code")
        need(row["response_transport"] == "parsed", "observed capture status")
        need(
            all(
                row[k] is True
                for k in (
                    "checks_exact_supplied_initial_projection",
                    "phase_ids_valid_and_distinct",
                    "native_prompt_exact_match",
                    "native_final_response_exact_match",
                )
            ),
            "this diagnosis requires exact retained phase reporting",
        )
        need(
            row["declared_envelope_in_prompt"] is False and "blockers" in missing,
            "observed undeclared envelope",
        )
        need(
            all(
                row[k] is False
                for k in (
                    "official_claims_supported",
                    "official_unsupported_success",
                    "official_valid_completion",
                )
            ),
            "unchanged official labels",
        )
        need(row["official_functional_success"] is (not is_review), "unchanged functional labels")
        need(
            row["additional_implementation_empty_findings_condition"]
            is (not is_review and row["findings_count"] > 0),
            "implementation findings",
        )
        review = row["review_evidence"]
        if is_review:
            need(
                type(review) is dict
                and set(review)
                == {
                    "classification",
                    "witnesses",
                    "covered_obligations",
                    "missing_obligations",
                    "official_grade_details_empty",
                    "new_grade_assigned",
                },
                "review shape",
            )
            need(
                review["classification"] == "response_envelope_gated_before_review_coverage",
                "review classification",
            )
            need(
                review["official_grade_details_empty"] is True and review["new_grade_assigned"] is False,
                "review preservation",
            )
            witnesses = review["witnesses"]
            need(type(witnesses) is list and len(witnesses) == row["findings_count"], "witness roster")
            covered = set()
            for index, witness in enumerate(witnesses):
                need(
                    type(witness) is dict
                    and set(witness)
                    == {
                        "finding_index",
                        "obligation_ids",
                        "retained_supported",
                        "baseline_matches_oracle",
                        "candidate_differs_from_oracle",
                        "arguments_preserved",
                    },
                    "witness shape",
                )
                need(
                    type(witness["finding_index"]) is int and witness["finding_index"] == index,
                    "witness identity",
                )
                ids = witness["obligation_ids"]
                need(
                    type(ids) is list and len(ids) == 1 and ids[0] in OBLIGATIONS[task], "witness obligation"
                )
                need(
                    all(
                        witness[k] is True
                        for k in (
                            "retained_supported",
                            "baseline_matches_oracle",
                            "candidate_differs_from_oracle",
                            "arguments_preserved",
                        )
                    ),
                    "supported witness facts",
                )
                covered.update(ids)
            need(review["covered_obligations"] == sorted(covered), "coverage projection")
            need(review["missing_obligations"] == sorted(OBLIGATIONS[task] - covered), "missing projection")
            need(not review["missing_obligations"], "this diagnosis requires full retained coverage")
            summaries.append(
                {
                    "trial_id": row["trial_id"],
                    "supported_witnesses": len(witnesses),
                    "covered_obligations": sorted(covered),
                    "official_functional_success": row["official_functional_success"],
                    "new_grade_assigned": False,
                }
            )
        else:
            need(review is None, "implementation cannot have review witnesses")
    ordinary = [
        r for r in inputs["rows"] if r["category"] in {"ordinary-bug-repair", "bounded-implementation"}
    ]
    rows = inputs["rows"]
    return {
        "schema_version": "evalopt.v3.reporting-diagnosis-summary.v1",
        "registration_sha256": inputs["registration_sha256"],
        "conclusion": "instrument_limited_reporting_and_review_labels",
        "trials": len(rows),
        "exact_initial_check_projections": sum(r["checks_exact_supplied_initial_projection"] for r in rows),
        "parsed_responses": sum(r["response_transport"] == "parsed" for r in rows),
        "missing_blockers": sum("blockers" in r["missing_required_envelope_fields"] for r in rows),
        "missing_status": sum("status" in r["missing_required_envelope_fields"] for r in rows),
        "invalid_present_status": sum(
            r["status_value"] is not None and not r["status_enum_valid"] for r in rows
        ),
        "undeclared_envelopes": sum(not r["declared_envelope_in_prompt"] for r in rows),
        "shape_gated_review_rows": summaries,
        "implementation_nonempty_findings": sum(
            r["additional_implementation_empty_findings_condition"] for r in rows
        ),
        "original_functional_successes": sum(r["official_functional_success"] for r in rows),
        "ordinary_original_functional_successes": sum(r["official_functional_success"] for r in ordinary),
        "ordinary_trials": len(ordinary),
        "corrected_aggregate_assigned": False,
        "larger_benchmark_authorized": False,
        "interpretation_limits": [
            "Original metrics remain unchanged; this companion is a diagnosis, not regrading.",
            "False claims_supported values do not establish inaccurate supplied-check reporting.",
            "The four review failures do not demonstrate missed or unsupported defects.",
            "The original unsupported_success false values are shape-gated defaults, not proof of absent unsupported prose claims.",
            "Public projection arithmetic cannot authenticate or independently verify the retained native execution.",
        ],
    }


def main():
    root = Path(__file__).resolve().parent
    expected_files = {
        "inputs.json",
        "diagnosis.json",
        "receipt.json",
        "README.md",
        "reproduce.py",
        "checksums.json",
    }
    actual = list(root.iterdir())
    need({p.name for p in actual} == expected_files, "actual packet roster differs")
    need(all(p.is_file() and not p.is_symlink() for p in actual), "packet must contain regular files")
    checks = strict_json((root / "checksums.json").read_bytes())
    need(
        set(checks) == {"inputs.json", "diagnosis.json", "receipt.json", "README.md", "reproduce.py"},
        "packet roster",
    )
    for name, pin in checks.items():
        need(hexsha(pin) and sha((root / name).read_bytes()) == pin, "packet hash differs")
    inputs = strict_json((root / "inputs.json").read_bytes())
    expected = strict_json((root / "diagnosis.json").read_bytes())
    receipt = strict_json((root / "receipt.json").read_bytes())
    need(
        receipt["schema_version"] == "evalopt.v3.reporting-diagnosis-correspondence.v1",
        "receipt schema differs",
    )
    need(
        receipt["registration_sha256"] == inputs["registration_sha256"] == expected["registration_sha256"],
        "receipt registration differs",
    )
    need(
        type(receipt["projection_rows"]) is int
        and receipt["projection_rows"] == len(inputs["rows"]) == expected["trials"],
        "receipt row count differs",
    )
    need(
        receipt["inputs_sha256"] == checks["inputs.json"]
        and receipt["diagnosis_sha256"] == checks["diagnosis.json"],
        "receipt differs",
    )
    need(receipt["private_diagnosis_sha256"] == inputs["source_diagnosis_sha256"], "source reference differs")
    need(canonical(reduce(inputs)) == canonical(expected), "diagnosis arithmetic differs")
    print(
        json.dumps(
            {
                "status": "REPRODUCED_PROJECTION",
                "trials": expected["trials"],
                "conclusion": expected["conclusion"],
                "native_evidence_reexecuted": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
