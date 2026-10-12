from lexer import scan


def feed(state, chunk, final):
    data = bytes(state["buffer"] + chunk)
    tokens, consumed = scan(data, final, state["offset"])
    return {"buffer": list(data[consumed:]), "offset": state["offset"] + consumed}, tokens
