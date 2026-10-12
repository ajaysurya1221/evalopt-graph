from quarantine import collect
from reachability import closure
from retention import roots


def solve(q):
    live = closure(q["objects"], roots(q["snapshots"], q["keep"], q["now"], q["window"]))
    dead, waiting = collect(q["objects"], live, q["quarantine"], q["now"], q["grace"])
    return {"live": sorted(live), "delete": dead, "quarantine": waiting}
