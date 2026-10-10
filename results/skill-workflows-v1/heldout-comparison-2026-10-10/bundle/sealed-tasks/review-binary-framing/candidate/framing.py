def decode(hex_data):
    raw = bytes.fromhex(hex_data)
    if len(raw) < 4:
        raise ValueError("missing length")
    length = int.from_bytes(raw[:4], "little")
    if len(raw) != 4 + length:
        raise ValueError("wrong length")
    return raw[4:].decode("utf-8")
