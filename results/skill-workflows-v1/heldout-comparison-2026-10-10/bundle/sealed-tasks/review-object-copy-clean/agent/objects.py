import json

def clone(value):
    return json.loads(json.dumps(value))
