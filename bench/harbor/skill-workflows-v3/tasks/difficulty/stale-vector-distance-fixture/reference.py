def solve(q):
    result = []
    for r in q["records"]:
        if any(t not in r["tags"] for t in q["required"]):
            continue
        value = 0
        for i in range(len(q["query"])):
            delta = q["query"][i] - r["vector"][i]
            value += q["weights"][i] * (delta if delta >= 0 else -delta)
        result.append({"id": r["id"], "distance": value})
    return sorted(result, key=lambda r: (r["distance"], r["id"]))[: q["limit"]]
