# Accept the STOP wind-down plan: preserve the kernel, publish migration guidance, prepare the final release

## A. Memo digest

**Memo:** `/Users/ajay/Developer/research/deep-research-2.md`. It is beside the repository, not inside it. Its SHA-256 is `e307514fc800c2ff37c8d1a6d9a454bbf4d4addf53acd38611cbbc50b5695e81`.

**Verdict: STOP, high confidence.** End evalopt’s standalone feature development, preserve its implementation and research record, direct users toward established policy and attestation tools, and keep the four other projects independent. Do not create another integration, predicate, policy language, benchmark programme or shared runtime dependency. The memo includes a final **v0.1.1 deprecation release with no new capability**. Repository archival remains your action.

### The memo’s sprint, unchanged

| ID | Memo task | Estimate | Execution disposition |
|---|---|---:|---|
| S1 | Record the STOP ADR | 2h | Execute |
| S2 | Publish use-instead matrix | 3h | Execute |
| S3 | Write schema migration map | 4h | Execute as documentation |
| S4 | Cut v0.1.1 deprecation release | 4h | Execute only after review and release gates |
| S5 | Freeze deprecated surfaces | 2h | Document; retain implementation |
| S6 | Remove portfolio dependency temptation | 2h | Audit; no unnecessary dependency edits |
| S7 | Standardise external wording | 3h | Four narrowly scoped README PRs |
| S8 | Preserve final reproducibility receipt | 2h | Retain actual artifact and verification evidence |
| S9 | Close migration surfaces | 1.5h | Update contribution and issue guidance |
| S10 | Archive GitHub repository | 1h | **HUMAN_INBOX only** |
| S11 | Publish portfolio index | 2h | One index in this repository |

The memo estimates **26.5 working hours**. This run has a **10-hour wall-clock cap**, using parallel lanes. Any unfinished item receives an explicit status rather than an implied completion.

### Metrics and kill criteria

| Metric | Memo target | Measurement in this run |
|---|---|---|
| Final release | v0.1.1 by 19 October 2026 | Actual GitHub/PyPI publication, or exact blocked stage |
| Portfolio runtime coupling | 0 of 4 repositories | Manifest, lockfile and runtime-import audit |
| Migration documentation | 100% of major capabilities covered | Fixed coverage roster; mapping or explicit non-equivalence |
| Archival | Enabled by 21 October 2026 | Human action pending; never claim archived prematurely |
| Migration blockers | 0 known by 11 November 2026 | Enumerated known blockers; no claim about undiscovered users |
| New features | 0 through 10 January 2027 | Zero feature changes during this run; future period unmeasured |
| Reopening | Three independent teams, one production integration commitment, demonstrated standards gap | Document as future prerequisites; do not pursue during closure |

The memo’s overlap, demand and portfolio-cost kill criteria are already triggered. Reopening requires all its stated conditions, including clearing the 80%-overlap gate.

The 30-day plan is **closure and migration validation**, not evalopt adoption. Standards-community messages will be drafts for clarification only; there is no integration partner or marketing campaign to recruit.

**Your portfolio decisions remain yours:** archive evalopt after closure; retain Actseal, Dorian, Frontier Scout and ARCI independently; rename nothing. This run implements supporting documentation and PRs, not repository archival or other portfolio restructuring.

## B. Verdict handling

### STOP means no new product development

Deliver a deprecation PR, migration documentation, the final report and—because S4 explicitly requests it—the final release with no added capability. Fable’s read-only planning consultation supported this interpretation of the STOP instruction and explicit release authorization.

The public notice will say:

> Standalone feature development has ended. This repository preserves the acceptance kernel and its research record. For new systems, use the alternatives listed below. Existing evidence remains subject to its original versions and limitations. Evalopt evaluates supplied evidence against policy; it is not a semantic truth oracle.

It will not say the repository is archived until you actually archive it.

### Starting point and preservation

Start from verified public main:

`fc3045dbda29c1d274747329ceb6724a783b0df7`

Do not merge the benchmark branch chain into main. Preserve PRs 33–36, all v1–v4 results, frozen sources, campaign records, existing tags and published assets. Link research through immutable public commit URLs where useful.

“Unchanged kernel” means unchanged from this verified main. Main already contains fixes beyond the v0.1.0 tag; release notes must disclose those inherited changes rather than claiming byte-identical behavior to the old release.

### Migration guidance must remain accurate

The alternatives matrix will route:

| User’s job | Destination |
|---|---|
| General policy evaluation | OPA |
| Software provenance and attestation verification | in-toto and Witness |
| Native merge enforcement | GitHub rulesets and required checks |
| Action-policy qualification / code-claim warrants | Actseal / Dorian |
| PR scope / stochastic regression | Frontier Scout / ARCI |

SLSA VSA will appear as **historical verification-summary prior art**, not an unqualified current recommendation: its cited specification is now marked **Retired**. This corrects migration wording without reopening the memo’s verdict. [SLSA VSA specification](https://slsa.dev/spec/v1.0/verification_summary)

No mapping will claim that a content hash authenticates a producer, that an in-toto envelope proves semantic correctness, or that another tool preserves evalopt’s five states automatically.

### Release authority

Tagging and publishing v0.1.1 are authorized, subject to successful checks and reviews. GitHub currently requires approval for the `pypi` environment.

After artifact review, Astra may use the **existing native approval endpoint** only if GitHub reports that the authenticated account can approve this exact deployment. This uses your release authorization; it does not remove or bypass a protection. If GitHub denies approval or requires an unavailable interactive action, record the exact action in HUMAN_INBOX and continue closure without waiting. [GitHub deployment-review API](https://docs.github.com/en/rest/actions/workflow-runs#review-pending-deployments-for-a-workflow-run)

## C. Lanes and contracts

### Five lanes

| Lane | Owner | File ownership |
|---|---|---|
| Control | Astra | `plan/exec/`, task specifications, status, reviews, integration and final reports |
| Semantics | Fable xhigh | STOP ADR, migration map, standards-source notes and semantic coverage |
| Notice | Fable high | README, contribution/security wording, issue guidance, portfolio index |
| Portfolio | Fable high | README-only changes in the four other repositories, one task/worktree each |
| Release and verification | Astra; Fable cross-review | Version metadata, existing CI/release plumbing, artifact qualification and publication |

Every task gets a distinct branch and worktree named `winddown/<run-id>/<id>` and `wt-<lane>-<id>`. Worktrees come from accepted integration points. There will be at most **two concurrent Fable task processes**, leaving capacity for verification and reviews.

`/plan/...` means **repository-relative `plan/...`**, not a new operating-system-root directory. `PLAN_ROOT` points to the control worktree’s `plan` directory. Raw logs remain ignored; sanitized reports are committed. No root workspace repository is created.

### Frozen contracts

1. **Kernel:** preserve all ten exports, kernel bytes, serialization, reason codes, replay, fail-closed behavior and zero runtime dependencies. Only the package’s `__version__` literal may change under `src/`.
2. **Research:** preserve all existing studies and evidence. No new trials, regrading, benchmark claims or global skill installation.
3. **Migration:** documentation only. No converter, adapter, schema extension, new predicate or claim of lossless standards equivalence.
4. **Portfolio:** no new evalopt dependency. Preserve attribution, including ARCI’s adapted hashing provenance. Preserve every entry in its current frozen manifest—48 entries were found.
5. **Publication:** retain protection rules, required checks, action pins, old assets and history. No administrative bypass, branch deletion, tag replacement or force-push.

The migration coverage roster is the ten stable exports plus six cross-cutting topics: terminal states/reasons, serialization/hash binding, replay, host authentication/signatures, freshness/record authority, and deprecated host surfaces. All **16 entries** must map honestly or be explicitly marked project-specific/unmapped.

### Review and integration protocol

Each merged diff needs two accepted review records: an independent Codex review and a fresh Fable REVIEW session. The implementer’s REPORT is not a review.

For Astra-authored changes, a Codex verification subagent and Fable review independently. For Fable-authored changes, Astra inspects the diff and reruns applicable checks; a fresh Fable session performs the second review.

Allow three revision rounds. Unresolved differences use your ordered tie-break and receive an ADR. An unresolved failed gate prevents merge regardless of an opinion.

Integrate in this order:

1. Bootstrap and operational controls.
2. STOP ADR, migration map and notice.
3. Release metadata and qualified deprecation PR.
4. Reviewed release and evidence receipt.
5. Final reports; portfolio README PRs proceed independently after wording is accepted.

Use squash PR merges, matching the repository’s ruleset. Never use `--admin` or automatic branch deletion.

### Continuous verification

The verification lane reruns relevant checks after accepted changes and the complete suite on the final candidate. The existing evalopt commands are:

```bash
uv lock --check
uv sync --frozen --extra dev
uv run --frozen --extra dev python scripts/verify_workflow_pins.py
uv run --frozen --extra dev python scripts/verify_test_count.py --minimum 408
uv run --frozen --extra dev python -m compileall -q src tests scripts
uv run --frozen --extra dev ruff check src tests scripts
uv run --frozen --extra dev ruff format --check src tests scripts
uv run --frozen --extra dev python -m pytest -p no:cacheprovider
uv run --frozen --extra dev python scripts/edit_demo.py
uv run --frozen --extra dev python scripts/epistemic_demo.py
uv run --frozen --extra dev python scripts/unattended_demo.py
uv run --frozen --extra dev python scripts/provenance_benchmark.py \
  --out "$RUN_ARTIFACTS/conformance.json"
bash scripts/smoke_test.sh
```

Use isolated tooling matching the repository’s pinned uv version. Do not modify global tooling or refresh dependency versions.

Evalopt has **no configured type-checking gate**. Report that as not applicable; do not invent a typing migration. Run the existing typing gates in portfolio repositories that have them.

## D. Copy-ready task specifications

All paths below are relative to the task’s repository unless prefixed by `PLAN_ROOT`. Every task inherits Sections B–C and the exact REPORT/REVIEW formats below. Each executor may write its own central REPORT as an explicit ownership exception.

### Bootstrap and contracts

**TASK 00: Persist the approved plan — Control | Owner: Astra**

- **Goal:** Start the clock and preserve the accepted instructions before execution.
- **Context:** This complete plan; the memo path and digest in A.
- **Interface contract:** PLAN.md is immutable after its initial commit; changes become dated decisions and ADRs.
- **Files:** Create `plan/exec/PLAN.md`, `tasks/<id>.md`, `DECISIONS.md`, `CONTRACT.md`, `STATUS.md`; add narrow ignores for raw logs and scratch artifacts. Touch no product files.
- **Acceptance criteria:** One initial commit contains the plan verbatim, every task specification and initial decisions. CONTRACT includes ownership, reporting, reviews, scope and time limits.
- **Tests to add:** None.
- **Constraints:** Commit on the new control branch, not main. No executor launch before this commit.
- **Done when:** `git diff --check`; `git show --stat HEAD`; verify the saved PLAN.md equals the accepted message and every listed task has a file.
- **Estimate:** 15 minutes.
- **Depends on:** Plan acceptance.
- **Reuses:** Existing public main and workspace contracts.
- **Write REPORT to:** `/plan/exec/reports/00.md`.

**TASK 01: Probe execution and publication prerequisites — Control | Owner: Astra**

- **Goal:** Establish the usable Fable invocation, authentication, network and GitHub capabilities.
- **Context:** Section E; current Claude help; repository rulesets and release workflow.
- **Interface contract:** Fable 5.1 only; requested and observed metadata recorded separately; no billing fallback.
- **Files:** Probe records and sanitized report under `plan/exec/`; raw output under ignored `plan/logs/`. No source or configuration changes.
- **Acceptance criteria:** Both effort levels exercised; valid JSON; actual model identity verified; GitHub identity and dry-run push checked; publication gates inventoried.
- **Tests to add:** Trivial success probe and bounded turn-limit probe in a disposable fixture.
- **Constraints:** No real tag, deployment approval, API-key provisioning or credential output.
- **Done when:** Execute all commands and assertions in E; classify each prerequisite as PASS, BLOCKED or UNVERIFIED.
- **Estimate:** 15 minutes, plus the bounded Fable recovery window if needed.
- **Depends on:** 00.
- **Reuses:** Existing Claude subscription authentication, gh authentication and Trusted Publishing configuration.
- **Write REPORT to:** `/plan/exec/reports/01.md`.

**TASK 02: Establish preservation and verification controls — Control / Verification | Owner: Astra**

- **Goal:** Make task admission, deadlines, scope checks and preservation auditable.
- **Context:** Sections C, E and G; repository contribution and release checks.
- **Interface contract:** Failed commands, invalid JSON, missing reports and timeouts produce PARTIAL; no self-reported DONE grants acceptance.
- **Files:** Run-specific supervisor, scope checks, verification shell runbook and tests under `plan/exec/`; baseline manifests and reports. No package code.
- **Acceptance criteria:** Record baseline refs and protected hashes; isolate worktrees/environments; retain process IDs, command arguments, exit status and timing; enforce ownership and task caps.
- **Tests to add:** Mock success, nonzero exit, malformed JSON, absent REPORT, timeout and out-of-scope modification. No model calls in these controls.
- **Constraints:** This is run-local orchestration, excluded from distributions—not a new product framework. Never terminate unrelated processes.
- **Done when:** `python3 -B -m unittest discover -s "$PLAN_ROOT/exec/tests"`; `git diff --check`; baseline verification runbook passes against version 0.1.0.
- **Estimate:** 45 minutes.
- **Depends on:** 01.
- **Reuses:** Existing release verifiers and characterization tests.
- **Write REPORT to:** `/plan/exec/reports/02.md`.

**TASK 03: Record STOP and the three independent decisions — Semantics | Owner: Fable xhigh**

- **Goal:** Preserve the approved disposition and resolve only its documentation contracts.
- **Context:** Memo STOP execution plan; Sections B, C and F; `docs/architecture.md`.
- **Interface contract:** STOP is fixed. No proposal may reopen feature development or create an integration.
- **Files:** `docs/decisions/archive-standalone.md`; three decision ADRs; task-owned proposal records under `plan/exec/`.
- **Acceptance criteria:** Both independent proposals retained for each decision; comparison occurs only after Astra’s proposal is written; disagreements use a fresh Fable opinion; reopening conditions are complete.
- **Tests to add:** None; semantic and citation review required.
- **Constraints:** Clearly distinguish memo findings from independently checked facts. Do not copy unresolved research citation markers into public prose.
- **Done when:** `git diff --check`; protected-file scope check passes; Codex and fresh Fable reviews ACCEPT.
- **Estimate:** 45 minutes; implementation cap 30 turns.
- **Depends on:** 02.
- **Reuses:** Memo, architecture and existing trust-boundary documentation.
- **Write REPORT to:** `/plan/exec/reports/03.md`.

### Migration and public notice

**TASK 04: Write the standards migration map — Semantics | Owner: Fable xhigh**

- **Goal:** Explain where existing users can go without overstating equivalence.
- **Context:** Memo S3; accepted Task 03; kernel definitions; primary in-toto, Witness, SLSA and OPA documentation.
- **Interface contract:** Cover all 16 roster entries; distinguish conceptual analogy, host responsibility, project-specific semantics and unsupported equivalence.
- **Files:** `docs/migration.md`, a source-reference appendix and coverage record. No schemas, kernel, adapters or benchmark files.
- **Acceptance criteria:** Preserve five-state distinctions, claim-support limits and replay meaning; disclose VSA retirement; hashes are never described as signatures; no automatic migration is promised.
- **Tests to add:** No product tests. Independently check each mapping against the cited primary source and frozen kernel.
- **Constraints:** No standards-conformance certification or upstream endorsement claim.
- **Done when:** `git diff --check`; scope check passes; all 16 entries have reviewed dispositions; both reviews ACCEPT.
- **Estimate:** 75 minutes; cap 45 turns.
- **Depends on:** 03.
- **Reuses:** Existing architecture, stable types and established standards documentation.
- **Write REPORT to:** `/plan/exec/reports/04.md`.

**TASK 05: Prepare the deprecation notice and migration routes — Notice | Owner: Fable high**

- **Goal:** Make the STOP status and alternatives clear to visitors.
- **Context:** Memo S2, S5, S9 and S11; accepted Tasks 03–04.
- **Interface contract:** “Standalone development ended” is accurate; “archived” and “published v0.1.1” require actual evidence.
- **Files:** README, CONTRIBUTING, bounded SECURITY wording, `.github/ISSUE_TEMPLATE/{config,feature,bug}.yml`, `docs/portfolio.md`; maintenance wording in CHANGELOG.
- **Acceptance criteria:** Alternatives matrix and four-project index present; legacy surfaces receive no new features; security reporting remains available; existing examples and historical evidence stay intact.
- **Tests to add:** None unless a genuinely new documentation check is necessary.
- **Constraints:** Preserve the tested README example and generated figures. Do not close existing issues/PRs or change repository settings.
- **Done when:** `git diff --check`; `uv run --frozen --extra dev python -m pytest tests/test_figures.py -q`; link and rendered README inspection; both reviews ACCEPT.
- **Estimate:** 50 minutes; cap 35 turns.
- **Depends on:** 03 and 04.
- **Reuses:** Existing README, security process, contribution guide and portfolio descriptions.
- **Write REPORT to:** `/plan/exec/reports/05.md`.

**TASK 06: Audit portfolio independence — Portfolio | Owner: Fable high**

- **Goal:** Measure S6 without deleting legitimate provenance.
- **Context:** Memo S6–S7; each repository’s contracts and dependency declarations.
- **Interface contract:** Package dependency, runtime import, historical source adaptation and documentation link are distinct observations.
- **Files:** Audit record and task REPORT only; read the four repositories.
- **Acceptance criteria:** Record exact repository heads, searched manifests/locks/source paths and findings; verify ARCI’s complete frozen manifest; preserve NOTICE attribution.
- **Tests to add:** None.
- **Constraints:** Planning inspection found zero evalopt package dependencies. Do not manufacture dependency-removal work.
- **Done when:** Targeted `rg -n 'evalopt[-_]graph'` searches are classified; manifest inspection complete; `shasum -a 256 -c FROZEN.sha256` passes in ARCI; both reviews ACCEPT.
- **Estimate:** 30 minutes; cap 25 turns.
- **Depends on:** 02.
- **Reuses:** Four existing package manifests, locks, source trees, READMEs and NOTICE files.
- **Write REPORT to:** `/plan/exec/reports/06.md`.

### Portfolio README tasks

These four tasks create reviewed, pushed PRs. They do not directly push or merge another repository’s main.

**TASK 07A: Clarify Actseal’s independent role — Portfolio | Owner: Fable high**

- **Goal:** State action-policy qualification ownership and correct the evalopt relationship.
- **Context:** Memo S7; Task 06; Actseal AGENTS, stability contracts and active state.
- **Interface contract:** Actseal’s risk/coverage and sealed-evidence semantics remain its own; evalopt is not infrastructure.
- **Files:** Actseal `README.md` only, plus central REPORT. Preserve NOTICE, source, tests, metadata and plans.
- **Acceptance criteria:** Small accurate paragraph; STOP wording; original attribution retained.
- **Tests to add:** None.
- **Constraints:** Claude authors the prose; Astra reviews/integrates. Do not claim guaranteed label truth or execution safety.
- **Done when:** `git diff --check`; `uv run --frozen ruff check .`; `uv run --frozen ruff format --check .`; `uv run --frozen mypy --strict src tests`; `uv run --frozen pytest -m "not integration and not packaging"`; both reviews ACCEPT; PR pushed.
- **Estimate:** 40 minutes plus hosted checks; cap 25 turns.
- **Depends on:** 05 and 06.
- **Reuses:** Existing Actseal ownership and Related Projects text.
- **Write REPORT to:** `/plan/exec/reports/07A.md`.

**TASK 07B: Clarify Dorian’s independent role — Portfolio | Owner: Fable high**

- **Goal:** State code-claim warrant ownership and project independence.
- **Context:** Memo S7; Task 06; Dorian CONTRIBUTING and validation-honesty documentation.
- **Interface contract:** Existing warrant states and deterministic revalidation remain unchanged.
- **Files:** Dorian `README.md` only, plus central REPORT.
- **Acceptance criteria:** Concise portfolio paragraph preserving examples, evidence qualifications and existing claims.
- **Tests to add:** None.
- **Constraints:** No source, dependency, benchmark or documentation-guard rewrites.
- **Done when:** `git diff --check`; `make lint`; `make test`; both reviews ACCEPT; PR pushed.
- **Estimate:** 35 minutes plus hosted checks; cap 25 turns.
- **Depends on:** 05 and 06.
- **Reuses:** Existing Dorian README and documentation tests.
- **Write REPORT to:** `/plan/exec/reports/07B.md`.

**TASK 07C: Clarify Frontier Scout’s independent role — Portfolio | Owner: Fable high**

- **Goal:** State native-control compilation and PR-scope ownership.
- **Context:** Memo S7; Task 06; Frontier Scout AGENTS and CONTRIBUTING.
- **Interface contract:** Existing GitHub/Sigstore signing rails remain external; receipts do not acquire approval authority.
- **Files:** Frontier Scout `README.md` only, plus central REPORT.
- **Acceptance criteria:** Accurate independence paragraph; no shared evalopt layer or new signing infrastructure.
- **Tests to add:** None.
- **Constraints:** Preserve policies, hooks, generated configuration, source and release tags.
- **Done when:** `git diff --check`; `make lint`; `make type`; `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -m "not live" -q`; both reviews ACCEPT; PR pushed.
- **Estimate:** 35 minutes plus hosted checks; cap 25 turns.
- **Depends on:** 05 and 06.
- **Reuses:** Existing compiler/verifier boundary and signing guidance.
- **Write REPORT to:** `/plan/exec/reports/07C.md`.

**TASK 07D: Clarify ARCI’s independent role — Portfolio | Owner: Fable high**

- **Goal:** State preregistered statistical-regression ownership.
- **Context:** Memo S7; Task 06; ARCI AGENTS, interfaces, schema and statistics documents.
- **Interface contract:** Statistical semantics and all frozen files remain unchanged; adapted-source attribution is retained.
- **Files:** ARCI `README.md` only, plus central REPORT.
- **Acceptance criteria:** Accurate domain sentence and independence paragraph; no absolute-reliability claim.
- **Tests to add:** None.
- **Constraints:** Fable uses no network or mutating Git commands here; Astra owns the branch, commit and PR. Use repository environment binaries directly.
- **Done when:** `git diff --check`; `shasum -a 256 -c FROZEN.sha256`; `.venv/bin/ruff format --check .`; `.venv/bin/ruff check .`; `.venv/bin/basedpyright`; `.venv/bin/pytest -p no:cacheprovider`; both reviews ACCEPT; PR pushed.
- **Estimate:** 35 minutes plus hosted checks; cap 25 turns.
- **Depends on:** 05 and 06.
- **Reuses:** Existing ARCI contracts, frozen manifest and checks.
- **Write REPORT to:** `/plan/exec/reports/07D.md`.

### Release and closeout

**TASK 08: Prepare the final release without changing capability — Release | Owner: Astra**

- **Goal:** Prepare S4 using the existing release process.
- **Context:** Memo S4–S5; accepted notice; current release workflow and version verifiers.
- **Interface contract:** Kernel and compatibility implementation stay byte-identical to the run baseline; only `__version__` changes in source.
- **Files:** Version fields in `pyproject.toml`, `__init__.py`, root package entry in `uv.lock`; live version expectations in CI/release workflow and artifact verifier; new `docs/releases/v0.1.1.md`; final README/CHANGELOG adjustments after Notice ownership ends.
- **Acceptance criteria:** Version consistency; dependency graph unchanged; historical version references retained; inherited changes since v0.1.0 disclosed; no added runtime warnings or features.
- **Tests to add:** Run-specific preservation and version-consistency controls, not rewritten kernel tests.
- **Constraints:** No dependency upgrades or release-process redesign. Any necessary scanner correction must be exact-content/path scoped, independently reviewed and negatively tested; never suppress a real secret or whole file.
- **Done when:** `uv lock --check`; `uv run --frozen --extra dev python scripts/verify_release.py --expected-version 0.1.1`; `git diff --check`; preservation checks and two independent reviews ACCEPT.
- **Estimate:** 60 minutes.
- **Depends on:** 04 and 05.
- **Reuses:** Existing v0.1.0 release automation and verifiers.
- **Write REPORT to:** `/plan/exec/reports/08.md`.

**TASK 09: Qualify the exact release candidate — Verification | Owner: Astra**

- **Goal:** Establish compatibility, package hygiene and truthful public wording.
- **Context:** Section C; accepted Task 08; existing artifact and installed-release verifiers.
- **Interface contract:** No skipped required check counts as success; local evidence and hosted evidence stay separately identified.
- **Files:** Verification records and sanitized reports only; no implementation repair in this task.
- **Acceptance criteria:** Full core checks pass; exact ten-export API and replay pass from installed wheel; zero required dependencies; wheel/sdist exclude operational logs; public docs render and links resolve.
- **Tests to add:** No product tests; use existing tests plus Task 02 controls.
- **Constraints:** Build in an isolated directory; set `SOURCE_DATE_EPOCH` from the reviewed commit; label local artifacts as candidates, not published release bytes.
- **Done when:** Run all C commands; `uv build --out-dir "$RUN_ARTIFACTS/dist"`; `uvx --from twine==6.2.0 twine check "$RUN_ARTIFACTS"/dist/*`; `python scripts/verify_artifacts.py "$RUN_ARTIFACTS/dist" --version 0.1.1`; install wheel with `--no-deps` in a clean environment and run `python scripts/verify_installed_release.py --version 0.1.1`; independent review ACCEPT.
- **Estimate:** 60 minutes plus hosted checks.
- **Depends on:** 08.
- **Reuses:** Existing characterization, conformance, package and replay checks.
- **Write REPORT to:** `/plan/exec/reports/09.md`.

**TASK 10: Merge the deprecation PR and publish through existing gates — Control / Release | Owner: Astra**

- **Goal:** Publish only the accepted, verified change and exact release artifacts.
- **Context:** Memo S4/S8; Sections B, C and G; accepted Tasks 03–05 and 08–09.
- **Interface contract:** Exact-head checks and reviews precede merge; exact main precedes annotated tag; published assets are never replaced.
- **Files/actions:** PR description, release-tag annotation, publication records; merge only this repository’s reviewed PR; create v0.1.1 once.
- **Acceptance criteria:** Main required checks pass; tag targets verified main; actual workflow bundle passes artifact review; native deployment approval remains within existing permissions; published bytes and attestations verify.
- **Tests to add:** None.
- **Constraints:** No tag if v0.1.1 already exists unexpectedly, checks are unresolved, or fewer than 105 minutes remain. No protection changes, admin merge or replacement release.
- **Done when:** `gh pr checks "$PR" --required`; `gh pr merge "$PR" --squash --match-head-commit "$REVIEWED_SHA"`; verify resulting main checks; run `scripts/verify_release.py` with `--expected-version 0.1.1 --tag v0.1.1 --main-ref refs/remotes/origin/main --require-annotated-tag`; push only `refs/tags/v0.1.1`; after publication run `python scripts/verify_pypi_release.py --version 0.1.1 --attempts 6 --delay-seconds 10`, checksum verification and `gh attestation verify` for both distributions.
- **Estimate:** 60 minutes plus bounded hosted waits.
- **Depends on:** 09 and accepted reviews.
- **Reuses:** Existing GitHub rulesets, release workflow, Trusted Publishing and attestation verification.
- **Write REPORT to:** `/plan/exec/reports/10.md`.

**TASK 11: Publish the final receipt and human inbox — Control | Owner: Astra**

- **Goal:** End with a coherent repository and an honest accounting of every sprint item.
- **Context:** Memo S8/S10/S11 and 30-day closure plan; all task reports and reviews.
- **Interface contract:** Published, prepared, blocked and human-owned actions remain distinct.
- **Files:** `plan/exec/FINAL_REPORT.md`, `HUMAN_INBOX.md`, `STATUS.md`, sanitized release receipt, launch/clarification drafts and final disclosure corrections.
- **Acceptance criteria:** Every S1–S11 item accounted for; two-review coverage shown; zero unreviewed shipped changes; metrics and usage sourced; every unfinished lane has a REPORT and pushed branch when networking permits.
- **Tests to add:** None.
- **Constraints:** Never archive, rename, delete, yank packages, close old benchmark PRs or post outreach. Preserve raw evidence privately.
- **Done when:** `git diff --check`; scope/privacy review ACCEPT; reviewed final-report PR passes required checks; `gh release view v0.1.1 --json tagName,isDraft,url` accurately matches the report if published; all worktrees and remote refs reconciled.
- **Estimate:** 45 minutes, reserved.
- **Depends on:** All completed tasks or the time cutoff.
- **Reuses:** Actual task, review, CI, artifact and publication records.
- **Write REPORT to:** `/plan/exec/reports/11.md`.

### Required record formats

```text
REPORT <id> — Status DONE/PARTIAL/BLOCKED | Changes |
Tests (commands + results) | Deviations (with reason) | Open issues | Spend.

REVIEW <id> — Reviewer (Astra / Fable high / Fable xhigh) |
Verdict ACCEPT/REVISE/REJECT | Findings by severity |
Required changes | Follow-ups.

ADR — Decision | Positions (Astra, Fable) |
Rule that decided | Consequences.
```

## E. Task 01: exact probe and degradation

Claude Code **2.1.281** is present. Planning consultations returned canonical model **`claude-fable-5-1`** using configured selector **`claude-fable-5-1[1m]`**. Help lists both `high` and `xhigh`. This is preliminary evidence, not a substitute for the execution probe.

1. **Identity and authentication.** Run `command -v claude`, `claude --version`, `claude --help`, `claude auth status` and `gh auth status`. Retain redacted status, never token values. Verify the current GitHub actor and repository permissions.
2. **Headless invocation.** Exercise the actual worker flags at both effort levels:

   ```bash
   claude -p "$(cat "$PLAN_ROOT/exec/tasks/01-probe.md")" \
     --model 'claude-fable-5-1[1m]' \
     --effort xhigh \
     --permission-mode bypassPermissions \
     --max-turns 3 \
     --output-format json \
     --no-session-persistence \
     --append-system-prompt "$(cat "$PLAN_ROOT/exec/CONTRACT.md")" \
     > "$PLAN_ROOT/logs/01-xhigh.json"
   ```

   Repeat with `high`. Confirm exit status, JSON shape, actual `modelUsage` identity and turn count. Confirm effective effort through native runtime metadata where available; if output does not expose it, record requested versus observable effort explicitly rather than accepting model self-report.
3. **Git/network.** Run `gh api user`, `gh api rate_limit`, a read-only request to PyPI, and `git push --dry-run origin HEAD:refs/heads/winddown/<run-id>/probe`. Refresh main, rulesets, existing tags and release/environment state. A dry run proves no deployment approval.
4. **Environment.** Require no new API key. Check only presence of provider-routing variables; prevent accidental API/alternate-provider fallback. Use existing subscription authentication and GitHub OIDC publishing. Root sets task paths, baseline commit and artifact directories.
5. **Failure handling.** Retry unavailable/rate-limited Fable after 1, 2, 4, 8 and 15 minutes. After 30 minutes, continue independent Astra work and retry every 10 minutes within the budget. No model substitution. Single-reviewed work stays on a branch. Network/push/publish failures become exact final HUMAN_INBOX commands; no credential or billing workaround.

Implementation calls have task-specific turn caps and external wall-clock caps. Review calls use high effort, at most 20 turns and 20 minutes; security/standards disputes use xhigh. Interrupted attempts retain their logs and receive PARTIAL before any continuation.

## F. Three bias-control decisions

STOP fixes the absence of a new API or integration. The three independent decisions therefore concern the documentation contracts:

| Decision | What proposals decide | What they cannot change |
|---|---|---|
| Public migration interface | Structure of the capability map, non-equivalence labels and migration instructions | Stable API, schemas or a new converter |
| Naming and positioning | STOP notice, final-release wording and portfolio descriptions | Project names, archival status or evidence limits |
| Integration boundary | How the guide routes users to existing domain tools and standards | No new wedge, adapter or common dependency |

For each, save Fable’s xhigh proposal without displaying it to Astra. Astra writes its proposal from the same brief, then reads and compares. A fresh Fable call resolves substantive disagreement under your hierarchy. Preserve both proposals and the resulting ADR.

## G. Definition of done, budget and wrap-up

### Successful run

The deprecation and migration documentation is reviewed and merged; the final release is published and verified if its existing gates permit; four portfolio README PRs are reviewed and pushed; all existing evidence is preserved; main passes its required checks.

No new runtime feature, dependency, benchmark or integration ships. Repository archival is deliberately unfinished and belongs to you.

### Schedule

| Elapsed time | Planned work |
|---|---|
| 0:00–1:00 | Persist plan, probe, preservation controls |
| 1:00–3:30 | ADRs, migration map, notice; portfolio audit in parallel |
| 3:30–6:30 | Portfolio PRs, release metadata, qualification |
| 6:30–9:15 | Exact-head CI, merge, release and receipts |
| 9:15–10:00 | Mandatory wrap-up; no new implementation tasks |

Do not start the irreversible release step after **T+8h15**. At **T+9h15**, stop admitting new tasks, finish or terminate owned processes, record partial work, and finalize reports. Stop sooner if the authorized work is finished.

### End-state rules

- Every change reaching main has two accepted reviews and required checks. No unresolved review or red check is waived to meet the deadline.
- Every lane is merged or has a pushed branch and REPORT. If push is unavailable, retain its local commit and exact push command in HUMAN_INBOX.
- Fable logs report actual tokens, cache usage, calls and elapsed time. CLI list-price estimates are not represented as subscription charges. Astra usage is reported only to the extent attributable; unavailable totals remain unavailable.
- FINAL_REPORT maps all S1–S11 items to evidence, includes deviations/ADRs, review coverage, metrics, cuts, known issues and the next three steps.
- HUMAN_INBOX contains only actual outstanding actions, ordered by impact. Archival instructions are: verify the final release and unresolved PR dispositions, then GitHub **Settings → General → Danger Zone → Archive this repository**. Do not perform that action during this run.

If publication cannot finish, the report says **release prepared or blocked**, not published. A bounded incomplete run is preferable to a false completion claim.

## H. PRE-FLIGHT FOR YOU

1. Accept this plan.
2. Switch this pane to execution mode with full filesystem access and network.
3. Confirm once: `claude -p 'Reply OK only.' --model 'claude-fable-5-1[1m]' --effort high --output-format json`.
4. Keep existing Claude and GitHub authentication available; no API keys or new environment variables are required.
5. Leave this pane and the computer running. You may go AFK; denied human-only actions will be recorded without waiting.

## I. Decisions made now

| Decision | Rule |
|---|---|
| Execute STOP, not another improvement sprint or benchmark | Memo recommendation is preapproved |
| Include the final no-capability-change release | Explicit release authorization and memo S4; confirmed through Fable consultation |
| Use current public main; preserve the benchmark branches separately | Repository boundaries and reversible integration |
| Interpret `/plan` as repository-relative; keep raw logs private | Commit requirement, portability and privacy |
| Preserve kernel bytes relative to current main, while disclosing inherited changes since v0.1.0 | Verified repository state and evidence honesty |

| Decision | Rule |
|---|---|
| Keep all new public interfaces and integrations out of scope | STOP and memo prohibitions |
| Use native authorized deployment approval only after exact artifact review; never alter protections | Explicit publishing authorization and existing approval mechanism |
| Open other-repository README PRs without merging their mains | Narrower cross-repository authorization |
| Keep single-reviewed work unmerged during Fable outages | The stricter two-review merge requirement |
| Leave archival, external outreach and unavailable interactive actions in HUMAN_INBOX | Explicit human-only boundaries |

**Next action: accept this plan.**
