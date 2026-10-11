from state_fold import solve

assert solve(*[[{"id": "x", "revision": 1, "writer": "a", "value": 7, "deleted": False}]]) == [
    {"id": "x", "value": 7}
]
print("visible smoke check completed")
