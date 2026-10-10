from cache import get_fresh
assert get_fresh({"a": ["x", 10]}, "a", 9) == "x"
assert get_fresh({}, "a", 9) is None
print("visible checks passed")
