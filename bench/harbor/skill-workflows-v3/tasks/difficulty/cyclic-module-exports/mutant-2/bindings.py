def seed(modules):
    return {m: {n: {m + ":" + n} for n in v["locals"]} for m, v in modules.items()}


def summarize(tables):
    result = {}
    for module, names in sorted(tables.items()):
        result[module] = {
            "exports": {
                name: next(iter(origins)) for name, origins in sorted(names.items()) if len(origins) == 1
            },
            "ambiguous": sorted(name for name, origins in names.items() if len(origins) > 1),
        }
    return result
