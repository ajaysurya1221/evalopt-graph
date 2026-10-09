from transactions import apply
assert apply({}, [["set", "x", 1]]) == {"x": 1}
print("visible checks passed")
