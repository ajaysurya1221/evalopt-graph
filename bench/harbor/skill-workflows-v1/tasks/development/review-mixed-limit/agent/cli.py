def read_limit(text):
    value = int(text)
    if value <= 0:
        raise ValueError("positive limit required")
    return value
