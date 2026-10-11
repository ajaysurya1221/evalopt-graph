def execute(jobs, required):
    # Legacy executor visits dependencies, but always requests every build.
    states, changed, order = {}, {}, []
    pending = set(required)
    while pending:
        ready = sorted(n for n in pending if all(d in states for d in jobs[n]["normal"] + jobs[n]["order"]))
        name = ready[0]
        pending.remove(name)
        order.append(name)
        failed = jobs[name]["fail"]
        states[name] = "failed" if failed else "built"
        changed[name] = not failed
    return {"order": order, "status": states, "changed": changed}
