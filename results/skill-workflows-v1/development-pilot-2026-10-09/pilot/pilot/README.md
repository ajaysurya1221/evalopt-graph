# Reproducible eval-opt evidence candidate

This folder is an offline publication candidate. It has not been uploaded by the exporter.

Verify retained bytes, policy replay and outcome analysis with the registered source version and CPython 3.13.12 exactly:

```sh
python bench/harbor/skill-workflows-v1/publish_bundle.py verify /path/to/public-bundle
```

See CLAIMS.md for evidence limits. Private Harbor directories, raw conversations, authentication files and readiness-source host paths are excluded. Hash-bound evidence is copied without redaction. A sensitive-content finding prevents export and requires explicit remediation. The bounded scanner is not a proof that every possible secret has been recognized.
