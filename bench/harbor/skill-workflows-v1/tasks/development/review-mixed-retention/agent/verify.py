from retention import eligible
assert eligible([{"id": "a", "created": 1, "pinned": False, "owner": "x"}], 3) == ["a"]
print("visible checks passed")
