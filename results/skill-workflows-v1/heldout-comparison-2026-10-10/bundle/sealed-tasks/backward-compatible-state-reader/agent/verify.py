from state_reader import read
assert read({"v":1,"count":2}) == {"count":2,"note":""}
print("visible checks passed")
