from offset import solve

assert solve("0x10") == 16
try:
    solve("-0x8000")
except ValueError:
    print("legacy symmetric-range check passed")
else:
    raise AssertionError("legacy check expects symmetric signed range")
