"""Exact interpreter identity for reproducible controller arithmetic."""

from __future__ import annotations

import platform
import sys

CONTROLLER_IMPLEMENTATION = "CPython"
CONTROLLER_VERSION = (3, 13, 12)


def require_controller() -> dict:
    """Reject interpreter drift before registration, dispatch or report generation."""
    if (
        platform.python_implementation() != CONTROLLER_IMPLEMENTATION
        or tuple(sys.version_info[:3]) != CONTROLLER_VERSION
    ):
        raise ValueError("benchmark controller requires CPython 3.13.12 for byte-reproducible reports")
    return {"implementation": CONTROLLER_IMPLEMENTATION, "version": "3.13.12"}
