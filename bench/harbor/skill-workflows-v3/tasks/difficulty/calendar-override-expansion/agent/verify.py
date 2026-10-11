from service import solve

assert isinstance(
    solve(
        {
            "start": 0,
            "step": 20,
            "count": 4,
            "cancel": [],
            "replace": {},
            "zones": [{"lo": -500, "hi": 500, "offset": 0}],
            "window": [-100, 300],
        }
    ),
    (dict, list, str),
)
