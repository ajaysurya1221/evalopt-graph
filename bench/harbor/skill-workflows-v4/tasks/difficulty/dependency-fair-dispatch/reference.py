from fractions import Fraction


def solve(q):
    rows = [dict(j, remaining=j["work"], state="pending", finished=None) for j in q["jobs"]]
    byid = {j["id"]: j for j in rows}
    totals = dict.fromkeys(q["weights"], 0)
    trace = []
    for time in range(q["horizon"] + 1):
        for j in rows:
            if j["state"] == "pending":
                reason = (
                    "cancelled"
                    if q["cancel"].get(j["id"]) == time
                    else "expired"
                    if time >= j["deadline"]
                    else None
                )
                if reason:
                    j.update(state=reason, finished=time)
        for _ in rows:
            for j in rows:
                if j["state"] == "pending" and any(
                    byid[d]["state"] not in ("pending", "complete") for d in j["deps"]
                ):
                    j.update(state="blocked", finished=time)
        if time == q["horizon"]:
            break
        available = [
            j
            for j in rows
            if j["state"] == "pending"
            and j["release"] <= time
            and all(byid[d]["state"] == "complete" for d in j["deps"])
        ]
        if not available:
            trace.append(None)
            continue
        job = min(
            available,
            key=lambda j: (Fraction(totals[j["tenant"]], q["weights"][j["tenant"]]), j["deadline"], j["id"]),
        )
        trace.append(job["id"])
        totals[job["tenant"]] += 1
        job["remaining"] -= 1
        if job["remaining"] == 0:
            job.update(state="complete", finished=time + 1)
    return {
        "trace": trace,
        "served": totals,
        "jobs": {j["id"]: {k: j[k] for k in ("state", "finished", "remaining")} for j in rows},
    }
