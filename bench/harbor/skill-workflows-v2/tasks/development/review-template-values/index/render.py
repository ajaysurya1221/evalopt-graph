import re


def token(name):
    return r"\{" + name + r"\}"


def solve(template, bindings):
    for name, value in bindings.items():
        template = re.sub(token(name), value, template)
    return template
