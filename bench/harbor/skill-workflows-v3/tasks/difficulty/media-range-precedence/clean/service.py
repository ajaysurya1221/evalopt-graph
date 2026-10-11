from quality import effective


def solve(q):
    scores = [effective(offer, q["ranges"]) for offer in q["offers"]]
    best = max(scores, default=0)
    return {"offer": scores.index(best) if best else None, "quality": best}
