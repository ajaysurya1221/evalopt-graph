def choose(options, served, weights):
    return min(options, key=lambda j: j["id"]) if options else None
