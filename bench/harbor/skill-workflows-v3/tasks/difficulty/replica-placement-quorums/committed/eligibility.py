def representatives(nodes):
    unique = {}
    for node in sorted(nodes, key=lambda n: (-n["rank"], n["id"])):
        if node["alive"] and node["capacity"] >= 0:
            unique.setdefault(node["physical"], node)
    return list(unique.values())
