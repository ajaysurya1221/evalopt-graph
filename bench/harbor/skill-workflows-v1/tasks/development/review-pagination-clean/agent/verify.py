from pages import page
assert page([1, 2, 3], 1, 1) == [2]
assert page([1], 9, 2) == []
assert page([1], 0, 0) == []
print("visible checks passed")
