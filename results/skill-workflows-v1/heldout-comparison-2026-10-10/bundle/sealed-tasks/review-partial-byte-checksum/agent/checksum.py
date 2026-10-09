def checksum(hex_data):
    raw = bytes.fromhex(hex_data)
    return sum(raw) % 256
