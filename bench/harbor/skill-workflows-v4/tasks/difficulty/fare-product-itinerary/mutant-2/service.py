from planner import best


def solve(q):
    return best(q["trips"], q["products"], q["daily_cap"])
