def apply(initial, operations):
    state = dict(initial)
    stack = []
    for operation in operations:
        kind = operation[0]
        if kind == "begin":
            stack.append(dict(state))
        elif kind == "set":
            state[operation[1]] = operation[2]
        elif kind in {"commit", "rollback"}:
            if not stack:
                raise ValueError("no transaction")
            saved = stack.pop()
            if kind == "rollback":
                state = saved
        else:
            raise ValueError("unknown operation")
    if stack:
        raise ValueError("open transaction")
    return state
