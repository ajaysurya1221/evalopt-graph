def merge_fields(b, left, r):
    out = {"id": b["id"]}
    errors = []
    for f in ("parent", "name", "value", "order"):
        if left[f] == r[f]:
            out[f] = left[f]
        elif left[f] == b[f]:
            out[f] = r[f]
        elif r[f] == b[f]:
            out[f] = left[f]
        else:
            errors.append(f)
            out[f] = b[f]
    return out, errors
