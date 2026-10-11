import json
import platform
import sys

# This authored fixture requires an absent target platform; no remote run occurs.
available = platform.machine() == "wasm32"
print(json.dumps({"evidence_available": available, "reason": "required target execution unavailable"}))
sys.exit(0 if available else 3)
