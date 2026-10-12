# Contributing to evalopt

Standalone feature development of evalopt has ended. The repository preserves the acceptance kernel
and its research record; see the notice at the top of the [README](README.md), the
[migration map](docs/migration.md) and the [archive decision](docs/decisions/archive-standalone.md).
This guide says what is still accepted.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through the private
process in [SECURITY.md](SECURITY.md), not through an issue or pull request.

## What is accepted

- **Bug reports** against a `0.1.x` release or a named commit, with the version, a minimal
  reproduction and the observed decision, record or traceback. Use the bug report form.
- **Documentation and migration corrections**: factual errors, broken links or missing limits in the
  README, the migration map and its appendices, the portfolio index or the decision records. Use the
  migration or documentation guidance form, or open a focused pull request.
- **Security reports**, privately, through [SECURITY.md](SECURITY.md).

## What is not accepted

- New features, predicate types, policy languages or benchmark programmes.
- New integrations, adapters, converters or host bridges, in the kernel or in the deprecated
  compatibility surfaces ([entry 16 of the migration map](docs/migration.md#the-sixteen-entries)).
- New root exports, or changes to the meaning, serialization, reason codes or replay behavior of the
  ten stable names in `evalopt_graph.__all__`.
- Requests to convert evalopt records into another tool's format, or for Actseal, Dorian, Frontier
  Scout or ARCI to support evalopt semantics. Those projects are independent of evalopt and of each
  other.

A migration question the map does not answer is a documentation issue: say which entry is unclear and
what you checked. Existing issues and pull requests are not closed by this notice.

## Development setup

```bash
git clone https://github.com/ajaysurya1221/evalopt-graph.git
cd evalopt-graph
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Run the local release checks before submitting a fix:

```bash
python -m compileall -q src tests scripts
python -m pytest -q
python -m ruff check src tests scripts
python -m ruff format --check src tests scripts
python scripts/edit_demo.py
python scripts/epistemic_demo.py
python scripts/unattended_demo.py
bash scripts/smoke_test.sh
uv build
```

The compatibility demos require the repository virtual environment to be active so nested `python`
commands resolve correctly.

## Pull requests

Keep each pull request small and tied to an accepted category above. Explain:

1. the problem, and the observed and expected behavior;
2. whether the change touches the stable kernel, a deprecated compatibility surface or documentation;
3. public API or serialized-record compatibility effects, which should be none;
4. failure modes and trust-boundary implications; and
5. the tests and evidence supporting the change.

Add a regression test for a kernel bug fix. Avoid weakening or deleting existing assertions simply to
make a change pass. Keep generated outputs, local run artifacts, secrets, caches, and environment files
out of commits. A passing authored case is conformance evidence, not a benchmark or general capability
result.

## Stable API and compatibility

The ten names in `evalopt_graph.__all__` are the `v0.1.x` stable API. A bug fix must not change their
meaning, serialization, reason codes, or replay behavior without explicit compatibility analysis and
release notes. New root exports are not accepted.

The graph, CLI, providers, Codex bridge, research loop, filesystem adapters, and historical lazy root
attributes are deprecated compatibility surfaces. They receive no feature work, are not stable API or
policy authorities, and must not grow or create a second acceptance-authority path. A bug in one of
them may be documented rather than fixed.

## Commit and review hygiene

- Write clear, imperative commit subjects.
- Keep unrelated formatting and generated changes out of the patch.
- Never commit API keys or credentials, including apparently harmless live keys.
- Treat fake-key fixtures as narrowly scoped test data and label them clearly.
- Expect CI to test supported Python versions, inspect built artifacts, scan secrets, and exercise a
  clean-wheel install.

Review capacity is not guaranteed: an issue or pull request may wait, and no response time is
promised.

By participating, you agree that your contributions are licensed under the repository's
[MIT License](LICENSE).
