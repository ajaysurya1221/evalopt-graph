def execute(jobs, required):
    states, changed, order = {}, {}, []
    pending = set(required)
    while pending:
        ready = sorted(n for n in pending if all(d in states for d in jobs[n]["normal"] + jobs[n]["order"]))
        name = ready[0]
        pending.remove(name)
        order.append(name)
        job = jobs[name]
        dependencies = job["normal"] + job["order"]
        if any(states[d] == "skipped" for d in dependencies):
            states[name], changed[name] = "skipped", False
            continue
        needs = (
            job["old"] is None
            or job["config_changed"]
            or job["dirty"]
            or any(changed[d] for d in job["normal"])
        )
        if not needs:
            states[name], changed[name] = "clean", False
        elif job["fail"]:
            states[name], changed[name] = "failed", False
        else:
            states[name], changed[name] = "built", job["new"] != job["old"]
    return {"order": order, "status": states, "changed": changed}
