def apply(state, op):
    columns, rows = state["columns"], state["rows"]
    kind = op[0]
    if kind == "add":
        _, name, value = op
        if name in columns:
            raise ValueError("duplicate column")
        columns.append(name)
        for row in rows:
            row[name] = value
    elif kind == "rename":
        _, old, new = op
        if old not in columns or new in columns:
            raise ValueError("rename")
        columns.remove(old)
        columns.append(new)
        for row in rows:
            row[new] = row.pop(old)
    elif kind == "scale":
        _, name, factor = op
        if name not in columns:
            raise ValueError("missing column")
        for row in rows:
            row[name] *= factor
    elif kind == "require":
        _, name, minimum = op
        if name not in columns or any(row[name] < minimum for row in rows):
            raise ValueError("assertion")
    else:
        raise ValueError("operation")
