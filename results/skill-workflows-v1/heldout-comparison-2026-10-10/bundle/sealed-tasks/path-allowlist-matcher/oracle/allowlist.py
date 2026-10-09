import fnmatch
from functools import lru_cache

def matches(path, patterns):
    if path.startswith("/") or "\\" in path:
        raise ValueError("invalid relative path")
    parts = []
    for part in path.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if not parts:
                raise ValueError("path escapes root")
            parts.pop()
        else:
            parts.append(part)
    for pattern in patterns:
        tokens = pattern.split("/")
        @lru_cache(None)
        def visit(i, j):
            if j == len(tokens):
                return i == len(parts)
            if tokens[j] == "**":
                return visit(i, j + 1) or (i < len(parts) and visit(i + 1, j))
            return i < len(parts) and fnmatch.fnmatchcase(parts[i], tokens[j]) and visit(i + 1, j + 1)
        if visit(0, 0):
            return True
    return False
