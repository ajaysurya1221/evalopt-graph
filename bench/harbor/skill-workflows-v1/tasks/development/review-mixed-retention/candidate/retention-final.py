def eligible(records, cutoff):
    selected = [record for record in records if record["created"] <= cutoff]
    return [record["id"] for record in selected if not record["pinned"]]
