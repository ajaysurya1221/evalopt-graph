def step(modules, old):
    result = {}
    for module, spec in modules.items():
        names = {n: {module + ":" + n} for n in spec["locals"]}
        for name, (other, imported) in spec["aliases"].items():
            names[name] = set(old[other].get(imported, set()))
        explicit = set(spec["locals"]) | set(spec["aliases"])
        for other in spec["stars"]:
            for name, origins in old[other].items():
                if name != "default" and name not in explicit:
                    names.setdefault(name, set()).update(origins)
        result[module] = names
    return result
