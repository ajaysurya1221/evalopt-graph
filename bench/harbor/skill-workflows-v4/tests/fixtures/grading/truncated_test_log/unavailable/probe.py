import json
import sys

log = "suite started\ntest_one passed\n"
complete = "suite completed" in log
print(json.dumps({"evidence_available": complete, "reason": "completion marker absent"}))
sys.exit(0 if complete else 3)
