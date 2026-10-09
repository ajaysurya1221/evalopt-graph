from cache import cache_key
assert cache_key("/a", {"X": "1"}, []) == ["/a", []]
print("visible checks passed")
