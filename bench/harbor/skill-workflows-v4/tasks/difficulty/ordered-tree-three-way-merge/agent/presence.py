def select(b, left, r):
    if left is None:
        return "drop", None
    return "keep", left
