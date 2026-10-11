from service import solve

assert isinstance(
    solve(
        {
            "snapshots": {"a": {"legacy": "L1|3|abc"}},
            "roots": ["a"],
            "reads": [{"name": "a", "start": 0, "length": 3}],
        }
    ),
    (dict, list, str),
)
