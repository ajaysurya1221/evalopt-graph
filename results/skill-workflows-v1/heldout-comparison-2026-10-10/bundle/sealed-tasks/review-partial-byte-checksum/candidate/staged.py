def checksum(hex_data):
    return sum(bytes.fromhex(hex_data)) & 255
