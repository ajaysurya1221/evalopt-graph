def latest(entries):
    return entries[-1]


def view(history, key, at):
    candidates = [v for rev, v in history.get(key, []) if rev <= at]
    return candidates[-1] if candidates else None
