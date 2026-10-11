from itertools import combinations


def choose(nodes, replicas):
    ordered = sorted(nodes, key=lambda n: (-n["rank"], n["id"]))
    options = list(combinations(range(len(ordered)), min(replicas, len(ordered))))
    selected = min(options, key=lambda ids: (-len({ordered[i]["zone"] for i in ids}), ids))
    return [ordered[i] for i in selected]
