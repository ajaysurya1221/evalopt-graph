from __future__ import annotations

import importlib.util
import os

from evalopt_graph import epistemic
from evalopt_graph.claim_ledger import ClaimLedger
from evalopt_graph.governance import unverified_central_claims


def test_unverified_central_claims_reports_only_unusable_central(tmp_path):
    kdir = str(tmp_path / "knowledge")
    led = ClaimLedger(knowledge_dir=kdir)
    led.add_claim(
        "secure auth token flow", type="security_claim", source_type="claude_inference", central=True
    )
    led.add_claim("confirmed fact", type="code_fact", source_type="user", central=True)  # user -> confirmed
    led.add_claim("noncentral note", type="model_inference", source_type="claude_inference", central=False)
    out = unverified_central_claims(kdir, now=epistemic.now_iso())
    texts = {c["text"] for c in out}
    assert "secure auth token flow" in texts
    assert "confirmed fact" not in texts
    assert "noncentral note" not in texts
    assert any(c["critical"] for c in out)


def test_unverified_central_claims_empty_when_no_dir(tmp_path):
    assert unverified_central_claims(str(tmp_path / "nope")) == []


def _load_stop_hook():
    path = os.path.join(
        os.path.dirname(__file__), "..", "claude_assets", "hooks", "stop_central_claim_check.py"
    )
    spec = importlib.util.spec_from_file_location("stop_hook", os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_stop_hook_blocks_on_unverified_central(tmp_path):
    kdir = str(tmp_path / ".evalopt" / "knowledge")
    led = ClaimLedger(knowledge_dir=kdir)
    led.add_claim(
        "secure auth token flow", type="security_claim", source_type="claude_inference", central=True
    )
    hook = _load_stop_hook()
    out = hook.stop_output(str(tmp_path))
    assert out.get("decision") == "block"
    assert "central" in out.get("reason", "").lower()


def test_stop_hook_silent_when_clean(tmp_path):
    hook = _load_stop_hook()
    assert hook.stop_output(str(tmp_path)) == {}
