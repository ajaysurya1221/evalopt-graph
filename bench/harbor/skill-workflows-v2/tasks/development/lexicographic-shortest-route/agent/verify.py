from routes import solve

assert solve(*[[["a", "b", 2]], "a", "b"]) == {"cost": 2, "path": ["a", "b"]}
print("visible smoke check completed")
