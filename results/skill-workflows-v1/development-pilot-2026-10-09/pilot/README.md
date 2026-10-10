# Offline amended pilot evidence candidate

This local candidate wraps unchanged pilot evidence with an explicit partial-accounting amendment. The exporter does not upload files.

Use the registered controller source and CPython 3.13.12:

```sh
python bench/harbor/skill-workflows-v1/amended_publish.py verify /path/to/bundle
```

[Resource report](resource-report.json), [amendment](amendment.json), [claim limits](CLAIMS.md), and [original pilot evidence](pilot/README.md). Public checks replay policy decisions, original outcome analysis and resource arithmetic. Raw native logs, local source paths and authentication data are excluded. Hashes establish content identity, not authentication or independent raw-log replay. The bounded sensitive-content scan is not proof that every possible secret was recognized.
