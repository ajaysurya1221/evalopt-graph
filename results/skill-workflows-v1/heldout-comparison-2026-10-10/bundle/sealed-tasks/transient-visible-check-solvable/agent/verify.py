from recovery import request
assert request("ready") == {"status":"ready","payload":"OK","calls":1}
print("visible checks passed")
