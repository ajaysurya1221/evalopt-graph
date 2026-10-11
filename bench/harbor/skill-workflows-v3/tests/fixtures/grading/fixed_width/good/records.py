def parse(encoded):
    raw = bytes.fromhex(encoded)
    if len(raw) != 8:
        raise ValueError("record width")
    label = raw[:4].decode("utf-8").rstrip()
    number = raw[4:].decode("ascii")
    if not number.isdigit():
        raise ValueError("numeric field")
    return [label, int(number)]
