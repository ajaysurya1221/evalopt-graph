def take(text, start, length):
    if start < 0 or length < 0:
        raise ValueError("range")
    return text[start : start + length]


def materialize(parts, read):
    result = []
    for part in parts:
        if "literal" in part:
            result.append(part["literal"])
        else:
            name, start, length = part["copy"]
            result.append(take(read(name), start, length))
    return "".join(result)
