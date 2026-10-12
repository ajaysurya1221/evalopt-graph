from service import solve

assert solve({"entries": [], "request": {"url": "/", "headers": {}}, "now": 0, "not_modified": None}) == {
    "state": "miss"
}
