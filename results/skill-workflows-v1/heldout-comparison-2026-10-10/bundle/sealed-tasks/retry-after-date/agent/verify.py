from retry_after import delay
assert delay("30", 0) == 30
print("visible checks passed")
