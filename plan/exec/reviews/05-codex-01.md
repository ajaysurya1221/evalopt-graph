REVIEW 05 — Reviewer Astra | Verdict REVISE

Reviewed exact head `7742bae5f90c371cc6f21c8309492099983f5586` in `wt-notice-05`, against base `cb5f3ceae4e149843dc37c0390668faaa3dc91b6`. Read all eight changed files and compared the notice, route table, portfolio descriptions, security/intake rules and inherited-change wording with the accepted ADRs, migration map/source appendix and relevant retained source/history. This review was independent of root's observations.

## Findings by severity

### P2 — Limit the independence claim to the four sibling projects

`README.md:48–49` says all listed “destinations are independent of evalopt and of each other.” That extends the accepted portfolio-independence statement to OPA, in-toto, Witness and GitHub. The accepted map deliberately says **the four sibling projects** (`docs/migration.md:30–33`); Witness's documented signed-policy and Rego/attestation use is not evidence that every named destination is independent of every other destination. This unnecessary global assertion is unsupported by the scoped four-repository audit.

Required change: make the subject explicitly “the four sibling projects,” preserving the map's bounded claim. State the separate migration limit as no automatic/lossless transfer of evalopt's decision states, reason codes and record semantics, rather than coupling it to an all-destinations independence assertion.

### P2 — Do not turn an architectural example into demonstrated integration history

`README.md:203–205` now asserts that “a host adapted observations from Codex, Claude Code, OpenHands, LangGraph, CI or its own runtime ... then stored the returned decision.” The base text described what a host could do; changing those verbs to past tense introduces an executed-history claim without a cited run or implementation. The preserved release notes still describe runtime independence conditionally, and the retained source says the former LangGraph subset was removed without behavioral parity (`src/evalopt_graph/graph.py:4`). The optional Harbor conformance example has its own finite evidence below and must not imply the whole runtime list was exercised.

Required change: describe the historical **design** or conditional host contract, such as “The kernel was designed to accept host-supplied observations through AcceptanceInput; the host remains responsible for adapting observations and storing the decision with its policy and input.” Keep the STOP routing notice and the bounded Harbor evidence unchanged. Do not add a run/adoption claim.

## Verification and accepted scope

- Target HEAD matched the assigned SHA; working tree remained clean after checks. Exactly the eight Task 05 owned files changed, with no source, tests, figures, frozen benchmark/result or configuration changes outside issue guidance.
- `git diff --check cb5f3ce..7742bae`: passed.
- `PYTHONDONTWRITEBYTECODE=1 /Users/ajay/Developer/.evalopt-worktrees/wt-control-00/plan/artifacts/tooling/bin/uv run --frozen --extra dev python -B -m pytest -p no:cacheprovider tests/test_figures.py -q`: **3 passed**. This executes the README example and checks generated figure/output consistency.
- `python3 -B plan/exec/preservation.py`: **75 protected files**, **zero errors**, baseline `fc3045dbda29c1d274747329ceb6724a783b0df7`.
- Independently compared the README Python example, displayed text-output blocks and complete picture blocks to the base: byte-identical.
- Parsed all three issue YAML files with the available system PyYAML; checked unique field IDs, allowed form element types and contact-link structure: passed. This is local structural checking, not hosted GitHub form validation.
- Checked 49 relative or this-repository main-blob Markdown link targets in the eight files: all target files exist locally. Network reachability and hosted anchors were not retested here.
- The scalar-row CHANGELOG entry matches the inherited validator change and source commit; the commit author and PR #4 attribution support the contributor credit. Dorian's local `v1.4.1` tag resolves to the cited `eeb1937` commit. Portfolio semantics and ARCI attribution correspond to the accepted source appendix and earlier reviewed independence audit.
- Private security reporting remains available; the supported patch line and best-effort response targets are retained with bounded maintenance wording. Issue guidance does not claim existing issues/PRs were closed. Release and archival statuses remain prospective. No new capability, destination, benchmark programme or runtime dependency was introduced.

## Required changes

Fix the two README wording findings above, retain the exact scope/preservation boundaries, rerun the short figure check and submit the resulting immutable head for targeted review. No product-code or test change is required.

## Follow-ups and limits

Root's integrated desktop/phone rendering check remains pending and is not represented as passed. Exact candidate package/CI/release qualification is a later task. This review did not call a model, alter source, access credentials, mutate the network or change any sibling repository. Only this assigned central review file was written.
