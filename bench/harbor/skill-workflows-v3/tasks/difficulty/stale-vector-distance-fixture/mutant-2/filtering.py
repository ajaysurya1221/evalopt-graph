def eligible(record, required):
    return not required or bool(set(required) & set(record["tags"]))
