from service import solve

assert solve(
    {"objects": {}, "snapshots": [], "keep": 0, "now": 0, "window": 0, "grace": 0, "quarantine": {}}
) == {"live": [], "delete": [], "quarantine": {}}
