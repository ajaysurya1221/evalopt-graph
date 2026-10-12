def apply_events(jobs, state, cancel, now):
    for i, j in jobs.items():
        if state[i]["state"] != "pending":
            continue
        if cancel.get(i) == now:
            state[i].update(state="cancelled", finished=now)
        elif j["deadline"] <= now:
            state[i].update(state="expired", finished=now)
