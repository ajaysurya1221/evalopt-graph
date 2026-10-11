# Review coverage

Identify the requested baseline and scope before examining findings. A commit
range, a dirty workspace and a branch comparison are different candidates. For a
workspace review, include committed, staged, unstaged, untracked and deleted
changes; inspect file contents and diffs, not only a filename inventory. Include
renames, mode/type changes and removed tests. Do not stash, reset, stage or commit
to make review easier.

For read-only Git inspection, disable optional locks and external diff/textconv
helpers. A detached checkout of HEAD omits uncommitted changes; do not use its
passing checks to certify a different workspace. If the baseline or relevant
content is unavailable, describe that gap instead of silently choosing another.

Check contract compliance and implementation correctness. Each actionable
finding needs a supported trigger, location and consequence. Keep complete
coverage without multiplying duplicates or discarding supported effects. A clean
review is a conclusion about the inspected scope and evidence, not a proof over
an unstated or unbounded input domain.
