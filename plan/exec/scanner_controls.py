"""Finite native controls for the wind-down scanner correction; not a product API."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import tomllib

BASE = "fc3045dbda29c1d274747329ceb6724a783b0df7"
V4 = "49a379c7001b5b156f9f75b358da03a4367b252e"
V1 = "a352c38a764afeb0f406848ebd14591af21a486b"
VP = "4c5467e1862dec0da5b53b61293e564040d1e5d0"
ROOT = Path(__file__).resolve().parents[2]
G = [
    (
        "H4",
        "generic-api-key",
        V4,
        "429252aed4b6276232a2a509de69c0b779fb21e1a5442cc3ad3721114e284fd3",
        [
            "bench/harbor/skill-workflows-v4/tasks/manifest.json",
            "results/skill-workflows-v4/offline-package-2026-10-12/reviews.json",
        ],
    ),
    (
        "HN",
        "generic-api-key",
        V1,
        "e814041bd09d1fb4f833aa2ca25ec1d2486633e1a2801310dfb4f14c18e0bd9d",
        [
            "results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-tasks/candidate-manifest.json",
            "results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-manifest.json",
        ],
    ),
    (
        "HO",
        "generic-api-key",
        V1,
        "100e5b33df33a7f63fe6697fa70525dedc3de5fb3131224b5633acca8279feac",
        [
            "results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-tasks/candidate-manifest.json",
            "results/skill-workflows-v1/heldout-comparison-2026-10-10/bundle/sealed-manifest.json",
        ],
    ),
    (
        "D",
        "generic-api-key",
        VP,
        "duplicate/unmatched",
        [
            "results/skill-workflows-v1/transfer-comparison-2026-10-10/operations/bounded-continuation/controller/classifier.py"
        ],
    ),
    (
        "T",
        "github-pat",
        V4,
        "gh" + "p_" + "SYNTHETIC" * 4,
        ["results/skill-workflows-v4/offline-package-2026-10-12/compatibility.json"],
    ),
]
FIELDS = ("Commit", "File", "RuleID", "StartLine", "EndLine", "StartColumn", "EndColumn")


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(row):
    return tuple(row.get(k) for k in FIELDS)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--history", type=Path, required=True)
    p.add_argument("--expected", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    env.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull, GIT_TERMINAL_PROMPT="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    binary = Path(shutil.which("gitleaks") or "").resolve()
    require(binary.is_file(), "gitleaks unavailable")
    records = []
    started = time.time()

    def command(name, args, cwd, allowed=(0,)):
        r = subprocess.run([str(x) for x in args], cwd=cwd, env=env, capture_output=True, timeout=180)
        (out / (name + ".stdout")).write_bytes(r.stdout)
        (out / (name + ".stderr")).write_bytes(r.stderr)
        records.append({"name": name, "argv": [str(x) for x in args], "cwd": str(cwd), "exit": r.returncode})
        (out / "commands.json").write_text(json.dumps(records, indent=2) + "\n")
        require(r.returncode in allowed, f"{name}: unexpected exit {r.returncode}")
        return r.stdout

    original = command("original-config", ["git", "show", BASE + ":.gitleaks.toml"], ROOT)
    candidate = (ROOT / ".gitleaks.toml").read_bytes()
    original_path = out / "original.toml"
    original_path.write_bytes(original)
    candidate_path = out / "candidate.toml"
    candidate_path.write_bytes(candidate)
    old = tomllib.loads(original.decode())
    new = tomllib.loads(candidate.decode())
    require(candidate.startswith(original), "original configuration prefix changed")
    require(set(new) == set(old), "top-level configuration widened")
    require(new["extend"] == old["extend"] == {"useDefault": True}, "stock extension changed")
    require(len(new["allowlists"]) == len(old["allowlists"]) + 5, "allowlist roster drift")
    require(new["allowlists"][: len(old["allowlists"])] == old["allowlists"], "existing exception changed")
    for group, entry in zip(G, new["allowlists"][len(old["allowlists"]) :], strict=True):
        label, rule, commit, value, paths = group
        require(
            set(entry)
            == {"description", "targetRules", "condition", "regexTarget", "commits", "paths", "regexes"},
            label + " unexpected fields",
        )
        require(entry["description"].startswith(label + ": "), label + " order")
        require(
            entry["targetRules"] == [rule]
            and entry["condition"] == "AND"
            and entry["regexTarget"] == "secret",
            label + " rule semantics",
        )
        require(entry["commits"] == [commit] and re.fullmatch("[0-9a-f]{40}", commit), label + " commit")
        require(entry["paths"] == ["^" + re.escape(x) + "$" for x in paths], label + " exact paths")
        expected = "^" + re.escape(value) + "$" if label != "T" else "^ghp[_]" + "SYNTHETIC" * 4 + "$"
        require(entry["regexes"] == [expected], label + " exact capture")

    def scan(name, config, cwd, mode="git", allowed=(0, 1)):
        report = out / (name + ".json")
        args = [
            binary,
            mode,
            "--no-banner",
            "--config",
            config,
            "--report-format",
            "json",
            "--report-path",
            report,
        ]
        if mode == "git":
            args += ["--log-opts=--all"]
        if Path(cwd).resolve() == a.history.resolve():
            args += ["--redact"]
        args += ["."]
        command(name, args, cwd, allowed)
        rows = json.loads(report.read_text()) if report.exists() else []
        require(isinstance(rows, list), name + " report shape")
        return rows

    before = command("refs-before", ["git", "show-ref"], a.history)
    count = command("count-before", ["git", "rev-list", "--all", "--count"], a.history).decode().strip()
    # The public history is already classified nonsecret; preserve new reports privately.
    baseline = scan("history-original", original_path, a.history)
    expected = json.loads(a.expected.read_text())
    require(len(baseline) == len(expected) == 17, "historical count")
    require(
        sorted(map(identity, baseline)) == sorted(map(identity, expected)),
        "historical occurrence roster changed",
    )
    clean = scan("history-candidate", candidate_path, a.history, allowed=(0,))
    require(clean == [], "candidate residual findings")
    require(command("refs-after", ["git", "show-ref"], a.history) == before, "history refs changed")
    fixture = out / "fixture"
    fixture.mkdir()
    command("fixture-init", ["git", "init", "--template=", "-q"], fixture)
    cases = []
    lines = {}

    def append(path, text, label, rule, value, positive=False):
        roster = lines.setdefault(path, [])
        roster.append(text)
        cases.append(
            {
                "file": path,
                "line": len(roster),
                "label": label,
                "rule": rule,
                "value": value,
                "exempt": positive,
            }
        )

    extra = "gh" + "p_" + sha(b"finite unrelated native scanner control")[:36]
    for label, rule, _commit, value, paths in G:

        def text(val):
            return 'api_key = "' + val + '"'

        for path in paths:
            append(path, text(value), label + " exact", rule, value, True)
            changed = ("0" if value[0] != "0" else "1") + value[1:] if label != "T" else value[:-1] + "Z"
            append(path, text(changed), label + " changed", rule, changed)
            if label != "T":
                for variant in ("X" + value, value + "X"):
                    append(path, text(variant), label + " anchored value", rule, variant)
            else:
                # Extra source suffix does not change this stock rule's 40-char capture.
                append(path, text(value + "SYNTHETIC"), label + " capture suffix", rule, value, True)
            append(
                path,
                text(value) + '; access_token = "' + extra + '"',
                label + " same-line exact",
                rule,
                value,
                True,
            )
            cases.append(
                {
                    "file": path,
                    "line": len(lines[path]),
                    "label": label + " same-line other",
                    "rule": "github-pat",
                    "value": extra,
                    "exempt": False,
                }
            )
            append(path, 'access_token = "' + extra + '"', label + " same-file other", "github-pat", extra)
            for wrong in ("wrong/" + path, path + ".extra", path.replace(".", "X")):
                append(wrong, text(value), label + " wrong/near path", rule, value)
    for path, content in lines.items():
        target = fixture / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(content) + "\n")
    command("fixture-add", ["git", "add", "--all"], fixture)
    command(
        "fixture-commit",
        [
            "git",
            "-c",
            "user.name=Finite scanner control",
            "-c",
            "user.email=scanner@example.invalid",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "Finite synthetic controls",
        ],
        fixture,
    )
    fixture_sha = command("fixture-sha", ["git", "rev-parse", "HEAD"], fixture).decode().strip()
    fixture_old = scan("fixture-original", original_path, fixture)

    def matches(case, rows):
        return [
            r
            for r in rows
            if r["File"] == case["file"]
            and r["StartLine"] == case["line"]
            and r["RuleID"] == case["rule"]
            and r["Secret"] == case["value"]
        ]

    for case in cases:
        require(
            bool(matches(case, fixture_old)),
            case["label"] + " not detected by original at " + case["file"] + ":" + str(case["line"]),
        )
    later = scan("fixture-later-commit", candidate_path, fixture)
    require(
        sorted(map(identity, later)) == sorted(map(identity, fixture_old)),
        "shipped config exempts a new commit",
    )
    rebound = candidate.decode()
    for commit in {g[2] for g in G}:
        rebound = rebound.replace('commits = ["' + commit + '"]', 'commits = ["' + fixture_sha + '"]')
    rb = tomllib.loads(rebound)
    expected_rebound = json.loads(json.dumps(new))
    for entry in expected_rebound["allowlists"][len(old["allowlists"]) :]:
        entry["commits"] = [fixture_sha]
    require(rb == expected_rebound, "derived configuration changes exceed commits")
    rebound_path = out / "matching-commit.toml"
    rebound_path.write_text(rebound)
    matched = scan("fixture-matching-commit", rebound_path, fixture)
    for case in cases:
        require(bool(matches(case, matched)) != case["exempt"], case["label"] + " per-finding expectation")
    # Missing regex and OR mutations must actually remove required negative findings.
    parts = rebound.split("[[allowlists]]")
    no_regex = "[[allowlists]]".join(
        parts[:2] + [re.sub(r"^regexes = .*\n", "", x, flags=re.M) for x in parts[2:]]
    )
    as_or = "[[allowlists]]".join(
        parts[:2] + [x.replace('condition = "AND"', 'condition = "OR"') for x in parts[2:]]
    )
    sensitivity = {}
    for name, mutation in [("missing-regex", no_regex), ("or-condition", as_or)]:
        conf = out / (name + ".toml")
        conf.write_text(mutation)
        rows = scan("mutant-" + name, conf, fixture)
        lost = [c for c in cases if not c["exempt"] and not matches(c, rows)]
        require(bool(lost), name + " sentinel insensitive")
        sensitivity[name] = len(lost)
    empty_original = scan("dir-original", original_path, fixture, "dir")
    empty_candidate = scan("dir-candidate", candidate_path, fixture, "dir")
    require(all(r.get("Commit", "") == "" for r in empty_candidate), "dir commit metadata not empty")
    require(
        sorted(map(identity, empty_original)) == sorted(map(identity, empty_candidate)),
        "empty commit metadata gained exemption",
    )
    # Dir paths are required to be the exact relative paths, not a false path mismatch.
    for case in cases:
        require(bool(matches(case, empty_candidate)), case["label"] + " dir path/capture correspondence")
    typo = candidate.decode().replace(V4, "0" + V4[1:])
    typo_path = out / "wrong-commit.toml"
    typo_path.write_text(typo)
    typo_rows = scan("history-wrong-commit", typo_path, a.history)
    require(len(typo_rows) == 11 and all(r["Commit"] == V4 for r in typo_rows), "exact commit typo sentinel")
    invalid_path = out / "invalid-condition.toml"
    invalid_path.write_text(candidate.decode().replace('condition = "AND"', 'condition = "AND_typo"', 1))
    command(
        "invalid-condition", [binary, "git", "--no-banner", "--config", invalid_path, "."], fixture, (1, 2)
    )
    require(
        "Failed to load config" in (out / "invalid-condition.stderr").read_text()
        and "unknown allowlist |condition|" in (out / "invalid-condition.stderr").read_text(),
        "invalid condition did not fail configuration loading",
    )
    # Existing OpenAI synthetic exception: independently show a stock positive first.
    legacy = out / "legacy-fixture"
    legacy.mkdir()
    token = "sk-" + "abcdefghij1234567890"
    for path in ("tests/test_context_hygiene.py", "tests/test_unattended.py", "other.py"):
        q = legacy / path
        q.parent.mkdir(parents=True, exist_ok=True)
        q.write_text('api_key = "' + token + '"\n')
    stock = out / "stock.toml"
    stock.write_text("[extend]\nuseDefault = true\n")
    stock_rows = scan("legacy-stock", stock, legacy, "dir")
    require(len(stock_rows) == 3, "legacy fixture not stock detected")
    for name, config in [("original", original_path), ("candidate", candidate_path)]:
        rows = scan("legacy-" + name, config, legacy, "dir")
        require(len(rows) == 1 and rows[0]["File"] == "other.py", "legacy exception changed")
    require(
        command("refs-final", ["git", "show-ref"], a.history) == before, "history refs changed after controls"
    )
    version = command("binary-version", [binary, "version"], ROOT).decode().strip()
    summary = {
        "status": "PASS",
        "binary": str(binary),
        "version": version,
        "binary_sha256": sha(binary.read_bytes()),
        "original_config_sha256": sha(original),
        "candidate_config_sha256": sha(candidate),
        "public_refs_sha256": sha(before),
        "public_commit_count": int(count),
        "historical_findings": len(baseline),
        "candidate_findings": 0,
        "fixture_commit": fixture_sha,
        "registered_cases": len(cases),
        "fixture_original_findings": len(fixture_old),
        "matching_commit_findings": len(matched),
        "mutation_lost_negative_cases": sensitivity,
        "dir_findings": len(empty_candidate),
        "typo_findings": len(typo_rows),
        "elapsed_seconds": round(time.time() - started, 3),
        "commands": len(records),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
