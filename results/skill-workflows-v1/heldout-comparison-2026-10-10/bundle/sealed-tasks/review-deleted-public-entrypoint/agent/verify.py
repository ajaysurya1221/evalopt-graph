import json
assert json.load(open("package.json"))["entrypoint"] == "cli:main"
