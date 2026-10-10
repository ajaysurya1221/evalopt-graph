from ledger import allocate
assert allocate("1.00", 2) == ["0.50", "0.50"]
print("visible checks passed")
