import json
report = json.load(open("compatibility.json"))
assert set(report) == {"removed", "changed", "added"}
assert all(isinstance(value, list) for value in report.values())
