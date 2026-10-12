# Four portfolio README render checks

Root inspected the exact public commit READMEs in the Codex in-app browser at the desktop viewport and a 390 x 844 phone viewport. Dorian and Frontier Scout were inspected before 22:25 UTC; Actseal and ARCI at 22:30 UTC on 2026-10-12. This is actual rendered-page inspection, not a substitute for source or semantic review.

| Repository | Exact source | Inspected section |
|---|---|---|
| Actseal | 52dbc14554486e8ff9e31455d550bfc3d43f139e | Related projects |
| Dorian | 5222f256ba23c2fa345fb5a2f6d033c336dcbcc1 | Related projects |
| Frontier Scout | b0d2ae108e62ef7c8a890e8294104a577217b4f8 | Related projects |
| ARCI | ba179f3a188710e38ec4557d2f65b66a8953c099 | Independence paragraph before Roadmap |

The changed paragraphs rendered with readable text and links, ordinary wrapping and no visible horizontal clipping at the inspected widths. Long paragraphs continue below the phone viewport; this is not a claim that an entire README fits one screen. GitHub's surrounding historical figures, tables and interface were not redesigned. Temporary viewport overrides were reset. No source or website content changed through the browser.

Fresh PR API snapshots retained under private artifacts/10-portfolio-final-ci show all four PRs open at those same heads. Actseal's 17, Dorian's five and Frontier Scout's seven check/status entries succeeded. ARCI's two Python check lanes were still running; two macOS statistics lanes and CodeRabbit had succeeded. This is a finite snapshot, not a future-main check or permission to merge sibling repositories.

Later root readback: ARCI PR14 remained open at the exact reviewed head, and all five current check/status entries succeeded, including both Python lanes. The completed JSON and observation time are retained as agent-reliability-ci-completed files beside the earlier snapshot. No sibling main was merged.
