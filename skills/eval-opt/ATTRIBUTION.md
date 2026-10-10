# Attribution

This portable bundle adapts the local eval-opt workflow and selected ideas from
[Matt Pocock's skills](https://github.com/mattpocock/skills) at commit
[`b0618bc436ad893b3c5e84e55fba86586d34a404`](https://github.com/mattpocock/skills/commit/b0618bc436ad893b3c5e84e55fba86586d34a404),
reviewed on 2026-10-08:

- [diagnosing-bugs](https://github.com/mattpocock/skills/blob/b0618bc436ad893b3c5e84e55fba86586d34a404/skills/engineering/diagnosing-bugs/SKILL.md):
  symptom reproduction, minimization, falsifiable hypotheses, and regression
  verification inform `references/debugging.md`.
- [to-tickets](https://github.com/mattpocock/skills/blob/b0618bc436ad893b3c5e84e55fba86586d34a404/skills/engineering/to-tickets/SKILL.md):
  behavior-first work slices and dependencies inform `references/work-packages.md`.
- [code-review](https://github.com/mattpocock/skills/blob/b0618bc436ad893b3c5e84e55fba86586d34a404/skills/engineering/code-review/SKILL.md):
  separate contract and implementation review questions inform
  `references/review-coverage.md`.

The upstream project is MIT licensed, copyright 2026 Matt Pocock. Its notice is
preserved in [LICENSE](LICENSE) alongside the eval-opt notice. These established
practices are not claimed as eval-opt inventions. Attribution does not imply
endorsement or a measured performance advantage.

Version `1.0.0` identifies this portable skill bundle, separately from the Python
kernel's package version. The bundle contains host instructions and no execution
engine. It intentionally excludes the personal installation's hooks, hardcoded
paths, external agent CLI bridge, and deprecated-runner integration assumptions.
Benchmark runs must identify the complete bundle by content hash, since a version
label alone does not prove the bytes used.
