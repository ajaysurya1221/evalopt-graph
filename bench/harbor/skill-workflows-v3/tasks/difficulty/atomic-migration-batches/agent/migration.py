from operations import apply


def apply_batch(state, batch):
    if batch["requires"] and not any(item in state["applied"] for item in batch["requires"]):
        raise ValueError("dependency")
    for operation in batch["ops"]:
        apply(state, operation)
    state["applied"].append(batch["id"])
