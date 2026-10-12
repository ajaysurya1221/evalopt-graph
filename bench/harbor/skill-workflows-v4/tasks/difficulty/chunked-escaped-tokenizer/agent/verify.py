from service import solve

assert solve({"chunks": [[]], "finish": True}) == {"batches": [[]], "state": {"buffer": [], "offset": 0}}
