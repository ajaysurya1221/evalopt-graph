import re


def segment(pattern, text):
    expression = ""
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if c == "\\":
            i += 1
            expression += re.escape(pattern[i])
        elif c == "*":
            expression += ".*"
        elif c == "?":
            expression += "."
        else:
            expression += re.escape(c)
        i += 1
    return re.fullmatch(expression, text) is not None
