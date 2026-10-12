from copy import deepcopy


def solve(q):
    req = q["request"]
    eligible = []

    def valid(e, headers):
        if e["url"] != req["url"]:
            return False
        a = e["request_headers"]
        b = req["headers"]
        keys = set(headers.get("vary", [])) | {"authorization"}
        if "*" in keys:
            return False
        return not any(a.get(k) != b.get(k) for k in keys)

    for e in q["entries"]:
        if valid(e, e["headers"]):
            eligible.append(e)
    if not eligible:
        return {"state": "miss"}
    e = sorted(eligible, key=lambda e: (-e["stored_at"], e["id"]))[0]
    age = q["now"] - e["stored_at"]
    if age < e["max_age"]:
        return dict(state="hit", id=e["id"], body=e["body"], headers=deepcopy(e["headers"]), age=age)
    n = q["not_modified"]
    if n is None:
        return {"state": "stale", "id": e["id"], "etag": e["headers"].get("etag")}
    h = deepcopy(e["headers"])
    h.pop("warning", None)
    for k, v in n["headers"].items():
        h[k] = deepcopy(v)
    if not valid(e, h):
        return {"state": "miss"}
    return dict(state="revalidated", id=e["id"], body=e["body"], headers=h, age=0)
