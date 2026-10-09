def allowed(member):
    if member.startswith("/") or "\\" in member:
        return False
    depth = 0
    for part in member.split("/"):
        if part == "..":
            depth -= 1
            if depth < 0:
                return False
        elif part not in {"", "."}:
            depth += 1
    return True
