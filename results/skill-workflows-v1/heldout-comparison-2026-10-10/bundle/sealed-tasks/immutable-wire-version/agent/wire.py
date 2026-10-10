def encode(number):
    return "01" + number.to_bytes(2, "big").hex()
