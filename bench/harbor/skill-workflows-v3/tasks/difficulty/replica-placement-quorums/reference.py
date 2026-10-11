from itertools import combinations


def solve(q):
    eligible = [n for n in q["nodes"] if n["alive"] and n["capacity"] > 0]
    survivors = [
        n
        for n in eligible
        if not any(
            m["physical"] == n["physical"] and (-m["rank"], m["id"]) < (-n["rank"], n["id"]) for m in eligible
        )
    ]
    survivors.sort(key=lambda n: (-n["rank"], n["id"]))
    size = min(q["replicas"], len(survivors))
    best = None
    key = None
    for group in combinations(survivors, size):
        rank = (-len(set(n["zone"] for n in group)), tuple((-n["rank"], n["id"]) for n in group))
        if key is None or rank < key:
            key = rank
            best = group
    ids = [n["id"] for n in best]
    quorum = q["replicas"] // 2 + 1
    got = set(n["physical"] for n in best if n["id"] in q["acks"])
    return {"replicas": ids, "quorum": quorum, "writable": len(got) >= quorum}
