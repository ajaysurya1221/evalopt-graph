def solve(events):
    return [{"id": e["id"], "value": e["value"]} for e in events if not e["deleted"]]
