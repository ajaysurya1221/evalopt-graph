def join(base, segment):
    while base.endswith("/"):
        base = base[:-1]
    while segment.startswith("/"):
        segment = segment[1:]
    return base + "/" + segment
