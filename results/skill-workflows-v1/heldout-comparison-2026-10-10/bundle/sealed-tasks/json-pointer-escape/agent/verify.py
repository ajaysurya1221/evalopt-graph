from pointer import resolve
assert resolve({"a": [3]}, "/a/0") == 3
print("visible checks passed")
