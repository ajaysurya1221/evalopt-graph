from fields import merge_fields
from presence import select
from structure import ordered, validate


def solve(q):
    maps = [{n["id"]: n for n in q[k]} for k in ("base", "local", "remote")]
    result = {}
    errors = []
    for ident in sorted(set().union(*[set(m) for m in maps])):
        b, left, r = [m.get(ident) for m in maps]
        state, node = select(b, left, r)
        if state == "conflict":
            errors.append([ident, node])
        elif state == "merge":
            node, bad = merge_fields(b, left, r)
            errors.extend([[ident, f] for f in bad])
            result[ident] = node
        elif state == "keep":
            result[ident] = dict(node)
    if not errors:
        errors = validate(result)
    return (
        {"nodes": None, "conflicts": sorted(errors)}
        if errors
        else {"nodes": ordered(result), "conflicts": []}
    )
