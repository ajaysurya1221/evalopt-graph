import json


def clone(value):
    encoded = json.dumps(value, separators=(",", ":"))
    return json.loads(encoded)
