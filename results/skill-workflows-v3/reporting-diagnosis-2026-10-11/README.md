# Reporting diagnosis: instrument-limited screen labels

All 16 responses accurately copied their supplied initial checks, but all 16 failed the frozen grader's undeclared top-level response-envelope requirement. The four recorded review functional failures were also stopped by this envelope check. Their retained witnesses cover every registered defect obligation and demonstrate supported violations; the failures do not establish missed defects.

This companion preserves the original screen and adds a separate diagnosis. It assigns no corrected scores. The ordinary repair/implementation tasks achieved their original functional outcome in **8/8 trials**. Neither this screen nor the diagnosis authorizes a larger benchmark or supports an upgrade claim.

| Retained observation | Count |
|---|---:|
| Parsed responses with exact supplied initial-check fields | 16/16 |
| Responses missing `blockers` | 16/16 |
| Responses missing `status` | 14/16 |
| Present `status` outside the required enum | 1/16 |
| Review rows stopped before witness coverage was evaluated | 4/4 |
| Supported retained review witnesses | 18/18 |
| Review rows with complete obligation coverage | 4/4 |

The common prompt specified JSON transport bounds, findings limits and the exact six check fields. It did not declare `status: completed|blocked` and `blockers: []`, though the frozen validator required them. All 16 supplied initial observations, including the stale-check task's initial facts, were reported exactly. The `claims_supported=false` labels therefore cannot be interpreted as inaccurate supplied-check reporting. Likewise, `unsupported_success=false` is a shape-gated default in these rows, not an established absence of unsupported prose claims.

The two replica-placement review responses each contain three supported witnesses covering three obligations. The two media-range review responses each contain six supported witnesses covering two obligations; duplicate supported findings are neutral. The retained baseline values match their frozen expected values and the retained candidate values violate them. No candidate or verifier was rerun for this diagnosis.

Two implementation responses also used `findings` for descriptions of repaired bugs. The grader requires that array to be empty for completed implementation tasks, but this requirement was not stated in the response instructions. A future repair must declare the complete envelope and contract-specific conditions from a shared definition, then prove every validator-required field, enum, type and empty-array condition is visible. It must be tested prospectively; this companion does not apply that repair or infer new live outcomes.

`inputs.json` contains only bounded typed projections. `diagnosis.json` is generated from those projections. `receipt.json` binds the separately retained private diagnosis and original report by hash, and states the custody limits. Native identifiers, artifact filenames, host paths, requests, values and response prose are omitted. The private diagnosis's source pins are retained separately for controller-custody review.

Run in a fresh directory containing these files:

```sh
python3 -I -B reproduce.py
```

The standard-library replayer validates the complete 16-row roster, field allowlists, phase-reporting facts and supported witness coverage, then reproduces the diagnosis arithmetic. It does not import the harness, execute candidate code, authenticate a producer or independently reproduce the live trials. The original report remains the authoritative record of the frozen instrument's outputs; the companion explains why some labels are unsuitable for the intended semantic interpretation.
