import heapq


def solve(edges, start, goal):
    queue = [(0, (start,))]
    best = {}
    while queue:
        cost, path = heapq.heappop(queue)
        node = path[-1]
        if node in best and best[node] != (cost, path):
            continue
        best[node] = (cost, path)
        if node == goal:
            return {"cost": cost, "path": list(path)}
        for source, target, weight in edges:
            if source == node and target not in best:
                best[target] = (cost + weight, path + (target,))
                heapq.heappush(queue, best[target])
    return None
