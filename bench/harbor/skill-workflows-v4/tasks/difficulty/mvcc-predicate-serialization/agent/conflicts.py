def conflict(history, t):
    changed = {k for k, versions in history.items() if versions[-1][0] > t["at"]}
    return bool(changed & t["reads"]) or any(lo < k < hi for k in changed for lo, hi in t["ranges"])
