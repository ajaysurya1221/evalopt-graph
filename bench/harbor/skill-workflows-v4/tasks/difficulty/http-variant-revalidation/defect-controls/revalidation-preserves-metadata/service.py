from revalidation import merge
from selection import select
from variants import matches


def solve(q):
    entry = select(q["entries"], q["request"])
    if entry is None:
        return {"state": "miss"}
    age = q["now"] - entry["stored_at"]
    if age < entry["max_age"]:
        return {
            "state": "hit",
            "id": entry["id"],
            "body": entry["body"],
            "headers": dict(entry["headers"]),
            "age": age,
        }
    update = q["not_modified"]
    if update is None:
        return {"state": "stale", "id": entry["id"], "etag": entry["headers"].get("etag")}
    headers = merge(entry["headers"], update["headers"])
    changed = {**entry, "headers": headers}
    if not matches(changed, q["request"]):
        return {"state": "miss"}
    return {"state": "revalidated", "id": entry["id"], "body": entry["body"], "headers": headers, "age": 0}
