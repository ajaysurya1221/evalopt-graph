# REPORT 08 scanner contract — Status DONE

Read-only API fact check for the root-owned Task 08 correction. This report creates no candidate configuration, changes no scanner suppression, performs no candidate scan, and supplies no acceptance verdict for an eventual patch.

## Version and primary-source identity

Installed command: `/opt/homebrew/bin/gitleaks`, symlinked to the Homebrew 8.30.1 package; `gitleaks version` reports **8.30.1**. Installed binary SHA-256: `f414bc2fb952be6c9072b75cb411e3368614ef4b16d48dbd9ad238034afd2302`. No tool was installed or upgraded. Go build metadata could not be queried because `go` is not installed; this does not authenticate the Homebrew binary against the release asset. Hosted Linux uses a different platform binary and must retain its own pinned checksum.

Official tag `v8.30.1` resolves to commit `83d9cd684c87d95d656c1458ef04895a7f1cbd8e`, as returned by the [GitHub tag-ref endpoint](https://api.github.com/repos/gitleaks/gitleaks/git/ref/tags/v8.30.1). All source references below are pinned to that commit. The existing 17-occurrence classification remains in `plan/exec/reports/08-scan-preflight.md`; this task checks configuration semantics, not those classifications again.

## Supported configuration structure

The top-level plural `[[allowlists]]` syntax supports `targetRules`; rule-local `[[rules.allowlists]]` is also supported. Arrays are appended when extending the built-in configuration. The preferred route here is top-level targeted allowlists, leaving `[extend] useDefault = true` and every stock detection rule intact. No copied rule regex, disabled rule, or full-file exclusion is needed. [Official configuration documentation](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/README.md#configuration)

The following is a **non-executable placeholder shape**, not the proposed patch:

```toml
[[allowlists]]
targetRules = ["<diagnosed-rule-id>"]
condition = "AND"
regexTarget = "secret"
paths = ['''^<escaped-exact-repository-relative-path>$''']
regexes = ['''^<escaped-exact-captured-Secret>$''']
```

`config/config.go:228–277` routes top-level entries with targetRules into only those named rules after extension; they are not added to the global allowlist roster. Unknown target rule IDs fail loading. At `:318–358`, `secret` is explicitly accepted and normalized to the default secret target; `AND` is accepted and missing condition defaults to OR. At `:450–477`, rule extension inherits stock attributes unless explicit overrides are supplied. Targeted top-level entries avoid such overrides altogether. [Parser and extension source](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/config.go#L228-L277)

The diagnosed groups require separate entries or equivalently narrow independently reviewed clauses:

| Group | Exact diagnosed rule | Allowed path aliases from scan-preflight | Occurrences |
|---|---|---|---:|
| H4 | generic-api-key | V4M, V4R | 10 |
| HN | generic-api-key | V1C, V1S | 2 |
| HO | generic-api-key | V1C, V1S | 2 |
| D | generic-api-key | V1P | 2 |
| T | github-pat | V4C | 1 |

Do not combine all five values and all six paths into one entry: that creates unreviewed cross-product permissions. HN and HO may share the same two path choices, but separate groups make the accepted scope auditable. The existing synthetic OpenAI fixture exception is separate and should not be broadened by this work.

## Exact path/value and AND behavior

Paths and content are regular expressions, not literal comparisons. Escape metacharacters and anchor both ends for each permitted literal. Each list is internally OR: one approved path may match, and one approved value may match; AND combines those criterion types. The source assembles lists as regex alternations and uses MatchString, so unanchored entries allow substrings. Explicit per-entry anchors avoid accidental suffix-path or partial-value matches. [Allowlist evaluation](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/allowlist.go#L104-L158), [alternation construction](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/utils.go#L28-L39)

The default build uses Go's regexp package; the alternative build tag uses go-re2. Use ordinary Go/RE2-compatible literal escaping and anchors, with no lookaround or inline multiline/case-fold flags. Exact path case should remain significant. [Standard-library wrapper](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/regexp/stdlib_regex.go), [alternative wrapper](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/regexp/wasilibs_regex.go)

## Multiple findings on one line

The detector loops over each regex match, extracts that match's Secret, applies allowlist tests to that individual finding, and appends remaining findings. AND entries containing regexes defer early commit/path skipping until finding evaluation. Therefore exact-path AND exact-secret exceptions do not inherently suppress another distinct captured secret on the same line. In contrast, `regexTarget = "line"` tests shared line content and can exempt several findings when one approved value occurs there; do not use it for this correction. `match` targets the rule's full match rather than its extracted Secret and would require a different approved value contract. [Detector source, extraction and allowlist checks](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go#L452-L567)

Fingerprints contain commit/path/rule/start-line but omit columns. Two findings on one line can share one fingerprint. Preserve the 17-element occurrence roster using commit, file, rule, start/end lines and columns, plus captured-value digest where available; do not collapse findings by fingerprint. `.gitleaksignore` fingerprint suppression would be too coarse here. [Fingerprint assignment](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/detect/detect.go#L710-L744)

## Limits the controls must preserve

1. **No line/column selectors exist in this allowlist schema.** The proposed narrow mechanism is rule + exact path + exact captured value. It does not encode “exactly these 17 historical coordinates” and will also exempt an identical value under the same rule in the same allowed path if encountered again. A claim of exactly 17 suppressions must come from comparing scans on the frozen public-ref roster, not configuration syntax alone. The schema exposes commits, paths, regexes and stopwords, without finding coordinates. [Allowlist schema](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/allowlist.go#L27-L57)
2. **Capture boundaries govern value controls.** The stock github-pat rule captures exactly the prefix plus 36 alphanumeric characters: 40 characters total, even when more characters follow in source. An appended source suffix may therefore leave the captured Secret unchanged and still match its exact allowlist. Tests must assert original scanner captures before assigning expected suppression outcomes. A changed captured value must remain detectable; source-only extensions outside the capture cannot prove that property. The generic rule has its own capture/entropy/context requirements. [Stock generic rule](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/gitleaks.toml#L637-L662), [stock GitHub rule](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/config/gitleaks.toml#L2158-L2167)
3. **CLI defaults come from the executable/source, not the README transcript.** The installed help and `cmd/root.go:91` both set max-decode-depth to 5; the README's captured help text says 0. Keep the original scan flags and actual defaults fixed across the before/after comparison. The installed CLI and `cmd/root.go:77` support `--report-path -` for stdout, avoiding the earlier `/dev/stdout` path issue. Redact or consume classified-only native captures privately; never print unknown matches. [Native CLI flag source](https://github.com/gitleaks/gitleaks/blob/83d9cd684c87d95d656c1458ef04895a7f1cbd8e/cmd/root.go#L75-L93)
4. **Source inspection is not native control evidence.** Root still needs the actual candidate configuration, immutable same-scope 17→0 comparison, changed-path/value/same-line stock-rule controls, preserved original logs, and both independent reviews. No baseline waiver, inline allow comment, rule-disable option, historical edit or blanket exclusion is justified by this report.

## Disposition and spend

The versioned API supports the intended narrower exception shape. Implementation and acceptance remain root-owned after Task 05. This fact check performed local binary/help inspection and read-only retrieval of official Gitleaks documentation/source; it created no candidate config, test implementation, scan output or model subprocess. A guessed `regexp/regexp.go` URL returned 404; the official directory listing identified the two actual wrappers above. The missing Go metadata tool and stale README help text are retained verification limits, not hidden successful checks.
