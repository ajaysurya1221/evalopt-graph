import re

def unique_slug(label, taken):
    base = re.sub("[^a-z0-9]+", "-", label.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"))).strip("-") or "item"
    candidate = base
    number = 2
    while candidate in taken:
        candidate = f"{base}-{number}"
        number += 1
    return candidate
