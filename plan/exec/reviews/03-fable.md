REVIEW 03 — Reviewer Fable xhigh | Verdict REVISE

Target: `winddown/20261013/03` at exact HEAD `2d5c307830185c7f31d8d7810a1a5304dc88cf4f` in `wt-semantics-03`; diff `0a7d374..HEAD`, four new files under `docs/decisions/` (144 insertions, nothing else touched). Fresh read-only session; the implementer REPORT and the Codex review were not used as evidence.

## Findings by severity

**Medium — `docs/decisions/archive-standalone.md:34`: inherited-change inventory is wrong.** The line says one commit (`624ed11`) changes `kernel.py` and "the rest are documentation, build, CI and dependency changes". Git history disagrees: `fc37732` ("build/docs: keep twine green on new hatchling, plain-words README, move personal tooling out of the package (#20)") also changes three runtime modules under `src/` (`epistemic.py`, `permissions.py`, `project_detect.py`): the detected Python test gate now runs `sys.executable -m pytest -q` instead of bare `python`, and the overnight-hook guidance strings change. Both are already disclosed under CHANGELOG "Unreleased", so the omission is in the ADR, not the public changelog. Because Task 08 will write release notes from this "facts checked" list, the under-count weakens the current-main versus old-release distinction the ADR exists to preserve. Verified with `git show --stat fc37732 -- src/` and `git log -S'sys.executable' v0.1.0..fc3045d -- src/`.

**Low — `docs/decisions/archive-standalone.md:32`: "no signing, key or identity concept" is overbroad.** `attestation.py` defines `claim_digest` with the label `evalopt.claim-identity.v1` (line 78) and `AdapterPolicy` "identity fields" (`adapter_id`, `adapter_version`, `retrieval_mechanism`, `parser_identity`, lines 100-107). These are content digests and policy-declared strings, not keys or producer authentication, so the intended claim is true only when narrowed. SECURITY.md:44 says "not a … signature system", which is the supportable statement.

**Low — `docs/decisions/archive-standalone.md:15`: release authorization misattributed.** "Astra … authorized one final `v0.1.1` deprecation release" reads as Astra granting authority. PLAN B "Release authority" and PLAN I attribute it to the maintainer's explicit release authorization and memo S4; Astra included the release under that authorization. Wording only.

**Info (no change needed).**
- "Recorded 2026-10-12": commit `2d5c307` is 2026-10-13 01:48 +0530, which is 2026-10-12 20:18Z. Consistent in UTC, the run's timebase.
- External URLs (in-toto attestation, Witness, SLSA VSA, OPA) were not fetched in this review. They match the memo's own citations and the plan's SLSA link.
- Four remote `feat/*` branches are not ancestors of `fc3045d`, consistent with "benchmark branches are not merged into main". PRs 33–36 were not checked (no network).

## Verified correct

- Whitespace: `git diff --check 0a7d374..HEAD` exit 0; all four files end with a newline; no tabs or CRLF.
- Ownership: only `docs/decisions/*.md` changed, a new directory at baseline; matches Task 03 files. `python3 -B plan/exec/preservation.py` reports 75 protected files, errors `[]`.
- Links: all 19 relative links resolve at HEAD (three sibling ADRs, kernel sources, SECURITY.md, architecture.md, CHANGELOG.md, six proposals, tie-break).
- Format: each ADR has Decision | Positions (Astra, Fable) | Rule that decided | Consequences. No `citeturn`/`fileciteturn` markers copied into public prose.
- STOP preserved: no new integration, converter, predicate, schema or shared dependency; four projects independent; ARCI attribution as adaptation; archival "human-owned, not claimed"; publication "later gated step, not claimed".
- Memo handling: SHA-256 of `/Users/ajay/Developer/research/deep-research-2.md` is `e307514f…5695e81`, matching line 9. Memo findings on lines 25–28 are attributed ("accepted as the maintainer's decision and not re-verified here") and correspond to memo text: overlap and 80%-overlap hard gate, no dated public demand, portfolio naming/attention cost, prompt-supplied star/fork/commit figures and unverified downloads. Reopening conditions on line 43 reproduce all four memo conditions plus "not an architectural argument".
- Kernel facts: ten names in `__all__`; `dependencies = []`; `_hash_record` is SHA-256 over canonical JSON (`attestation.py:44-51`) and is what `kernel.py` imports; `validate()` checks schema, status and digest (`kernel.py:292-298`); `replay()` is equality with fresh `evaluate_acceptance` (`kernel.py:301-302`); five states match `_DECISIONS`.
- History facts: `origin/main` = `fc3045d`; ten commits after `v0.1.0` (tag dated 2026-07-20); `624ed11` changes `kernel.py` and `tests/test_kernel.py` and "scalar" does not appear in CHANGELOG.
- Canonical notice in `winddown-positioning.md:9` is byte-identical to PLAN B. Task 05 file list, three issue templates, `0.1.x` patch policy (SECURITY.md:11-14), private advisory channel, "for one migration cycle" at README.md:183 and docs/architecture.md:106 all confirmed.
- Seven routes in `routing-boundary.md` match the brief's order and the plan's destinations; Tasks 07A–07D exist in PLAN D.
- Positions are faithful to the proposals: Fable I-3/I-4/template/greppable labels, N-2/N-9/N-11, R-2/R-4/R-10 and the README-quote-at-commit form (boundary proposal line 73) are summarised accurately; Astra proposals at `aa28b4c` are byte-identical to the lane copy `068a2fc`; Fable proposals unchanged since `0663549`. Tie-break dispositions and retained items (roster closure, one primary label, appendix columns including title, dated VSA check, CHANGELOG-referenced disclosure, vocabulary ban rejected) are carried into the ADRs.

## Required changes

1. `docs/decisions/archive-standalone.md:34`: replace the inventory with one that names both source-touching commits. Suggested text: "Main holds ten commits after the `v0.1.0` tag (2026-07-20). Two touch `src/`: "Reject scalar acceptance input rows" (`624ed11`) changes `kernel.py` and tests and has no CHANGELOG entry yet; `fc37732` changes three non-kernel modules (`epistemic.py`, `permissions.py`, `project_detect.py`), so the detected Python test gate runs under `sys.executable` and hook guidance wording changes, both disclosed under CHANGELOG "Unreleased". The other eight are documentation, build, CI and dependency changes."
2. `docs/decisions/archive-standalone.md:32`: change "no signing, key or identity concept" to "no signing, key or producer-authentication concept".

Optional in the same round: `archive-standalone.md:15`, "accepted STOP as preapproved and included one final `v0.1.1` deprecation release under the maintainer's explicit release authorization and memo S4".

The other three ADRs (`migration-interface.md`, `routing-boundary.md`, `winddown-positioning.md`) need no change.

## Follow-ups

- Task 08 release notes should enumerate inherited `src/` changes from Git, not from this ADR's prose, and cite CHANGELOG "Unreleased".
- Task 04 should confirm that a `file:line` reference exists for the six topic rows (for example `SECURITY.md` or `docs/architecture.md` for host authentication), since `migration-interface.md:11` requires one per row.

## Tested commands and results

```
git rev-parse HEAD                              -> 2d5c307830185c7f31d8d7810a1a5304dc88cf4f
git status --porcelain                          -> clean
git diff --check 0a7d374..HEAD                  -> exit 0, no output
git diff --stat 0a7d374..HEAD                   -> 4 files, 144 insertions
python3 -B plan/exec/preservation.py            -> {"protected_files": 75, "errors": []}
shasum -a 256 .../deep-research-2.md            -> e307514f...5695e81 (matches)
git rev-list --count v0.1.0..fc3045d            -> 10
git show --stat 624ed11                         -> kernel.py, tests/test_kernel.py
git show --stat fc37732 -- src/                 -> epistemic.py, permissions.py, project_detect.py
git log -S'sys.executable' v0.1.0..fc3045d -- src/ -> fc37732 (and fc3045d, docs only)
git diff --stat aa28b4c 068a2fc -- plan/exec/decisions/ -> only Fable files differ (Astra copies identical)
git diff --stat 0663549 HEAD -- plan/exec/decisions/03-fable-*.md -> empty
link resolution loop (git cat-file -e at HEAD)  -> 19/19 OK
diff of PLAN B notice vs winddown-positioning.md:9 -> IDENTICAL
grep -rn 'citeturn|fileciteturn' docs/decisions -> none
```

## Scope limits

Read-only; no file in `wt-semantics-03` was modified, staged or committed, and only this review file was written in `wt-control-00` (left unstaged). No model or subagent calls, no network, no secret or `.env` reads. External URLs and GitHub PR state were not fetched. Memo read limited to verdict, kill-criteria, reopening, assumptions and citation lines. Requested model `claude-fable-5-1`, requested effort xhigh; effective effort not observable in-session.
