import json
a = json.load(open("builder.json"))
b = json.load(open("release.json"))
assert a["build_id"] == b["build_id"]
assert a["source_sha256"] == b["source_sha256"]
