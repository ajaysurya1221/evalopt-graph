from urls import join
assert join("https://example.invalid/a//", "//b//c") == "https://example.invalid/a/b//c"
assert join("https://example.invalid", "") == "https://example.invalid/"
print("visible checks passed")
