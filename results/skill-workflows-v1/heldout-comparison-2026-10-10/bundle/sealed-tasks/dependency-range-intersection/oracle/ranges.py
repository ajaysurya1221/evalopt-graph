import re

def _parse(text):
    lower = upper = None
    if not text or "  " in text or text.startswith(" ") or text.endswith(" "):
        raise ValueError("invalid range")
    for token in text.split(" "):
        match = re.fullmatch(r"(>=|>|<=|<|=)(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})\.(0|[1-9][0-9]{0,2})", token)
        if not match:
            raise ValueError("invalid token")
        op = match[1]
        version = tuple(map(int, match.groups()[1:]))
        if op == "=":
            if lower is not None or upper is not None or len(text.split(" ")) != 1:
                raise ValueError("equality alone")
            lower = (version, True)
            upper = (version, True)
        elif op.startswith(">"):
            if lower is not None:
                raise ValueError("duplicate lower")
            lower = (version, op == ">=")
        else:
            if upper is not None:
                raise ValueError("duplicate upper")
            upper = (version, op == "<=")
    return lower, upper

def intersect(left, right):
    bounds = [_parse(left), _parse(right)]
    lowers = [b[0] for b in bounds if b[0] is not None]
    uppers = [b[1] for b in bounds if b[1] is not None]
    lower = max(lowers, key=lambda x: (x[0], not x[1])) if lowers else None
    upper = min(uppers, key=lambda x: (x[0], x[1])) if uppers else None
    def rank(version):
        major, minor, patch = map(int, version)
        return major * 1000000 + minor * 1000 + patch
    first = rank(lower[0]) + (not lower[1]) if lower else 0
    last = rank(upper[0]) - (not upper[1]) if upper else 999999999
    if first > last:
        return None
    def show(bound):
        return [".".join(map(str, bound[0])), bound[1]] if bound else None
    return {"lower": show(lower), "upper": show(upper)}
