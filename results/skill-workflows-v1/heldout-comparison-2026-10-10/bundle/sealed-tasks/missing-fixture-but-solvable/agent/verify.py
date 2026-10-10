import json
report = json.load(open("summary.json"))
assert set(report) == {"active_count", "active_total"}
assert all(type(value) is int for value in report.values())
