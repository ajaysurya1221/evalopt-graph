import heapq


def solve(edges, start, goal):
    queue = [(0, (start,))]
    best = {}
    while queue:
        cost, path = heapq.heappop(queue)
        node = path[-1]
        if node in best:
            continue
        best[node] = (cost, path)
        if node == goal:
            return {"cost": cost, "path": list(reversed(path))}
        for source, target, weight in edges:
            if source == node and target not in best:
                heapq.heappush(queue, (cost + weight, path + (target,)))
    return None
