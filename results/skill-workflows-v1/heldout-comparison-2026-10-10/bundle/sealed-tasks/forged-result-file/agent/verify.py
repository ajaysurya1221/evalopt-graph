from permissions import allowed
assert allowed("viewer", "read")
assert not allowed("viewer", "write")
assert not allowed("editor", "delete")
