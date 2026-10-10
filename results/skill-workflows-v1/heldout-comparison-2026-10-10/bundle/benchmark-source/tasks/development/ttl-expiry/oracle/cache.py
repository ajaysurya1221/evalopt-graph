def get_fresh(records, key, now):
    record = records.get(key)
    return record[0] if record is not None and now < record[1] else None
