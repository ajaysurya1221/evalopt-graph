import re


def solve(template, bindings):
    return re.sub(r"\{([a-z]+)\}", lambda m: bindings.get(m.group(1), m.group(0)), template)
