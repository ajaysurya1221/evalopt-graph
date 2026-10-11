from render import solve

assert solve(*["hello {x}", {"x": "world"}]) == "hello world"
print("visible smoke check completed")
