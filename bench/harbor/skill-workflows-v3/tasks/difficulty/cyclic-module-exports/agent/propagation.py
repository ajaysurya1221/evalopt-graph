def step(modules, old):
    # Legacy linker supports local declarations and one layer of stars only.
    result = {}
    for module, spec in modules.items():
        names = {n: {module + ":" + n} for n in spec["locals"]}
        for other in spec["stars"]:
            for name, origins in old[other].items():
                if name != "default":
                    names.setdefault(name, set()).update(origins)
        result[module] = names
    return result
