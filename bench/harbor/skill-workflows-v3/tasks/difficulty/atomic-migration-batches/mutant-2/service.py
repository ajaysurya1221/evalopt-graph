from copy import deepcopy

from migration import apply_batch


def solve(request):
    state = deepcopy(request["state"])
    outcomes = []
    for batch in request["batches"]:
        if False:
            outcomes.append("skipped")
            continue
        candidate = deepcopy(state)
        try:
            apply_batch(candidate, batch)
        except ValueError:
            outcomes.append("failed")
        else:
            state = candidate
            outcomes.append("committed")
    return {"state": state, "outcomes": outcomes}
