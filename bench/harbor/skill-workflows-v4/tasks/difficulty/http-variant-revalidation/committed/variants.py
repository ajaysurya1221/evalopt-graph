def matches(entry, request):
    if entry["url"] != request["url"]:
        return False
    old = entry["request_headers"]
    new = request["headers"]
    if old.get("authorization") != new.get("authorization"):
        return False
    vary = entry["headers"].get("vary", [])
    return "*" not in vary and (not vary or any(old.get(k) == new.get(k) for k in vary))
