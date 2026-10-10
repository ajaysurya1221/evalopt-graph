from environment import expand
assert expand([["B", "${A}! "]], {"A": "x"}) == {"A": "x", "B": "x! "}
print("visible checks passed")
