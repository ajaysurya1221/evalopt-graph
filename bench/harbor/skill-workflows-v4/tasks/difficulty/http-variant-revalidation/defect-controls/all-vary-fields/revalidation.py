def merge(old, new):
    headers = {**old, **new}
    if "warning" not in new:
        headers.pop("warning", None)
    return headers
