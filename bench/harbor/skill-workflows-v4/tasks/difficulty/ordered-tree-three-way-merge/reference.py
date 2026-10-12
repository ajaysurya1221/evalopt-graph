from copy import deepcopy


def solve(q):
    old, left_map, right = ({n["id"]: deepcopy(n) for n in q[k]} for k in ("base", "local", "remote"))
    merged = {}
    problems = set()
    for i in sorted(old.keys() | left_map.keys() | right.keys()):
        values = [d.get(i) for d in (old, left_map, right)]
        b, left, r = values
        if b is None:
            options = [v for v in (left, r) if v is not None]
            if len(options) == 2 and options[0] != options[1]:
                problems.add((i, "add"))
            else:
                merged[i] = options[0]
        elif left is None or r is None:
            survivor = left or r
            if survivor is not None and survivor != b:
                problems.add((i, "delete"))
        else:
            dl = {k: left[k] for k in b if left[k] != b[k]}
            dr = {k: r[k] for k in b if r[k] != b[k]}
            problems.update((i, k) for k in dl.keys() & dr.keys() if dl[k] != dr[k])
            merged[i] = {**b, **dl, **dr}
    if not problems:
        for i, n in merged.items():
            par = n["parent"]
            if par is not None and par not in merged:
                problems.add((i, "parent_missing"))
            seen = []
            j = i
            while j is not None and j in merged and j not in seen:
                seen.append(j)
                j = merged[j]["parent"]
            if j in seen:
                problems.update((v, "cycle") for v in seen[seen.index(j) :])
            for k, m in merged.items():
                if i != k and (par, n["name"]) == (m["parent"], m["name"]):
                    problems.add((i, "name_collision"))
    if problems:
        return {"nodes": None, "conflicts": [list(p) for p in sorted(problems)]}

    def descend(parent):
        flat = []
        for n in sorted(
            [x for x in merged.values() if x["parent"] == parent], key=lambda x: (x["order"], x["id"])
        ):
            flat += [n] + descend(n["id"])
        return flat

    return {"nodes": descend(None), "conflicts": []}
