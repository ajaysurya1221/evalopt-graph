# Review coverage

Preserve the requested scope: commit range, pull request, current workspace, or
named files. Record the baseline, current HEAD when available, initial status,
and pre-existing changes. Resolve a branch comparison to its merge base; use
the specified commits for an explicit before/after comparison. If a baseline
cannot be resolved, report the gap instead of silently choosing one.

For a current-workspace candidate, inspect the union of committed, staged,
unstaged, and untracked changes. With Git, the following inventory is useful at
the repository root. Supply the resolved base as one argument, parse
NUL-delimited paths, and set `GIT_OPTIONAL_LOCKS=0` for read-only inspection.

```text
git diff --no-ext-diff --no-textconv --name-status -z <resolved-base> HEAD
git diff --no-ext-diff --no-textconv --cached --name-status -z
git diff --no-ext-diff --no-textconv --name-status -z
git ls-files --others --exclude-standard -z
```

Read the actual diffs and relevant untracked contents; filenames alone are not
review evidence. Include deletions, renames, type changes, and binary changes.
Explicitly scoped ignored files also need inspection. Inspect deleted regression
tests and frozen-file changes even when the remaining checks pass. Compare
behavior to the contract, not only to a test result.

Keep pre-existing changes distinct from this task's edits while considering their
effect on verification. Refresh the inventory after authorized edits. Record
excluded paths and unavailable contents. Use argv-based invocation for file
lists; an empty selection must not become an unintended whole-directory scan
or rewrite. Deleted files remain review inputs even when a tool requires a path
that still exists.

For commit-only review, keep local changes outside the scope and ensure checks
exercise that commit. Do not attribute dirty-workspace results to a clean
revision. A worktree created at HEAD omits staged, unstaged, and untracked changes;
verify worker inputs match the candidate before using their conclusions. Never
stash, reset, stage, or overwrite user changes to prepare a review. Without Git
or a first commit, use explicit inventories and available before/after artifacts;
do not initialize a repository solely to obtain a diff.

Assess both contract compliance and implementation correctness. Independent
reviewers, when available and useful, must receive the same candidate and
baseline and inspect evidence themselves. A read-only reviewer does not repair
the target or write state into it. Check commands may require a faithfully
copied candidate in an allowed temporary location to remain read-only.

Each actionable finding needs a triggering condition, severity, located evidence,
consequence, and concrete fix. Merge duplicates into one ranked assessment and
preserve unresolved contradictions. State the inspected scope and unrun checks.
Do not equate agreement between reviewers with correctness.

Separate review questions draw on the upstream workflow identified in
[ATTRIBUTION.md](../ATTRIBUTION.md).
