def get_fresh(records, key, now):
    record = records.get(key)
    if record and now <= record[1]:
        return record[0]
    return None
