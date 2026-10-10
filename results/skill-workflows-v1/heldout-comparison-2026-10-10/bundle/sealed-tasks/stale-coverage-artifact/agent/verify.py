import hashlib, json
report = json.load(open("coverage.json"))
assert report["source_sha256"] == hashlib.sha256(open("app.py", "rb").read()).hexdigest()
assert report["percent"] >= 90
