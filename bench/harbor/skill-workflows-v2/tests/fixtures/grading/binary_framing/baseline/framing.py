def decode(encoded):
    raw = bytes.fromhex(encoded)
    count = int.from_bytes(raw[:2], "little")
    payload = raw[2:]
    if count > len(payload):
        raise ValueError("incomplete frame")
    return payload[:count].hex()
