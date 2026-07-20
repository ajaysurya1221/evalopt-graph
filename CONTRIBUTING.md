# Contributing to evalopt

Thank you for helping make agent acceptance more explicit, inspectable, and reproducible. Contributions
are welcome across the kernel, adapters, tests, documentation, and independently authored conformance
cases.

Please follow the [Code of Conduct](CODE_OF_CONDUCT.md). Report vulnerabilities through the private
process in [SECURITY.md](SECURITY.md), not through an issue or pull request.

## Before opening a change

- Search existing issues and discussions first.
- Use an issue form for bugs or proposals that change behavior.
- Keep model orchestration, tools, retrieval, sandboxes, scheduling, and benchmarks outside the stable
  kernel boundary.
- State the evidence level your change supports. A passing authored case is conformance evidence, not a
  benchmark or general capability result.

Small documentation and test corrections may go directly to a pull request.

## Development setup

```bash
git clone https://github.com/ajaysurya1221/evalopt-graph.git
cd evalopt-graph
uv venv .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

Run the local release checks before submitting:

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

Keep each pull request focused and explain:

1. the problem and intended behavior;
2. whether the change belongs to the kernel or a host adapter;
3. public API or serialized-record compatibility effects;
4. failure modes and trust-boundary implications; and
5. the tests and evidence supporting the change.

Add regression tests for behavior changes. Avoid weakening or deleting existing assertions simply to
make a change pass. Keep generated outputs, local run artifacts, secrets, caches, and environment files
out of commits.

## Stable API and compatibility

The ten names in `evalopt_graph.__all__` are the `v0.1.x` stable API. Changes to their meaning,
serialization, reason codes, or replay behavior require explicit compatibility analysis and release
notes. New root exports are not accepted casually; prefer a focused module-level experimental surface.

The graph, CLI, providers, Codex bridge, research loop, filesystem adapters, and historical lazy root
attributes are deprecated compatibility surfaces for one migration cycle. New features should not grow
those surfaces or create a second acceptance-authority path.

## Commit and review hygiene

- Write clear, imperative commit subjects.
- Keep unrelated formatting and generated changes out of the patch.
- Never commit API keys or credentials, including apparently harmless live keys.
- Treat fake-key fixtures as narrowly scoped test data and label them clearly.
- Expect CI to test supported Python versions, inspect built artifacts, scan secrets, and exercise a
  clean-wheel install.

By participating, you agree that your contributions are licensed under the repository's
[MIT License](LICENSE).
