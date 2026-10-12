#!/usr/bin/env bash
set -euo pipefail
: "${RUN_ARTIFACTS:?private artifact directory required}"
: "${UV_BIN:?isolated uv0.11.29 executable required}"
[[ "$($UV_BIN --version)" == uv\ 0.11.29* ]]
mkdir -p "$RUN_ARTIFACTS"
"$UV_BIN" lock --check
"$UV_BIN" sync --frozen --extra dev
export PATH="$PWD/.venv/bin:$PATH"
"$UV_BIN" run --frozen --extra dev python scripts/verify_workflow_pins.py
"$UV_BIN" run --frozen --extra dev python scripts/verify_test_count.py --minimum 408
"$UV_BIN" run --frozen --extra dev python -m compileall -q src tests scripts
"$UV_BIN" run --frozen --extra dev ruff check src tests scripts
"$UV_BIN" run --frozen --extra dev ruff format --check src tests scripts
"$UV_BIN" run --frozen --extra dev python -m pytest -p no:cacheprovider
"$UV_BIN" run --frozen --extra dev python scripts/edit_demo.py
"$UV_BIN" run --frozen --extra dev python scripts/epistemic_demo.py
"$UV_BIN" run --frozen --extra dev python scripts/unattended_demo.py
"$UV_BIN" run --frozen --extra dev python scripts/provenance_benchmark.py --out "$RUN_ARTIFACTS/conformance.json"
bash scripts/smoke_test.sh
python3 -B plan/exec/preservation.py
