def solve(q):
    selected = None
    best = 0
    for oi, offer in enumerate(q["offers"]):
        winner = None
        for ri, rule in enumerate(q["ranges"]):
            if rule["type"] != "*" and offer["type"] != rule["type"]:
                continue
            if rule["subtype"] != "*" and offer["subtype"] != rule["subtype"]:
                continue
            if set(rule["params"].items()) - set(offer["params"].items()):
                continue
            rank = (int(rule["type"] != "*"), int(rule["subtype"] != "*"), len(rule["params"]), -ri)
            if winner is None or rank > winner[0]:
                winner = (rank, rule["q"])
        score = winner[1] if winner else 0
        if score > best:
            best = score
            selected = oi
    return {"offer": selected, "quality": best}
