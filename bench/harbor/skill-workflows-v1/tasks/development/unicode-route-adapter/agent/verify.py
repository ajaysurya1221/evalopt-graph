from routes import user_route
assert user_route("a b") == "/users/a%20b"
print("visible checks passed")
