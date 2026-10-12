def merge(old, new):
    headers = dict(new)
    if "warning" not in new:
        headers.pop("warning", None)
    return headers
