"""Offline dry demo of the code-editing loop — no network, no API key.

Shows the standalone runner actually EDIT code: a tiny repo ships a bug (`add` returns a-b) and a real
failing pytest gate. A deterministic fixed-diff provider stands in for an LLM; the loop asks it for a
unified diff, applies it via the edit worker, re-runs the real gate, and reaches PASS. This is the one
thing prose can't show — proof the loop changes files and verifies the change deterministically.

Run:  python scripts/edit_demo.py
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from evalopt_graph.generation import make_diff_generation_hook
from evalopt_graph.graph import RunContext, run_loop
from evalopt_graph.state import new_state

_FIX_DIFF = (
    "--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n-    return a - b\n+    return a + b\n"
)


class _FixedDiffProvider:
    """Deterministic stand-in for an LLM: always returns the fix as a fenced unified diff."""

    def complete(self, system, prompt, *, tag=None, **kw):
        return f"```diff\n{_FIX_DIFF}```"


def main() -> None:
    tmp = Path(tempfile.mkdtemp())
    (tmp / "calc.py").write_text("def add(a, b):\n    return a - b\n")  # the bug
    (tmp / "tests").mkdir()
    (tmp / "tests" / "test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    (tmp / "pyproject.toml").write_text("[tool.ruff]\n")
    for args in (
        ["init", "-q"],
        ["add", "-A"],
        ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "i"],
    ):
        subprocess.run(["git", "-C", str(tmp), *args], check=True, capture_output=True, text=True)

    print("=== EDIT DEMO: loop edits a RED repo to GREEN via the --edit-worker diff hook ===")
    before = (tmp / "calc.py").read_text().strip()
    print(f"before: {before}   (add(2,3) -> {2 - 3}, test expects 5 -> RED)")

    ctx = RunContext(provider=_FixedDiffProvider(), generation_hook=make_diff_generation_hook())
    state = new_state("make add() correct so the tests pass", str(tmp), required_gates=["tests"])
    final = run_loop(state, ctx)

    after = (tmp / "calc.py").read_text().strip()
    print(f"after:  {after}   (the loop applied a diff and re-ran the real pytest gate)")
    print(f"stop_reason: {final.get('stop_reason')}   iterations: {final.get('iteration')}")
    ok = str(final.get("stop_reason")) in ("pass", "pass_with_warnings") and "a + b" in after
    print(
        "RESULT: the loop edited the file and reached PASS through the deterministic gate. OK"
        if ok
        else "RESULT: FAILED"
    )
    if not ok:
        raise SystemExit(1)
    print("\nEDIT DEMO PASSED")


if __name__ == "__main__":
    main()
