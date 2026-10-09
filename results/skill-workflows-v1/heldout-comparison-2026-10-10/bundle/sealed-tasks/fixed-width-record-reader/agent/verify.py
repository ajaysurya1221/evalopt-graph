from records import parse_records
assert parse_records("4120202030303032") == [{"name": "A", "count": 2}]
print("visible checks passed")
