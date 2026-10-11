def closure(jobs, roots):
    done, active = set(), set()

    def visit(name):
        if name in active:
            raise ValueError("cycle")
        if name in done:
            return
        active.add(name)
        for child in jobs[name]["normal"] + jobs[name]["order"]:
            visit(child)
        active.remove(name)
        done.add(name)

    for root in roots:
        visit(root)
    return done
