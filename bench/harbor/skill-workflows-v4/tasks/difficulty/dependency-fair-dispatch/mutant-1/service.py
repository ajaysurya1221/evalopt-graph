from dependencies import propagate, ready
from events import apply_events
from fairness import choose


def solve(q):
    jobs = {j["id"]: dict(j) for j in q["jobs"]}
    state = {i: {"state": "pending", "finished": None, "remaining": j["work"]} for i, j in jobs.items()}
    served = {t: 0 for t in q["weights"]}
    trace = []
    for now in range(q["horizon"] + 1):
        apply_events(jobs, state, q["cancel"], now)
        propagate(jobs, state, now)
        if now == q["horizon"]:
            break
        options = [j for i, j in jobs.items() if state[i]["state"] == "pending" and ready(j, state, now)]
        selected = choose(options, served, q["weights"])
        trace.append(selected["id"] if selected else None)
        if selected:
            i = selected["id"]
            state[i]["remaining"] -= 1
            served[selected["tenant"]] += 1
            if state[i]["remaining"] == 0:
                state[i].update(state="complete", finished=now + 1)
    return {"trace": trace, "jobs": {i: state[i] for i in sorted(state)}, "served": served}
