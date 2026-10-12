from patterns import matches


def decide(path, rules):
    options = []
    for index, r in enumerate(rules):
        base = r["base"]
        if path[: len(base)] != base:
            continue
        relative = path[len(base) :]
        direct = matches(r["pattern"], relative)
        inherited = r["inherit"] and any(matches(r["pattern"], relative[:n]) for n in range(len(relative)))
        if direct or inherited:
            options.append(
                ((len(base), int(direct), index), r["effect"], "direct" if direct else "inherited")
            )
    if not options:
        return {"path": "/".join(path), "decision": "deny", "rule": None, "kind": "default"}
    rank, effect, kind = max(options)
    return {"path": "/".join(path), "decision": effect, "rule": rank[2], "kind": kind}
