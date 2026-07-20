"""Deprecated standalone compatibility runner for the governance kernel.

Defaults are fully offline: ``--provider mock`` and ``--backend pure`` need no API key and no
optional dependency. ``--simulate`` injects a fake gate runner for deterministic demonstrations.

Examples:
    evalopt --repo . --task "Fix the failing checkout tests"
    evalopt --repo . --task "Implement password reset" --max-iters 8
    evalopt --repo . --task demo --simulate --simulate-fail 2   # show the reflection loop
    evalopt --repo . --task demo --simulate --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

from . import __version__
from .checks import CommandResult
from .codex_bridge import CodexConfig
from .graph import RunContext, node_project_scan, node_tool_router, run_loop
from .providers import get_provider
from .state import new_state


def _simulated_runner(fail_first: int):
    """Return a fake gate runner: FAIL for the first ``fail_first`` calls per gate, then PASS."""
    counts: dict[str, int] = {}

    def runner(gate: str, command: str, cwd: str) -> CommandResult:
        counts[gate] = counts.get(gate, 0) + 1
        if counts[gate] <= fail_first:
            return CommandResult(gate, command, 1, "FAIL", f"simulated failure #{counts[gate]}")
        return CommandResult(gate, command, 0, "PASS", "simulated pass")

    return runner


def _simulated_argv_runner(gate: str, argv: list[str], cwd: str) -> CommandResult:
    """Offline stub for optional (argv) gates under --simulate: deterministic PASS, runs nothing."""
    from .checks import safe_quote_argv

    return CommandResult(gate, safe_quote_argv(argv), 0, "PASS", "simulated optional-gate pass")


def _progress(state: dict) -> None:
    node = state.get("_node", "?")
    last = state.get("verification_results") or []
    last_status = ",".join(f"{r.get('gate')}={r.get('result')}" for r in last) or "-"
    print(
        f"  [iter {state.get('iteration')}/{state.get('max_iterations')}] node={node} gates={last_status}",
        file=sys.stderr,
    )


_GATE_ALIASES = {
    "test": "tests",
    "tests": "tests",
    "lint": "lint",
    "typecheck": "typecheck",
    "type": "typecheck",
    "build": "build",
}


def _parse_gates(threshold: str | None) -> list[str] | None:
    """Parse --threshold as a gate list. Accepts a single gate ("lint") or a '+'-joined list
    ("tests+lint+typecheck"). Returns None for a numeric rubric threshold or an unrecognized value
    (the caller handles the numeric case and warns on garbage)."""
    if not threshold:
        return None
    parts = [p.strip() for p in threshold.split("+") if p.strip()]
    if parts and all(p in _GATE_ALIASES for p in parts):
        return [_GATE_ALIASES[p] for p in parts]
    return None  # numeric threshold or garbage handled by the caller


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="evalopt", description="evalopt compatibility host")
    ap.add_argument("--version", action="version", version=f"evalopt {__version__}")
    ap.add_argument("--task", required=True, help="the task to accomplish")
    ap.add_argument("--repo", default=".", help="path to the target repository (default: .)")
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic", "openai"])
    ap.add_argument("--backend", default="pure", choices=["pure", "langgraph"])
    ap.add_argument("--max-iters", type=int, default=6)
    ap.add_argument("--quality-threshold", type=float, default=0.90)
    ap.add_argument(
        "--threshold",
        default=None,
        help="required gates, e.g. tests+lint+typecheck (or a numeric rubric threshold)",
    )
    ap.add_argument(
        "--simulate",
        action="store_true",
        help="use a fake gate runner instead of real commands (offline demo)",
    )
    ap.add_argument(
        "--simulate-fail",
        type=int,
        default=0,
        help="with --simulate: fail the first N runs per gate (demo the reflection loop)",
    )
    ap.add_argument(
        "--mock-score",
        type=float,
        default=0.95,
        help="mock provider rubric score (use <0.90 to force a fail path)",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="write .evalopt/ contract, config, state and run trace into the repo",
    )
    ap.add_argument("--json", action="store_true", help="print final state as JSON to stdout")
    ap.add_argument("--quiet", action="store_true", help="suppress per-node progress")
    ap.add_argument(
        "--codex",
        default="off",
        choices=["off", "review", "adversarial"],
        help="read-only Codex compatibility review mode; host runtimes own patch scheduling",
    )
    ap.add_argument(
        "--codex-full-access",
        action="store_true",
        help="HIGH RISK: allow Codex danger-full-access (no sandbox). Off by default.",
    )
    ap.add_argument(
        "--edit-worker",
        default="off",
        choices=["off", "diff"],
        help="code-editing worker: 'diff' lets the provider emit+apply unified diffs (real edits)",
    )
    ap.add_argument("--risk", default="low", choices=["low", "med", "high"], help="task risk level")
    ap.add_argument(
        "--diff-base",
        default="auto",
        help="git base for diff-scoping optional gates (auto|<ref>, e.g. origin/main)",
    )
    ap.add_argument(
        "--no-tool-router",
        action="store_true",
        help="disable the tool router (no optional gates / research / browser planning)",
    )
    ap.add_argument(
        "--no-optional-gates",
        action="store_true",
        help="plan optional gates but do not execute them (decision is still recorded)",
    )
    ap.add_argument(
        "--plan-tools",
        action="store_true",
        help="print the tool-router decision for the repo (project_scan + tool_router) and exit",
    )
    ap.add_argument(
        "--mode",
        default="build",
        choices=["build", "research", "mixed"],
        help="task family: build (default), research (evidence synthesis), or mixed",
    )
    ap.add_argument(
        "--max-research-rounds", type=int, default=4, help="research-mode round ceiling (default 4)"
    )
    ap.add_argument(
        "--research-question",
        action="append",
        default=None,
        dest="research_questions",
        help="a research question to cover (repeatable). Defaults to the task + criteria.",
    )
    ap.add_argument(
        "--no-epistemic",
        action="store_true",
        help="disable the epistemic governor (claims/contradictions/adjudication)",
    )
    ap.add_argument(
        "--unattended",
        action="store_true",
        help="overnight mode: never wait for human input; defer risky actions; write a morning report",
    )
    ap.add_argument("--overnight", action="store_true", help="alias for --unattended")
    ap.add_argument(
        "--max-wall-clock-hours", type=float, default=8.0, help="unattended wall-clock budget (default 8h)"
    )
    ap.add_argument("--autonomy", default="high", choices=["low", "medium", "high"], help="autonomy level")
    return ap


def _bench_prep_main(argv: list[str]) -> int:
    del argv
    print("ERROR: local SWE-bench preparation was removed; use the official Docker harness.", file=sys.stderr)
    return 2


def _bench_main(argv: list[str]) -> int:
    return _bench_prep_main(argv)


def main(argv: list[str] | None = None) -> int:
    raw = argv if argv is not None else sys.argv[1:]
    if raw and raw[0] == "bench":
        return _bench_main(raw[1:])
    args = build_arg_parser().parse_args(argv)
    repo = os.path.abspath(args.repo)

    # --threshold is either a gate list (tests+lint) or a numeric rubric threshold (0.95).
    required_gates = _parse_gates(args.threshold)
    quality_threshold = args.quality_threshold
    if args.threshold and required_gates is None:
        try:
            quality_threshold = float(args.threshold)
        except ValueError:
            print(
                f"WARNING: --threshold '{args.threshold}' is neither a gate list "
                "(tests+lint+typecheck) nor a number — ignored.",
                file=sys.stderr,
            )

    router_config = {"tool_router": {"enabled": not args.no_tool_router, "diff_base": args.diff_base}}
    epistemic_config = {"epistemic_governor": {"enabled": not args.no_epistemic}}
    unattended_on = args.unattended or args.overnight
    if args.backend == "langgraph":
        print(
            "ERROR: --backend langgraph was removed because it never reached behavioral parity; "
            "use the pure host adapter and stable kernel API.",
            file=sys.stderr,
        )
        return 2
    unattended_cfg = {
        "enabled": unattended_on,
        "autonomy_level": args.autonomy,
        "max_wall_clock_hours": args.max_wall_clock_hours,
    }
    # In unattended mode use the larger overnight budgets unless the user overrode them on the CLI.
    max_iters = args.max_iters
    max_research_rounds = args.max_research_rounds
    if unattended_on:
        if max_iters == 6:
            max_iters = 12
        if max_research_rounds == 4:
            max_research_rounds = 6
    state = new_state(
        args.task,
        repo,
        max_iterations=max_iters,
        required_gates=required_gates,
        quality_threshold=quality_threshold,
        risk=args.risk,
        tool_router_config=router_config,
        mode=args.mode,
        epistemic_config=epistemic_config,
        max_research_rounds=max_research_rounds,
        research_questions=args.research_questions,
        unattended=unattended_cfg,
    )

    provider = (
        get_provider(args.provider, score=args.mock_score)
        if args.provider == "mock"
        else get_provider(args.provider)
    )
    runner = _simulated_runner(args.simulate_fail) if args.simulate else None

    # Codex config from CLI flags (the skill/.evalopt config use 'auto' by default).
    codex_cfg = CodexConfig(
        enabled=args.codex != "off",
        mode=args.codex,
        full_access_allowed=args.codex_full_access,
    )
    if args.codex_full_access:
        print("WARNING: Codex danger-full-access enabled — no sandbox. High risk.", file=sys.stderr)
    # Read-only model review is not an edit worker. Without one, a red build remains red.
    if args.provider != "mock" and args.edit_worker == "off" and args.mode != "research":
        print(
            "NOTE: --provider "
            f"{args.provider} powers the rubric/planning only. With no code-editing worker the standalone "
            "runner does not edit files — use --edit-worker diff or an embedding host that supplies "
            "a generation_hook to change code.",
            file=sys.stderr,
        )

    # A run dir is created when writing artifacts OR when Codex is enabled (to capture its logs).
    # The knowledge ledger lives at .evalopt/knowledge (shared, append-only) when --write is set.
    run_dir = None
    knowledge_dir = None
    if args.write or codex_cfg.enabled or unattended_on:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = os.path.join(repo, ".evalopt", "runs", ts)
        os.makedirs(run_dir, exist_ok=True)
    if args.write or unattended_on:
        knowledge_dir = os.path.join(repo, ".evalopt", "knowledge")
        os.makedirs(knowledge_dir, exist_ok=True)

    from .generation import make_diff_generation_hook

    generation_hook = make_diff_generation_hook() if args.edit_worker == "diff" else None

    ctx = RunContext(
        provider=provider,
        runner=runner if runner else RunContext().runner,
        on_progress=None if args.quiet else _progress,
        generation_hook=generation_hook,
        codex=codex_cfg,
        run_dir=run_dir,
        router_config=router_config,
        argv_runner=_simulated_argv_runner if args.simulate else RunContext().argv_runner,
        execute_optional_gates=not args.no_optional_gates,
        docker_enabled="auto",
        epistemic_config=epistemic_config,
        knowledge_dir=knowledge_dir,
    )

    # --plan-tools: deterministic planning only (no gates executed, no LLM loop) — for inspection.
    if args.plan_tools:
        s = node_project_scan(state, ctx)
        s = node_tool_router(s, ctx)
        print(json.dumps(s.get("router_decision", {}), indent=2, default=str))
        return 0

    final = run_loop(state, ctx)

    if args.write:
        _write_artifacts(final, repo, run_dir)

    outcome = {
        "pass": "PASS",
        "pass_with_warnings": "PASS_WITH_WARNINGS",
        "blocked_human_gate": "BLOCKED",
        "stuck_repeated_failure": "BLOCKED",
        "failed_max_iters": "FAILED_MAX_ITERS",
        "research_synthesis": "RESEARCH_SYNTHESIS",
        "research_rounds_exhausted": "RESEARCH_SYNTHESIS",
        "blocked_unverified_central_claim": "BLOCKED_UNVERIFIED",
        "wall_clock_exhausted": "WALL_CLOCK",
        "completed_with_deferred_actions": "DEFERRED",
        "crashed_mid_iteration": "CRASHED",
    }.get(str(final.get("stop_reason")), str(final.get("stop_reason")))

    if args.json:
        print(json.dumps({k: v for k, v in final.items() if not k.startswith("_")}, indent=2, default=str))
    elif final.get("mode") == "research":
        print(
            f"\nOutcome: {outcome}  ({final.get('research_round')}/{final.get('max_research_rounds')} rounds)"
        )
        print(f"Summary: {final.get('final_summary')}")
        print("\n" + (final.get("research_report") or "(no report)"))
    else:
        print(f"\nOutcome: {outcome}")
        print(f"Stop reason: {final.get('stop_reason')}")
        print(f"Iterations: {final.get('iteration')}/{final.get('max_iterations')}")
        print(f"Summary: {final.get('final_summary')}")
        print(f"Gates: {[(r.get('gate'), r.get('result')) for r in final.get('verification_results', [])]}")
        adj = final.get("adjudication", {}) or {}
        if adj:
            print(
                f"Adjudication: confirmed={len(adj.get('confirmed_facts', []))} "
                f"central_unverified={adj.get('central_unverified', [])} blocks_pass={adj.get('blocks_pass', False)}"
            )

    # Only claim a morning report when one was actually written (the pure backend's _unattended_finish
    # sets it). This avoids printing a misleading path when unattended behavior did not run.
    if final.get("morning_report") and not args.json:
        mr = os.path.join(repo, ".evalopt", "overnight", "MORNING_REPORT.md")
        print(f"Morning report: {mr}")
        bd = final.get("blocked_decisions", []) or []
        print(
            f"Blocked (deferred) decisions: {len(bd)} · parked branches: {len(final.get('parked_branches', []))}"
        )

    return 0 if outcome in ("PASS", "PASS_WITH_WARNINGS", "RESEARCH_SYNTHESIS", "DEFERRED") else 1


def _write_artifacts(final: dict, repo: str, run_dir: str | None = None) -> None:
    base = os.path.join(repo, ".evalopt")
    if run_dir is None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        run_dir = os.path.join(base, "runs", ts)
    os.makedirs(run_dir, exist_ok=True)
    # Materialize the tunable config template into the repo (once), so the file the Layer-1 skill reads
    # actually exists after --write. The standalone runner itself is configured via CLI flags, not this file.
    cfg_path = os.path.join(base, "config.yaml")
    if not os.path.exists(cfg_path):
        try:
            from importlib.resources import files

            tmpl = files("evalopt_graph.templates").joinpath("config.yaml").read_text(encoding="utf-8")
            with open(cfg_path, "w", encoding="utf-8") as fh:
                fh.write(tmpl)
        except Exception:
            pass
    with open(os.path.join(base, "quality_contract.md"), "w", encoding="utf-8") as fh:
        fh.write(final.get("quality_contract", ""))
    with open(os.path.join(base, "state.json"), "w", encoding="utf-8") as fh:
        json.dump({k: v for k, v in final.items() if not k.startswith("_")}, fh, indent=2, default=str)
    with open(os.path.join(run_dir, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write(
            f"# Run\n\n- Stop: {final.get('stop_reason')}\n- {final.get('final_summary')}\n"
            f"- Codex calls: {final.get('codex_calls_total', 0)}\n"
        )
    with open(os.path.join(run_dir, "trace.jsonl"), "w", encoding="utf-8") as fh:
        for t in final.get("router_trace", []):
            fh.write(json.dumps({"node": "tool_router", **t}, default=str) + "\n")
        for r in final.get("verification_results", []):
            fh.write(json.dumps({"node": "verification", **r}, default=str) + "\n")
        for n in final.get("codex_notes", []):
            fh.write(json.dumps({"node": "codex", "note": n}, default=str) + "\n")
    with open(os.path.join(run_dir, "router_decision.json"), "w", encoding="utf-8") as fh:
        json.dump(final.get("router_decision", {}), fh, indent=2, default=str)


if __name__ == "__main__":
    raise SystemExit(main())
