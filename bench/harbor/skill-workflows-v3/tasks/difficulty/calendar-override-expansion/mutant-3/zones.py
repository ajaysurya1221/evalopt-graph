def to_utc(local, zones):
    while True:
        matches = [local - z["offset"] for z in zones if z["lo"] <= local - z["offset"] < z["hi"]]
        if matches:
            return min(matches)
        # Every shift must be resolved against the supported UTC intervals again.
        for before, after in zip(zones, zones[1:], strict=False):
            first = before["hi"] + before["offset"]
            last = after["lo"] + after["offset"]
            if first <= local < last:
                return local - before["offset"]
        else:
            raise ValueError("outside supported zone range")
