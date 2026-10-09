def eligible(records, cutoff):
    return [record["id"] for record in records if record["created"] < cutoff and not record["pinned"]]
