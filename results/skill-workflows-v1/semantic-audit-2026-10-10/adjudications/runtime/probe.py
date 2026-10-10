"""Trusted stdlib mechanism probes; no candidate modules, files, or graders run."""

from __future__ import annotations

import copy
import hashlib
import json
import platform
import sys
from pathlib import Path


def nesting_probe(kind: str, depth: int, leaf: object) -> dict:
    value = leaf
    for _ in range(depth):
        value = [value] if kind == "list" else {"x": value}
    outcomes = {}
    for name in ("json_roundtrip", "deepcopy"):
        try:
            result = json.loads(json.dumps(value)) if name == "json_roundtrip" else copy.deepcopy(value)
            original, cloned = value, result
            independent = True
            for _ in range(depth):
                independent = independent and original is not cloned
                original = original[0] if kind == "list" else original["x"]
                cloned = cloned[0] if kind == "list" else cloned["x"]
            outcomes[name] = {
                "status": "returned",
                "depth": depth,
                "leaf_type_preserved": type(cloned) is type(leaf),
                "leaf_equal": cloned == leaf,
                "mutable_containers_independent": independent,
            }
        except RecursionError:
            outcomes[name] = {"status": "raised", "error": "RecursionError"}
    return {"kind": kind, "depth": depth, "leaf": leaf, "operations": outcomes}


def run() -> dict:
    try:
        bytes.fromhex("ff202020").decode("utf-8")
    except ValueError as error:
        exception = {
            "concrete_name": type(error).__name__,
            "caught_by_ValueError": True,
            "mro": [c.__name__ for c in type(error).__mro__],
        }
    else:
        raise AssertionError("invalid UTF-8 unexpectedly decoded")
    return {
        "schema_version": "evalopt.semantic-mechanism-probe.v1",
        "scope": "New stdlib-only mechanism probes; neither original trials nor candidate execution.",
        "candidate_code_executed": False,
        "original_grader_executed": False,
        "model_trials": 0,
        "runtime": {
            "implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "system": platform.system(),
            "machine": platform.machine(),
            "recursion_limit": sys.getrecursionlimit(),
            "copy_module_sha256": hashlib.sha256(Path(copy.__file__).read_bytes()).hexdigest(),
            "json_module_sha256": hashlib.sha256(Path(json.__file__).read_bytes()).hexdigest(),
        },
        "invalid_utf8": exception,
        "byte_digit_primitives": [
            {
                "hex": value.hex(),
                "bytes_isdigit": value.isdigit(),
                "ascii_range_all": all(ord("0") <= byte <= ord("9") for byte in value),
            }
            for value in (b"0001", b"-001", b"00 1", b"\xff001")
        ],
        "copy_nesting": [
            nesting_probe(kind, depth, leaf)
            for kind in ("list", "dict")
            for depth, leaf in ((1, None), (500, 0), (600, None), (600, 0), (600, 1))
        ],
    }


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2, allow_nan=False))
