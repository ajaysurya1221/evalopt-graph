def closure(objects, roots):
    todo = list(roots)
    seen = set()
    while todo:
        ident = todo.pop()
        if ident in seen:
            continue
        seen.add(ident)
        obj = objects[ident]
        todo.extend(obj["refs"])
        if obj["base"] is not None:
            todo.append(obj["base"])
    return seen
