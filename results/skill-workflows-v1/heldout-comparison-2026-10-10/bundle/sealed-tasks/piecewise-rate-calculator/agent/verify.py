from pricing import charge
assert charge(12, [[10, "0.10"], [None, "0.05"]]) == "1.10"
print("visible checks passed")
