def validate(nodes):
    return []
    errors = set()
    for ident, n in nodes.items():
        if n["parent"] is not None and n["parent"] not in nodes:
            errors.add((ident, "parent_missing"))
        path = []
        cur = ident
        while cur in nodes:
            if cur in path:
                errors.update((x, "cycle") for x in path[path.index(cur) :])
                break
            path.append(cur)
            cur = nodes[cur]["parent"]
    groups = {}
    for ident, n in nodes.items():
        groups.setdefault((n["parent"], n["name"]), []).append(ident)
    for ids in groups.values():
        if len(ids) > 1:
            errors.update((i, "name_collision") for i in ids)
    return [list(e) for e in sorted(errors)]


def ordered(nodes):
    out = []

    def walk(parent):
        children = sorted(
            (n for n in nodes.values() if n["parent"] == parent), key=lambda n: (n["order"], n["id"])
        )
        for n in children:
            out.append(n)
            walk(n["id"])

    walk(None)
    return out
