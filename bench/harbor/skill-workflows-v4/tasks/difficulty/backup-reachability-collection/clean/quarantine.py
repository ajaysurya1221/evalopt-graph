def collect(objects, live, quarantine, now, grace):
    deleted = []
    waiting = {}
    for ident in sorted(objects):
        if ident in live:
            continue
        if ident in quarantine and now - quarantine[ident] >= grace:
            deleted.append(ident)
        else:
            waiting[ident] = quarantine.get(ident, now)
    return deleted, waiting
