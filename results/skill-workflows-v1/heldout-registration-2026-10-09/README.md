# Held-out registration

Registration identity: `bd8bc5e42717a26570055db5896fb880ba92c7dc5725b3bcaca330d3abed4f8e`.
This is SHA-256 of compact, sorted JSON for [heldout-lock.json](heldout-lock.json).

The [manifest](manifest.json) and [schedule](evidence/schedule.json) freeze 48 tasks
across six categories, three arms and three attempts: 432 planned trials. Arm
order is randomized within task/repetition blocks using seed `20261008`.
This registration contains no workflow results.

The source is commit `31231949412ea6d0101331720c0f0ed2d9f50b46`, with exact
[source identities](source-lock.json). The controller checks this frozen source,
task bytes, runtime images, regrade evidence and subscription allowance before
dispatch. The [protocol](../../../bench/harbor/skill-workflows-v1/PROTOCOL.md)
defines the outcome and claim rules; the
[accounting policy](accounting-policy.json) retains partial values as lower bounds
and prohibits efficiency claims from incomplete accounting.

The [pilot review](pilot-review.json) follows the completed
[development pilot](../development-pilot-2026-10-09/README.md) and
[regrade receipt](pilot-regrade-receipt.json). It is a maintainer-controlled review,
not independent human validation.

These files are exact copies from the private frozen campaign. Sealed task
contents and local source paths are withheld during execution. The lock binds
those private inputs by hash, but this registration alone is insufficient to
replay them. The later outcome package must retain the full sanitized evidence
needed for reproduction. Hashes identify bytes; they do not authenticate the
producer.
