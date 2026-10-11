def solve(q):
    columns = tuple(q["state"]["columns"])
    rows = tuple(tuple(row[c] for c in columns) for row in q["state"]["rows"])
    applied = tuple(q["state"]["applied"])
    outcomes = []
    for b in q["batches"]:
        if b["id"] in applied:
            outcomes.append("skipped")
            continue
        c, r = columns, rows
        okay = all(x in applied for x in b["requires"])
        for op in b["ops"]:
            if not okay:
                break
            kind = op[0]
            if kind == "add":
                okay = op[1] not in c
                if okay:
                    c, r = c + (op[1],), tuple(row + (op[2],) for row in r)
            elif kind == "rename":
                okay = op[1] in c and op[2] not in c
                if okay:
                    c = tuple(op[2] if x == op[1] else x for x in c)
            elif kind == "scale":
                okay = op[1] in c
                if okay:
                    j = c.index(op[1])
                    r = tuple(tuple(v * op[2] if i == j else v for i, v in enumerate(row)) for row in r)
            elif kind == "require":
                okay = op[1] in c and all(row[c.index(op[1])] >= op[2] for row in r)
            else:
                okay = False
        if okay:
            columns, rows, applied = c, r, applied + (b["id"],)
        outcomes.append("committed" if okay else "failed")
    return {
        "state": {
            "columns": list(columns),
            "rows": [dict(zip(columns, r, strict=True)) for r in rows],
            "applied": list(applied),
        },
        "outcomes": outcomes,
    }
