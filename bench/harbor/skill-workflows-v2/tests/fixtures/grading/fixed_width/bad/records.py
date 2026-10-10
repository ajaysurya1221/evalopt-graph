def parse(encoded):
    raw = bytes.fromhex(encoded)
    return [raw[:4].decode("utf-8", errors="replace").rstrip(), 0]
