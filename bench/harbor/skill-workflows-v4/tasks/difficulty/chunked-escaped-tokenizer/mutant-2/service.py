from api import feed


def solve(q):
    state = {"buffer": [], "offset": 0}
    batches = []
    for i, chunk in enumerate(q["chunks"]):
        state, tokens = feed(state, chunk, q["finish"] and i == len(q["chunks"]) - 1)
        batches.append(tokens)
    return {"batches": batches, "state": state}
