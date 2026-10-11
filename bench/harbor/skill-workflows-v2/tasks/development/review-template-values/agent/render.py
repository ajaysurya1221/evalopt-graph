import re

from patterns import token


def solve(template, bindings):
    for name, value in bindings.items():
        template = re.sub(token(name), value, template)
    return template
