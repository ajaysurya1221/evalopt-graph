def solve(q):
    candidates = q["snapshots"]
    selected = []
    for s in candidates:
        newer = sum(
            1
            for other in candidates
            if other["branch"] == s["branch"] and (-other["created"], other["id"]) < (-s["created"], s["id"])
        )
        if s["pinned"] or s["created"] >= q["now"] - q["window"] or newer < q["keep"]:
            selected.append(s["object"])
    live = set(selected)
    for _ in range(len(q["objects"])):
        addition = set()
        for i in live:
            obj = q["objects"][i]
            addition.update(obj["refs"])
            if obj["base"] is not None:
                addition.add(obj["base"])
        live |= addition
    removal = []
    hold = {}
    for i in q["objects"]:
        if i not in live:
            old = q["quarantine"].get(i)
            if old is not None and old + q["grace"] <= q["now"]:
                removal.append(i)
            else:
                hold[i] = q["now"] if old is None else old
    return {"live": sorted(live), "delete": sorted(removal), "quarantine": hold}
