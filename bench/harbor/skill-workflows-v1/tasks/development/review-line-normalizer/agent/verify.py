from normalizer import normalize
assert normalize("a\r\nb\r") == "a\nb\n"
print("visible checks passed")
