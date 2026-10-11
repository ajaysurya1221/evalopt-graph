from distance import distance
from filtering import eligible
from ranking import order


def solve(q):
    scored = [
        (distance(q["query"], r["vector"], q["weights"]), r["id"])
        for r in q["records"]
        if eligible(r, q["required"])
    ]
    return order(scored, q["limit"])
