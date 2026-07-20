#!/usr/bin/env bash
# Offline smoke test for the Evaluator-Optimizer Graph template.
# Requires NO API keys and does NOT install LangGraph. Uses uv if present, else python venv.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
echo "==> Project: $HERE"

# 1) Environment (isolated). Reuse an existing .venv if present (idempotent re-runs).
if command -v uv >/dev/null 2>&1; then
  echo "==> Using uv"
  [ -d .venv ] || uv venv --python 3 .venv >/dev/null 2>&1 || uv venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -e ".[dev]" >/dev/null
else
  echo "==> uv not found; using python venv"
  [ -d .venv ] || python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install -q --upgrade pip
  python -m pip install -q -e ".[dev]"
fi

# 2) Import check (no langgraph, no API key)
echo "==> Import check"
python -c "import evalopt_graph as e; print('evalopt_graph', e.__version__, 'imported OK')"

# 3) Unit tests
echo "==> Unit tests"
python -m pytest -q

# 4) CLI end-to-end on a throwaway repo (mock provider, simulated gates) — three scenarios
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/pyproject.toml" <<'EOF'
[project]
name = "smoke"
version = "0.0.0"
EOF
mkdir -p "$TMP/tests"
echo "def test_ok(): assert True" > "$TMP/tests/test_ok.py"

echo "==> CLI scenario A: clean pass"
evalopt --repo "$TMP" --task "smoke pass" --simulate --quiet
echo "   exit=$?  (expected 0)"

echo "==> CLI scenario B: reflection loop then pass (fail first 2 runs)"
evalopt --repo "$TMP" --task "smoke recover" --simulate --simulate-fail 2 --max-iters 6 --quiet
echo "   exit=$?  (expected 0)"

echo "==> CLI scenario C: stuck -> blocked (always fails); must terminate, exit!=0"
set +e
evalopt --repo "$TMP" --task "smoke stuck" --simulate --simulate-fail 999 --max-iters 6 --quiet
code=$?
set -e
echo "   exit=$code  (expected non-zero, bounded — no infinite loop)"

echo "==> CLI scenario D: write artifacts"
evalopt --repo "$TMP" --task "smoke write" --simulate --write --quiet >/dev/null
test -f "$TMP/.evalopt/quality_contract.md" && echo "   wrote .evalopt/quality_contract.md OK"
test -f "$TMP/.evalopt/state.json" && echo "   wrote .evalopt/state.json OK"

echo ""
echo "==> SMOKE TEST PASSED"
