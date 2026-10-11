import re


def solve(text):
    if not isinstance(text, str) or re.fullmatch(r"[+-]?0[xX][0-9a-fA-F]+", text) is None:
        raise ValueError("syntax")
    value = int(text, 16)
    if abs(value) > 32767:
        raise ValueError("range")
    return value
