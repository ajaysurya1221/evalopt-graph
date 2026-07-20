"""Stability controller — self-healing controls so the autonomous loop stays bounded and stable.

Pure, deterministic helpers: classify tool failures (so the loop retries only *transient* ones),
detect patch oscillation (A→B→A→B), classify flaky tests from rerun outcomes, and detect
diminishing returns so the loop stops when marginal information gain is low.
"""

from __future__ import annotations

# failure classes
TRANSIENT = "transient"
MISSING_DEPENDENCY = "missing_dependency"
PERMISSION = "permission_auth"
NETWORK = "network"
CODE_FAILURE = "code_failure"
UNKNOWN = "unknown"

_NETWORK = (
    "network",
    "connection reset",
    "econnreset",
    "etimedout",
    "getaddrinfo",
    "dns",
    "ssl",
    "tls handshake",
)
_TRANSIENT = (
    "timeout",
    "timed out",
    "temporarily unavailable",
    "rate limit",
    "429",
    "503",
    "try again",
    "deadlock",
)
_PERMISSION = (
    "permission denied",
    "unauthorized",
    "forbidden",
    " 401",
    " 403",
    "eacces",
    "access denied",
    "not authenticated",
)
_MISSING = (
    "command not found",
    "no module named",
    "modulenotfounderror",
    "not installed",
    "cannot find module",
    "no such file or directory",
    "executable not found",
)
_CODE = (
    "assertionerror",
    "assert ",
    "traceback",
    "syntaxerror",
    "typeerror",
    "test failed",
    "failed",
    "compile error",
    "exit code 1",
)
# Unambiguous code-failure markers that OVERRIDE a co-occurring transient keyword, so an
# 'AssertionError: request timed out' is a code failure (not blindly retried) rather than a transient.
_STRONG_CODE = ("assertionerror", "traceback", "syntaxerror", "typeerror")


def classify_tool_failure(text: str, exit_code: int | None = None) -> str:
    """Classify a failure so the loop can decide whether to retry, swap tools, or stop.

    Real network errors first, then a definitive code marker (so it is not misread as transient), then
    permission/missing-dependency, then transient, then generic code failure. A bare 'connection timed
    out' stays transient; an 'AssertionError: timed out' is a code failure.
    """
    t = (text or "").lower()
    if any(k in t for k in _NETWORK):
        return NETWORK
    if any(k in t for k in _STRONG_CODE):
        return CODE_FAILURE
    if any(k in t for k in _PERMISSION):
        return PERMISSION
    if any(k in t for k in _MISSING):
        return MISSING_DEPENDENCY
    if any(k in t for k in _TRANSIENT):
        return TRANSIENT
    if any(k in t for k in _CODE):
        return CODE_FAILURE
    if exit_code not in (None, 0):
        return CODE_FAILURE
    return UNKNOWN


def is_retryable(kind: str) -> bool:
    """Only transient failures are retried (network is surfaced, not blind-retried)."""
    return kind == TRANSIENT


def detect_patch_oscillation(signatures: list[str], window: int = 4) -> bool:
    """True when recent failure signatures oscillate A→B→A→B (a patch that ping-pongs between two
    failure shapes) — a signal to switch to root-cause mode rather than keep patching."""
    tail = [s for s in signatures if s][-window:]
    if len(tail) < 4:
        return False
    a, b, c, d = tail[-4:]
    return a == c and b == d and a != b


def classify_flaky(outcomes: list[bool]) -> str:
    """Classify a gate from its rerun outcomes (True=pass). 'flaky' if results disagree,
    'pass' if all passed, 'consistent_failure' if all failed, 'no_data' if empty."""
    if not outcomes:
        return "no_data"
    if all(outcomes):
        return "pass"
    if not any(outcomes):
        return "consistent_failure"
    return "flaky"


def low_information_gain(
    new_confirmed_per_round: list[int], *, threshold: int = 1, lookback: int = 2
) -> bool:
    """True when the last ``lookback`` research rounds each added fewer than ``threshold`` new
    confirmed claims — i.e. diminishing returns; stop instead of looping for fake certainty."""
    if len(new_confirmed_per_round) < lookback:
        return False
    return all(n < threshold for n in new_confirmed_per_round[-lookback:])


def analyze(state: dict, *, repeated_failure_threshold: int = 3) -> dict:
    """Summarize stability signals from loop state for the trace + routing hints."""
    sigs = state.get("failure_signatures", []) or []
    tail = [s for s in sigs if s]
    repeated = (
        bool(tail)
        and len(tail) >= repeated_failure_threshold
        and all(s == tail[-1] for s in tail[-repeated_failure_threshold:])
    )
    return {
        "repeated_failure": repeated,
        "patch_oscillation": detect_patch_oscillation(sigs),
        "low_information_gain": low_information_gain(state.get("confirmed_gain_history", []) or []),
    }
