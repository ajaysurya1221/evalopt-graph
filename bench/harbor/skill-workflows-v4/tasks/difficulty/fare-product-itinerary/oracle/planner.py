from functools import lru_cache

from coverage import endpoints
from pricing import charge, day


def best(trips, products, cap):
    @lru_cache(None)
    def visit(i, spent):
        if i == len(trips):
            return (0, ())
        choices = []
        for p in products:
            paid = charge(p["price"], spent, cap)
            for end in endpoints(trips, i, p):
                next_spent = (
                    spent + paid if end < len(trips) and day(trips[end]["at"]) == day(trips[i]["at"]) else 0
                )
                tail = visit(end, next_spent)
                if tail is not None:
                    choices.append((paid + tail[0], ((i, end, p["id"], paid),) + tail[1]))
        return min(choices) if choices else None

    answer = visit(0, 0)
    return None if answer is None else {"cost": answer[0], "tickets": [list(t) for t in answer[1]]}
