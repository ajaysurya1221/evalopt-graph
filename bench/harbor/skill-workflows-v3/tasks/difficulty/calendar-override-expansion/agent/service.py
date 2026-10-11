from overrides import apply_changes
from recurrence import nominal_times
from zones import to_utc


def solve(q):
    nominal = nominal_times(q["start"], q["step"], q["count"])
    nominal = [(i, t) for i, t in nominal if q["window"][0] <= t < q["window"][1]]
    events = apply_changes(nominal, q["cancel"], q["replace"])
    result = []
    for identity, local in events:
        utc = to_utc(local, q["zones"])
        if q["window"][0] <= utc < q["window"][1]:
            result.append({"id": identity, "utc": utc})
    return sorted(result, key=lambda x: (x["utc"], x["id"]))
