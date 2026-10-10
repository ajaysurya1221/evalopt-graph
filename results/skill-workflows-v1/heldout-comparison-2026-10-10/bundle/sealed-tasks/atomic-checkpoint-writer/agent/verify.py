from checkpoint import save
assert save({}, "x", "a", False)["files"] == {"x": "a"}
print("visible checks passed")
