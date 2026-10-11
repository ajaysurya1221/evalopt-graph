def apply_changes(nominal, cancel, replace):
    cancelled = set(cancel)
    return [(i, replace.get(str(i), local)) for i, local in nominal if i not in cancelled]
