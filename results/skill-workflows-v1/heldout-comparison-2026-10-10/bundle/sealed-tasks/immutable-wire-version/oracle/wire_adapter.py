from wire import encode

def serialize(value):
    if isinstance(value, str):
        if not 1 <= len(value) <= 5 or not all("0" <= char <= "9" for char in value):
            raise ValueError("invalid number")
        value = int(value)
    if type(value) is not int or not 0 <= value <= 65535:
        raise ValueError("invalid number")
    return encode(value)
