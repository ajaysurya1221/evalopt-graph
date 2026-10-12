from rules import decide


def solve(q):
    return [decide(path, q["rules"]) for path in q["paths"]]
