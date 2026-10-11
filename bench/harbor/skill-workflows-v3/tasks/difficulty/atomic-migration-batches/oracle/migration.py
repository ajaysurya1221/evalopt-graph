from operations import apply


def apply_batch(state, batch):
    if any(item not in state["applied"] for item in batch["requires"]):
        raise ValueError("dependency")
    for operation in batch["ops"]:
        apply(state, operation)
    state["applied"].append(batch["id"])
