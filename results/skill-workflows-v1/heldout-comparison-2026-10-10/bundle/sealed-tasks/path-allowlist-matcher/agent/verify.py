from allowlist import matches
assert matches("src/main.py", ["src/*.py"]) is True
print("visible checks passed")
