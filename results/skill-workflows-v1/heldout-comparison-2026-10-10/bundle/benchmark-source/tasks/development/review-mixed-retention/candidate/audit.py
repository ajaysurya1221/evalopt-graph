def count_by_owner(records):
    counts = {}
    for record in records:
        counts[record["owner"]] += 1
    return counts
