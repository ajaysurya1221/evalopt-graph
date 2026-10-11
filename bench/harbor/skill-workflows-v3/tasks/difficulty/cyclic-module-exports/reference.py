def solve(modules):
    names = set()
    for spec in modules.values():
        names.update(spec["locals"])
        names.update(spec["aliases"])
    result = {}
    for module in sorted(modules):
        values = {}
        for name in names:
            pending = [(module, name)]
            visited = set()
            found = set()
            while pending:
                m, n = pending.pop()
                if (m, n) in visited:
                    continue
                visited.add((m, n))
                spec = modules[m]
                if n in spec["locals"]:
                    found.add(m + ":" + n)
                elif n in spec["aliases"]:
                    pending.append(tuple(spec["aliases"][n]))
                elif n != "default":
                    pending.extend((other, n) for other in spec["stars"])
            values[name] = found
        result[module] = {
            "exports": {n: next(iter(v)) for n, v in sorted(values.items()) if len(v) == 1},
            "ambiguous": sorted(n for n, v in values.items() if len(v) > 1),
        }
    return result
