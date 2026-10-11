def order(scored, limit):
    return [{"id": identity, "distance": value} for value, identity in sorted(scored)[:limit]]
