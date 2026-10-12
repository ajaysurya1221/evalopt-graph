from versions import view


def read(history, t, key):
    t["reads"].add(key)
    return t["writes"][key] if key in t["writes"] else view(history, key, t["at"])


def scan(history, t, lo, hi):
    t["ranges"].append((lo, hi))
    return [
        [k, read(history, t, k)]
        for k in sorted(set(history) | set(t["writes"]))
        if lo <= k < hi and read(history, t, k) is not None
    ]
