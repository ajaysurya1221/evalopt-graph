from service import solve

assert solve({"jobs": [], "weights": {"a": 1}, "cancel": {}, "horizon": 0}) == {
    "trace": [],
    "jobs": {},
    "served": {"a": 0},
}
