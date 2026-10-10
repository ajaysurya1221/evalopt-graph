def order(nodes, edges):
    if len(set(nodes)) != len(nodes):
        raise ValueError("duplicate node")
    children = {node: set() for node in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for before, after in edges:
        if before not in children or after not in children:
            raise ValueError("unknown node")
        if after not in children[before]:
            children[before].add(after)
            indegree[after] += 1
    ready = sorted(node for node in nodes if indegree[node] == 0)
    result = []
    while ready:
        node = ready.pop(0)
        result.append(node)
        for child in sorted(children[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()
    if len(result) != len(nodes):
        raise ValueError("cycle")
    return result
