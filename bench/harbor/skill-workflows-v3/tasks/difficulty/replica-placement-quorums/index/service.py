from eligibility import representatives
from placement import choose
from quorum import writable


def solve(q):
    chosen = choose(representatives(q["nodes"]), q["replicas"])
    return {
        "replicas": [n["id"] for n in chosen],
        "quorum": q["replicas"] // 2 + 1,
        "writable": writable(chosen, q["acks"], q["replicas"]),
    }
