#!/usr/bin/env python3
"""Fail when pytest collects fewer than the release's regression-test floor."""

from __future__ import annotations

import argparse

import pytest


class CollectionCounter:
    count = 0

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        self.count = len(session.items)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--minimum", type=int, required=True)
    args = parser.parse_args()
    counter = CollectionCounter()
    result = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider"], plugins=[counter])
    if result != pytest.ExitCode.OK:
        raise SystemExit(int(result))
    if counter.count < args.minimum:
        raise SystemExit(f"collected {counter.count} tests; release floor is {args.minimum}")
    print(f"collected {counter.count} tests (minimum {args.minimum})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
