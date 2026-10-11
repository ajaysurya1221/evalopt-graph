from replica_order import choose_order


def choose(nodes, replicas):
    ordered = sorted(nodes, key=lambda n: (-n["rank"], n["id"]))
    return choose_order(ordered, replicas)
