# Transfer evidence candidate

This offline candidate contains allowlisted controller reward projections and retained identities. Raw stopped archives, private paths, authentication and trajectories are excluded. The projection is explicitly recorded in each retained transfer result; no hash-bound artifact is silently redacted.

Verify with the registered source and CPython 3.13.12 exactly:

    python bench/harbor/skill-workflows-v1/transfer_publish.py verify /path/to/bundle

The bounded sensitive-content scanner is a publication check, not a proof that every possible secret has been detected. See CLAIMS.md for reproduction limits.
