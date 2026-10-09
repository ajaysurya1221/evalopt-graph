import re

def parse(text):
    if not re.fullmatch(r"[0-9]{1,18}[hms]( [0-9]{1,18}[hms]){0,2}", text):
        raise ValueError("invalid duration")
    rank = {"h": 0, "m": 1, "s": 2}
    scale = {"h": 3600, "m": 60, "s": 1}
    previous = -1
    total = 0
    for component in text.split(" "):
        unit = component[-1]
        if rank[unit] <= previous:
            raise ValueError("invalid order")
        previous = rank[unit]
        total += int(component[:-1]) * scale[unit]
    return total
