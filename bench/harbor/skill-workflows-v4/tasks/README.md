# Fresh v4 difficulty tasks

Eight independently conceived task instances form a **development-only difficulty screen**: two ordinary repairs, two bounded implementations, and one each of committed review, mixed review, constraint preservation and misleading evidence. These are new authored codebases and cases, not variants of v1–v3 or held-out tasks. Generic authoring and control interfaces were adapted from v3; the response declaration is supplied by the v4 runtime.

| Task | Category | Interacting mechanisms | Registered cases |
|---|---|---|---:|
| mvcc-predicate-serialization | Ordinary repair | Snapshot isolation, local overlays, predicate reads, tombstone/write history and atomic conflict resolution | 18 |
| fare-product-itinerary | Ordinary repair | Contiguous product covers, transfer chains, mode/zone eligibility, cross-midnight cap state and deterministic global optimization | 18 |
| ordered-tree-three-way-merge | Bounded implementation | Identity/presence merge, independent field edits, deletion conflicts, structural validation and deterministic forest order | 18 |
| dependency-fair-dispatch | Bounded implementation | Preemption, exact weighted service, event order, transitive dependency failure and persistent tenant accounting | 18 |
| backup-reachability-collection | Committed review | Branch retention, delta/reference closure, revival and inclusive quarantine expiration | 18 |
| http-variant-revalidation | Mixed review | Multi-field Vary matching, authorization isolation and conditional metadata merge across three workspace layers | 18 |
| chunked-escaped-tokenizer | Constraint preservation | Frozen incremental ABI, UTF-8 carry, quoted/escaped syntax and byte-accurate per-feed emission | 18 |
| inherited-glob-policy | Misleading evidence | Segment wildcards, escaped literals, recursive matching, inheritance and precedence under a disclosed obsolete check | 18 |

Every task publishes its full behavioral domain, editable paths and boundary restrictions. Review tasks additionally publish the finite witness requests and exact accepted location/request bindings without expected answers. The clean review snapshot is checked against **every** registered case. Authored references are separate implementations outside all delivered agent snapshots; expected answers never enter an agent workspace. Implementation controls include the unrepaired baseline and three separate semantic mutants. Invalid-token examples in the tokenizer are ordinary stated error semantics, not artificial runtime failures.

Difficulty has **not** been established by static complexity or these controls. Only the separately registered B-only screen can measure headroom. Reporting validity is separate from functional and boundary success; the disclosed stale glob smoke check must not manufacture difficulty. No new trials or scores are part of this authoring package.

`author.py` deterministically generates task snapshots and the source manifest from `definitions/*.py`. It neither imports older tasks nor reads candidate outputs. It uses the installed Ruff formatter/import sorter and records the resulting source bytes. From the repository root:

```sh
python -B bench/harbor/skill-workflows-v4/tasks/author.py
python -B -m pytest bench/harbor/skill-workflows-v4/tests/test_fresh_tasks.py
python -B bench/harbor/skill-workflows-v4/tasks/qa.py
```

The default QA calls trusted authored code in fresh local Python processes; that is not a hostile-code sandbox. A production Docker invoker is supplied separately for retained containment controls. Both initial and post-stop visible checks are actually executed. Each case is evaluated independently, semantic negatives must fail, complete rosters are checked, and input/snapshot preservation is verified. Controls also reject false claims, solvable refusals and boundary violations; review controls cover clean results, missing/fabricated findings and neutral supported duplicates.

Authoring and review use separated AI-agent roles in a maintainer-run study. This is not independent human authorship or independent human replication. Preserve the source-bound control receipts and any earlier failed authoring probes; they are development evidence, not model scores.
