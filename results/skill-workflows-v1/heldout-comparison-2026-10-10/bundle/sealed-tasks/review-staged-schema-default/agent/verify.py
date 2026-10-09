from serializer import encode
assert encode({"name":"a", "enabled":True}) == {"name":"a","enabled":True}
