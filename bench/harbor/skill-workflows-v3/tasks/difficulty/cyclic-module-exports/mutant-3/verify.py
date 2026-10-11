from service import solve

assert isinstance(solve({"a": {"locals": ["x"], "aliases": {}, "stars": []}}), (dict, list, str))
