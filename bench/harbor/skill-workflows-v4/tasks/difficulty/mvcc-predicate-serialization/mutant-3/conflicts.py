def conflict(history, t):
    changed = {k for k, versions in history.items() if versions[-1][0] > t["at"]}
    return bool(changed & (set(t["writes"]) | t["reads"])) or any(
        lo < k < hi for k in changed if history[k][-1][1] is not None for lo, hi in t["ranges"]
    )
