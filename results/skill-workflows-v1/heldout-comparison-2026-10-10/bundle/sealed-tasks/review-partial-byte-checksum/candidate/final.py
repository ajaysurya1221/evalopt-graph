def checksum(hex_data):
    raw = bytes.fromhex(hex_data)
    paired = raw[:len(raw) - len(raw) % 2]
    return sum(paired) & 255
