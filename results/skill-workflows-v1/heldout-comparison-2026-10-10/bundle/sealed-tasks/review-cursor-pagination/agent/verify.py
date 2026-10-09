from pagination import page
assert page([[1,"a"],[2,"b"]], [1,"a"], 2) == [[2,"b"]]
print("visible checks passed")
