from migration003 import plan
assert plan(["id", "deleted_at"], ["items_deleted_at_idx"]) == []
print("visible checks passed")
