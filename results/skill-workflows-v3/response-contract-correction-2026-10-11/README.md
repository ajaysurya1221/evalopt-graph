# Prospective correction: declare the complete response envelope

This patch makes the final-response contract explicit before an agent works on a task. It is an **offline prospective correction**, based on commit `f36088d17adcbfdfe24ec2a15d1268fd539daae6`. It does not modify the completed difficulty screen, its frozen harness, prompts, responses, grades or analysis. No corrected live trials were run, and no improvement claim follows from these controls.

The original common prompt described the six controller-check fields and JSON transport limits, but did not declare all required top-level fields. The validators also required `status`, `findings` and `blockers`; completed implementations had to use empty `findings` and `blockers` arrays. A response could therefore copy the supplied initial check correctly while failing an undeclared envelope requirement. Review coverage also depended on that envelope. Those original decisions remain retained in the original report; this patch does not infer what an agent would have returned under corrected instructions.

The correction adds a small shared declaration used by prompt rendering and pure validation:

- Every response includes `status`, `findings`, `blockers` and `checks`.
- `status` is exactly `completed` or `blocked`. Empty arrays are explicit rather than omitted.
- Completed implementations use `findings=[]` and `blockers=[]`. Summaries of fixed bugs belong in optional `summary` or `validation_notes` fields.
- Completed reviews use `blockers=[]`; supported findings follow the visible task's bounded witness contract, and a clean review uses `findings=[]`.
- Blocker-report tasks retain their specified resource, nonempty reason and unavailable-evidence requirements.
- `checks` still quotes only the supplied initial observations, with the same six exact keys and values. Post-stop evidence remains separate.

The existing semantic decisions are preserved in the prospective copy. The controls compare patched and original pure validators across representative valid and malformed synthetic JSON responses, missing required fields, invalid statuses, review findings, clean reviews, refusals and blocker reports. They also verify phase transitions in both directions and that fixed-bug prose cannot silently become review findings. No candidate code, container, model, native history or original trial result is executed or regraded.

## Reproduce in a fresh copy

Use CPython **3.13.12** from a checkout containing the pinned base commit. From the repository root, run:

```sh
python3.13 -I -B results/skill-workflows-v3/response-contract-correction-2026-10-11/apply_verify.py --repo "$(pwd -P)" --output-dir "$(pwd -P)/response-contract-offline-check"
python3.13 -I -B results/skill-workflows-v3/response-contract-correction-2026-10-11/test_apply_verify.py "$(pwd -P)"
```

Choose a new output directory name if the example already exists. The helper rejects existing destinations and any destination overlapping the original source or patch bundle. It reads the exact base Git objects, validates every declared source and payload hash, verifies the readable patch matches the payload, copies the original package, applies changes only to the fresh copy, and runs the data-only controls there. The original working sources must have identical before/after hashes. `receipt.json` and the control logs remain in the fresh output.

`response-contract.patch` is the human-readable patch. `manifest.json` binds the complete original package and every changed payload. `payload/` contains the proposed replacement files and the new test. `prepare_bundle.py` only regenerates these patch artifacts from the same pinned Git objects; running it is unnecessary for reproduction.

`controls.json` records the offline checks on the published bytes. A separate review receipt records the scope of independent AI review. These receipts establish finite source correspondence and control results, not producer authentication, independent human authorship, model efficacy or empirical hardness. Any future live evaluation must freeze its own corrected conditions and registration; this artifact authorizes no additional trials.
