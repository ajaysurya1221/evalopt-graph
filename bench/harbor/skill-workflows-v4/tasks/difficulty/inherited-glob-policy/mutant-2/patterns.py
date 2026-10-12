from functools import lru_cache

from segments import segment


def matches(pattern, path):
    parts = pattern.split("/")

    @lru_cache(None)
    def walk(i, j):
        if i == len(parts):
            return j == len(path)
        if parts[i] == "**":
            return walk(i + 1, j) or (j < len(path) and walk(i, j + 1))
        return j < len(path) and segment(parts[i], path[j]) and walk(i + 1, j + 1)

    return walk(0, 0)
