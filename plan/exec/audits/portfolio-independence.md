# Portfolio independence audit (Task 06, memo S6)

Read-only audit of the four surviving repositories for any dependency on
`evalopt-graph`. Audited in the supervised interval 2026-10-12T19:46:32.523296Z to
2026-10-12T19:52:06.902040Z (334.281 s, retained supervisor receipt `plan/logs/06-audit/`)
from the task worktree `wt-portfolio-06` (branch `winddown/20261013/06`). Revision R1
(2026-10-13) corrects this record's stated evidence bounds after the two independent
reviews; it changes no finding, classification, head, count or disposition. Observations
marked "R1" were made during the revision with the same read-only tools. No file in the four
repositories was modified; no model call, no network command and no mutating
Git command was run there. Tools: ripgrep 15.2.0, `shasum`, `git` read-only
subcommands (`rev-parse`, `status`, `log`, `describe`, `remote -v`,
`cat-file -t`, `ls-files`, `diff --quiet`, `worktree list`), `python3`
`tomllib`, `unzip -l/-p`, `tar -tzf`.

## 1. Interface contract: four distinct observations

| Class | Meaning | Counts as S6 coupling? |
|---|---|---|
| **P** Package/runtime dependency | `evalopt-graph` in `[project].dependencies`, extras, dependency groups, a lock, `requirements.txt`, built-artifact metadata, or an installed site-package | Yes |
| **I** Runtime import | `import evalopt…` / `from evalopt… import` / `import_module("evalopt…")` in source | Yes |
| **A** Adapted-source attribution | NOTICE or module docstring stating code was adapted from evalopt-graph at a pinned commit | No; licensing provenance that must be preserved |
| **D** Documentation link / planning record | README, ADR, planning inventory or documentation-guard test that names or links evalopt-graph | No; wording is Task 07A–07D scope |

## 2. Repository heads (all on `main`, working trees clean at audit time)

| Repository | HEAD | `git describe --tags` | Last commit (committer time) | Remote |
|---|---|---|---|---|
| actseal | `111afb3cf0dbab94e7bdf7917e800ba6faaeac0b` | `v1.0.1-6-g111afb3` | 2026-10-12T17:31:27+05:30 "build: bound the lock's resolution environments below Python 3.15 (#69)" | `https://github.com/ajaysurya1221/actseal.git` |
| dorian | `eeb193792fac8a66b18f5222287a8fcf336dda08` | `v1.4.1` | 2026-10-13T00:36:38+05:30 "release: prepare 1.4.1 — documentation, metadata and a PyPI-safe long description (#43)" | `https://github.com/ajaysurya1221/dorian.git` |
| frontier-scout | `e34d4a6dc1aee6f9f875b0b1fceb792a083a9a1c` | `v2.2.0-1-ge34d4a6` | 2026-10-12T17:14:09+05:30 "docs: public-text precision and sample fixes after 2.2.0 (#80)" | `https://github.com/ajaysurya1221/frontier-scout.git` |
| agent-reliability-ci (ARCI) | `a5adc834f74f5546fa3585b4ce6adfc96e2c37a3` | `evidence-2026-10-06-10-ga5adc83` | 2026-10-13T00:04:55+05:30 "Merge pull request #13 from ajaysurya1221/claude/presence-2026-10-12" | `https://github.com/ajaysurya1221/agent-reliability-ci.git` |

`git -C <repo> status --short` printed nothing for all four. actseal additionally
has three linked worktrees under `actseal/.worktrees/` (`ci-artifact-actions`
@ `9ec4193`, `presence-docs` @ `3549413`, `uv-environments` @ `9289cda`). They were
**not** inside the search scope of sections 5–6: `actseal/.gitignore:19` ignores
`.worktrees/`, ripgrep honours `.gitignore` even with `--hidden`, and `rg --files` with the
audit's globs lists 0 paths under `.worktrees/`. The original record wrongly said they were
searched with no hits. R1 supplementary direct search, `rg -n -i --hidden -g '!.git'
-g '!.venv' 'evalopt' actseal/.worktrees`: 36 lines in 24 files, the same eight files in
each worktree as on `main` (`NOTICE`, `README.md`, `docs/decisions/0002-…`, `plan/PLAN.md`,
`plan/RECONCILIATION.md`, `plan/SOURCES.md`, `plan/VERIFICATION.md`,
`tests/docs/test_readme.py`), all class A/D; 0 Python import hits and 0 hits in their
`pyproject.toml`/`uv.lock`. The S6 conclusion is unchanged by them. The audit's primary
scope remains the four primary working trees at the heads above.

## 3. Operating contracts read (safe mode disables automatic discovery)

| Repository | Files read | Rules relevant to this audit |
|---|---|---|
| actseal | `CLAUDE.md`, `AGENTS.md`, `NOTICE`, `plan/CONTRACTS.md` (outline), `plan/v1/STATE.md` (head) | Codex integrates; executors edit only owned files; "stdlib runtime core"; "Port only the approved public primitives at their pinned commits and preserve attribution"; never print `.env` values (not read). |
| dorian | `CONTRIBUTING.md` (no `AGENTS.md`/`CLAUDE.md` exists) | "Zero runtime dependencies. `[project].dependencies` stays empty"; `tests/test_firewall_import_closure.py` guards the verdict-path import graph; README example and wording are pinned by tests. |
| frontier-scout | `CLAUDE.md`, `AGENTS.md`; dogfood `.claude/settings.json` summarised (56 allow / 12 deny / 21 ask; PreToolUse+PostToolUse hooks) | "the only runtime dependency is `pydantic`"; `hook_runtime.py` stays stdlib-only; policy/lock/hooks are approval-gated. This audit ran from outside that repository and only read files. |
| ARCI | `AGENTS.md`, `NOTICE` | Frozen files listed in `FROZEN.sha256`; no state-changing git; no network; no new dependencies; runtime uses only stdlib, `pydantic`, `pyyaml`; use `.venv/bin/*` directly, never `uv`. Complied: only `shasum`, read-only `git`, `rg`, `awk` were run there. |

## 4. Manifests and locks (class P)

Command per repository (same Python snippet for each):

```bash
python3 - <repo>/pyproject.toml   # tomllib: [project].dependencies, optional-dependencies,
                                  # [dependency-groups], tool.uv.sources, build-system
grep -c -i evalopt <repo>/uv.lock  # or requirements.txt
```

| Repository | Manifest files found (depth 1) | `[project].dependencies` | Extras / groups (none name evalopt) | Lock / requirements | `evalopt` hits |
|---|---|---|---|---|---|
| actseal 1.0.1 | `pyproject.toml`, `uv.lock` | `[]` | extra `laya` (laya, torch, transformers, huggingface-hub, safetensors, numpy); groups `assets`, `dev` | `uv.lock`, 61 `name =` entries | 0 |
| dorian-vwp 1.4.1 | `pyproject.toml`, `uv.lock` | `[]` | extras `extract` (anthropic), `data` (duckdb); group `dev` | `uv.lock`, 29 entries | 0 |
| frontier-scout 2.2.0 | `pyproject.toml`, `requirements.txt` (no lock) | `['pydantic>=2.0']` | extra `dev` (tooling only) | `requirements.txt`: `pydantic>=2.0` only | 0 |
| agent-reliability-ci 0.7.0 | `pyproject.toml`, `uv.lock` | `['pydantic>=2.7,<3', 'pyyaml>=6,<7']` | group `dev` (basedpyright, pytest, ruff, types-pyyaml, typesafe-sdk) | `uv.lock`, 26 entries | 0 |

No `package.json`, `poetry.lock`, `setup.py`, `setup.cfg` or `Pipfile` exists in any of the four.
`tool.uv.sources` names only `torch` (actseal). No git/path/URL source points at evalopt.

Built artifacts: `actseal/dist/actseal-0.1.0-py3-none-any.whl` METADATA lists only
`laya`-extra `Requires-Dist` lines; neither the wheel listing nor the sdist listing contains
an `evalopt` path. No `dist/` exists in the other three.

Installed environments: `ls <repo>/.venv/lib/python*/site-packages/*evalopt*` matched
nothing in actseal, frontier-scout and ARCI. dorian has no local `.venv`, so its runtime
environment was not observed; its manifest and lock are the evidence there.

**Result P: 0 of 4 repositories declare or lock an evalopt package** (manifests, extras,
groups, three `uv.lock` files and one `requirements.txt` fully inspected). Built-artifact
evidence is limited to the only artifacts on disk, actseal 0.1.0 wheel/sdist dated 6 Oct and
older than the current 1.0.1 head; no artifacts exist for the other three and none were
built. Installed-environment evidence is limited to a site-package directory-name check in
the three local `.venv`s present (actseal py3.12, frontier-scout py3.14, ARCI py3.13);
dorian has no local `.venv`. "Built" and "installed" states were therefore not established
for all four repositories, only observed where artifacts or environments existed.

## 5. Runtime imports (class I)

```bash
rg -n --hidden -g '!.git' -g '!.venv' -g '!node_modules' -g '!*.egg-info' -t py \
   -e '^\s*(from|import)\s+evalopt' -e 'import_module\(\s*["'"'"']evalopt' <repo>
```

| Repository | Python files searched | Import hits |
|---|---|---|
| actseal | 129 | 0 |
| dorian | 150 | 0 |
| frontier-scout | 58 | 0 |
| ARCI | 148 | 0 |

The broader case-insensitive `evalopt` search in section 6 also found no import,
string-import or entry-point reference; every hit is prose or a docstring.

**Result I: 0 of 4 repositories import evalopt at runtime.**

## 6. Targeted `rg -n 'evalopt[-_]graph'` and broader `rg -n -i 'evalopt'`, classified

Scope: the four primary working trees on disk at the heads in section 2, including
dotfiles not otherwise ignored (`.github`, `.claude`), with explicit globs excluding `.git`,
`.venv`, `node_modules`, `*.egg-info`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`.
Actual ignore behaviour: ripgrep was run without `--no-ignore`, so each repository's
`.gitignore` was honoured; `--hidden` admits dotfiles but does not override `.gitignore`.
Gitignored, untracked directories present on disk and therefore excluded were: actseal
`.worktrees/` (see section 2), `dist/` (checked separately by `unzip`/`tar` listing),
`research/`, `plan/dispatch/`, `plan/local-receipts/`; frontier-scout `.frontier-scout/`;
ARCI `examples/jev_triage_agent/node_modules/`; dorian none beyond `.venv`-class paths.
R1 spot check with `--no-ignore` on those excluded paths: actseal `research/` 14 lines in 2
local research notes and `plan/dispatch/` 7 lines in 4 local dispatch packets/streams, all
untracked (`git ls-files` lists none), 0 Python imports; `plan/local-receipts/`,
`.frontier-scout/` and the ARCI `node_modules/` 0. Those untracked local files are not part
of any repository's committed tree and are not classified line by line. Archives were not
expanded (actseal `dist/` listings were checked by name only).

```bash
rg -n --hidden -g '!.git' -g '!.venv' -g '!node_modules' -g '!*.egg-info' \
   -g '!.mypy_cache' -g '!.pytest_cache' -g '!.ruff_cache' 'evalopt[-_]graph' <repo>
rg -n -i --hidden <same globs> 'evalopt' <repo>
```

| Repository | `evalopt[-_]graph` lines | `-i evalopt` lines |
|---|---:|---:|
| actseal | 8 | 12 |
| dorian | 0 | 0 |
| frontier-scout | 0 | 0 |
| ARCI | 6 | 6 |

### actseal (12 lines; 8 match the strict pattern)

| File:line | Class | Observation | Disposition |
|---|---|---|---|
| `NOTICE:12` | A (design) | "Canonical hashing and self-sealing evidence are also informed by the public evalopt-graph design. No evalopt-graph source implementation is included." The same NOTICE attributes Clopper–Pearson primitives to ARCI at `d13dd94124cb71d378a4e76224fc115b750e8133` (Apache-2.0); that commit exists in ARCI (merge of PR #10, 2026-10-06). | Preserve verbatim. |
| `README.md:181` | D | "Related projects" paragraph links Evalopt Graph as a sibling that "evaluates acceptance policies against supplied evidence". | Wording is Task 07A scope. |
| `tests/docs/test_readme.py:191` | D (guard) | `RELATED_REPOSITORIES` tuple pins the four sibling URLs including `evalopt-graph`; a documentation-guard test, not an import. `test_related_projects_are_three_sentences_naming_four_repositories` (line 636) also requires the "Related projects" section to be one paragraph of exactly three sentences, to contain the `COMPARISON` string (line 136), to end with "against supplied evidence." and to contain `(<url>)` for all four pinned repositories. | Task 07A is README-only and must preserve tests: its README edit must retain the pinned `https://github.com/ajaysurya1221/evalopt-graph` URL and satisfy the guard's three-sentence, `COMPARISON` and closing-phrase constraints. The test is not in 07A scope and is not to be co-edited. |
| `docs/decisions/0002-minimal-attributed-reuse.md:18` | D (ADR, historical) | Records that canonical JSON / self-sealing pattern "may be adapted from MIT evalopt-graph at `9bbc192443dc713f0f3344939a441c4a66e8a44d`". | Historical decision record; preserve. |
| `docs/decisions/0002-minimal-attributed-reuse.md:22` | D (ADR) | Explicitly declines a dependency: "Depending on evalopt-graph would introduce an additional acceptance/evidence vocabulary. Neither is needed." | Already states independence. |
| `plan/SOURCES.md:129`, `:141` | D (planning inventory) | Source/licence inventory pinning evalopt-graph 0.1.0 at `9bbc192…` (that commit exists in the evalopt repository: 2026-10-05 "deps: update optional dependency floors and refresh uv lock"). | Preserve. |
| `plan/VERIFICATION.md:19` | D (planning inventory) | Licence table row for evalopt-graph, MIT, 0.1.0. | Preserve. |
| `plan/RECONCILIATION.md:31` | D (planning prose, `-i` only) | "Evidence and assumptions" paragraph: "ARCI, evalopt and Dorian supply relevant existing concepts." A concept-level planning statement, not a dependency, import or link. Omitted from the original table; the twelve-line inventory is now complete. | Preserve. |
| `plan/PLAN.md:61`, `plan/RECONCILIATION.md:128`, `:147` | D (planning, `-i` only) | Planning reconciliation rows ("adopt separation/canonicalization with notices, not nested dependency"; rejects a "recursive ARCI/evalopt CI gate"). | Preserve. |

Source check behind the NOTICE claim: `src/actseal/serialization.py:134 canonical_json`
is Actseal's own function with a pre-validation pass (`_check_json_value`) and `SchemaError`
handling; it shares the common `json.dumps(sort_keys=True, separators=(",",":"),
ensure_ascii=False, allow_nan=False)` idiom. No evalopt module, file or symbol is present
under `actseal/src`. This audit does not adjudicate derivation beyond that observation.

### ARCI (6 lines)

| File:line | Class | Observation | Disposition |
|---|---|---|---|
| `src/arci/hashing.py:6–7` | A | Module docstring: "`canonical_json` and `hash_record` are adapted from evalopt-graph (src/evalopt_graph/attestation.py), MIT License, (c) 2026 Ajay Surya Senthilrajan." The file is in `FROZEN.sha256`. | Frozen; preserve. |
| `NOTICE:4,5,7,9` | A | Attributes `src/arci/hashing.py` (from `attestation.py`) and the self-sealing decision pattern in `src/arci/schema.py` (from `kernel.py`) to evalopt-graph, MIT. `schema.py` itself carries no inline evalopt mention; the NOTICE is the attribution of record and `schema.py` is frozen. | Preserve. |

### dorian and frontier-scout

Zero hits for either pattern, including READMEs, CHANGELOGs, workflows and tests. dorian's
README mentions none of the sibling projects. frontier-scout's README names no sibling
project (its only "related" text compares Notari). ARCI's README mentions frontier-scout
once as a tested subject (`README.md:179`) and never evalopt.

**Result for S6:** no declared, locked or imported evalopt dependency in any of the four
primary trees as inspected (bounds in sections 4, 6 and 8); two attribution sites (ARCI
adapted source; actseal design/NOTICE) and one documentation link set (actseal README plus
its guard test and planning records) are legitimate provenance to retain. No
dependency-removal work exists to do, and none was manufactured.

## 7. ARCI frozen manifest: full verification

```bash
cd /Users/ajay/Developer/agent-reliability-ci
wc -l FROZEN.sha256                      # 48
grep -c -v '^\s*$' FROZEN.sha256         # 48 (no blank lines)
awk '{print $2}' FROZEN.sha256 | sort -u | wc -l   # 48 distinct paths
shasum -a 256 -c FROZEN.sha256           # 48 × OK, exit 0
while read -r line; do p="${line#*  }"; git ls-files --error-unmatch -- "$p"; \
  git diff --quiet HEAD -- "$p"; done < FROZEN.sha256   # 48 tracked, 0 differ from HEAD
shasum -a 256 FROZEN.sha256   # c57d097d625f613f23ce43c7e4960956ec74fd1ffa9d7550aaea1033ba9fa3e2
git rev-parse HEAD:FROZEN.sha256   # 3904622ff3e7544de143b03192afb496559d1c6f
git log -1 --format='%H %cI' -- FROZEN.sha256   # e304e81695d19398285c2b47cdc5560cba5fb267 2026-10-03T15:27:18Z
```

All **48** entries verified OK (planning's count of 48 is confirmed; the memo-era figure of
47 is not current). Every listed path is tracked and byte-identical to HEAD `a5adc83`. The
manifest covers `AGENTS.md`, `justfile`, `pyproject.toml`, `uv.lock`, three `docs/*.md`
(`AGENT_SEMANTICS`, `STATISTICS`, `TRUST_MODEL`), four `docs/design/*.md`, six
`src/arci/*.py` (`contracts`, `fingerprint`, `hashing`, `interfaces`, `schedule`, `schema`),
`tests/__init__.py` and 30 files under `tests/acceptance/` (4 + 3 + 4 + 6 + 1 + 30 = 48).
`src/arci/hashing.py` (the evalopt-adapted module) is among them, so its attribution cannot
change without breaking the manifest.

## 8. Limits of this audit

- Searched the four primary working trees on disk at the heads above, not Git history,
  other branches, actseal's linked worktrees (section 2), remote state, published PyPI
  metadata or GitHub repository settings.
- Text searches honoured each repository's `.gitignore`; the gitignored untracked paths
  that were therefore excluded are listed in section 6 together with an R1 spot check.
- `.venv` directories were excluded from text search and checked only by site-package
  directory name in the three repositories that have one; dorian has no local `.venv`, so
  no installed state was observed for it.
- Built-artifact evidence covers only actseal's stale 0.1.0 wheel/sdist; nothing was built
  for any current head and no artifacts exist for dorian, frontier-scout or ARCI.
- Archives were listed, not unpacked and grepped (actseal `dist/` 0.1.0 artifacts only).
- No test suites, linters or type checkers were run in the four repositories; the only
  check executed there is the frozen-hash verification, as the task specifies.
- Non-derivation of actseal's five-line `json.dumps` idiom from evalopt is not something a
  text search can establish; the NOTICE statement is recorded as the repository's claim.
- Counts are line counts from ripgrep; a line with two mentions counts once.
