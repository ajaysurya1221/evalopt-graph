def select(b, left, r):
    if b is None:
        if left is not None and r is not None and left != r:
            return "conflict", "add"
        return "keep", left if left is not None else r
    if left is None or r is None:
        other = r if left is None else left
        return ("drop", None) if other is None or other == b else ("conflict", "delete")
    return "merge", None
