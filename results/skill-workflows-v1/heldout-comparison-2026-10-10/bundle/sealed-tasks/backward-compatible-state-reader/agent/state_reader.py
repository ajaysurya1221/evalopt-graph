def read(document):
    if set(document) != {"v", "count"}:
        raise ValueError("unexpected field")
    return {"count": document["count"], "note": ""}
