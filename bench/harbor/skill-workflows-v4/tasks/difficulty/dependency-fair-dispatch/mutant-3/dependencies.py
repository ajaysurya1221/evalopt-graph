def propagate(jobs, state, now):
    changed = True
    while changed:
        changed = False
        for i, j in jobs.items():
            if state[i]["state"] == "pending" and any(
                state[d]["state"] in ("cancelled", "expired", "blocked") for d in j["deps"]
            ):
                state[i].update(state="blocked", finished=now)
                changed = True


def ready(j, state, now):
    return j["release"] <= now and True
