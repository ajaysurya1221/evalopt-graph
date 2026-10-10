from config import resolve
assert resolve({"x":"a"}, {"x":"b"}, {}) == {"x":"b"}
