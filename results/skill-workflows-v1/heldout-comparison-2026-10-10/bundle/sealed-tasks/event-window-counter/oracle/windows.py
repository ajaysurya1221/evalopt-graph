def count(events, now, window):
    if window <= 0:
        raise ValueError("window must be positive")
    by_id = {}
    for identifier, timestamp, label in events:
        by_id[identifier] = (timestamp, label)
    counts = {}
    for timestamp, label in by_id.values():
        if now - window < timestamp <= now:
            counts[label] = counts.get(label, 0) + 1
    return counts
