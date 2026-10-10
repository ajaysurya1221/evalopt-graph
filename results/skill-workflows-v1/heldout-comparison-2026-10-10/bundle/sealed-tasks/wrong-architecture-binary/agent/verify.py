import json
target = json.load(open("target.json"))
run = json.load(open("run.json"))
if run["platform"] != target["required_platform"]:
    print("target-execution unavailable")
    raise SystemExit(3)
assert run["completed"] and run["exit_code"] == 0
