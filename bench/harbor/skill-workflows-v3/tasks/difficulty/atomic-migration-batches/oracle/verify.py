from service import solve

assert isinstance(
    solve(
        {
            "state": {"columns": ["x", "y"], "rows": [{"x": 2, "y": 4}, {"x": -1, "y": 8}], "applied": []},
            "batches": [{"id": "a", "requires": [], "ops": [["scale", "x", 2]]}],
        }
    ),
    (dict, list, str),
)
