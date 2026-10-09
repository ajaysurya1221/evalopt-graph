def read(document):
    if type(document.get("v")) is not int or document["v"] != 1:
        raise ValueError("unsupported version")
    count = document.get("count")
    note = document.get("note", "")
    if type(count) is not int or not 0 <= count <= 1000000000 or not isinstance(note, str):
        raise ValueError("invalid state")
    return {"count": count, "note": note}
