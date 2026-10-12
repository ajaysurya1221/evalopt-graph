from conflicts import conflict
from transaction import read, scan
from versions import latest


def solve(q):
    history = {k: [(0, v)] for k, v in q["initial"].items()}
    revision = 0
    active = {}
    out = []
    for op in q["operations"]:
        tag = op[0]
        ident = op[1]
        if tag == "begin":
            active[ident] = {"at": revision, "writes": {}, "reads": set(), "ranges": []}
            out.append(["begin", ident, revision])
            continue
        t = active[ident]
        if tag == "get":
            out.append(["get", ident, read(history, t, op[2])])
        elif tag == "scan":
            out.append(["scan", ident, scan(history, t, op[2], op[3])])
        elif tag in ("put", "delete"):
            t["writes"][op[2]] = op[3] if tag == "put" else None
            out.append([tag, ident])
        elif tag == "commit":
            if t["writes"] and conflict(history, t):
                out.append(["commit", ident, "conflict", revision])
            else:
                if t["writes"]:
                    revision += 1
                    for k, v in t["writes"].items():
                        history.setdefault(k, []).append((revision, v))
                out.append(["commit", ident, "ok", revision])
            del active[ident]
    final = {k: latest(v)[1] for k, v in sorted(history.items()) if latest(v)[1] is not None}
    return {"events": out, "revision": revision, "values": final}
