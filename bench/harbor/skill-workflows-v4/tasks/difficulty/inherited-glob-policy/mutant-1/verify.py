from service import solve

assert solve(
    {
        "paths": [["a", "b", "c"]],
        "rules": [{"pattern": "a/*", "effect": "allow", "base": [], "inherit": False}],
    }
) == [{"path": "a/b/c", "decision": "allow", "rule": 0, "kind": "direct"}]
