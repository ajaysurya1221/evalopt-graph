def eligible(record, required):
    return set(required).issubset(record["tags"])
