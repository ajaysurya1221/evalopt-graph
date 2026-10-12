# Exact CI nonsecret disposition for the v4 screen

The unchanged Gitleaks scan found **eleven nonsecret occurrences** in published commit [`49a379c7001b5b156f9f75b358da03a4367b252e`](https://github.com/ajaysurya1221/evalopt-graph/commit/49a379c7001b5b156f9f75b358da03a4367b252e): ten reproducible source SHA-256 values associated with an API-named fixture, and one deliberate synthetic pytest parameter. The exact occurrences and their source derivations belong in [diagnosis.json](diagnosis.json). This classification is limited to those findings; it does not establish that no other credential could exist.

The [original push run](https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38243778569) and [original PR run](https://github.com/ajaysurya1221/evalopt-graph/actions/runs/38243792456) retain their red Gitleaks results. Any dependent aggregate failures remain failures. This appendix accompanies [draft PR #36](https://github.com/ajaysurya1221/evalopt-graph/pull/36). It does **not** claim green CI, completed unfinished lanes, a passing stock scan or a live difficulty result.

## Narrow operational change

For this fixed screen only, the operator's previous requirement of all-green hosted CI is replaced by two requirements: every independent nonsecret CI lane must succeed for the exact current public head, and a fresh stock full-history scan must receive independently reviewed `ACCEPT_KNOWN_NONSECRETS` adjudication for exactly these eleven provenance-bound findings. Only Gitleaks and aggregates failing solely because of it may remain red. Pending, skipped, cancelled, missing or otherwise failed independent lanes block dispatch. Earlier-head successes cannot substitute for current-head evidence.

The scanner stays at pinned Gitleaks 8.30.1, with the unchanged committed configuration and complete `--all` public history. No ignore file, path/rule suppression, history rewrite, token-validity request or scanner exit-code relabeling is introduced. A new or unknown finding—including one introduced by this appendix—blocks dispatch. This policy authorizes no additional or future exception.

The [machine-readable policy](operational-policy.json) fixes the eleven immutable commit/path/rule/line fingerprints. The separately reviewed adjudicator also checks raw report completeness, scan/configuration identity, immutable file and line hashes, and source derivation; matching fingerprints alone are insufficient. [receipt.json](receipt.json) binds accepted helper code, controls and sanitized historical-head evidence. It does not pre-clear the later publication head. The presence of this policy alone does not prove completion or authorize a launch.

## Reproduce the historical source correspondence

From a complete clone containing the published historical commit, run:

```sh
python3 -I -B results/skill-workflows-v4/ci-disposition-2026-10-12/reproduce.py --repo .
```

The replay verifies the packet and exact finding/source bindings without running a scanner, candidate code or model. Raw scanner author/contact/message metadata stays private. Its retained byte commitments and the sanitized public projection are distinct artifacts. This replay neither authenticates the original scan execution nor clears a later head for dispatch. The separate capture helper retains pinned macOS scanner/Git identities; the hosted Linux run remains the original failed run.

## Frozen study remains unchanged

This changes only the external CI launch predicate. The [registered screen](../difficulty-registration-2026-10-12/README.md), its 819 frozen manifest entries and registration pin `5c75186aeb6081b4a7dac4b10704c9992cda7f55b62acc8ae64718c5dd06b0ac` remain unchanged: eight tasks, two attempts each, sixteen upstream-only B trials. Tasks, response contracts, model/runtime/image/budget conditions, grading, difficulty decision and every native admission/continuation gate retain their original meaning. All existing source and result packets remain byte-identical.

Before dispatch, retain the original failures, verify the current exact-head scan and nonsecret lanes, reproduce preservation and the existing public packets, then apply the unchanged native lock, quiescence, storage, runtime and subscription checks. Neither this appendix nor a passing difficulty screen authorizes a larger benchmark.

This is maintainer-run review with separated AI author/reviewer roles, not independent human or live replication. Hashes establish content correspondence, not producer authentication; trusted retained execution custody remains necessary. Repository protections, merge permissions and release authority are unchanged. A red protected check is not turned green by this policy.
