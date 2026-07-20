"""Nested checkers — independent verification that cites logs/files/commands/claim IDs, never a
model summary. Each returns a structured result persisted under ``.evalopt/runs/<ts>/checkers/``.

No checker may rely only on another model's summary; every ``passed`` verdict carries citations
(claim ids, gate names + exit codes, file paths, repro commands).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from . import epistemic
from .claim_ledger import ClaimLedger


@dataclass
class CheckerResult:
    name: str
    passed: bool
    citations: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evidence_checker(ledger: ClaimLedger) -> CheckerResult:
    """Every CENTRAL claim must have at least one relevant NON-MODEL supporting source."""
    issues, citations = [], []
    for c in ledger.central_claims():
        if not epistemic.has_nonmodel_support(c, ledger.sources):
            issues.append(f"central claim {c.id} has only model-generated support: {c.text[:80]}")
        else:
            citations.append(f"{c.id}<-{','.join(c.evidence_refs)}")
    return CheckerResult("evidence_checker", passed=not issues, citations=citations, issues=issues)


def patch_checker(state: dict[str, Any]) -> CheckerResult:
    """The patch must address the task and must NOT have weakened tests."""
    issues, citations = [], []
    changed = state.get("changed_files", []) or []
    if state.get("tests_weakened"):
        issues.append("tests were weakened/deleted/skipped (anti-gaming flag set)")
    if not changed:
        issues.append("no files changed — patch did not address the task")
    else:
        citations.append(f"changed_files={changed[:20]}")
    # cite the test gate result as proof the change was exercised
    for r in state.get("verification_results", []):
        if r.get("gate") == "tests":
            citations.append(f"tests gate={r.get('result')} exit={r.get('exit_code')}")
    return CheckerResult("patch_checker", passed=not issues, citations=citations, issues=issues)


def gate_checker(state: dict[str, Any]) -> CheckerResult:
    """Commands actually ran and pass/fail was interpreted correctly (exit code ⇔ result)."""
    issues, citations = [], []
    for r in state.get("verification_results", []):
        result = str(r.get("result", "")).upper()
        ec = r.get("exit_code")
        if result == "NOT_CONFIGURED":
            continue
        if ec is None and result not in ("ERROR",):
            issues.append(f"gate {r.get('gate')} has no exit code but result={result}")
        if ec == 0 and result not in ("PASS",):
            issues.append(f"gate {r.get('gate')} exit 0 but result={result} (misinterpreted)")
        if isinstance(ec, int) and ec != 0 and result == "PASS":
            issues.append(f"gate {r.get('gate')} nonzero exit {ec} but result=PASS (misinterpreted)")
        citations.append(f"{r.get('gate')}:exit={ec}:result={result}")
    return CheckerResult("gate_checker", passed=not issues, citations=citations, issues=issues)


def context_checker(pack_text: str, ledger: ClaimLedger) -> CheckerResult:
    """The retrieval pack must not carry stale/contradicted/unverified claims as premises."""
    import re

    ids = sorted(set(re.findall(r"\[(c\d+)\]", pack_text or "")))
    bad = []
    for cid in ids:
        c = ledger.get_claim(cid)
        if c is not None and c.status not in epistemic.USABLE_STATUSES:
            bad.append(f"{cid} status={c.status}")
    return CheckerResult(
        "context_checker",
        passed=not bad,
        citations=[f"pack_claim_ids={ids}"],
        issues=[f"non-usable claim in pack: {b}" for b in bad],
    )


def final_checker(state: dict[str, Any]) -> CheckerResult:
    """The final report must separate confirmed facts / assumptions / blocked actions / unresolved."""
    issues, citations = [], []
    adj = state.get("adjudication", {}) or {}
    report = state.get("research_report", "") or state.get("final_adjudication", "") or ""
    if (
        "blocked" not in report.lower()
        and not state.get("blocked_decisions")
        and not state.get("mode") == "research"
    ):
        # build runs without blocks may legitimately omit; only flag when blocks exist but unreported
        pass
    if state.get("blocked_decisions") and "block" not in report.lower():
        issues.append("blocked decisions exist but are not surfaced in the final report")
    if adj:
        citations.append(
            f"confirmed={len(adj.get('confirmed_facts', []))} assumptions={len(adj.get('assumptions', []))} "
            f"unresolved={len(adj.get('unresolved_contradictions', []))} blocked={len(state.get('blocked_decisions', []))}"
        )
    else:
        issues.append("no adjudication present in final state")
    return CheckerResult("final_checker", passed=not issues, citations=citations, issues=issues)


def run_all(state: dict[str, Any], ledger: ClaimLedger, *, pack_text: str = "") -> dict[str, dict[str, Any]]:
    """Run every checker and return name -> result dict (for persistence under checkers/)."""
    return {
        "evidence_checker": evidence_checker(ledger).to_dict(),
        "patch_checker": patch_checker(state).to_dict(),
        "gate_checker": gate_checker(state).to_dict(),
        "context_checker": context_checker(pack_text, ledger).to_dict(),
        "final_checker": final_checker(state).to_dict(),
    }
