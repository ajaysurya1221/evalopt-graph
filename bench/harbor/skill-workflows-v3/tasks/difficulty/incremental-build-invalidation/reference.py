def solve(q):
    jobs = q["jobs"]
    required = set()
    todo = list(q["roots"])
    while todo:
        n = todo.pop()
        if n in required:
            continue
        required.add(n)
        todo.extend(jobs[n]["normal"] + jobs[n]["order"])
    remaining = set(required)
    order = []
    statuses = {}
    modified = {}
    while remaining:
        runnable = [n for n in remaining if not (set(jobs[n]["normal"] + jobs[n]["order"]) & remaining)]
        if not runnable:
            raise ValueError("cycle")
        n = min(runnable)
        remaining.remove(n)
        order.append(n)
        j = jobs[n]
        parents = [statuses[d] for d in j["normal"] + j["order"]]
        state = "skipped" if any(s in ("failed", "skipped") for s in parents) else "clean"
        if state == "clean" and (
            j["old"] is None or j["dirty"] or j["config_changed"] or any(modified[d] for d in j["normal"])
        ):
            state = "failed" if j["fail"] else "built"
        statuses[n] = state
        modified[n] = state == "built" and j["old"] != j["new"]
    return {"order": order, "status": statuses, "changed": modified}
