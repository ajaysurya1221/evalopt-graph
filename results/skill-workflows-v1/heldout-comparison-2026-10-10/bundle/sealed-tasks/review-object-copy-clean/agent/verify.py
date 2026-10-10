from objects import clone
source = {"x": [{"y": 1}]}
copy = clone(source)
copy["x"][0]["y"] = 2
assert source == {"x": [{"y": 1}]}
print("visible checks passed")
