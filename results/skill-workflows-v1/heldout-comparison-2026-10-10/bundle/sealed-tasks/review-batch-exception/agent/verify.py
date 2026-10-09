from batch import parse_batch
assert parse_batch(["1", "2"]) == [{"value": 1}, {"value": 2}]
print("visible checks passed")
