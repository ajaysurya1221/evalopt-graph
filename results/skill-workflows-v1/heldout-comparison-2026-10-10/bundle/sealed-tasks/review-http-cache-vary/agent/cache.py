def cache_key(url, headers, vary):
    normalized = {name.lower(): value for name, value in headers.items()}
    names = sorted(set(name.lower() for name in vary))
    return [url, [[name, normalized.get(name, "")] for name in names]]
