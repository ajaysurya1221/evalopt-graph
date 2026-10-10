from ranges import intersect
assert intersect(">=1.0.0", "<2.0.0") == {"lower": ["1.0.0", True], "upper": ["2.0.0", False]}
print("visible checks passed")
