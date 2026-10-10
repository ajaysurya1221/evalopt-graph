# Public-source reproduction

The [receipt](public-source-reproduction-01.json) records successful offline
reproduction of public commit `f5154567100a61ec9ab8769c01e27c3e7f0644a4` from a
fresh anonymous clone. A fresh CPython 3.13.12 virtual environment had no installed
distributions; replay ran with an empty environment and isolated imports.

The [retained output](public-source-reproduction-01-output.json) reproduces the
pilot package identity, original outcomes, policy decisions, regrade results and
overhead arithmetic. Its byte hash is recorded in the receipt. The fetched
checkout remained clean.

The [hosted CI observation](hosted-ci.json) records successful jobs on that exact
commit, including the separate workflow benchmark lane and stable-kernel matrix.
It links directly to the public run; it is not evidence of an agent-performance
advantage. Later commits need their own CI result.

This is maintainer-run reproduction of supplied artifacts. It performs no model
calls or candidate execution and does not establish independent agent replication
or authenticate the producer's observations.
