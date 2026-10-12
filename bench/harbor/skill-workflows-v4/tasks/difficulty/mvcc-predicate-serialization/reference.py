from copy import deepcopy


def solve(q):
    state = deepcopy(q["initial"])
    serial = 0
    transactions = {}
    log = []
    events = []
    for op in q["operations"]:
        kind, tx, *args = op
        if kind == "begin":
            transactions[tx] = [serial, deepcopy(state), {}, set(), []]
            events.append(["begin", tx, serial])
            continue
        stamp, snap, writes, reads, ranges = transactions[tx]
        overlay = {**snap, **writes}
        if kind == "get":
            reads.add(args[0])
            events.append(["get", tx, overlay.get(args[0])])
        elif kind == "scan":
            lo, hi = args
            ranges.append((lo, hi))
            events.append(
                [
                    "scan",
                    tx,
                    [[k, overlay[k]] for k in sorted(overlay) if lo <= k < hi and overlay[k] is not None],
                ]
            )
        elif kind in ("put", "delete"):
            writes[args[0]] = args[1] if kind == "put" else None
            events.append([kind, tx])
        else:
            touched = set().union(*(keys for rev, keys in log if rev > stamp)) if log else set()
            invalid = bool(touched & (reads | set(writes))) or any(
                a <= k < b for a, b in ranges for k in touched
            )
            if writes and invalid:
                events.append(["commit", tx, "conflict", serial])
            else:
                if writes:
                    serial += 1
                    log.append((serial, set(writes)))
                    for k, v in writes.items():
                        if v is None:
                            state.pop(k, None)
                        else:
                            state[k] = v
                events.append(["commit", tx, "ok", serial])
            del transactions[tx]
    return {"events": events, "revision": serial, "values": state}
