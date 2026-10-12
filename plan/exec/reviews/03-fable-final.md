REVIEW 03 — Reviewer Fable xhigh | Verdict ACCEPT

Target: lane `winddown/20261013/03` at exact immutable HEAD `9d306137ab78b473ff3419c4375735819a803cce` in `wt-semantics-03` (committed 2026-10-13T01:58:39+05:30, which is 2026-10-12T20:28:39Z). Revision diff `2d5c307..HEAD`: three files under `docs/decisions/`, 10 insertions, 10 deletions; `winddown-positioning.md` byte-identical to `2d5c307`. Full task diff `0a7d374..HEAD`: exactly the four owned ADRs, all `A`, nothing else. Fresh read-only session; prior reviews `03-fable.md` and `03-codex.md` were read for the list of required corrections, and every correction was then verified against source, Git history, the plan and the central preflight records, not against REPORT 03-R1.

## Required corrections, verified

1. **Inherited-source inventory (Codex P2 / Fable Medium), `archive-standalone.md:34` — correct.** `git rev-list --count v0.1.0..fc3045d` = 10; `git log v0.1.0..fc3045d -- src/` lists exactly `624ed11` and `fc37732`; `git diff --stat v0.1.0 fc3045d -- src` shows exactly `epistemic.py`, `kernel.py`, `permissions.py`, `project_detect.py`. `git show fc37732 -- src/` confirms: `project_detect.py` adds `_python_command()` (`sys.executable`, `shlex.quote`, Windows branch) and replaces the bare `python -m pytest -q`; `permissions.py` changes its module docstring and three `assess_readiness` warnings to point at `examples/claude-code-overnight/` and call the skill external; `epistemic.py` changes one docstring sentence only. `624ed11` changes `kernel.py` (`rows()` now raises `ValueError` on str/bytes containers or rows and non-iterables instead of silently tuple-splitting) and `tests/test_kernel.py`; "fail closed" is a fair description. `grep -i scalar CHANGELOG.md` is empty, so "no CHANGELOG entry yet" holds. CHANGELOG "Unreleased" discloses the `sys.executable` gate change (Changed) and the helper move (Removed). The other eight commits are three docs, three dependency (hatchling 1.31.0→1.32.4, anyio, optional floors), two CI; `dependencies = []` unchanged at `pyproject.toml:31`. Tag `v0.1.0` is annotated 2026-07-20 (18:10:17+05:30) targeting `42a6523`.
2. **Identity/authentication wording (Codex P2 / Fable Low), `archive-standalone.md:32` — correct.** `attestation.py:75-84` defines `claim_digest` with label `evalopt.claim-identity.v1`; `attestation.py:88-107` defines `AdapterPolicy` with identity fields `adapter_id`, `adapter_version`, `retrieval_mechanism`, `parser_identity` and rejects empty ones; `kernel.py:306-331` keys `EvidenceAuthority` policies by `adapter_id`. `SECURITY.md:42-44` says the kernel is not a signature system and hosts authenticate observations. The ADR now says the kernel carries declared identifiers but has no signing, key management, signature verification or cryptographic producer-authentication concept, and a supplied identifier is not an authenticated producer identity. Accurate and no longer overbroad.
3. **VSA version clarification (Codex P2), `archive-standalone.md:25`, `migration-interface.md:12`, `routing-boundary.md:19` — matches primary-source evidence.** Central `reports/04-primary-sources-preflight.md` (access date 2026-10-12 UTC, tool clock 20:22:56Z) records the cited v1.0 VSA observed Retired, v1.1 observed Retired, v1.2 observed Approved and current, "status context only", "does not change approved routes". The ADRs state exactly that: cited v1.0 is retired prior art and never a destination; v1.2 Approved is source-status context only; no route added; STOP not reopened. PLAN line 79 cites the same v1.0 URL as Retired prior art. The seven routes, their order and destinations are unchanged from `2d5c307`. `winddown-positioning.md` contains no VSA statement and needed none.
4. **Release authority (Fable Low, optional), `archive-standalone.md:15` — correct.** "included one final `v0.1.1` deprecation release under the maintainer's explicit release authorization and memo S4" matches PLAN line 49, the Release authority section (lines 83-87) and the decision table at line 492; memo line 155 is S4 "Cut v0.1.1 deprecation release". Astra is no longer described as granting authority.
5. **Scoped metadata permission (Codex P2, second part), `archive-standalone.md:39` — correct and bounded.** "nothing under `src/` except the `__version__` literal" preserves the frozen-kernel rule. The allowed list outside `src/` (package version metadata, the package's own `uv.lock` entry, workflow and verifier expected-version values, release notes) matches PLAN line 342 (Task 08 files) and the `08-release-preflight.md` change table. Release notes are told to enumerate inherited differences from Git, not from the ADR prose, and never to claim byte- or behaviour-identical to `v0.1.0`; this matches the preflight's "Inherited differences" section.

## Contract checks

- No publication or archival claim: `archive-standalone.md:39-40` ("later gated step; this record does not claim it happened"; archival "future, human-owned"), `winddown-positioning.md:13,17` (both prospective). No adoption, demand or superiority claim; routing keeps "no statement about user demand appears unless proven".
- Human release authority preserved; no authority shifted to a model lane. STOP, no new integration/converter/predicate/schema/dependency, four-project independence and ARCI attribution-as-adaptation all unchanged from the previously verified head.
- Owned scope unchanged: `git diff --name-status 0a7d374..HEAD` = four `A` lines under `docs/decisions/`, matching the Task 03 implementation spec's "Create only" list. No proposal, PLAN, task spec, source, test, bench or other tracked file touched.
- Dates: "revised 2026-10-12 UTC" agrees with the commit time in UTC.
- Memo digest reproduces: `e307514fc800c2ff37c8d1a6d9a454bbf4d4addf53acd38611cbbc50b5695e81`.
- All 23 relative link targets across the four ADRs exist at HEAD (including the three new module links and two new `archive-standalone.md` back-links). No `/Users`, `citeturn` or `fileciteturn` markers. All four files end with a newline.

## Findings by severity

No blocking or correctness findings.

**Info 1 — traceability of the VSA status sentence.** `archive-standalone.md:25` attributes the dated page check to "the run's control lane" and links the two live URLs, but does not name the central preflight record that holds the immutable snapshot revisions. The statuses match that record exactly, so nothing is inaccurate. Task 04's appendix is the right place to cite the preflight's immutable revisions (v1.0 `7d5078a…`, v1.1 `3e02e58…`, v1.2 `ae7fc76…`) with the access date; no ADR change needed.

**Info 2 — length.** The four ADRs total 2508 words (per file: 922 527 519 540) against the spec's "about 2,000" guidance. The growth since `2d5c307` is the disclosure text both prior reviews required; a cut would reintroduce the omission. No change requested.

## Required changes

None.

## Follow-ups (outside this diff)

- Task 05: add a CHANGELOG entry for `624ed11` ("Reject scalar acceptance input rows"); it is still absent.
- Task 08: enumerate inherited `src/`, packaging, optional-dependency-floor and sdist-include changes from `git diff v0.1.0 fc3045d` and CHANGELOG, as the ADR directs; scope any "no dependency changes" statement to the wind-down diff.
- Task 04: cite the primary-source preflight's immutable revisions for the VSA dated check (Info 1).
- Root: the ADRs link to `plan/exec/decisions/` and `plan/exec/reports/03-tiebreak.md`; those resolve publicly only once on main.

## Commands and results

```
git rev-parse HEAD                                   -> 9d306137ab78b473ff3419c4375735819a803cce
git status --porcelain                               -> clean (0 lines)
git log --oneline 0a7d374..HEAD                      -> 9d30613, 2d5c307
git diff --stat 2d5c307..HEAD                        -> 3 files, 10 insertions(+), 10 deletions(-)
git diff --name-status 0a7d374..HEAD                 -> 4 x A under docs/decisions/
git diff --quiet 2d5c307 HEAD -- docs/decisions/winddown-positioning.md -> identical
git diff --check 0a7d374..HEAD                       -> exit 0, no output
python3 -B plan/exec/preservation.py                 -> {"baseline": "fc3045d…", "protected_files": 75, "errors": []}, exit 0
grep -n -E '/Users|fileciteturn|citeturn' docs/decisions/*.md -> no matches
relative-link loop (git cat-file -e at HEAD)         -> 23/23 OK
git rev-list --count v0.1.0..fc3045d                 -> 10
git log v0.1.0..fc3045d -- src/                      -> 624ed11, fc37732
git diff --stat v0.1.0 fc3045d -- src                -> 4 files (epistemic, kernel, permissions, project_detect)
git show fc37732 -- src/                             -> as described in finding 1
git show 624ed11 --stat                              -> kernel.py, tests/test_kernel.py
git diff v0.1.0 fc3045d -- pyproject.toml            -> hatchling pin, description, optional floors, metadata 2.4 pin, sdist include; dependencies = [] unchanged
git for-each-ref refs/tags/v0.1.0                    -> annotated 2026-07-20T18:10:17+05:30 -> 42a6523
git rev-parse origin/main; main                      -> fc3045dbda29c1d274747329ceb6724a783b0df7 (both)
grep -i scalar CHANGELOG.md                          -> no match
sed -n 70,110p attestation.py; 288,335p kernel.py; 38,48p SECURITY.md -> identity fields, validate/replay, security boundary as cited
shasum -a 256 .../deep-research-2.md                 -> e307514f…5695e81; grep '\bS4\b' -> line 155 "Cut v0.1.1 deprecation release"
sed PLAN.md 45-52, 76-82, 83-87, 228-236, 342, 488-496 -> release authority, VSA Retired v1.0, Task 04 criteria, Task 08 files, decision table
grep -n -i 'slsa|vsa|retired|approved' reports/04-primary-sources-preflight.md -> v1.0 Retired, v1.1 Retired, v1.2 Approved, status context only
awk sections of reports/08-release-preflight.md      -> change table and inherited-differences list match ADR line 39
cat -n docs/decisions/*.md                           -> full text read at HEAD
wc -w docs/decisions/*.md                            -> 2508 total
```

## Limits

Read-only. No file in `wt-semantics-03` was modified, staged or committed; the tree is clean at `9d30613`. Only this review record was written in `wt-control-00`, left unstaged. No model, subagent or network call; no credential or `.env` read; the SLSA pages were not fetched here, so their status is taken from the central preflight record as the brief directs. Memo access limited to the digest and one `S4` grep. Requested model `claude-fable-5-1`, requested effort xhigh; effective effort not observable in-session. 16 assistant turns of 20, single session, about 12 minutes wall clock.
