from service import solve

assert isinstance(
    solve(
        {
            "jobs": {
                "a": {
                    "normal": [],
                    "order": [],
                    "old": "a",
                    "new": "a",
                    "dirty": False,
                    "config_changed": False,
                    "fail": False,
                }
            },
            "roots": ["a"],
        }
    ),
    (dict, list, str),
)
