def solve(q):
    answer = []
    for identity in range(q["count"]):
        if identity in q["cancel"]:
            continue
        minute = q["replace"].get(str(identity), q["start"] + identity * q["step"])
        represented = {}
        for instant in range(q["zones"][0]["lo"], q["zones"][-1]["hi"]):
            zone = next(z for z in q["zones"] if z["lo"] <= instant < z["hi"])
            represented.setdefault(instant + zone["offset"], instant)
        gaps = [
            (left["hi"] + left["offset"], right["lo"] + right["offset"])
            for left, right in zip(q["zones"], q["zones"][1:], strict=False)
            if right["offset"] > left["offset"]
        ]
        while minute not in represented:
            match = next(((first, last) for first, last in gaps if first <= minute < last), None)
            if match is None:
                raise ValueError("outside supported zone range")
            minute += match[1] - match[0]
        utc = represented[minute]
        if q["window"][0] <= utc < q["window"][1]:
            answer.append({"id": identity, "utc": utc})
    return sorted(answer, key=lambda row: (row["utc"], row["id"]))
