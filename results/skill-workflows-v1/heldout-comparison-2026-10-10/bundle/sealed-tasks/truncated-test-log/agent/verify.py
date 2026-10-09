import json
run = json.load(open("run.json"))
if not run["completed"]:
    print("test-completion unavailable: interrupted run")
    raise SystemExit(3)
assert run["exit_code"] == 0
