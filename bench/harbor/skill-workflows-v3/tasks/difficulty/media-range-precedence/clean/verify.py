from service import solve

assert isinstance(
    solve(
        {
            "offers": [{"type": "text", "subtype": "plain", "params": {}}],
            "ranges": [{"type": "*", "subtype": "*", "params": {}, "q": 1000}],
        }
    ),
    (dict, list, str),
)
